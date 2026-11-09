from datetime import date
from decimal import Decimal

from fa_contratos import Fatura, ItemFatura
from fa_motor import analisar_nivel_a


def test_confere_leituras_e_total() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        leitura_anterior=Decimal("10"),
        leitura_atual=Decimal("20"),
        consumo_kwh=Decimal("10"),
        itens=[ItemFatura(descricao="Energia", valor=Decimal("8"))],
        total=Decimal("8"),
    )

    achados = analisar_nivel_a(fatura)

    assert [achado.item for achado in achados] == ["Consumo medido", "Total da fatura"]
    assert [(achado.valor_esperado, achado.valor_cobrado) for achado in achados] == [
        (Decimal("10"), Decimal("10")),
        (Decimal("8"), Decimal("8")),
    ]


def test_indica_divergencias_de_consumo_e_total() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        leitura_anterior=Decimal("10"),
        leitura_atual=Decimal("20"),
        consumo_kwh=Decimal("11"),
        itens=[ItemFatura(descricao="Energia", valor=Decimal("8"))],
        total=Decimal("9"),
    )

    achados = analisar_nivel_a(fatura)

    assert [(achado.valor_esperado, achado.valor_cobrado) for achado in achados] == [
        (Decimal("10"), Decimal("11")),
        (Decimal("8"), Decimal("9")),
    ]
    assert all("não confere" in achado.descricao for achado in achados)


def test_se_abstem_quando_as_leituras_estao_em_ordem_decrescente() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        leitura_anterior=Decimal("99999"),
        leitura_atual=Decimal("0"),
        consumo_kwh=Decimal("1"),
        total=Decimal("8"),
    )

    achado = analisar_nivel_a(fatura)[0]

    assert achado.item == "Consumo medido"
    assert achado.abstencao is True


def test_se_abstem_sem_campos_suficientes() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        consumo_kwh=Decimal("10"),
        total=Decimal("8"),
    )

    achado = analisar_nivel_a(fatura)[0]

    assert achado.abstencao is True
