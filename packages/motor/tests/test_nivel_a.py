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
    assert all("confere" in achado.descricao for achado in achados)


def test_se_abstem_sem_campos_suficientes() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        consumo_kwh=Decimal("10"),
        total=Decimal("8"),
    )

    achado = analisar_nivel_a(fatura)[0]

    assert achado.abstencao is True
