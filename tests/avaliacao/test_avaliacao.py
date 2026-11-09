"""Testes da estatística, da calibração do juiz e da rodada B2 × B3 (S3-02)."""

from __future__ import annotations

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


def test_modelo_do_juiz_tem_40_itens_dois_avaliadores_e_nenhum_veredito(tmp_path: Path) -> None:
    arq = tmp_path / "juiz.csv"
    cj.gerar_modelo(arq)
    linhas = cj.ler_csv(arq)
    assert len(linhas) == 40 and len({r["item_id"] for r in linhas}) == 40
    assert {r["anotador_1"] for r in linhas} == set(gs.ANOTADORES)
    assert all(r["anotador_1"] != r["anotador_2"] for r in linhas)
    assert {r["tipo"] for r in linhas} == {"fatura", "pergunta"}
    assert not any(
        r["veredito_humano_1"] or r["veredito_humano_2"] or r["veredito_juiz"] for r in linhas
    )
    with pytest.raises(ValueError, match="incompleta"):
        cj.calcular(arq)


def _csv_sintetico(arq: Path, *, erros_juiz: int, erros_h2: int = 0) -> None:
    """Anotação SINTÉTICA, só para testar o cálculo; não é resultado de pesquisa."""
    linhas = cj.selecionar_itens()
    for k, r in enumerate(linhas):
        base = "suportada" if k % 2 == 0 else "sem_suporte"
        outro = "sem_suporte" if base == "suportada" else "suportada"
        r["veredito_humano_1"] = base
        r["veredito_humano_2"] = outro if k < erros_h2 else base
        r["veredito_juiz"] = outro if k < erros_juiz else base
    cj.escrever_csv(arq, linhas)


def test_calibracao_calcula_kappas_e_aprova_com_concordancia_alta(tmp_path: Path) -> None:
    arq = tmp_path / "juiz.csv"
    _csv_sintetico(arq, erros_juiz=2)
    r = cj.calcular(arq)
    assert r["n"] == 40 and r["acuracia_humano1_juiz"] == pytest.approx(38 / 40)
    assert r["kappa_humano1_juiz"] == pytest.approx(0.9) and r["aprovado"] is True
    assert r["kappa_humano1_humano2"] == pytest.approx(1.0) and r["referencia_humana_confiavel"]


def test_calibracao_reprova_quando_um_dos_humanos_discorda_do_juiz(tmp_path: Path) -> None:
    arq = tmp_path / "juiz.csv"
    _csv_sintetico(arq, erros_juiz=2, erros_h2=12)
    r = cj.calcular(arq)
    assert r["kappa_humano2_juiz"] < cj.LIMIAR_KAPPA <= r["kappa_humano1_juiz"]
    assert r["aprovado"] is False and r["referencia_humana_confiavel"] is False


def test_calibracao_rejeita_rotulo_fora_do_vocabulario(tmp_path: Path) -> None:
    arq = tmp_path / "juiz.csv"
    _csv_sintetico(arq, erros_juiz=0)
    linhas = cj.ler_csv(arq)
    linhas[0]["veredito_juiz"] = "talvez"
    cj.escrever_csv(arq, linhas)
    with pytest.raises(ValueError, match="incompleta"):
        cj.calcular(arq)


def test_csv_versionado_nao_tem_veredito_humano_inventado() -> None:
    """Sem anotação humana real, as colunas humanas do CSV versionado ficam vazias."""
    linhas = cj.ler_csv(cj.ARQUIVO_PADRAO)
    assert len(linhas) == 40
    assert not any(r["veredito_humano_1"] or r["veredito_humano_2"] for r in linhas)
    if any(r["veredito_juiz"] for r in linhas):
        assert all(r["saida_do_sistema"] and r["evidencia"] for r in linhas if r["veredito_juiz"])
    else:
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
