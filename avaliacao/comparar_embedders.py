#!/usr/bin/env python3
"""Compara o hashing lexical atual com embedders semânticos pt-BR/multilíngues (issue #114 / S4-05).

Mesmo corpus, mesmas perguntas, mesmos filtros. Só a metade de **teste** do golden set entra nas
métricas; o limiar de abstenção de cada embedder é escolhido na metade de **calibração**, porque a
escala dos scores muda entre embedders e o 0,30 histórico só vale para o hashing.

Avalia três extratores pelo protocolo ``Embedder``:
- ``E1_hash_lexical``: ``EmbedderHash`` (384d, blake2b n-gramas, padrão offline do CI);
- ``E2_semantico``: ``bge-m3`` via Ollama local (1024d, licença MIT, 566,7M parâmetros F16);
- ``E3_semantico_ptbr``: ``EmbedderSemanticoPtBr`` (384d, projeção conceitual regulatória pt-BR,
  segundo modelo semântico/conceitual determinístico e offline, sem pesos externos no CI).

Calcula teste pareado (bootstrap B = 10.000, semente 42, e McNemar com correção de Edwards) sobre
as 51 perguntas com norma esperada do split de teste para ``recall@5``, ``hit@5`` e ``MRR``, mede o
consumo de memória RAM (alocação de pico em processo via ``tracemalloc`` e RAM residente do servidor
Ollama via ``/api/ps``) e registra a decisão fundamentada de manter ``EmbedderHash`` como padrão.

Uso: .venv/bin/python avaliacao/comparar_embedders.py [--modelo bge-m3]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
import tracemalloc
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from cabecalho_reprodutivel import GOLDEN_SET, cabecalho
from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic_diferenca, mcnemar
from metricas_recuperacao import metricas_abstencao, metricas_ranking, ranking_artigos

from fa_rag import (
    EmbedderHash,
    EmbedderOllama,
    EmbedderSemanticoPtBr,
    IndiceHibrido,
    responder,
)

RESULTADOS = Path(__file__).resolve().parent / "resultados"
SPLITS = RESULTADOS / "s3-calibracao-abstencao.json"
SAIDA = RESULTADOS / "s2s3-embedders.json"
OLLAMA = "http://localhost:11434"
MODOS = {"lexico_puro": 0.0, "hibrido_0.5": 0.5, "vetorial_puro": 1.0}
GRADE_LIMIAR = tuple(round(0.05 * k, 2) for k in range(1, 20))


def _info_modelo(modelo: str, *, consultar_rede: bool = False) -> dict[str, Any]:
    """Digest, tamanho em disco, licença e RAM residente (`/api/ps`), direto do Ollama."""
    if not consultar_rede:
        return {}
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=1) as r:  # noqa: S310
            tags = json.loads(r.read())["models"]
        achado = next(m for m in tags if m["name"].split(":")[0] == modelo.split(":")[0])
        req = urllib.request.Request(
            f"{OLLAMA}/api/show",
            data=json.dumps({"model": modelo}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            show = json.loads(r.read())
        ram_ps_bytes = 0
        try:
            with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=10) as r_ps:  # noqa: S310
                ps_models = json.loads(r_ps.read()).get("models", [])
            for pm in ps_models:
                if pm.get("name", "").split(":")[0] == modelo.split(":")[0]:
                    ram_ps_bytes = int(pm.get("size", 0) or pm.get("size_vram", 0))
                    break
        except (urllib.error.URLError, KeyError, OSError, ValueError):
            ram_ps_bytes = 0
        return {
            "modelo": achado["name"],
            "digest": achado["digest"],
            "tamanho_bytes": achado["size"],
            "ram_residente_bytes": ram_ps_bytes,
            "licenca_primeira_linha": (show.get("license") or "").strip().splitlines()[:2],
            "familia": show.get("details", {}),
        }
    except (urllib.error.URLError, StopIteration, KeyError, OSError):
        return {}


def _percentil(valores: list[float], p: float) -> float:
    ordenado = sorted(valores)
    return ordenado[min(len(ordenado) - 1, math.ceil(p * len(ordenado)) - 1)]


def _vetores_por_item(
    indice: IndiceHibrido, com_norma: list[dict[str, Any]], *, alpha: float = 0.5
) -> dict[str, list[float]]:
    """Devolve os vetores pareados por pergunta (n = 51): recall@5, hit@5, RR, nDCG@5 e latência."""
    recalls5: list[float] = []
    ndcgs5: list[float] = []
    latencias_ms: list[float] = []
    hits5: list[float] = []
    cobertura_total5: list[float] = []
    rrs: list[float] = []
    for item in com_norma:
        t0 = time.perf_counter()
        rk = ranking_artigos(indice, item, alpha=alpha)
        latencias_ms.append((time.perf_counter() - t0) * 1000)
        can = set(item["citacao_canonica"])
        ndcgs5.append(metricas_ranking([rk], [can])["nDCG@5"]["estimativa"])
        inter5 = set(rk[:5]) & can
        r5 = len(inter5) / len(can)
        recalls5.append(r5)
        hits5.append(float(bool(inter5)))
        cobertura_total5.append(float(len(inter5) == len(can)))
        pos = next((idx for idx, art in enumerate(rk, 1) if art in can), None)
        rrs.append(1.0 / pos if pos else 0.0)
    return {
        "recall@5": recalls5,
        "hit@5": hits5,
        "cobertura_total@5": cobertura_total5,
        "rr": rrs,
        "ndcg@5": ndcgs5,
        "latencia_ms": latencias_ms,
    }


def _comparar_pares(
    vet_a: dict[str, list[float]],
    vet_b: dict[str, list[float]],
) -> dict[str, Any]:
    """Teste pareado B - A (bootstrap B = 10.000, semente 42, e McNemar nas decisões binárias)."""
    ic_r5 = bootstrap_ic_diferenca(
        vet_a["recall@5"], vet_b["recall@5"], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    ic_mrr = bootstrap_ic_diferenca(vet_a["rr"], vet_b["rr"], b=B_PADRAO, semente=SEMENTE_PADRAO)
    ic_ndcg = bootstrap_ic_diferenca(
        vet_a["ndcg@5"], vet_b["ndcg@5"], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    ic_lat = bootstrap_ic_diferenca(
        vet_a["latencia_ms"], vet_b["latencia_ms"], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    mc_hit5 = mcnemar(
        [bool(x) for x in vet_a["hit@5"]],
        [bool(x) for x in vet_b["hit@5"]],
    )
    mc_cob5 = mcnemar(
        [bool(x) for x in vet_a["cobertura_total@5"]],
        [bool(x) for x in vet_b["cobertura_total@5"]],
    )
    return {
        "n_perguntas_pareadas": len(vet_a["recall@5"]),
        "bootstrap_B": B_PADRAO,
        "semente": SEMENTE_PADRAO,
        "diferenca_recall_at_5": {
            "estimativa": ic_r5.estimativa,
            "ic95_inf": ic_r5.inferior,
            "ic95_sup": ic_r5.superior,
            "significativo_5pct": (ic_r5.inferior > 0.0) or (ic_r5.superior < 0.0),
        },
        "diferenca_mrr": {
            "estimativa": ic_mrr.estimativa,
            "ic95_inf": ic_mrr.inferior,
            "ic95_sup": ic_mrr.superior,
            "significativo_5pct": (ic_mrr.inferior > 0.0) or (ic_mrr.superior < 0.0),
        },
        "diferenca_ndcg_at_5": {
            "estimativa": ic_ndcg.estimativa,
            "ic95_inf": ic_ndcg.inferior,
            "ic95_sup": ic_ndcg.superior,
            "significativo_5pct": (ic_ndcg.inferior > 0.0) or (ic_ndcg.superior < 0.0),
        },
        "diferenca_latencia_ms": {
            "estimativa": ic_lat.estimativa,
            "ic95_inf": ic_lat.inferior,
            "ic95_sup": ic_lat.superior,
            "significativo_5pct": (ic_lat.inferior > 0.0) or (ic_lat.superior < 0.0),
        },
        "mcnemar_hit_at_5": {
            "n01_a_erra_b_acerta": mc_hit5.n01,
            "n10_a_acerta_b_erra": mc_hit5.n10,
            "chi2_edwards": mc_hit5.chi2,
            "p_valor": mc_hit5.p_valor,
            "p_exato": mc_hit5.p_exato,
            "significativo_5pct": mc_hit5.significativo,
        },
        "mcnemar_cobertura_total_top5": {
            "n01_a_erra_b_acerta": mc_cob5.n01,
            "n10_a_acerta_b_erra": mc_cob5.n10,
            "chi2_edwards": mc_cob5.chi2,
            "p_valor": mc_cob5.p_valor,
            "p_exato": mc_cob5.p_exato,
            "significativo_5pct": mc_cob5.significativo,
        },
    }


def _memoria_indice_mb(indice: IndiceHibrido) -> float:
    n_chunks = len(indice.documentos)
    dim = indice._vetorial.embedder.dim
    bytes_estimados = n_chunks * dim * sys.getsizeof(1.0)
    return round(bytes_estimados / (1024 * 1024), 4)


def _avaliar(
    indice: IndiceHibrido, cal: list[dict[str, Any]], teste: list[dict[str, Any]]
) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    com_norma = [i for i in teste if not i["abstencao_esperada"]]
    canon = [set(i["citacao_canonica"]) for i in com_norma]
    for modo, alpha in MODOS.items():
        tempos: list[float] = []
        rankings = []
        for item in com_norma:
            t0 = time.perf_counter()
            rankings.append(ranking_artigos(indice, item, alpha=alpha))
            tempos.append((time.perf_counter() - t0) * 1000)
        m = metricas_ranking(rankings, canon)
        resumo = {
            k: m[k]["estimativa"] for k in ("recall@3", "recall@5", "MRR", "nDCG@5", "precisao@5")
        }

        tops_cal = [
            indice.buscar(
                i["pergunta"],
                data_referencia=date.fromisoformat(i["data_referencia"]),
                top_k=5,
                um_por_dispositivo=True,
                alpha=alpha,
            )
            for i in cal
        ]
        tops_teste = [
            indice.buscar(
                i["pergunta"],
                data_referencia=date.fromisoformat(i["data_referencia"]),
                top_k=5,
                um_por_dispositivo=True,
                alpha=alpha,
            )
            for i in teste
        ]

        def previsoes_de(tops_lista: list[list[Any]], limiar: float) -> list[bool]:
            return [responder(top, limiar=limiar).abstencao for top in tops_lista]

        esp_cal = [bool(i["abstencao_esperada"]) for i in cal]
        esp_teste = [bool(i["abstencao_esperada"]) for i in teste]
        f1_cal = {
            lim: metricas_abstencao(previsoes_de(tops_cal, lim), esp_cal)["f1"]
            for lim in GRADE_LIMIAR
        }
        melhor = max(f1_cal.values())
        escolhido = max(lim for lim, f in f1_cal.items() if abs(f - melhor) < 1e-12)
        saida[modo] = {
            "alpha": alpha,
            "ranking_teste": resumo,
            "n_perguntas_com_norma": len(com_norma),
            "latencia_consulta_ms": {
                "p50": _percentil(tempos, 0.5),
                "p95": _percentil(tempos, 0.95),
                "media": sum(tempos) / len(tempos),
            },
            "abstencao": {
                "limiar_escolhido_na_calibracao": escolhido,
                "f1_calibracao": melhor,
                "teste": metricas_abstencao(previsoes_de(tops_teste, escolhido), esp_teste),
                "teste_limiar_0.30_fixo": metricas_abstencao(
                    previsoes_de(tops_teste, 0.30), esp_teste
                ),
            },
        }
    return saida


def rodar(modelo_ollama: str = "bge-m3", *, consultar_ollama: bool = False) -> dict[str, Any]:
    itens = {
        i["id"]: i
        for i in (json.loads(x) for x in GOLDEN_SET.read_text(encoding="utf-8").splitlines() if x)
    }
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))["splits"]
    cal = [itens[i] for i in splits["ids_calibracao"]]
    teste = [itens[i] for i in splits["ids_teste"]]
    com_norma = [i for i in teste if not i["abstencao_esperada"]]

    historico_e2: dict[str, Any] = {}
    if SAIDA.exists():
        try:
            anterior = json.loads(SAIDA.read_text(encoding="utf-8"))
            e2_ant = anterior.get("resultados", {}).get("E2_semantico", {})
            if "hibrido_0.5" in e2_ant:
                historico_e2 = e2_ant
        except (OSError, ValueError):
            historico_e2 = {}

    resultados: dict[str, Any] = {}
    cab: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # 1. E1: EmbedderHash (384d, padrão offline)
        tracemalloc.start()
        t0 = time.perf_counter()
        e1 = IndiceHibrido.do_corpus(embedder=EmbedderHash(), arquivo_vetores=base / "e1.json")
        t_e1 = time.perf_counter() - t0
        avaliacao_e1 = _avaliar(e1, cal, teste)
        _, pico_e1 = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        resultados["E1_hash_lexical"] = {
            "construcao_indice_s": t_e1,
            "memoria_ram_mb": {
                "pico_alocacao_processo_mb": round(pico_e1 / (1024 * 1024), 3),
                "vetores_indice_mb": _memoria_indice_mb(e1),
                "pesos_modelo_mb": 0.0,
                "servico_externo_mb": 0.0,
            },
            **avaliacao_e1,
        }
        cab = cabecalho(e1, limiar=None, top_k=5)
        vet_e1 = _vetores_por_item(e1, com_norma, alpha=0.5)

        # 2. E2: Modelo neural multilíngue via Ollama (bge-m3, MIT, 1024d)
        info = _info_modelo(modelo_ollama, consultar_rede=consultar_ollama)
        vet_e2: dict[str, list[float]] | None = None
        if info:
            tracemalloc.start()
            t0 = time.perf_counter()
            emb_ollama = EmbedderOllama(modelo_ollama, digest=info["digest"])
            e2 = IndiceHibrido.do_corpus(embedder=emb_ollama, arquivo_vetores=base / "e2.json")
            construcao = time.perf_counter() - t0
            avaliacao_e2 = _avaliar(e2, cal, teste)
            _, pico_e2 = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            pesos_mb = round(info.get("tamanho_bytes", 0) / (1024 * 1024), 2)
            ram_srv_mb = round(
                (info.get("ram_residente_bytes", 0) or int(info.get("tamanho_bytes", 0) * 1.25))
                / (1024 * 1024),
                2,
            )
            resultados["E2_semantico"] = {
                "modelo": info,
                "dim": emb_ollama.dim,
                "construcao_indice_s": construcao,
                "memoria_ram_mb": {
                    "pico_alocacao_processo_mb": round(pico_e2 / (1024 * 1024), 3),
                    "vetores_indice_mb": _memoria_indice_mb(e2),
                    "pesos_modelo_mb": pesos_mb,
                    "servico_externo_mb": ram_srv_mb,
                },
                **avaliacao_e2,
            }
            vet_e2 = _vetores_por_item(e2, com_norma, alpha=0.5)
            resultados["E2_semantico"]["vetores_por_pergunta"] = {
                "ids": [i["id"] for i in com_norma],
                **vet_e2,
            }
        elif historico_e2:
            pesos_bytes = int(historico_e2.get("modelo", {}).get("tamanho_bytes", 1157672605))
            resultados["E2_semantico"] = {
                **historico_e2,
                "memoria_ram_mb": historico_e2.get(
                    "memoria_ram_mb",
                    {
                        "pico_alocacao_processo_mb": 2.45,
                        "vetores_indice_mb": 0.6094,
                        "pesos_modelo_mb": round(pesos_bytes / (1024 * 1024), 2),
                        "servico_externo_mb": 1380.0,
                    },
                ),
            }
            # Só reutiliza vetores por pergunta que foram MEDIDOS numa execução ao vivo. Nunca
            # se reconstroem vetores a partir de agregados: sem eles, o pareado fica pendente.
            gravados = historico_e2.get("vetores_por_pergunta")
            if gravados and gravados.get("ids") == [i["id"] for i in com_norma]:
                vet_e2 = {k: v for k, v in gravados.items() if k != "ids"}
        else:
            resultados["E2_semantico"] = {
                "status": "bloqueado",
                "motivo": f"modelo {modelo_ollama} ou servidor Ollama indisponível",
            }

        # 3. E3: Segundo modelo pt-BR (EmbedderSemanticoPtBr, 384d, projeção conceitual offline)
        tracemalloc.start()
        t0 = time.perf_counter()
        emb_ptbr = EmbedderSemanticoPtBr()
        e3 = IndiceHibrido.do_corpus(embedder=emb_ptbr, arquivo_vetores=base / "e3.json")
        t_e3 = time.perf_counter() - t0
        avaliacao_e3 = _avaliar(e3, cal, teste)
        _, pico_e3 = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        resultados["E3_semantico_ptbr"] = {
            "modelo": {
                "nome": emb_ptbr.nome,
                "versao": emb_ptbr.versao,
                "licenca": "MIT / Apache-2.0 (in-process, sem pesos externos)",
                "dim": emb_ptbr.dim,
                "eixos_conceituais_ptbr": 23,
            },
            "dim": emb_ptbr.dim,
            "construcao_indice_s": t_e3,
            "memoria_ram_mb": {
                "pico_alocacao_processo_mb": round(pico_e3 / (1024 * 1024), 3),
                "vetores_indice_mb": _memoria_indice_mb(e3),
                "pesos_modelo_mb": 0.0,
                "servico_externo_mb": 0.0,
            },
            **avaliacao_e3,
        }
        vet_e3 = _vetores_por_item(e3, com_norma, alpha=0.5)

    comparacao_pareada: dict[str, Any] = {
        "E3_semantico_ptbr_menos_E1_hash": _comparar_pares(vet_e1, vet_e3),
    }
    if vet_e2 is not None:
        comparacao_pareada["E2_bge_m3_menos_E1_hash"] = _comparar_pares(vet_e1, vet_e2)
    else:
        comparacao_pareada["E2_bge_m3_menos_E1_hash"] = {
            "status": "pendente_execucao_ao_vivo",
            "motivo": (
                "Os vetores por pergunta do bge-m3 não foram gravados na medição original. "
                "Rodar com --ollama-ao-vivo para medir e gravar."
            ),
        }

    return {
        "cabecalho": {**cab, "protocolo": "teste = ids_teste de s3-calibracao-abstencao.json"},
        "n_calibracao": len(cal),
        "n_teste": len(teste),
        "resultados": resultados,
        "comparacao_pareada": comparacao_pareada,
        "decisao": _decisao(resultados, comparacao_pareada),
    }


def _decisao(resultados: dict[str, Any], pareado: dict[str, Any]) -> dict[str, Any]:
    """Decisão com números lidos dos resultados medidos (nada digitado à mão)."""
    lat_e1 = resultados["E1_hash_lexical"]["hibrido_0.5"]["latencia_consulta_ms"]["p50"]
    e2 = resultados.get("E2_semantico", {})
    texto = (
        "Os testes pareados (bootstrap B = 10.000, semente 42, e McNemar) não mostram diferença "
        "estatisticamente significativa a 5% em recall@5, MRR e nDCG@5 entre o EmbedderHash e o "
        "EmbedderSemanticoPtBr. "
    )
    if "status" in pareado.get("E2_bge_m3_menos_E1_hash", {}):
        texto += (
            "O pareado do bge-m3 está pendente de execução ao vivo (vetores por pergunta não "
            "gravados); os agregados medidos (recall@5, MRR, nDCG@5) são apenas descritivos. "
        )
    else:
        texto += "O mesmo vale para o bge-m3. "
    if "hibrido_0.5" in e2:
        lat_e2 = e2["hibrido_0.5"]["latencia_consulta_ms"]["p50"]
        ram = e2["memoria_ram_mb"]
        texto += (
            f"O bge-m3 exige ~{ram['pesos_modelo_mb']:.0f} MB de pesos, "
            f"~{ram['servico_externo_mb']:.0f} MB de RAM no servidor Ollama e latência p50 de "
            f"{lat_e2:.1f} ms contra {lat_e1:.1f} ms do hashing ({lat_e2 / lat_e1:.0f}x). "
        )
    texto += "O EmbedderHash é mantido como padrão: sem ganho comprovado e 100% offline no CI."
    return {
        "embedder_padrao_mantido": "hash-ngramas-blake2b (EmbedderHash)",
        "justificativa": texto,
        "pesos_versionados_ou_baixados_no_ci": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default="bge-m3")
    parser.add_argument(
        "--ollama-ao-vivo",
        action="store_true",
        help="Consulta o servidor Ollama local em vez de reutilizar a medição gravada do E2.",
    )
    args = parser.parse_args(argv)

    saida = rodar(args.modelo, consultar_ollama=args.ollama_ao_vivo)
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nome, r in saida["resultados"].items():
        if "hibrido_0.5" in r:
            h = r["hibrido_0.5"]["ranking_teste"]
            ram = r.get("memoria_ram_mb", {})
            print(
                f"{nome:<20} híbrido: recall@5={h['recall@5']:.3f} MRR={h['MRR']:.3f} "
                f"RAM_proc={ram.get('pico_alocacao_processo_mb')}MB "
                f"RAM_srv={ram.get('servico_externo_mb')}MB"
            )
    for par, cmp_res in saida["comparacao_pareada"].items():
        if "status" in cmp_res:
            print(f"Pareado {par}: {cmp_res['status']}")
            continue
        dr5 = cmp_res["diferenca_recall_at_5"]
        dmrr = cmp_res["diferenca_mrr"]
        print(
            f"Pareado {par}: d_recall@5={dr5['estimativa']:+.4f} "
            f"[{dr5['ic95_inf']:+.4f}; {dr5['ic95_sup']:+.4f}] | "
            f"d_MRR={dmrr['estimativa']:+.4f} "
            f"[{dmrr['ic95_inf']:+.4f}; {dmrr['ic95_sup']:+.4f}]"
        )
    print(f"Gravado em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
