from datetime import date
from decimal import Decimal

from fa_contratos import Achado, Fatura, ItemFatura, Nivel
from fa_motor import (
    analisar_nivel_b,
    carregar_tabela_tarifas_versionada,
    checar_bandeira,
    checar_tusd_te,
    obter_tarifa_aplicacao_b1,
)

TERMOS_PROIBIDOS = ("ilegal", "ilícito", "ilicito", "restituição", "restituicao", "ressarcimento")


def _validar_invariantes_nivel_b(achados: list[Achado], *, deve_divergir: bool) -> None:
    tabela = carregar_tabela_tarifas_versionada()
    fonte = tabela.proveniencia.fonte
    data_iso = tabela.proveniencia.data_download.isoformat()

    assert achados
    for achado in achados:
        assert achado.nivel == Nivel.B
        assert achado.citacoes
        assert fonte in achado.descricao
        assert data_iso in achado.descricao
        assert fonte in achado.citacoes[0].ato
        assert data_iso in achado.citacoes[0].ato
        texto_baixo = achado.descricao.lower()
        for proibido in TERMOS_PROIBIDOS:
            assert proibido not in texto_baixo
        if deve_divergir:
            assert "diverge da tabela oficial que conseguimos obter" in achado.descricao


def test_carrega_tabela_versionada_e_converte_mwh_para_kwh() -> None:
    tabela = carregar_tabela_tarifas_versionada()
    assert tabela.proveniencia.data_download == date(2026, 10, 29)
    assert len(tabela.linhas) > 0

    reh_2025 = obter_tarifa_aplicacao_b1(date(2026, 5, 1), tabela=tabela)
    assert reh_2025 is not None
    assert reh_2025.tusd_kwh == Decimal("0.42392")
    assert reh_2025.te_kwh == Decimal("0.40280")
    assert reh_2025.tusd_mais_te_kwh == Decimal("0.82672")

    reh_2026 = obter_tarifa_aplicacao_b1(date(2026, 11, 1), tabela=tabela)
    assert reh_2026 is not None
    assert reh_2026.tusd_kwh == Decimal("0.45347")
    assert reh_2026.te_kwh == Decimal("0.38082")
    assert reh_2026.tusd_mais_te_kwh == Decimal("0.83429")


def test_checar_tusd_te_confere_e_diverge_com_fonte_e_data() -> None:
    fatura_ok = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        itens=[
            ItemFatura(
                descricao="Consumo-TUSD",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.42392"),
                valor=Decimal("42.39"),
            ),
            ItemFatura(
                descricao="Consumo-TE",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.40280"),
                valor=Decimal("40.28"),
            ),
        ],
        total=Decimal("82.67"),
    )
    achados_ok = checar_tusd_te(fatura_ok)
    _validar_invariantes_nivel_b(achados_ok, deve_divergir=False)
    assert achados_ok[0].valor_esperado == achados_ok[0].valor_cobrado == Decimal("0.82672")

    fatura_divergente = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        itens=[
            ItemFatura(
                descricao="Consumo Ativo",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.98500"),
                valor=Decimal("98.50"),
            )
        ],
        total=Decimal("98.50"),
    )
    achados_div = checar_tusd_te(fatura_divergente)
    _validar_invariantes_nivel_b(achados_div, deve_divergir=True)
    assert achados_div[0].valor_esperado == Decimal("0.82672")
    assert achados_div[0].valor_cobrado == Decimal("0.98500")


def test_checar_tusd_te_abstem_fora_da_vigencia_ou_sem_tarifa() -> None:
    fatura_fora_vigencia = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2024, 1, 1),
        consumo_kwh=Decimal("100"),
        itens=[ItemFatura(descricao="Consumo", tarifa=Decimal("0.80"), valor=Decimal("80.00"))],
        total=Decimal("80.00"),
    )
    achados_fora = checar_tusd_te(fatura_fora_vigencia)
    _validar_invariantes_nivel_b(achados_fora, deve_divergir=False)
    assert achados_fora[0].abstencao is True

    fatura_sem_tarifa = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        itens=[ItemFatura(descricao="Consumo", valor=Decimal("82.67"))],
        total=Decimal("82.67"),
    )
    achados_sem = checar_tusd_te(fatura_sem_tarifa)
    _validar_invariantes_nivel_b(achados_sem, deve_divergir=False)
    assert achados_sem[0].abstencao is True


def test_checar_bandeira_confere_e_diverge_com_fonte_e_data() -> None:
    fatura_verde_indevida = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        bandeira="verde",
        itens=[
            ItemFatura(
                descricao="Acrés. Band. VERDE",
                quantidade=Decimal("100"),
                unidade="kWh",
                tarifa=Decimal("0.04463"),
                valor=Decimal("4.46"),
            )
        ],
        total=Decimal("4.46"),
    )
    achados_verde_div = checar_bandeira(fatura_verde_indevida)
    _validar_invariantes_nivel_b(achados_verde_div, deve_divergir=True)
    assert achados_verde_div[0].valor_esperado == Decimal("0.00000")
    assert achados_verde_div[0].valor_cobrado == Decimal("0.04463")

    fatura_amarela_sem_tarifa_divergente = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 6, 1),
        consumo_kwh=Decimal("100"),
        bandeira="amarela",
        itens=[
            ItemFatura(
                descricao="Adicional Bandeira Amarela",
                quantidade=Decimal("100"),
                unidade="kWh",
                valor=Decimal("9.50"),
            )
        ],
        total=Decimal("9.50"),
    )
    achados_amarela_div = checar_bandeira(fatura_amarela_sem_tarifa_divergente)
    _validar_invariantes_nivel_b(achados_amarela_div, deve_divergir=True)
    assert achados_amarela_div[0].valor_esperado == Decimal("1.89")
    assert achados_amarela_div[0].valor_cobrado == Decimal("9.50")


def test_analisar_nivel_b_retorna_tusd_te_e_bandeira_com_citacoes() -> None:
    fatura = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=date(2026, 7, 1),
        consumo_kwh=Decimal("150"),
        bandeira="vermelha 1",
        itens=[
            ItemFatura(
                descricao="Consumo-TUSD",
                quantidade=Decimal("150"),
                unidade="kWh",
                tarifa=Decimal("0.50000"),
                valor=Decimal("75.00"),
            ),
            ItemFatura(
                descricao="Consumo-TE",
                quantidade=Decimal("150"),
                unidade="kWh",
                tarifa=Decimal("0.45000"),
                valor=Decimal("67.50"),
            ),
            ItemFatura(
                descricao="Acrés. Band. VERMELHA 1",
                quantidade=Decimal("150"),
                unidade="kWh",
                tarifa=Decimal("0.06000"),
                valor=Decimal("9.00"),
            ),
        ],
        total=Decimal("151.50"),
    )
    achados = analisar_nivel_b(fatura)
    assert [a.item for a in achados] == ["Tarifa TUSD+TE", "Bandeira tarifária"]
    _validar_invariantes_nivel_b(achados, deve_divergir=True)
