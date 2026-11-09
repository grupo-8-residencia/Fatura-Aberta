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
