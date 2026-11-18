#!/usr/bin/env python3
"""Medição do recall@5 da norma vigente em 30 perguntas (Gate da Sprint S2 - F2).

Critério do Gate S2: recall@5 >= 0,70 em 30 perguntas com versão-gabarito.
Fórmula e protocolo: docs/avaliacao/metricas.md.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path
from typing import Any

from estatistica import B_PADRAO, SEMENTE_AMOSTRA, SEMENTE_PADRAO, Intervalo, bootstrap_ic

from fa_rag import IndiceHibrido

RAIZ = Path(__file__).resolve().parents[1]
PERGUNTAS = RAIZ / "dados" / "golden-set" / "perguntas.jsonl"
SAIDA_PADRAO = Path(__file__).resolve().parent / "resultados" / "s2-recall-gate.json"
META_GATE_RECALL = 0.70
N_PERGUNTAS_PADRAO = 30
TOP_K = 5


def _artigo(doc_id: str) -> str:
    return doc_id.split("::")[0]


def amostra_estratificada(
    perguntas: list[dict[str, Any]], n: int, semente: int = SEMENTE_AMOSTRA
) -> list[dict[str, Any]]:
    """Amostra de n perguntas, proporcional ao tamanho de cada categoria, com semente fixa.

    Cada categoria entra com ao menos 1 pergunta (a alocação usa o maior resto), para que o gate
    não meça só os primeiros temas do arquivo.
    """
    grupos: dict[str, list[dict[str, Any]]] = {}
    for p in perguntas:
        grupos.setdefault(str(p.get("categoria", "")), []).append(p)
    if n < len(grupos):
        raise ValueError(f"n = {n} é menor que o número de categorias ({len(grupos)}).")
    total = len(perguntas)
    cotas = {c: max(1, int(n * len(g) / total)) for c, g in grupos.items()}
    restos = sorted(grupos, key=lambda c: (n * len(grupos[c]) / total) % 1, reverse=True)
    i = 0
    while sum(cotas.values()) < n:
        cotas[restos[i % len(restos)]] += 1
        i += 1
    while sum(cotas.values()) > n:  # o mínimo de 1 pode ter estourado o total
        maior = max(cotas, key=lambda c: cotas[c])
        cotas[maior] -= 1
    rng = random.Random(semente)
    escolhidas: list[dict[str, Any]] = []
    for categoria in sorted(grupos):
        escolhidas += rng.sample(grupos[categoria], cotas[categoria])
    return sorted(escolhidas, key=lambda p: str(p["id"]))


def medir_recall_s2(
    n_perguntas: int = N_PERGUNTAS_PADRAO,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Executa a medição de recall@5 para o Gate da S2."""
    linhas = [
        json.loads(linha)
        for linha in PERGUNTAS.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    com_norma = [p for p in linhas if not p.get("abstencao_esperada", False)]
    if len(com_norma) < n_perguntas:
        raise ValueError(
            f"Conjunto possui apenas {len(com_norma)} perguntas com norma esperada "
            f"(necessárias: {n_perguntas})."
        )
    perguntas_gate = amostra_estratificada(com_norma, n_perguntas)

    indice = IndiceHibrido.do_corpus()
    detalhes: list[dict[str, Any]] = []
    acertos: list[float] = []

    for item in perguntas_gate:
        dt = date.fromisoformat(item["data_referencia"])
        top = indice.buscar(
            item["pergunta"],
            data_referencia=dt,
            top_k=top_k,
            filtrar_vigencia=True,
            um_por_dispositivo=True,
        )
        canonicos = set(item["citacao_canonica"])
        achou = any(
            _artigo(r.documento.id) in canonicos and r.documento.vigente_em(dt) for r in top
        )
        acertos.append(1.0 if achou else 0.0)
        detalhes.append(
            {
                "id": item["id"],
                "categoria": item.get("categoria", ""),
                "pergunta": item["pergunta"],
                "esperado": list(canonicos),
                "recuperou": achou,
                "top5": [
                    {
                        "id": r.documento.id,
                        "dispositivo": r.documento.citacao.dispositivo,
                        "score": round(r.score, 4),
                        "vigente": r.documento.vigente_em(dt),
                    }
                    for r in top
                ],
            }
        )

    ic: Intervalo = bootstrap_ic(acertos, b=B_PADRAO, semente=SEMENTE_PADRAO)
    passou_gate = ic.estimativa >= META_GATE_RECALL

    return {
        "sprint": "S2",
        "frente": "F2",
        "n_perguntas": len(perguntas_gate),
        "amostra": "estratificada por categoria, semente " + str(SEMENTE_AMOSTRA),
        "ids_amostra": [p["id"] for p in perguntas_gate],
        "composicao_por_categoria": {
            c: sum(1 for p in perguntas_gate if p.get("categoria") == c)
            for c in sorted({str(p.get("categoria", "")) for p in perguntas_gate})
        },
        "acertos": int(sum(acertos)),
        "meta_gate": META_GATE_RECALL,
        "passou_gate": passou_gate,
        "recall_at_5": {
            "estimativa": round(ic.estimativa, 4),
            "ic95_inferior": round(ic.inferior, 4),
            "ic95_superior": round(ic.superior, 4),
            "formatado": ic.formatar(3),
        },
        "detalhes": detalhes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mede o recall@5 da norma vigente em 30 perguntas (Gate S2)."
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="Caminho do arquivo JSON de resultado.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=N_PERGUNTAS_PADRAO,
        help="Número de perguntas a avaliar (padrão: 30).",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("FATURA ABERTA - AVALIAÇÃO OFICIAL DE GATE DA SPRINT S2 (F2)")
    print("=" * 65)
    resultado = medir_recall_s2(n_perguntas=args.n)

    rec = resultado["recall_at_5"]
    acertos = resultado["acertos"]
    total = resultado["n_perguntas"]
    print(f"Perguntas avaliadas: {total}")
    print(f"Acertos (norma vigente no top-5): {acertos}/{total} ({acertos / total:.1%})")
    print(f"Recall@5 [IC 95% Bootstrap]: {rec['formatado']}")
    print(f"Meta de Gate: >= {resultado['meta_gate']:.1%}")

    if resultado["passou_gate"]:
        print("\n>>> RESULTADO: GATE S2 APROVADO (GO) <<<")
    else:
        print("\n>>> RESULTADO: GATE S2 REPROVADO (NO-GO) <<<")

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultado detalhado salvo em: {args.saida}")

    return 0 if resultado["passou_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
