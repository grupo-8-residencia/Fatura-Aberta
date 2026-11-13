#!/usr/bin/env python3
"""Métricas ampliadas de recuperação e fundamentação (S3), sobre as 120 perguntas do golden set.

Ranking (perguntas com norma esperada, nível de artigo): recall@1/3/5/10, precisão@5, hit rate,
MRR, nDCG@5. Abstenção (todas as perguntas): precisão, recall e F1 de abster-se, com varredura do
limiar. Fundamentação: citações vigentes, resposta com citação canônica e literalidade do texto.
Também mede latência e faz uma ablação do peso α (vetorial × léxico).

Uso: .venv/bin/python avaliacao/metricas_recuperacao.py
"""

from __future__ import annotations

import json
import math
import statistics
import time
from datetime import date
from pathlib import Path
from typing import Any

from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic

from fa_rag import IndiceHibrido, responder
from fa_rag.sintese import LIMIAR_PADRAO

RAIZ = Path(__file__).resolve().parents[1]
PERGUNTAS = RAIZ / "dados" / "golden-set" / "perguntas.jsonl"
SAIDA = Path(__file__).resolve().parent / "resultados" / "s3-metricas-recuperacao.json"
KS = (1, 3, 5, 10)
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
LIMIARES = (0.20, 0.25, 0.30, 0.35, 0.40, 0.50)


def _artigo(doc_id: str) -> str:
    return doc_id.split("::")[0]


def _ic(valores: list[float]) -> dict[str, float]:
    ic = bootstrap_ic(valores, b=B_PADRAO, semente=SEMENTE_PADRAO)
    return {"estimativa": ic.estimativa, "ic95_inf": ic.inferior, "ic95_sup": ic.superior}


def ranking_artigos(
    indice: IndiceHibrido, item: dict[str, Any], *, alpha: float | None = None
) -> list[str]:
    data = date.fromisoformat(item["data_referencia"])
    top = indice.buscar(
        item["pergunta"], data_referencia=data, top_k=10, um_por_dispositivo=True, alpha=alpha
    )
    return [_artigo(r.documento.id) for r in top]


def metricas_ranking(rankings: list[list[str]], canonicos: list[set[str]]) -> dict[str, Any]:
    """Métricas de ranking por artigo; ``canonicos[i]`` é o conjunto relevante da pergunta i."""
    saida: dict[str, Any] = {"n": len(rankings)}
    for k in KS:
        saida[f"recall@{k}"] = _ic(
            [len(set(r[:k]) & c) / len(c) for r, c in zip(rankings, canonicos, strict=True)]
        )
        saida[f"hit@{k}"] = _ic(
            [float(bool(set(r[:k]) & c)) for r, c in zip(rankings, canonicos, strict=True)]
        )
    saida["precisao@5"] = _ic(
        [len(set(r[:5]) & c) / 5 for r, c in zip(rankings, canonicos, strict=True)]
    )
    rr, ndcg = [], []
    for r, c in zip(rankings, canonicos, strict=True):
        posicao = next((i for i, a in enumerate(r, 1) if a in c), None)
        rr.append(1 / posicao if posicao else 0.0)
        dcg = sum(1 / math.log2(i + 1) for i, a in enumerate(r[:5], 1) if a in c)
        ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(c), 5) + 1))
        ndcg.append(dcg / ideal if ideal else 0.0)
    saida["MRR"] = _ic(rr)
    saida["nDCG@5"] = _ic(ndcg)
    return saida


def metricas_abstencao(previsto: list[bool], esperado: list[bool]) -> dict[str, float]:
    """Positivo = abster-se. Precisão, recall e F1 da decisão de abstenção."""
    tp = sum(p and e for p, e in zip(previsto, esperado, strict=True))
    fp = sum(p and not e for p, e in zip(previsto, esperado, strict=True))
    fn = sum((not p) and e for p, e in zip(previsto, esperado, strict=True))
    precisao = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precisao * recall / (precisao + recall) if precisao + recall else 0.0
    return {
        "precisao": precisao,
        "recall": recall,
        "f1": f1,
        "acuracia": sum(p == e for p, e in zip(previsto, esperado, strict=True)) / len(previsto),
        "vp": tp,
        "fp": fp,
        "fn": fn,
    }


