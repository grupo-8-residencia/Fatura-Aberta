"""Testes mínimos do pacote RAG da frente F2."""

from datetime import date

import pytest

import fa_rag
from fa_contratos import Citacao, Nivel
from fa_rag.chunker import chunkar_texto
from fa_rag.indexer import IndiceNormativo


def _norma(
    *,
    dispositivo: str,
    texto: str,
    inicio: date,
    fim: date | None = None,
    url: str = "https://exemplo.invalid/norma",
) -> dict[str, object]:
    return {
        "id": dispositivo,
        "titulo": f"Norma {dispositivo}",
        "texto": texto,
        "citacao": Citacao(
            ato="Ato sintético 1/2024",
            dispositivo=dispositivo,
            vigencia_inicio=inicio,
            vigencia_fim=fim,
            url=url,
        ),
        "subgrupos": ("B1",),
        "tags": ("tarifa", "energia"),
    }


def test_pacote_importa_e_enxerga_contratos() -> None:
    assert fa_rag.FRENTE == "F2"
    assert {n.value for n in Nivel} == {"A", "B", "C"}


def test_filtra_vigentes_respeita_data_da_consulta() -> None:
    corpus = [
        _norma(
            dispositivo="art. 1º",
            texto="norma antiga",
            inicio=date(2020, 1, 1),
            fim=date(2023, 12, 31),
        ),
        _norma(dispositivo="art. 2º", texto="norma vigente", inicio=date(2024, 1, 1)),
        _norma(dispositivo="art. 3º", texto="norma futura", inicio=date(2025, 1, 1)),
    ]

    vigentes = fa_rag.filtra_vigentes(corpus, date(2024, 6, 15))

    assert [item["citacao"].dispositivo for item in vigentes] == ["art. 2º"]


def test_recall_at_5_calcula_relevancia_dentro_dos_5_primeiros() -> None:
    relevantes = {"art. 1º", "art. 2º", "art. 3º"}
    top_5 = ["art. 9º", "art. 1º", "art. 8º", "art. 2º", "art. 7º"]

    assert fa_rag.recall_at_5(top_5, relevantes) == pytest.approx(2 / 3)


def test_busca_lexica_retorna_resultados_vigentes() -> None:
    corpus = [
        _norma(
            dispositivo="art. 1º",
            texto="A bandeira tarifária amarela depende do consumo.",
            inicio=date(2024, 1, 1),
        ),
        _norma(
            dispositivo="art. 2º",
            texto="A tarifa de energia é cobrada por consumo residencial.",
            inicio=date(2023, 1, 1),
            fim=date(2024, 12, 31),
        ),
        _norma(
            dispositivo="art. 3º",
            texto="Regra futura para as bandeiras tarifárias.",
            inicio=date(2025, 1, 1),
        ),
    ]

    resultados = fa_rag.buscar_normas(
        "bandeira tarifária",
        corpus=corpus,
        data_referencia=date(2024, 6, 1),
        top_k=5,
    )

    assert [item["citacao"].dispositivo for item in resultados] == ["art. 1º"]


def test_chunkar_texto_divide_em_blocos_coerentes() -> None:
    texto = "Art. 1º. Regra inicial sobre bandeiras tarifárias.\n\nArt. 2º. Regra sobre consumo."

    blocos = chunkar_texto(texto, max_chars=80)

    assert len(blocos) >= 2
    assert all(bloco.strip() for bloco in blocos)


def test_indice_normativo_busca_por_vigencia_e_texto() -> None:
    corpus = [
        _norma(
            dispositivo="art. 1º",
            texto="Regra sobre a bandeira tarifária amarela.",
            inicio=date(2024, 1, 1),
        ),
        _norma(
            dispositivo="art. 2º",
            texto="Regra futura sobre bandeira tarifária.",
            inicio=date(2025, 1, 1),
        ),
    ]

    indice = IndiceNormativo(corpus)
    resultados = indice.buscar(
        "bandeira tarifária",
        data_referencia=date(2024, 6, 1),
        top_k=5,
    )

    assert [resultado["citacao"].dispositivo for resultado in resultados] == ["art. 1º"]
