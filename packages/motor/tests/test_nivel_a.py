from datetime import date
from decimal import Decimal

import pytest

from fa_contratos import Achado, Fatura, ItemFatura, Nivel
from fa_motor import (
    analisar_nivel_a,
    checar_icms,
    checar_linhas,
    checar_parcela_ate_80_kwh,
)


def _tem_falso_alarme(achados: list[Achado]) -> bool:
    return any(
        not achado.abstencao
        and achado.valor_esperado is not None
        and achado.valor_cobrado is not None
        and achado.valor_esperado != achado.valor_cobrado
        for achado in achados
    )


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


def test_checar_linhas_confere_produto_e_detecta_divergencia_ou_duplicidade() -> None:
    fatura_correta = Fatura(
        distribuidora="Neoenergia Brasília",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("120"),
        itens=[
            ItemFatura(
                descricao="Consumo-TUSD",
                quantidade=Decimal("120.00"),
                unidade="kWh",
                tarifa=Decimal("0.50000000"),
                valor=Decimal("60.00"),
            ),
            ItemFatura(
                descricao="Consumo-TE",
                quantidade=Decimal("120.00"),
                unidade="kWh",
                tarifa=Decimal("0.47000000"),
                valor=Decimal("56.40"),
            ),
        ],
        total=Decimal("116.40"),
    )
    achados_corretos = checar_linhas(fatura_correta)
    assert [a.item for a in achados_corretos] == ["Linha: Consumo-TUSD", "Linha: Consumo-TE"]
    assert not _tem_falso_alarme(achados_corretos)
    assert all(a.nivel is Nivel.A for a in achados_corretos)

    fatura_com_erros = Fatura(
        distribuidora="Neoenergia Brasília",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        itens=[
            ItemFatura(
                descricao="Consumo de energia",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.80"),
                valor=Decimal("92.00"),
            ),
            ItemFatura(descricao="Ilum. Púb. Distrital", valor=Decimal("12.00")),
            ItemFatura(descricao="Ilum. Púb. Distrital", valor=Decimal("12.00")),
            ItemFatura(
                descricao="Linha incompleta",
                quantidade=Decimal("10"),
                tarifa=None,
                valor=Decimal("8.00"),
            ),
        ],
        total=Decimal("124.00"),
    )
    por_item = {a.item: a for a in checar_linhas(fatura_com_erros)}
    assert por_item["Linha: Consumo de energia"].valor_esperado == Decimal("80.00")
    assert por_item["Linha: Consumo de energia"].valor_cobrado == Decimal("92.00")
    assert por_item["Linha duplicada: Ilum. Púb. Distrital"].valor_esperado == Decimal("0.00")
    assert por_item["Linha duplicada: Ilum. Púb. Distrital"].valor_cobrado == Decimal("12.00")
    assert por_item["Linha: Linha incompleta"].abstencao is True
    assert all(a.nivel is Nivel.A for a in por_item.values())


def test_checar_icms_confere_detecta_divergencia_e_se_abstem() -> None:
    correta = Fatura(
        distribuidora="Neoenergia Brasília",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("150"),
        aliquota_icms=Decimal("0.20"),
        itens=[
            ItemFatura(descricao="Consumo", valor=Decimal("100.00")),
            ItemFatura(
                descricao="ICMS",
                quantidade=Decimal("100.00"),
                tarifa=Decimal("0.20"),
                valor=Decimal("20.00"),
            ),
        ],
        total=Decimal("120.00"),
    )
    achado_ok = checar_icms(correta)[0]
    assert achado_ok.nivel is Nivel.A
    assert achado_ok.abstencao is False
    assert achado_ok.valor_esperado == achado_ok.valor_cobrado == Decimal("20.00")

    divergente = Fatura(
        distribuidora="Neoenergia Brasília",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("150"),
        aliquota_icms=Decimal("0.20"),
        itens=[
            ItemFatura(descricao="Consumo", valor=Decimal("100.00")),
            ItemFatura(descricao="ICMS", quantidade=Decimal("100.00"), valor=Decimal("25.00")),
        ],
        total=Decimal("125.00"),
    )
    achado_div = checar_icms(divergente)[0]
    assert achado_div.nivel is Nivel.A
    assert (achado_div.valor_esperado, achado_div.valor_cobrado) == (
        Decimal("20.00"),
        Decimal("25.00"),
    )

    sem_aliquota = Fatura(
        distribuidora="Neoenergia Brasília",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        itens=[ItemFatura(descricao="ICMS", valor=Decimal("16.00"))],
        total=Decimal("16.00"),
    )
    assert checar_icms(sem_aliquota)[0].abstencao is True