def rodar() -> dict[str, Any]:
    itens = [json.loads(x) for x in PERGUNTAS.read_text(encoding="utf-8").splitlines() if x]
    indice = IndiceHibrido.do_corpus()
    com_norma = [i for i in itens if not i["abstencao_esperada"]]
    canon = [set(i["citacao_canonica"]) for i in com_norma]

    tempos: list[float] = []
    rankings = []
    for i in com_norma:
        t0 = time.perf_counter()
        rankings.append(ranking_artigos(indice, i))
        tempos.append((time.perf_counter() - t0) * 1000)

    ablacao = {}
    for a in ALPHAS:
        rk = [ranking_artigos(indice, i, alpha=a) for i in com_norma]
        m = metricas_ranking(rk, canon)
        ablacao[f"alpha={a}"] = {k: m[k] for k in ("recall@5", "MRR", "nDCG@5")}

    esperado = [bool(i["abstencao_esperada"]) for i in itens]
    varredura = {}
    for lim in LIMIARES:
        prev = []
        for i in itens:
            data = date.fromisoformat(i["data_referencia"])
            top = indice.buscar(
                i["pergunta"], data_referencia=data, top_k=5, um_por_dispositivo=True
            )
            prev.append(responder(top, limiar=lim).abstencao)
        varredura[f"limiar={lim}"] = metricas_abstencao(prev, esperado)

    # fundamentação: toda frase da resposta vem de trecho recuperado; citações vigentes e canônicas
    literais, vigentes, com_canonico, respondidas = [], [], [], 0
    for i in itens:
        data = date.fromisoformat(i["data_referencia"])
        top = indice.buscar(i["pergunta"], data_referencia=data, top_k=5, um_por_dispositivo=True)
        r = responder(top)
        if r.abstencao:
            continue
        respondidas += 1
        fontes = [x for x in top if x.documento.id in r.ids_fontes]
        literais.append(
            float(all(" ".join(x.documento.texto.split())[:200] in r.texto for x in fontes))
        )
        vigentes.append(float(all(x.documento.vigente_em(data) for x in fontes)))
        if not i["abstencao_esperada"]:
            com_canonico.append(
                float(any(_artigo(x.documento.id) in set(i["citacao_canonica"]) for x in fontes))
            )

    return {
        "configuracao": {
            "n_perguntas": len(itens),
            "n_com_norma": len(com_norma),
            "alpha": indice.alpha,
            "limiar": LIMIAR_PADRAO,
            "embedder": "hash (determinístico)",
            "bootstrap_B": B_PADRAO,
            "semente": SEMENTE_PADRAO,
            "nivel": "artigo (um chunk por artigo)",
        },
        "ranking": metricas_ranking(rankings, canon),
        "ablacao_alpha": ablacao,
        "abstencao_por_limiar": varredura,
        "fundamentacao": {
            "respostas_nao_abstidas": respondidas,
            "citacoes_vigentes": _ic(vigentes),
            "resposta_cita_artigo_canonico": _ic(com_canonico),
            "texto_literal_dos_trechos": _ic(literais),
        },
        "latencia_ms": {
            "media": statistics.mean(tempos),
            "p95": sorted(tempos)[int(0.95 * len(tempos)) - 1],
            "max": max(tempos),
        },
    }


def main() -> int:
    r = rodar()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rk = r["ranking"]
    print(f"Ranking (n={rk['n']}):")
    for chave in ("recall@1", "recall@3", "recall@5", "recall@10", "precisao@5", "MRR", "nDCG@5"):
        v = rk[chave]
        print(f"  {chave:<11} {v['estimativa']:.3f} [{v['ic95_inf']:.3f}; {v['ic95_sup']:.3f}]")
    print("Ablação de alpha (recall@5 / MRR):")
    for k, v in r["ablacao_alpha"].items():
        print(f"  {k:<11} {v['recall@5']['estimativa']:.3f} / {v['MRR']['estimativa']:.3f}")
    print("Abstenção por limiar (precisão / recall / F1):")
    for k, v in r["abstencao_por_limiar"].items():
        print(f"  {k:<12} {v['precisao']:.2f} / {v['recall']:.2f} / {v['f1']:.2f}")
    print(
        f"Latência: média {r['latencia_ms']['media']:.1f} ms, p95 {r['latencia_ms']['p95']:.1f} ms"
    )
    print(f"Gravado em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
