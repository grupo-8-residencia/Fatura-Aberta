"""Persistência atômica do índice, integridade do chunking e estabilidade do ranking.

Complementa `test_vector_store.py` (débitos S2/S3): nada aqui altera o ranking, a fórmula nem o
chunking; os testes só fixam propriedades que antes não eram verificadas.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

import pytest

from fa_contratos import Citacao
from fa_rag import (
    DocumentoNormativo,
    EmbedderHash,
    IndiceHibrido,
    carregar_corpus,
    chunkar_dispositivo,
)
from fa_rag import vector_store as vs

HOJE = date(2026, 11, 9)


def _doc(
    id_: str,
    texto: str,
    *,
    inicio: date = date(2022, 1, 3),
    fim: date | None = None,
    subgrupos: tuple[str, ...] = ("B1",),
    dispositivo: str = "art. 1º",
) -> DocumentoNormativo:
    citacao = Citacao(
        ato="Ato sintético",
        dispositivo=dispositivo,
        vigencia_inicio=inicio,
        vigencia_fim=fim,
        url="https://exemplo.invalid/ato",
    )
    return DocumentoNormativo(
        id=id_, titulo=id_, texto=texto, citacao=citacao, subgrupos=subgrupos, tags=()
    )


def _docs() -> list[DocumentoNormativo]:
    return [_doc("a", "suspensão do fornecimento de energia"), _doc("b", "multa por atraso")]


# --------------------------------------------------------------------------- persistência


def test_recarga_reproduz_vetores_e_ranking_do_corpus_real(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    novo = IndiceHibrido.do_corpus(arquivo_vetores=arq)
    carregado = IndiceHibrido.do_corpus(arquivo_vetores=arq)
    for chave, vetor in novo._vetorial._vetores.items():
        recarregado = carregado._vetorial._vetores[chave]
        assert all(abs(a - b) < 1e-7 for a, b in zip(vetor, recarregado, strict=True))
    for consulta in (
        "multa por atraso no pagamento",
        "religação de urgência",
        "bandeira tarifária",
    ):
        a = novo.buscar(consulta, data_referencia=HOJE)
        b = carregado.buscar(consulta, data_referencia=HOJE)
        assert [r.documento.id for r in a] == [r.documento.id for r in b]


def test_arquivo_registra_formato_embedder_e_dimensao(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    dados = json.loads(arq.read_text(encoding="utf-8"))
    assert dados["versao_formato"] == vs.VERSAO_FORMATO
    assert dados["embedder"] == {"nome": "hash-ngramas-blake2b", "versao": "1"}
    assert dados["dim"] == 384


def test_escrita_e_atomica_e_nao_deixa_temporario(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    assert [p.name for p in tmp_path.iterdir()] == ["indice.json"]


def test_falha_na_escrita_preserva_o_indice_anterior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    antes = arq.read_bytes()

    def falhar(*_args: object, **_kwargs: object) -> None:
        raise OSError("disco cheio simulado")

    monkeypatch.setattr(os, "replace", falhar)
    with pytest.raises(OSError):
        IndiceHibrido([*_docs(), _doc("c", "novo dispositivo")], arquivo_vetores=arq)
    assert arq.read_bytes() == antes  # o arquivo anterior segue íntegro
    assert [p.name for p in tmp_path.iterdir()] == ["indice.json"]  # sem resíduo .tmp


@pytest.mark.parametrize(
    "conteudo",
    [
        "{truncado",
        "[]",
        '{"vetores": []}',
        '{"versao_formato": 2, "vetores": {"a": ["x"]}}',
    ],
)
def test_arquivo_corrompido_e_descartado_com_aviso(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, conteudo: str
) -> None:
    arq = tmp_path / "indice.json"
    arq.write_text(conteudo, encoding="utf-8")
    with caplog.at_level(logging.INFO, logger="fa_rag.vector_store"):
        ix = IndiceHibrido(_docs(), arquivo_vetores=arq)
    assert ix.buscar("fornecimento de energia", data_referencia=HOJE)
    assert caplog.records, "o descarte do índice inválido deve deixar rastro em log"
    assert json.loads(arq.read_text(encoding="utf-8"))["versao_formato"] == vs.VERSAO_FORMATO


def test_vetor_com_dimensao_errada_e_recalculado(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    dados = json.loads(arq.read_text(encoding="utf-8"))
    dados["vetores"]["a"] = dados["vetores"]["a"][:10]
    arq.write_text(json.dumps(dados), encoding="utf-8")
    ix = IndiceHibrido(_docs(), arquivo_vetores=arq)
    assert len(ix._vetorial._vetores["a"]) == 384


def test_embedder_com_outro_nome_nao_reaproveita_vetores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    monkeypatch.setattr(EmbedderHash, "nome", "outro-embedder", raising=False)
    chamadas: list[int] = []
    original = EmbedderHash.embed

    def contar(self: EmbedderHash, textos: list[str]) -> list[list[float]]:
        chamadas.append(len(textos))
        return original(self, textos)

    monkeypatch.setattr(EmbedderHash, "embed", contar)
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    assert chamadas, "vetores de outro embedder não podem ser reaproveitados"
    assert json.loads(arq.read_text(encoding="utf-8"))["embedder"]["nome"] == "outro-embedder"


def test_formato_antigo_sem_versao_e_reconstruido(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    dados = json.loads(arq.read_text(encoding="utf-8"))
    del dados["versao_formato"]
    arq.write_text(json.dumps(dados), encoding="utf-8")
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    assert json.loads(arq.read_text(encoding="utf-8"))["versao_formato"] == vs.VERSAO_FORMATO


def test_corpus_alterado_reconstroi_o_indice(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido(_docs(), arquivo_vetores=arq)
    mais = [*_docs(), _doc("c", "religação de urgência")]
    ix = IndiceHibrido(mais, arquivo_vetores=arq)
    assert set(json.loads(arq.read_text(encoding="utf-8"))["vetores"]) == {"a", "b", "c"}
    assert {r.documento.id for r in ix.buscar("religação urgência", data_referencia=HOJE)} >= {"c"}


# --------------------------------------------------------------------------- chunking


def test_chunks_do_corpus_real_tem_ids_unicos_e_metadados_de_citacao() -> None:
    chunks = [c for d in carregar_corpus() for c in chunkar_dispositivo(d)]
    assert len({c.id for c in chunks}) == len(chunks)
    for c in chunks:
        assert c.citacao.ato and c.citacao.dispositivo
        assert str(c.citacao.url).startswith("https://")
        assert c.subgrupos


def test_chunks_herdam_vigencia_subgrupo_e_url_do_dispositivo() -> None:
    for doc in carregar_corpus():
        for c in chunkar_dispositivo(doc):
            assert c.citacao.vigencia_inicio == doc.citacao.vigencia_inicio
            assert c.citacao.vigencia_fim == doc.citacao.vigencia_fim
            assert c.citacao.url == doc.citacao.url
            assert c.subgrupos == doc.subgrupos


def test_inciso_fica_no_chunk_do_caput_e_paragrafo_vira_chunk_proprio() -> None:
    doc = _doc(
        "d",
        "Art. 5º A regra geral:\nI - primeiro;\nII - segundo.\n§ 1º Parágrafo.",
        dispositivo="art. 5º",
    )
    caput, paragrafo = chunkar_dispositivo(doc)
    assert "A regra geral" in caput.texto and "I - primeiro" in caput.texto
    assert "II - segundo" in caput.texto
    assert paragrafo.texto.startswith("§ 1º") and "regra geral" not in paragrafo.texto


def test_dispositivos_independentes_nao_se_misturam() -> None:
    a = _doc("a", "Art. 1º Regra A.", dispositivo="art. 1º")
    b = _doc("b", "Art. 2º Regra B.", dispositivo="art. 2º")
    for doc, outro in ((a, "Regra B"), (b, "Regra A")):
        assert all(outro not in c.texto for c in chunkar_dispositivo(doc))


def test_dispositivo_revogado_ou_futuro_nao_e_recuperado() -> None:
    revogado = _doc("rev", "multa por atraso antiga", inicio=date(2010, 1, 1), fim=date(2020, 1, 1))
    futuro = _doc("fut", "multa por atraso futura", inicio=date(2030, 1, 1))
    vigente = _doc("vig", "multa por atraso vigente")
    ix = IndiceHibrido([revogado, futuro, vigente])
    ids = [r.documento.id for r in ix.buscar("multa por atraso", data_referencia=HOJE)]
    assert ids == ["vig"]


def test_subgrupo_diferente_de_b1_fica_fora() -> None:
    a4 = _doc("a4", "multa por atraso em alta tensão", subgrupos=("A4",))
    b1 = _doc("b1", "multa por atraso residencial")
    ix = IndiceHibrido([a4, b1])
    ids = [r.documento.id for r in ix.buscar("multa por atraso", data_referencia=HOJE)]
    assert "a4" not in ids and "b1" in ids


# --------------------------------------------------------------------------- ranking


def test_ranking_e_estavel_em_empates() -> None:
    iguais = [_doc(f"d{i}", "multa por atraso no pagamento") for i in range(4)]
    ix = IndiceHibrido(iguais)
    primeiro = [r.documento.id for r in ix.buscar("multa por atraso", data_referencia=HOJE)]
    for _ in range(3):
        assert [r.documento.id for r in ix.buscar("multa por atraso", data_referencia=HOJE)] == (
            primeiro
        )
    assert primeiro == sorted(primeiro)


def test_scores_ficam_em_zero_a_um_e_filtros_valem_antes_do_ranking() -> None:
    fora = _doc("fora", "multa por atraso", subgrupos=("A4",))
    ix = IndiceHibrido([fora, *_docs()])
    resultados = ix.buscar("multa por atraso", data_referencia=HOJE)
    assert resultados and all(0.0 <= r.score <= 1.0 for r in resultados)
    assert "fora" not in {r.documento.id for r in resultados}