def test_checar_parcela_ate_80_kwh_confere_detecta_divergencia_e_se_abstem() -> None:
    elegivel = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("130"),
        itens=[
            ItemFatura(
                descricao="Parcela até 80 kWh - faixa 01",
                quantidade=Decimal("80"),
                unidade="kWh",
                tarifa=Decimal("0.30"),
                valor=Decimal("24.00"),
            ),
            ItemFatura(
                descricao="Consumo excedente - faixa 02",
                quantidade=Decimal("50"),
                unidade="kWh",
                tarifa=Decimal("0.80"),
                valor=Decimal("40.00"),
            ),
        ],
        total=Decimal("64.00"),
    )
    achado_ok = checar_parcela_ate_80_kwh(elegivel)[0]
    assert achado_ok.nivel is Nivel.A
    assert achado_ok.abstencao is False
    assert achado_ok.valor_esperado == achado_ok.valor_cobrado == Decimal("80")

    divergente = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("120"),
        itens=[
            ItemFatura(
                descricao="Parcela até 80 kWh",
                quantidade=Decimal("95"),
                unidade="kWh",
                tarifa=Decimal("0.30"),
                valor=Decimal("28.50"),
            ),
        ],
        total=Decimal("28.50"),
    )
    achado_div = checar_parcela_ate_80_kwh(divergente)[0]
    assert achado_div.nivel is Nivel.A
    assert (achado_div.valor_esperado, achado_div.valor_cobrado) == (
        Decimal("80"),
        Decimal("95"),
    )

    nao_elegivel = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B3",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("70"),
        itens=[
            ItemFatura(
                descricao="Parcela até 80 kWh",
                quantidade=Decimal("70"),
                unidade="kWh",
                tarifa=Decimal("0.30"),
                valor=Decimal("21.00"),
            )
        ],
        total=Decimal("21.00"),
    )
    achado_b3 = checar_parcela_ate_80_kwh(nao_elegivel)[0]
    assert achado_b3.nivel is Nivel.A
    assert (achado_b3.valor_esperado, achado_b3.valor_cobrado) == (
        Decimal("0"),
        Decimal("70"),
    )

    sem_quantidade = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("70"),
        itens=[ItemFatura(descricao="Parcela até 80 kWh", valor=Decimal("21.00"))],
        total=Decimal("21.00"),
    )
    assert checar_parcela_ate_80_kwh(sem_quantidade)[0].abstencao is True


@pytest.mark.parametrize(
    "fatura_correta",
    [
        Fatura(
            distribuidora="Neoenergia Brasília",
            mes_referencia=date(2026, 6, 1),
            leitura_anterior=Decimal("1000"),
            leitura_atual=Decimal("1120"),
            consumo_kwh=Decimal("120"),
            bandeira="amarela",
            aliquota_icms=Decimal("0.12"),
            itens=[
                ItemFatura(
                    descricao="Consumo-TUSD",
                    quantidade=Decimal("120.00"),
                    unidade="kWh",
                    tarifa=Decimal("0.50"),
                    valor=Decimal("60.00"),
                ),
                ItemFatura(
                    descricao="Consumo-TE",
                    quantidade=Decimal("120.00"),
                    unidade="kWh",
                    tarifa=Decimal("0.47"),
                    valor=Decimal("56.40"),
                ),
                ItemFatura(
                    descricao="Acrés. Band. AMARELA",
                    quantidade=Decimal("120.00"),
                    unidade="kWh",
                    tarifa=Decimal("0.025"),
                    valor=Decimal("3.00"),
                ),
                ItemFatura(descricao="Ilum. Púb. Distrital", valor=Decimal("12.00")),
            ],
            total=Decimal("131.40"),
        ),
        Fatura(
            distribuidora="Neoenergia Brasília",
            grupo_tarifario="B1",
            mes_referencia=date(2026, 8, 1),
            leitura_anterior=Decimal("500"),
            leitura_atual=Decimal("640"),
            consumo_kwh=Decimal("140"),
            bandeira="verde",
            aliquota_icms=Decimal("0.20"),
            itens=[
                ItemFatura(
                    descricao="Parcela até 80 kWh (faixa 01)",
                    quantidade=Decimal("80"),
                    unidade="kWh",
                    tarifa=Decimal("0.30"),
                    valor=Decimal("24.00"),
                ),
                ItemFatura(
                    descricao="Consumo excedente (faixa 02)",
                    quantidade=Decimal("60"),
                    unidade="kWh",
                    tarifa=Decimal("0.80"),
                    valor=Decimal("48.00"),
                ),
                ItemFatura(
                    descricao="ICMS",
                    quantidade=Decimal("72.00"),
                    tarifa=Decimal("0.20"),
                    valor=Decimal("14.40"),
                ),
            ],
            total=Decimal("86.40"),
        ),
    ],
)
def test_zero_falso_alarme_nas_faturas_corretas_e_nivel_a(fatura_correta: Fatura) -> None:
    achados = analisar_nivel_a(fatura_correta)

    assert not _tem_falso_alarme(achados)
    assert all(achado.nivel is Nivel.A for achado in achados)
