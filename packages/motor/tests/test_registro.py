"""Registro auditável e categoria dos achados do motor (#169). Dados 100% sintéticos."""

from datetime import date
from decimal import Decimal

from fa_contratos import Achado, Categoria, Fatura, ItemFatura
from fa_motor import analisar_nivel_a, analisar_nivel_b_api, carregar_tabela_tarifas_versionada


def _fatura(**campos: object) -> Fatura:
    base: dict[str, object] = {
        "distribuidora": "Distribuidora Sintética",
        "mes_referencia": date(2026, 3, 1),
        "leitura_anterior": Decimal("10"),
        "leitura_atual": Decimal("20"),
        "consumo_kwh": Decimal("11"),
        "itens": [ItemFatura(descricao="Energia", valor=Decimal("8"))],
        "total": Decimal("9"),
    }
    return Fatura(**{**base, **campos})


def _por_item(achados: list[Achado], item: str) -> Achado:
    return next(a for a in achados if a.item == item)


def test_leituras_divergentes_pedem_verificacao_com_regra_a2() -> None:
    achado = _por_item(analisar_nivel_a(_fatura()), "Consumo medido")
    assert achado.categoria == Categoria.VERIFICACAO_NECESSARIA
    assert achado.registro is not None
    assert achado.registro.regra_aplicada.startswith("A2")
    assert "calculado = 10" in (achado.registro.calculo or "")
    assert achado.registro.limitacoes


def test_leituras_que_conferem_sao_compativeis() -> None:
    fatura = _fatura(consumo_kwh=Decimal("10"), total=Decimal("8"))
    achado = _por_item(analisar_nivel_a(fatura), "Consumo medido")
    assert achado.categoria == Categoria.COMPATIVEL


def test_total_divergente_e_divergencia_identificada_com_regra_a1() -> None:
    achado = _por_item(analisar_nivel_a(_fatura(consumo_kwh=Decimal("10"))), "Total da fatura")
    assert achado.categoria == Categoria.DIVERGENCIA_IDENTIFICADA
    assert achado.registro is not None
    assert achado.registro.regra_aplicada.startswith("A1")


def test_nivel_b_tusd_traz_data_da_tabela_e_regra_b1() -> None:
    tabela = carregar_tabela_tarifas_versionada()
    fatura = _fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        itens=[
            ItemFatura(
                descricao="Consumo-TUSD",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.50000"),
                valor=Decimal("50.00"),
            ),
            ItemFatura(
                descricao="Consumo-TE",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.40000"),
                valor=Decimal("40.00"),
            ),
        ],
        total=Decimal("90.00"),
    )
    achado = _por_item(analisar_nivel_b_api(fatura, tabela=tabela), "Tarifa TUSD+TE")
    assert achado.registro is not None
    assert achado.registro.regra_aplicada.startswith("B1")
    assert achado.registro.data_consulta == tabela.proveniencia.data_download
    assert any("REH 3.614/2026" in limitacao for limitacao in achado.registro.limitacoes)


def test_bandeira_abstem_com_registro_e_categoria_dados_insuficientes() -> None:
    fatura = _fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        bandeira="Verde",
    )
    achado = _por_item(analisar_nivel_b_api(fatura), "Bandeira tarifária")
    assert achado.abstencao is True
    assert achado.categoria == Categoria.DADOS_INSUFICIENTES
    assert achado.registro is not None
    assert achado.registro.limitacoes


def test_fora_do_escopo_b1_e_marcado_explicitamente() -> None:
    achado = _por_item(analisar_nivel_b_api(_fatura()), "Tarifa TUSD+TE")
    assert achado.abstencao is True
    assert achado.categoria == Categoria.FORA_DO_ESCOPO
