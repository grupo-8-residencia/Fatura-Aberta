"""Testes de contrato com exemplos 100% sintéticos (nenhum dado de fatura real)."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from fa_contratos import Achado, Citacao, Fatura, ItemFatura, Nivel


def citacao_sintetica() -> Citacao:
    return Citacao(
        ato="Ato sintético 1/2000",
        dispositivo="art. 1º, inciso I",
        vigencia_inicio=date(2000, 1, 1),
        url="https://exemplo.invalid/ato-1-2000",
    )


def fatura_sintetica() -> Fatura:
    return Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        leitura_anterior=Decimal("1000"),
        leitura_atual=Decimal("1150"),
        consumo_kwh=Decimal("150"),
        bandeira="verde",
        aliquota_icms=Decimal("0.20"),
        itens=[
            ItemFatura(
                descricao="Consumo",
                quantidade=Decimal("150"),
                unidade="kWh",
                tarifa=Decimal("0.80"),
                valor=Decimal("120.00"),
            ),
        ],
        total=Decimal("120.00"),
    )


def test_nivel_tem_exatamente_a_b_c() -> None:
    assert [n.value for n in Nivel] == ["A", "B", "C"]


def test_fatura_ida_e_volta_em_json() -> None:
    original = fatura_sintetica()
    assert Fatura.model_validate_json(original.model_dump_json()) == original


def test_fatura_nao_tem_campos_de_dados_pessoais() -> None:
    campos = set(Fatura.model_fields)
    assert not campos & {"nome", "endereco", "instalacao", "numero_instalacao", "cpf"}


def test_fatura_rejeita_campo_desconhecido() -> None:
    dados = fatura_sintetica().model_dump(mode="json")
    dados["nome"] = "Fulano"
    with pytest.raises(ValidationError):
        Fatura.model_validate(dados)


def test_fatura_rejeita_consumo_negativo() -> None:
    dados = fatura_sintetica().model_dump(mode="json")
    dados["consumo_kwh"] = "-1"
    with pytest.raises(ValidationError):
        Fatura.model_validate(dados)


def test_achado_nivel_a_ida_e_volta_em_json() -> None:
    achado = Achado(
        item="Consumo",
        nivel=Nivel.A,
        descricao="Total do item não confere com quantidade x tarifa.",
        valor_esperado=Decimal("120.00"),
        valor_cobrado=Decimal("125.00"),
    )
    assert Achado.model_validate_json(achado.model_dump_json()) == achado
    assert achado.abstencao is False
    assert achado.citacoes == []


def test_achado_com_citacao_e_abstencao() -> None:
    achado = Achado(
        item="Bandeira",
        nivel=Nivel.C,
        descricao="Indício não confirmável; pedir esclarecimento.",
        citacoes=[citacao_sintetica()],
        abstencao=True,
    )
    assert achado.citacoes[0].dispositivo == "art. 1º, inciso I"
    assert achado.abstencao is True


def test_achado_rejeita_nivel_invalido() -> None:
    with pytest.raises(ValidationError):
        Achado.model_validate({"item": "x", "nivel": "D", "descricao": "y"})


def test_citacao_rejeita_vigencia_invertida() -> None:
    with pytest.raises(ValidationError):
        Citacao(
            ato="Ato",
            dispositivo="art. 1º",
            vigencia_inicio=date(2026, 5, 1),
            vigencia_fim=date(2026, 4, 30),
            url="https://exemplo.invalid/ato",
        )


@pytest.mark.parametrize(
    ("dia", "esperado"),
    [
        (date(1999, 12, 31), False),
        (date(2000, 1, 1), True),
        (date(2030, 6, 15), True),
    ],
)
def test_citacao_vigente_em(dia: date, esperado: bool) -> None:
    assert citacao_sintetica().vigente_em(dia) is esperado


def test_citacao_vigencia_com_fim_e_inclusiva() -> None:
    c = Citacao(
        ato="Ato",
        dispositivo="art. 2º",
        vigencia_inicio=date(2024, 1, 1),
        vigencia_fim=date(2024, 12, 31),
        url="https://exemplo.invalid/ato",
    )
    assert c.vigente_em(date(2024, 12, 31)) is True
    assert c.vigente_em(date(2025, 1, 1)) is False


def test_modelos_sao_imutaveis() -> None:
    achado = Achado(item="x", nivel=Nivel.A, descricao="y")
    with pytest.raises(ValidationError):
        achado.item = "z"  # type: ignore[misc]
