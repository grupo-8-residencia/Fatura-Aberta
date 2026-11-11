"""Testes do corpus curado, chunking por dispositivo, embeddings e busca híbrida."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
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
    criar_embedder,
    responder,
)

RAIZ = Path(__file__).resolve().parents[3]


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


def test_corpus_tem_ao_menos_20_dispositivos_auditaveis() -> None:
    corpus = carregar_corpus()
    artigos = {d.id for d in corpus}
    assert len(artigos) >= 20
    for d in corpus:
        assert d.texto.strip() and d.titulo.strip()
        assert str(d.citacao.url).startswith("https://")
        assert d.citacao.dispositivo and d.subgrupos and d.tags


def test_corpus_nao_usa_linguagem_proibida() -> None:
    bruto = (RAIZ / "dados/normas/corpus_b1.json").read_text(encoding="utf-8").lower()
    assert "ilegal" not in bruto


def test_itens_nao_conferidos_ficam_fora_do_indice(tmp_path: Path) -> None:
    import json

    item = {
        "id": "x",
        "titulo": "t",
        "texto": "t",
        "citacao": {
            "ato": "a",
            "dispositivo": "art. 1º",
            "vigencia_inicio": "2022-01-03",
            "vigencia_fim": None,
            "url": "https://exemplo.invalid/a",
        },
        "subgrupos": ["B1"],
        "tags": [],
        "conferido": "A verificar",
    }
    arq = tmp_path / "c.json"
    arq.write_text(json.dumps([item]), encoding="utf-8")
    assert carregar_corpus(arq) == []
    assert len(carregar_corpus(arq, so_conferidos=False)) == 1


def test_chunking_separa_caput_paragrafos_e_incisos() -> None:
    doc = _doc(
        "d",
        "Art. 5º A regra geral:\nI - primeiro;\nII - segundo.\n§ 1º Primeiro parágrafo.\n"
        "Parágrafo único. Último.",
        dispositivo="art. 5º",
    )
    chunks = chunkar_dispositivo(doc)
    assert [c.citacao.dispositivo for c in chunks] == [
        "art. 5º, caput",
        "art. 5º, § 1º",
        "art. 5º, parágrafo único",
    ]
    assert "II - segundo" in chunks[0].texto


def test_paragrafo_unico_nao_fica_colado_no_caput() -> None:
    doc = _doc("d", "Art. 9º Regra.\nParágrafo único. Exceção.", dispositivo="art. 9º")
    caput, unico = chunkar_dispositivo(doc)
    assert "Exceção" not in caput.texto and unico.texto.startswith("Parágrafo único")


def test_incisos_soltos_viram_chunks_e_texto_simples_fica_inteiro() -> None:
    soltos = _doc("c", "VI - um;\nVIII - dois;", dispositivo="art. 6º, incisos VI e VIII")
    assert [c.citacao.dispositivo for c in chunkar_dispositivo(soltos)] == [
        "art. 6º, inciso VI",
        "art. 6º, inciso VIII",
    ]
    simples = _doc("s", "Sem estrutura nenhuma.")
    assert chunkar_dispositivo(simples) == [simples]


def test_chunks_preservam_literalidade() -> None:
    for doc in carregar_corpus():
        juntos = "\n".join(c.texto for c in chunkar_dispositivo(doc))
        assert juntos.replace("\n", " ") == doc.texto.replace("\n", " ")


def test_embedder_e_normalizado_deterministico_e_offline() -> None:
    e = EmbedderHash()
    a, b = e.embed(["suspensão do fornecimento", "suspensão do fornecimento"])
    assert a == b and len(a) == e.dim == 384
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)
    assert criar_embedder("hash").dim == 384
    with pytest.raises(ValueError):
        criar_embedder("inexistente")


def _cos(x: list[float], y: list[float]) -> float:
    return sum(i * j for i, j in zip(x, y, strict=True))


def test_cosseno_maior_para_texto_parecido() -> None:
    e = EmbedderHash()
    q, perto, longe = e.embed(
        [
            "notificação de suspensão",
            "notificação prévia da suspensão",
            "bandeira tarifária amarela",
        ]
    )
    assert _cos(q, perto) > _cos(q, longe)


def test_busca_filtra_vigencia_e_subgrupo_antes_do_ranking() -> None:
    docs = [
        _doc("antigo", "corte sem notificação", inicio=date(2010, 1, 1), fim=date(2020, 12, 31)),
        _doc("atual", "corte sem notificação prévia"),
        _doc("outro-grupo", "corte sem notificação prévia", subgrupos=("A4",)),
        _doc("futuro", "corte sem notificação", inicio=date(2030, 1, 1)),
    ]
    ix = IndiceHibrido(docs)
    ids = [
        r.documento.id for r in ix.buscar("corte sem notificação", data_referencia=date(2024, 5, 1))
    ]
    assert ids == ["atual"]
    antigo = ix.buscar("corte sem notificação", data_referencia=date(2015, 5, 1))
    assert [r.documento.id for r in antigo] == ["antigo"]
    # B2: sem filtro de vigência, o revogado e o futuro voltam a competir.
    b2 = ix.buscar(
        "corte sem notificação", data_referencia=date(2024, 5, 1), filtrar_vigencia=False
    )
    assert {"antigo", "futuro"} <= {r.documento.id for r in b2}


def test_alpha_combina_linearmente_os_dois_scores() -> None:
    ix = IndiceHibrido.do_corpus()
    base = ix.buscar("suspensão por inadimplemento", data_referencia=date(2026, 1, 1), top_k=1)[0]
    soh_vet = ix.buscar("suspensão por inadimplemento", data_referencia=date(2026, 1, 1), alpha=1.0)
    soh_lex = ix.buscar("suspensão por inadimplemento", data_referencia=date(2026, 1, 1), alpha=0.0)
    assert all(math.isclose(r.score, r.score_vetorial) for r in soh_vet)
    assert all(math.isclose(r.score, r.score_lexico) for r in soh_lex)
    assert math.isclose(base.score, 0.5 * base.score_vetorial + 0.5 * base.score_lexico)
    with pytest.raises(ValueError):
        ix.buscar("x", data_referencia=date(2026, 1, 1), alpha=1.5)


def test_filtro_de_vigencia_no_corpus_real() -> None:
    ix = IndiceHibrido.do_corpus()
    antes = ix.buscar("suspensão do fornecimento", data_referencia=date(2021, 6, 1), top_k=20)
    assert all("Lei nº 8.078" in r.documento.citacao.ato for r in antes)
    depois = ix.buscar("suspensão do fornecimento", data_referencia=date(2026, 1, 1), top_k=3)
    assert any("art. 360" in r.documento.citacao.dispositivo for r in depois)


def test_recuperacao_encontra_norma_esperada_em_top5() -> None:
    ix = IndiceHibrido.do_corpus()
    casos = {
        "prazo mínimo para vencimento da fatura": "art. 337",
        "multa por atraso no pagamento da fatura": "art. 343",
        "devolução em dobro de valores cobrados a maior": "art. 323",
        "notificação prévia antes da suspensão do fornecimento": "art. 360",
    }
    for consulta, artigo in casos.items():
        top = ix.buscar(
            consulta, data_referencia=date(2026, 11, 9), top_k=5, um_por_dispositivo=True
        )
        assert any(r.documento.citacao.dispositivo.startswith(artigo) for r in top), consulta


def test_resposta_cita_fontes_e_abstem_se_fora_do_escopo() -> None:
    ix = IndiceHibrido.do_corpus()
    dentro = responder(
        ix.buscar(
            "notificação prévia antes da suspensão do fornecimento",
            data_referencia=date(2026, 11, 9),
        )
    )
    assert not dentro.abstencao and dentro.citacoes
    assert all(str(c.url).startswith("https://") for c in dentro.citacoes)
    assert "ilegal" not in dentro.texto.lower()
    assert not re.search(r"R\$\s*\d", dentro.texto)
    fora = responder(
        ix.buscar(
            "como declarar criptomoedas no imposto de renda", data_referencia=date(2026, 11, 9)
        )
    )
    assert fora.abstencao and not fora.citacoes


def test_demonstracao_executa_e_mostra_fontes() -> None:
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "scripts/demonstrar_rag.py")],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout
    assert saida.count("Fontes:") >= 3
    assert "Link oficial: https://" in saida and "Vigência:" in saida
    assert "abstenção" in saida


def test_indice_duravel_salva_carrega_e_da_o_mesmo_resultado(tmp_path: Path) -> None:
    arq = tmp_path / "vetores" / "indice.json"
    novo = IndiceHibrido.do_corpus(arquivo_vetores=arq)
    assert arq.exists()
    carregado = IndiceHibrido.do_corpus(arquivo_vetores=arq)
    hoje = date(2026, 11, 9)
    a = novo.buscar("suspensão por inadimplemento sem notificação", data_referencia=hoje)
    b = carregado.buscar("suspensão por inadimplemento sem notificação", data_referencia=hoje)
    assert [r.documento.id for r in a] == [r.documento.id for r in b]
    assert [round(r.score, 6) for r in a] == [round(r.score, 6) for r in b]


def test_indice_duravel_nao_recalcula_quando_o_arquivo_confere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arq = tmp_path / "indice.json"
    IndiceHibrido.do_corpus(arquivo_vetores=arq)
    chamadas: list[int] = []
    original = EmbedderHash.embed

    def contar(self: EmbedderHash, textos: list[str]) -> list[list[float]]:
        chamadas.append(len(textos))
        return original(self, textos)

    monkeypatch.setattr(EmbedderHash, "embed", contar)
    IndiceHibrido.do_corpus(arquivo_vetores=arq)
    assert chamadas == []  # nada foi recalculado: os vetores vieram do disco


def test_indice_duravel_recalcula_se_o_texto_dimensao_ou_arquivo_mudou(tmp_path: Path) -> None:
    arq = tmp_path / "indice.json"
    docs = [_doc("a", "suspensão do fornecimento"), _doc("b", "multa por atraso")]
    IndiceHibrido(docs, arquivo_vetores=arq)
    # texto diferente com o mesmo id: assinatura não confere, então recalcula e regrava
    docs2 = [_doc("a", "suspensão do fornecimento de energia"), docs[1]]
    novo = IndiceHibrido(docs2, arquivo_vetores=arq)
    assert novo.buscar("fornecimento de energia", data_referencia=date(2024, 1, 1))
    # dimensão diferente
    outro = IndiceHibrido(docs2, embedder=EmbedderHash(dim=64), arquivo_vetores=arq)
    assert len(outro._vetorial._vetores["a"]) == 64
    # arquivo corrompido
    arq.write_text("não é json", encoding="utf-8")
    ok = IndiceHibrido(docs2, arquivo_vetores=arq)
    assert len(ok.documentos) == 2 and json.loads(arq.read_text(encoding="utf-8"))["dim"] == 384


def test_recuperacao_termos_leigos_e_sinonimos() -> None:
    ix = IndiceHibrido.do_corpus()
    hoje = date(2026, 11, 9)
    casos = {
        "de quanto em quanto tempo o medidor é lido no grupo B?": "art. 260",
        "paguei a conta de energia duas vezes": "art. 342",
        "corte por falta de pagamento sem avisar antes": "art. 360",
        "onde fica o código para pagar a fatura?": "art. 327",
    }
    for consulta, artigo in casos.items():
        top = ix.buscar(consulta, data_referencia=hoje, top_k=5, um_por_dispositivo=True)
        assert any(r.documento.citacao.dispositivo.startswith(artigo) for r in top), consulta
        resp = responder(top)
        assert not resp.abstencao, consulta


def test_escopo_negativo_e_entidades_induzem_abstencao() -> None:
    ix = IndiceHibrido.do_corpus()
    hoje = date(2026, 11, 9)
    for consulta in (
        "a taxa de iluminação sofre multa por atraso?",
        "a CIP/COSIP entra no cálculo da multa da fatura?",
    ):
        top = ix.buscar(consulta, data_referencia=hoje, top_k=5, um_por_dispositivo=True)
        assert responder(top).abstencao, consulta

    valida = ix.buscar(
        "posso pedir revisão da CIP por cobrança em duplicidade?",
        data_referencia=hoje,
        top_k=5,
        um_por_dispositivo=True,
    )
    resp = responder(valida)
    assert not resp.abstencao
    assert any("7.888/2026" in c.ato for c in resp.citacoes)


def test_chunkar_dispositivo_preserva_nao_cobre() -> None:
    doc = DocumentoNormativo(
        id="df7888-teste",
        titulo="Direitos da CIP",
        texto="Art. 1º Direitos.\n§ 1º Revisão garantida.",
        citacao=Citacao(
            ato="Lei Teste",
            dispositivo="art. 1º",
            vigencia_inicio=date(2026, 1, 1),
            url="https://exemplo.test/lei",
        ),
        nao_cobre=("aliquota", "multa"),
    )
    chunks = chunkar_dispositivo(doc)
    assert len(chunks) == 2
    assert all(chunk.nao_cobre == ("aliquota", "multa") for chunk in chunks)
