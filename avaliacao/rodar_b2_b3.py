#!/usr/bin/env python3
"""Rodada B2 × B3 da S3 sobre as 120 perguntas do golden set (recuperação, sem LLM gerador).

- B2: RAG híbrido SEM filtro de vigência.
- B3: RAG híbrido COM filtro de vigência (e de subgrupo).
- B1 (motor determinístico) e a rodada com LLM estão em `rodada_s3.py`. Este script mede só a
  recuperação, sem LLM.

Um item é "acerto" quando:
- a pergunta tem norma esperada: algum artigo canônico está no top-5 e estava vigente na data;
- a abstenção é esperada (fora do corpus ou data anterior à vigência): a síntese se abstém.

Uso: .venv/bin/python avaliacao/rodar_b2_b3.py [--saida avaliacao/resultados/s3-b2-b3.json]
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from estatistica import (  # noqa: E402
    B_PADRAO,
    SEMENTE_PADRAO,
    Intervalo,
    bootstrap_ic,
    bootstrap_ic_diferenca,
    mcnemar,
)

from fa_rag import IndiceHibrido, responder  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PERGUNTAS = RAIZ / "dados" / "golden-set" / "perguntas.jsonl"
SAIDA_PADRAO = Path(__file__).resolve().parent / "resultados" / "s3-b2-b3.json"
TOP_K = 5


def _artigo(doc_id: str) -> str:
    return doc_id.split("::")[0]


def avaliar_item(
    indice: IndiceHibrido, item: dict[str, Any], *, filtrar_vigencia: bool
) -> dict[str, Any]:
    data = date.fromisoformat(item["data_referencia"])
    top = indice.buscar(
        item["pergunta"],
        data_referencia=data,
        top_k=TOP_K,
        filtrar_vigencia=filtrar_vigencia,
        um_por_dispositivo=True,
    )
    resposta = responder(top)
    citados = [r for r in top if r.documento.id in resposta.ids_fontes]
    violacoes = sum(1 for r in citados if not r.documento.vigente_em(data))
    canonicos = set(item["citacao_canonica"])
    achou = any(_artigo(r.documento.id) in canonicos and r.documento.vigente_em(data) for r in top)
    acerto = resposta.abstencao if item["abstencao_esperada"] else achou
    return {
        "acerto": acerto,
        "recuperou_canonico": achou,
        "abstencao": resposta.abstencao,
        "violacoes_vigencia": violacoes,
        "top5": [r.documento.id for r in top],
    }


def _ic(valores: list[bool]) -> dict[str, float]:
    ic: Intervalo = bootstrap_ic([float(v) for v in valores], b=B_PADRAO, semente=SEMENTE_PADRAO)
    return {"estimativa": ic.estimativa, "ic95_inf": ic.inferior, "ic95_sup": ic.superior}


def rodar() -> dict[str, Any]:
    itens = [
        json.loads(linha) for linha in PERGUNTAS.read_text(encoding="utf-8").splitlines() if linha
    ]
    indice = IndiceHibrido.do_corpus()
    por_baseline: dict[str, list[dict[str, Any]]] = {
        "B2": [avaliar_item(indice, i, filtrar_vigencia=False) for i in itens],
        "B3": [avaliar_item(indice, i, filtrar_vigencia=True) for i in itens],
    }
    com_norma = [k for k, i in enumerate(itens) if not i["abstencao_esperada"]]
    sem_norma = [k for k, i in enumerate(itens) if i["abstencao_esperada"]]
    vig = [k for k, i in enumerate(itens) if i["tipo"] == "vigencia"]

    def sub(b: str, idx: list[int], campo: str = "acerto") -> list[bool]:
        return [bool(por_baseline[b][k][campo]) for k in idx]

    todos = list(range(len(itens)))
    metricas: dict[str, Any] = {}
    for b in ("B2", "B3"):
        resultados = por_baseline[b]
        metricas[b] = {
            "acerto_por_item": _ic(sub(b, todos)),
            "recall_at_5_vigente": _ic(sub(b, com_norma, "recuperou_canonico")),
            "abstencao_correta": _ic(sub(b, sem_norma)),
            "abstencao_correta_vigencia": _ic(sub(b, vig)),
            "violacoes_de_vigencia": sum(r["violacoes_vigencia"] for r in resultados),
            "itens_com_violacao": sum(1 for r in resultados if r["violacoes_vigencia"] > 0),
        }
    a = sub("B2", todos)
    b3 = sub("B3", todos)
    mc = mcnemar(a, b3)
    dif = bootstrap_ic_diferenca(
        [float(x) for x in a], [float(x) for x in b3], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    return {
        "configuracao": {
            "embedder": "hash (determinístico, sem LLM gerador)",
            "alpha": indice.alpha,
            "top_k": TOP_K,
            "limiar_abstencao": 0.30,
            "bootstrap_B": B_PADRAO,
            "semente": SEMENTE_PADRAO,
            "n_itens": len(itens),
            "n_com_norma": len(com_norma),
            "n_abstencao_esperada": len(sem_norma),
            "n_vigencia": len(vig),
            "revisao_humana": "pendente",
        },
        "metricas": metricas,
        "comparacao_b3_menos_b2": {
            "diferenca_acerto": {
                "estimativa": dif.estimativa,
                "ic95_inf": dif.inferior,
                "ic95_sup": dif.superior,
            },
            "mcnemar": {
                "n01_b2_erra_b3_acerta": mc.n01,
                "n10_b2_acerta_b3_erra": mc.n10,
                "chi2_edwards": mc.chi2,
                "p_valor": mc.p_valor,
                "p_exato": mc.p_exato,
                "significativo_5pct": mc.significativo,
            },
        },
        "itens": [
            {
                "id": it["id"],
                "tipo": it["tipo"],
                "B2": por_baseline["B2"][k],
                "B3": por_baseline["B3"][k],
            }
            for k, it in enumerate(itens)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = ap.parse_args(argv)
    resultado = rodar()
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    m = resultado["metricas"]
    for b in ("B2", "B3"):
        x = m[b]
        print(
            f"{b}: acerto={x['acerto_por_item']['estimativa']:.3f} "
            f"recall@5={x['recall_at_5_vigente']['estimativa']:.3f} "
            f"abstencao={x['abstencao_correta']['estimativa']:.3f} "
            f"violacoes_vigencia={x['violacoes_de_vigencia']}"
        )
    mc = resultado["comparacao_b3_menos_b2"]["mcnemar"]
    n01, n10 = mc["n01_b2_erra_b3_acerta"], mc["n10_b2_acerta_b3_erra"]
    print(f"McNemar B3 vs B2: n01={n01} n10={n10} p={mc['p_valor']:.4f}")
    print(f"Gravado em {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
