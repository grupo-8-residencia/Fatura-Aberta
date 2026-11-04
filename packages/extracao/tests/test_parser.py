"""Parser de PDF: PDF sintético válido gera `Fatura` e nenhum dado pessoal sai dele."""

import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from fa_contratos import Fatura
from fa_extracao import ErroExtracao, parse_pdf, parse_texto
from fa_extracao.layouts import LAYOUT_ANTERIOR, LAYOUT_POSTERIOR, escolher_layout


def test_pdf_sintetico_gera_fatura_valida(pdf_fatura: bytes) -> None:
    fatura = parse_pdf(pdf_fatura)

    assert Fatura.model_validate(fatura.model_dump()) == fatura
    assert fatura.mes_referencia == date(2026, 6, 1)
    assert fatura.leitura_anterior == Decimal("1000")
    assert fatura.leitura_atual == Decimal("1150")
    assert fatura.consumo_kwh == Decimal("150")
    assert fatura.bandeira == "Amarela"
    assert fatura.aliquota_icms == Decimal("0.2")
    assert fatura.total == Decimal("142.75")
    assert [(i.descricao, i.valor) for i in fatura.itens] == [
        ("Energia ativa", Decimal("120.50")),
        ("Bandeira tarifaria", Decimal("8.25")),
        ("Contribuicao de iluminacao", Decimal("14.00")),
    ]


def test_nenhum_dado_pessoal_sai_do_parser(
    pdf_fatura: bytes, pii: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        fatura = parse_pdf(pdf_fatura)

    saida = fatura.model_dump_json() + caplog.text
    for dado in pii.values():
        assert dado not in saida


def test_erros_nao_vazam_dados_pessoais(
    pii: dict[str, str], linhas_fatura: Callable[[str], list[str]]
) -> None:
    linhas = [linha for linha in linhas_fatura("06/2026") if not linha.startswith("Consumo")]

    with pytest.raises(ErroExtracao) as erro:
        parse_texto("\n".join(linhas))

    for dado in pii.values():
        assert dado not in str(erro.value)


def test_campo_obrigatorio_ausente(linhas_fatura: Callable[[str], list[str]]) -> None:
    linhas = [linha for linha in linhas_fatura("06/2026") if not linha.startswith("Total")]

    with pytest.raises(ErroExtracao, match="total"):
        parse_texto("\n".join(linhas))


def test_valor_invalido_no_contrato_nao_repete_o_valor(
    linhas_fatura: Callable[[str], list[str]],
) -> None:
    linhas = [
        "ICMS: 250,00%" if linha.startswith("ICMS") else linha for linha in linhas_fatura("06/2026")
    ]

    with pytest.raises(ErroExtracao, match="aliquota_icms") as erro:
        parse_texto("\n".join(linhas))

    assert "250" not in str(erro.value)


def test_pdf_corrompido() -> None:
    with pytest.raises(ErroExtracao, match="ilegível"):
        parse_pdf(b"isto nao e um pdf")


def test_layout_escolhido_pelo_mes_de_referencia() -> None:
    assert escolher_layout(date(2026, 4, 1)) is LAYOUT_ANTERIOR
    assert escolher_layout(date(2026, 5, 1)) is LAYOUT_POSTERIOR


@pytest.mark.parametrize("referencia", ["03/2026", "05/2026"])
def test_parser_atende_os_dois_layouts(
    referencia: str,
    linhas_fatura: Callable[[str], list[str]],
    gerar_pdf: Callable[[list[str]], bytes],
) -> None:
    fatura = parse_pdf(gerar_pdf(linhas_fatura(referencia)))

    assert fatura.mes_referencia == date(2026, int(referencia[:2]), 1)
