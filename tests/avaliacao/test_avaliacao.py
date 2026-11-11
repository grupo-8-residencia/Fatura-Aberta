"""Testes da estatística, da calibração do juiz e da rodada B2 × B3 (S3-02)."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import calibrar_juiz as cj
import estatistica as est
import gerar_golden_set as gs
import pytest
import rodar_b2_b3 as rb


def test_mcnemar_com_correcao_de_edwards() -> None:
    a = [False] * 10 + [True] * 10
    b = [True] * 10 + [True] * 10
    r = est.mcnemar(a, b)
    assert (r.n01, r.n10) == (10, 0)
    assert r.chi2 == pytest.approx((10 - 1) ** 2 / 10)
    assert r.p_valor == pytest.approx(math.erfc(math.sqrt(r.chi2 / 2)))
    assert r.p_exato == pytest.approx(2 * 0.5**10)
    assert r.significativo


def test_mcnemar_sem_discordantes_nao_e_significativo() -> None:
    r = est.mcnemar([True, False], [True, False])
    assert (r.chi2, r.p_valor) == (0.0, 1.0) and not r.significativo


def test_bootstrap_ic_cobre_a_media_e_e_reprodutivel() -> None:
    dados = [1.0] * 80 + [0.0] * 20
    ic = est.bootstrap_ic(dados, b=2000, semente=1)
    assert ic.inferior <= ic.estimativa <= ic.superior
    assert ic.estimativa == pytest.approx(0.8)
    assert 0.70 < ic.inferior < 0.80 < ic.superior < 0.90
    assert ic == est.bootstrap_ic(dados, b=2000, semente=1)


def test_bootstrap_diferenca_pareada() -> None:
    ic = est.bootstrap_ic_diferenca([0.0] * 50, [1.0] * 50, b=500)
    assert ic.estimativa == pytest.approx(1.0) and ic.inferior == pytest.approx(1.0)


def test_kappa_de_cohen_valores_conhecidos() -> None:
    assert est.kappa_cohen(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == pytest.approx(1.0)
    # po = 0,5; pe = 0,5 => kappa 0
    assert est.kappa_cohen(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)
    # exemplo clássico: po = 0,7; pe = 0,5 => kappa 0,4
    humano = ["s"] * 25 + ["n"] * 25
    juiz = ["s"] * 20 + ["n"] * 5 + ["s"] * 10 + ["n"] * 15
    assert est.kappa_cohen(humano, juiz) == pytest.approx(0.4)


def test_modelo_do_juiz_tem_40_itens_sem_numeros(tmp_path: Path) -> None:
    arq = tmp_path / "juiz.csv"
    cj.gerar_modelo(arq)
    with arq.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 40 and len({r["item_id"] for r in linhas}) == 40
    assert {r["anotador"] for r in linhas} == set(gs.ANOTADORES)
    with pytest.raises(ValueError, match="incompleta"):
        cj.calcular(arq)


def test_calibracao_calcula_kappa_com_anotacao_sintetica(tmp_path: Path) -> None:
    """Anotação SINTÉTICA, só para testar o cálculo; não é resultado de pesquisa."""
    arq = tmp_path / "juiz.csv"
    with arq.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cj.COLUNAS)
        for k in range(40):
            humano = "confere" if k % 2 == 0 else "diverge_A"
            juiz = humano if k >= 2 else ("diverge_A" if humano == "confere" else "confere")
            w.writerow([f"X{k}", "t", humano, juiz])
    r = cj.calcular(arq)
    assert r["n"] == 40 and r["acuracia"] == pytest.approx(38 / 40)
    assert r["aprovado"] is True and float(str(r["kappa"])) > cj.LIMIAR_KAPPA


def test_modelo_versionado_continua_vazio() -> None:
    """Enquanto não houver anotação humana real, o CSV versionado não pode ter números."""
    with cj.ARQUIVO_PADRAO.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if any(r["veredito_humano"] or r["veredito_juiz"] for r in linhas):
        pytest.skip("anotação humana já preenchida")
    assert cj.main([]) == 2


def test_rodada_b2_b3_e_reprodutivel_e_b3_nao_viola_vigencia() -> None:
    r = rb.rodar()
    assert r["configuracao"]["n_itens"] == 120
    assert r["metricas"]["B3"]["violacoes_de_vigencia"] == 0
    assert r["metricas"]["B2"]["violacoes_de_vigencia"] > 0
    # onde a data é atual, o filtro não muda a recuperação: a vantagem do B3 vem da vigência
    iguais = [i for i in r["itens"] if i["tipo"] == "normativa" and i["B2"] != i["B3"]]
    assert not iguais
    versionado = json.loads(rb.SAIDA_PADRAO.read_text(encoding="utf-8"))
    assert versionado["metricas"] == r["metricas"]


def test_metricas_de_ranking_valores_conhecidos() -> None:
    import math as m

    import metricas_recuperacao as mr

    rk = [["a", "b", "c"], ["x", "a", "c"], ["x", "y", "z"]]
    can = [{"a"}, {"a"}, {"a"}]
    r = mr.metricas_ranking(rk, can)
    assert r["hit@1"]["estimativa"] == pytest.approx(1 / 3)
    assert r["hit@3"]["estimativa"] == pytest.approx(2 / 3)
    assert r["MRR"]["estimativa"] == pytest.approx((1 + 1 / 2 + 0) / 3)
    assert r["nDCG@5"]["estimativa"] == pytest.approx((1 + 1 / m.log2(3) + 0) / 3)
    assert r["precisao@5"]["estimativa"] == pytest.approx((1 / 5 + 1 / 5 + 0) / 3)


def test_metricas_de_abstencao_valores_conhecidos() -> None:
    import metricas_recuperacao as mr

    m = mr.metricas_abstencao([True, True, False, False], [True, False, True, False])
    assert (m["vp"], m["fp"], m["fn"]) == (1, 1, 1)
    assert m["precisao"] == pytest.approx(0.5) and m["recall"] == pytest.approx(0.5)
    assert m["f1"] == pytest.approx(0.5) and m["acuracia"] == pytest.approx(0.5)
    zero = mr.metricas_abstencao([False, False], [False, False])
    assert zero["f1"] == 0.0


def test_metricas_ampliadas_batem_com_o_arquivo_versionado() -> None:
    import metricas_recuperacao as mr

    r = mr.rodar()
    versionado = json.loads(mr.SAIDA.read_text(encoding="utf-8"))
    for chave in ("ranking", "ablacao_alpha", "abstencao_por_limiar", "fundamentacao"):
        assert r[chave] == versionado[chave]
    assert r["fundamentacao"]["citacoes_vigentes"]["estimativa"] == 1.0


def test_gate_s2_recall_em_30_perguntas() -> None:
    import medir_recall_s2 as mr_s2

    resultado = mr_s2.medir_recall_s2(n_perguntas=30)
    assert resultado["n_perguntas"] == 30
    assert resultado["acertos"] >= 21  # >= 70% de 30
    assert resultado["recall_at_5"]["estimativa"] >= 0.70
    assert resultado["passou_gate"] is True


def test_gate_s2_amostra_cobre_todas_as_categorias_e_e_reprodutivel() -> None:
    import medir_recall_s2 as mr_s2

    linhas = [
        json.loads(x) for x in mr_s2.PERGUNTAS.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    com_norma = [p for p in linhas if not p["abstencao_esperada"]]
    a = mr_s2.amostra_estratificada(com_norma, 30)
    assert len(a) == 30 and len({p["id"] for p in a}) == 30
    assert {p["categoria"] for p in a} == {p["categoria"] for p in com_norma}
    assert a == mr_s2.amostra_estratificada(com_norma, 30)  # semente fixa
    resultado = mr_s2.medir_recall_s2(n_perguntas=30)
    assert resultado["ids_amostra"] == [p["id"] for p in a]
    assert sum(resultado["composicao_por_categoria"].values()) == 30


def test_gate_s2_motor_nao_da_falso_alarme_em_faturas_corretas() -> None:
    import medir_falso_alarme_s2 as fa

    r = fa.medir()
    assert r["benchmark_v0"]["n_corretas"] == 15 and r["golden_set"]["n_corretas"] == 103
    assert r["total_falsos_alarmes"] == 0 and r["passou_gate"] is True
    # o motor também acusa os erros injetados: não passa só por nunca acusar nada
    assert r["benchmark_v0"]["detectadas"] == r["benchmark_v0"]["n_com_erro_injetado"]
    assert r["golden_set"]["detectadas"] == r["golden_set"]["n_com_erro_injetado"]
    versionado = json.loads(fa.SAIDA_PADRAO.read_text(encoding="utf-8"))
    assert versionado["total_falsos_alarmes"] == r["total_falsos_alarmes"]


def test_calibracao_abstencao_sem_vazamento_e_reprodutivel() -> None:
    import calibrar_abstencao as ca

    from fa_rag.sintese import LIMIAR_PADRAO

    itens = [
        json.loads(x) for x in ca.PERGUNTAS.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    cal_a, tst_a = ca.dividir_estratificado(itens)
    cal_b, tst_b = ca.dividir_estratificado(itens)
    assert cal_a == cal_b and tst_a == tst_b
    assert len(cal_a) == 60 and len(tst_a) == 60
    ids_cal = {i["id"] for i in cal_a}
    ids_tst = {i["id"] for i in tst_a}
    assert ids_cal.isdisjoint(ids_tst)
    assert ids_cal | ids_tst == {i["id"] for i in itens}

    r = ca.rodar()
    versionado = json.loads(ca.SAIDA.read_text(encoding="utf-8"))
    assert r == versionado
    assert r["configuracao"]["limiar_escolhido"] == LIMIAR_PADRAO
    assert r["teste"]["abstencao"]["precisao"] == 1.0
    assert r["teste"]["ranking_com_norma"]["recall@5"]["estimativa"] >= 0.95
