"""Parser de PDF: PDF sintético válido gera `Fatura` e nenhum dado pessoal sai dele."""

import logging
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from fa_contratos import Fatura
from fa_extracao import ErroExtracao, parse_pdf, parse_texto

LinhasFatura = Callable[[str], list[str]]


def test_pdf_sintetico_gera_fatura_valida(pdf_fatura: bytes) -> None:
    fatura = parse_pdf(pdf_fatura)

    assert Fatura.model_validate(fatura.model_dump()) == fatura
    assert fatura.distribuidora == "Neoenergia Brasília"
    assert fatura.grupo_tarifario == "B1"
    assert fatura.mes_referencia == date(2026, 6, 1)
    assert fatura.consumo_kwh == Decimal("120.00")
    assert fatura.bandeira == "Amarela"
    assert fatura.aliquota_icms == Decimal("0.12")
    assert fatura.total == Decimal("130.40")


def test_leituras_vem_da_tabela_do_medidor_e_nao_das_datas(pdf_fatura: bytes) -> None:
    fatura = parse_pdf(pdf_fatura)

    assert fatura.leitura_anterior == Decimal("1000.00")
    assert fatura.leitura_atual == Decimal("1120.00")


def test_itens_com_quantidade_tarifa_e_credito_negativo(pdf_fatura: bytes) -> None:
    fatura = parse_pdf(pdf_fatura)

    assert [(i.descricao, i.valor) for i in fatura.itens] == [
        ("Consumo-TUSD", Decimal("60.00")),
        ("Consumo-TE", Decimal("56.40")),
        ("Acrés. Band. AMARELA", Decimal("3.00")),
        ("Ilum. Púb. Distrital", Decimal("12.00")),
        ("CREDITO-TESTE-01/02", Decimal("-1.00")),
    ]
    tusd = fatura.itens[0]
    assert (tusd.quantidade, tusd.unidade, tusd.tarifa) == (
        Decimal("120.00"),
        "kWh",
        Decimal("0.50000000"),
    )
    assert sum(i.valor for i in fatura.itens) == fatura.total


def test_tributos_e_medidores_nao_viram_itens(pdf_fatura: bytes) -> None:
    descricoes = {i.descricao.lower() for i in parse_pdf(pdf_fatura).itens}

    assert not descricoes & {"pis", "cofins", "icms", "total"}
    assert not any("energia ativa" in d for d in descricoes)


def test_consumo_soma_as_linhas_do_medidor(linhas_fatura: LinhasFatura) -> None:
    linhas = [
        "1234567890 Energia Ativa Único 1.000,00 1.050,00 1,00000 50,00"
        if linha.endswith("1.120,00 1,00000 120,00")
        else linha
        for linha in linhas_fatura("06/2026")
    ]

    assert parse_texto("\n".join(linhas)).consumo_kwh == Decimal("50.00")


def test_nenhum_dado_pessoal_sai_do_parser(
    pdf_fatura: bytes, pii: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        fatura = parse_pdf(pdf_fatura)

    saida = fatura.model_dump_json() + caplog.text
    for dado in pii.values():
        assert dado not in saida


def test_erros_nao_vazam_dados_pessoais(pii: dict[str, str], linhas_fatura: LinhasFatura) -> None:
    linhas = [linha for linha in linhas_fatura("06/2026") if "Energia Ativa" not in linha]

    with pytest.raises(ErroExtracao) as erro:
        parse_texto("\n".join(linhas))

    for dado in pii.values():
        assert dado not in str(erro.value)


def test_campo_obrigatorio_ausente(linhas_fatura: LinhasFatura) -> None:
    linhas = [linha for linha in linhas_fatura("06/2026") if "TOTAL A PAGAR" not in linha]

    with pytest.raises(ErroExtracao, match="total"):
        parse_texto("\n".join(linhas))


def test_mes_de_referencia_ausente(linhas_fatura: LinhasFatura) -> None:
    linhas = [linha for linha in linhas_fatura("06/2026") if "REF:" not in linha]

    with pytest.raises(ErroExtracao, match="referência"):
        parse_texto("\n".join(linhas))


def test_distribuidora_fora_do_escopo(linhas_fatura: LinhasFatura) -> None:
    linhas = [
        "EQUATORIAL GOIÁS DISTRIBUIDORA DE ENERGIA S.A" if "NEOENERGIA" in linha else linha
        for linha in linhas_fatura("06/2026")
    ]

    with pytest.raises(ErroExtracao, match="fora do escopo"):
        parse_texto("\n".join(linhas))


def test_grupo_tarifario_fora_do_b1(linhas_fatura: LinhasFatura) -> None:
    linhas = [
        "CLASSIFICAÇÃO: B3 DEMAIS CLASSES" if "CLASSIFICAÇÃO" in linha else linha
        for linha in linhas_fatura("06/2026")
    ]

    with pytest.raises(ErroExtracao, match="B1"):
        parse_texto("\n".join(linhas))


def test_valor_invalido_no_contrato_nao_repete_o_valor(linhas_fatura: LinhasFatura) -> None:
    linhas = [
        "ICMS 119,40 250,00 14,33" if linha.startswith("ICMS") else linha
        for linha in linhas_fatura("06/2026")
    ]

    with pytest.raises(ErroExtracao, match="aliquota_icms") as erro:
        parse_texto("\n".join(linhas))

    assert "250" not in str(erro.value)


def test_pdf_corrompido() -> None:
    with pytest.raises(ErroExtracao, match="ilegível"):
        parse_pdf(b"isto nao e um pdf")
