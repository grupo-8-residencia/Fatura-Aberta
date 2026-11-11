"""Testes do pacote RAG da frente F2 cobrindo os critérios de S2-02."""

from datetime import date

import pytest

import fa_rag
from fa_contratos import Citacao, Nivel
from fa_rag.chunker import chunkar_dispositivos, chunkar_texto
from fa_rag.indexer import IndiceNormativo
from fa_rag.models import DocumentoNormativo, ResultadoBusca


def _norma(
    *,
    dispositivo: str,
    texto: str,
    inicio: date,
    fim: date | None = None,
    url: str = "https://exemplo.invalid/norma",
    subgrupos: tuple[str, ...] = ("B1",),
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
        "subgrupos": subgrupos,
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
        alfa=1.0,
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


def test_chunkar_dispositivos_gera_citacoes_canonicas() -> None:
    texto_normativo = (
        "Art. 1º Estabelecer as condições gerais de fornecimento de energia elétrica.\n"
        "§ 1º Aplica-se ao grupo B e consumidores residenciais B1.\n"
        "§ 2º As distribuidoras devem observar o padrão regulatório.\n"
        "Art. 2º Para efeito desta Resolução, entende-se por:\n"
        "I - consumidor: pessoa física ou jurídica;\n"
        "II - distribuidora: concessionária de serviço público."
    )

    chunks = chunkar_dispositivos(
        texto_normativo,
        ato="REN ANEEL 1.000/2021",
        vigencia_inicio=date(2021, 12, 7),
        vigencia_fim=None,
        url="https://www2.aneel.gov.br/cedoc/ren20211000.html",
        subgrupos=("B1",),
        tags=("condicoes-gerais", "regulacao"),
    )

    assert len(chunks) >= 5
    for chunk in chunks:
        assert isinstance(chunk, DocumentoNormativo)
        assert isinstance(chunk.citacao, Citacao)
        assert chunk.citacao.ato == "REN ANEEL 1.000/2021"
        assert chunk.citacao.vigente_em(date(2024, 1, 1)) is True
        assert chunk.citacao.vigente_em(date(2020, 1, 1)) is False
        assert chunk.subgrupos == ("B1",)

    dispositivos = [c.citacao.dispositivo for c in chunks]
    assert "Art. 1º, caput" in dispositivos
    assert "Art. 1º, § 1º" in dispositivos
    assert "Art. 2º, inc. I" in dispositivos


def test_busca_hibrida_combina_lexico_e_vetorial() -> None:
    doc_exato = _norma(
        dispositivo="art. 10",
        texto="A bandeira tarifária vermelha patamar 2 possui taxa adicional.",
        inicio=date(2023, 1, 1),
    )
    doc_semantico = _norma(
        dispositivo="art. 11",
        texto="Custos extraordinários da geração elétrica são repassados no acionamento térmico.",
        inicio=date(2023, 1, 1),
    )
    corpus = [doc_exato, doc_semantico]
    indice = IndiceNormativo(corpus)

    # Busca puramente léxica (alfa=1.0): termo exato 'bandeira'
    res_lex = indice.buscar("bandeira", data_referencia=date(2024, 1, 1), alfa=1.0)
    assert len(res_lex) >= 1
    assert res_lex[0]["citacao"].dispositivo == "art. 10"

    # Busca híbrida detalhada (alfa=0.5): retorna ResultadoBusca com decomposição
    res_hibrido = indice.buscar_detalhado(
        "bandeira tarifária",
        data_referencia=date(2024, 1, 1),
        alfa=0.5,
    )
    assert len(res_hibrido) >= 1
    top = res_hibrido[0]
    assert isinstance(top, ResultadoBusca)
    assert top.score > 0.0
    assert top.score_lexico > 0.0


def test_filtro_subgrupos_exclui_outros_grupos() -> None:
    norma_b1 = _norma(
        dispositivo="art. 15",
        texto="Regra específica para o subgrupo B1 residencial.",
        inicio=date(2024, 1, 1),
        subgrupos=("B1",),
    )
    norma_a4 = _norma(
        dispositivo="art. 16",
        texto="Regra específica de alta tensão para o subgrupo A4 industrial.",
        inicio=date(2024, 1, 1),
        subgrupos=("A4",),
    )
    corpus = [norma_b1, norma_a4]
    indice = IndiceNormativo(corpus)

    res_b1 = indice.buscar("regra específica", data_referencia=date(2024, 6, 1), subgrupos=("B1",))
    assert len(res_b1) == 1
    assert res_b1[0]["citacao"].dispositivo == "art. 15"

    res_a4 = indice.buscar("regra específica", data_referencia=date(2024, 6, 1), subgrupos=("A4",))
    assert len(res_a4) == 1
    assert res_a4[0]["citacao"].dispositivo == "art. 16"


def test_filtro_vigencia_com_data_limite_inclusiva() -> None:
    norma = _norma(
        dispositivo="art. 50",
        texto="Tarifa transitória de 2024.",
        inicio=date(2024, 1, 1),
        fim=date(2024, 12, 31),
    )
    corpus = [norma]

    # Antes do início: não vigente
    assert len(fa_rag.filtra_vigentes(corpus, date(2023, 12, 31))) == 0
    # No primeiro dia (limite inferior inclusivo): vigente
    assert len(fa_rag.filtra_vigentes(corpus, date(2024, 1, 1))) == 1
    # No último dia (limite superior inclusivo): vigente
    assert len(fa_rag.filtra_vigentes(corpus, date(2024, 12, 31))) == 1
    # Após o encerramento: revogada/não vigente
    assert len(fa_rag.filtra_vigentes(corpus, date(2025, 1, 1))) == 0
