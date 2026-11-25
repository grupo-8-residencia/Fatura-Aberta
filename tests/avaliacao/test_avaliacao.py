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
    decisoes = sum(bool(r["veredito_humano_1"]) + bool(r["veredito_humano_2"]) for r in linhas)
    # vereditos humanos só entram pelo importador, que registra cada importação em importacoes.jsonl
    registro = Path(__file__).resolve().parents[2] / "dados/golden-set/anotacoes/importacoes.jsonl"
    importadas = 0
    if registro.exists():
        for linha in registro.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                importadas += int(json.loads(linha).get("novos", {}).get("juiz", 0))
    assert decisoes <= importadas, "veredito humano no CSV sem importação registrada"
    assert all(
        r[c] in ("", "suportada", "sem_suporte")
        for r in linhas
        for c in ("veredito_humano_1", "veredito_humano_2")
    )
    if any(r["veredito_juiz"] for r in linhas):
        assert all(r["saida_do_sistema"] and r["evidencia"] for r in linhas if r["veredito_juiz"])
    elif not decisoes:
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
    assert r["configuracao"]["limiar_escolhido"] in (0.20, 0.25)
    assert r["configuracao"]["limiar_padrao_pacote"] == LIMIAR_PADRAO == 0.30
    assert r["teste"]["abstencao"]["precisao"] == 1.0
    assert r["teste"]["ranking_com_norma"]["recall@5"]["estimativa"] >= 0.95


def test_recalibracao_divide_sem_vazar_e_rotula() -> None:
    import recalibrar_juiz as rj

    linhas = [
        {"item_id": f"GS-{i:02d}", "veredito_humano_1": "sem_suporte" if i < 4 else "suportada"}
        for i in range(12)
    ]
    dev, retida = rj.dividir(linhas)
    assert dev.isdisjoint(retida) and len(dev | retida) == 12
    assert sum(1 for i in dev if int(i[3:]) < 4) == 2  # estratificada pelo veredito humano
    assert rj.rotular([{"suportada": True}, {"suportada": False}]) == "sem_suporte"
    assert rj.rotular([{"suportada": True}]) == "suportada"
    assert rj.metricas(["suportada"] * 3, ["suportada"] * 3)["acuracia"] == 1.0
    # Sem veredito do juiz: erro na acurácia, mas fora do κ e das contagens de classe.
    m = rj.metricas(["suportada", "sem_suporte", "suportada"], ["suportada", "sem_suporte", None])
    assert m["acuracia"] == 2 / 3 and m["sem_veredito_do_juiz"] == 1
    assert m["n_vereditos_validos"] == 2 and m["kappa"] == 1.0 and m["sem_suporte_juiz"] == 1


def test_comparar_embedders_registra_teste_pareado_ram_e_segundo_modelo() -> None:
    import comparar_embedders as ce

    versionado = json.loads(ce.SAIDA.read_text(encoding="utf-8"))
    res = versionado["resultados"]
    assert {"E1_hash_lexical", "E2_semantico", "E3_semantico_ptbr"} <= set(res)
    for mod in ("E1_hash_lexical", "E2_semantico", "E3_semantico_ptbr"):
        ram = res[mod]["memoria_ram_mb"]
        assert ram["pico_alocacao_processo_mb"] > 0.0
        assert ram["vetores_indice_mb"] > 0.0
    assert res["E2_semantico"]["memoria_ram_mb"]["pesos_modelo_mb"] > 1000.0
    assert res["E2_semantico"]["memoria_ram_mb"]["servico_externo_mb"] > 1000.0

    pareado = versionado["comparacao_pareada"]
    assert {"E2_bge_m3_menos_E1_hash", "E3_semantico_ptbr_menos_E1_hash"} <= set(pareado)
    # O pareado do bge-m3 só vale se vier de vetores por pergunta medidos ao vivo; nunca
    # reconstruídos de agregados. Sem eles, fica marcado como pendente.
    e2_par = pareado["E2_bge_m3_menos_E1_hash"]
    if "status" in e2_par:
        assert e2_par["status"] == "pendente_execucao_ao_vivo"
        assert "vetores_por_pergunta" not in res["E2_semantico"]
    else:
        assert res["E2_semantico"]["vetores_por_pergunta"]["ids"]
    for chave_par, bloco in pareado.items():
        if "status" in bloco:
            continue
        assert bloco["n_perguntas_pareadas"] == 51
        for medida in ("diferenca_recall_at_5", "diferenca_mrr", "diferenca_ndcg_at_5"):
            assert bloco[medida]["significativo_5pct"] is False, (chave_par, medida)
        lat = bloco["diferenca_latencia_ms"]
        assert lat["ic95_inf"] <= lat["estimativa"] <= lat["ic95_sup"]
        assert bloco["mcnemar_hit_at_5"]["significativo_5pct"] is False
        assert bloco["mcnemar_cobertura_total_top5"]["significativo_5pct"] is False

    dec = versionado["decisao"]
    assert "EmbedderHash" in dec["embedder_padrao_mantido"]
    assert dec["pesos_versionados_ou_baixados_no_ci"] is False


def test_conjunto_independente_abstencao_e_disjunto_e_mede_limiar_030_congelado() -> None:
    import avaliar_abstencao_teste as aat

    linhas = aat.ler_conjunto_independente()
    assert len(linhas) == 36
    assert {r["tipo"] for r in linhas} == {"normativa", "lacuna", "vigencia", "fora_do_corpus"}
    assert len({r["categoria"] for r in linhas}) == 7
    assert all(r["anotador_1"] != r["anotador_2"] for r in linhas)
    assert all(r["veredito_humano_1"] in ("abster", "responder") for r in linhas)
    # Sem inventar veredito humano da segunda pessoa:
    assert all(r["veredito_humano_2"] == "" for r in linhas)

    # Teste sintético de dupla anotação completa para validar cálculo de Kappa:
    sinteticas = [dict(r) for r in linhas]
    for idx, r in enumerate(sinteticas):
        v1 = r["veredito_humano_1"]
        r["veredito_humano_2"] = v1 if idx >= 2 else ("responder" if v1 == "abster" else "abster")
    conc = aat.calcular_concordancia_dupla(sinteticas)
    assert conc["status"] == "concluida" and conc["n_pares_completos"] == 36
    assert conc["kappa_humano1_humano2"] > 0.80

    saida = aat.rodar()
    ind = saida["resultados"]["conjunto_independente_limiar_030_congelado"]
    assert ind["n"] == 36 and ind["limiar_congelado"] == 0.30
    assert ind["reescolha_de_limiar"] is False
    assert set(ind["por_tipo"]) == {"normativa", "lacuna", "vigencia", "fora_do_corpus"}
    assert len(ind["por_categoria"]) == 7
    glob = ind["global_limiar_030"]
    assert glob["ic95"]["f1"]["ic95_inf"] <= glob["f1"] <= glob["ic95"]["f1"]["ic95_sup"]
    versionado = json.loads(aat.SAIDA.read_text(encoding="utf-8"))
    assert versionado["resultados"] == saida["resultados"]
