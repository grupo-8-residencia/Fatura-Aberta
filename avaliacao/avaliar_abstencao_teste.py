#!/usr/bin/env python3
"""Reavalia o limiar de abstenção só no split de teste, por categoria (débito S2/S3).

Não recalibra nada e não altera os resultados históricos: lê os IDs de calibração e de teste que
`calibrar_abstencao.py` já gravou e mede os limiares 0,20, 0,25 e 0,30 em cada metade, mais o
conjunto fora da amostra, separando por tipo e categoria.

Limitação registrada no resultado: o 0,30 hoje em `LIMIAR_PADRAO` foi escolhido depois de ver o
split de teste e o fora da amostra (comentário em `fa_rag/sintese.py`). Por isso as métricas de
teste do 0,30 são descritivas, não uma estimativa independente. Uma estimativa independente exige
perguntas novas, anotadas por pessoas, que ainda não existem.

Uso: .venv/bin/python avaliacao/avaliar_abstencao_teste.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from cabecalho_reprodutivel import GOLDEN_SET, cabecalho
from metricas_recuperacao import metricas_abstencao

from fa_rag import IndiceHibrido, responder
from fa_rag.sintese import LIMIAR_PADRAO

RESULTADOS = Path(__file__).resolve().parent / "resultados"
ENTRADA_SPLITS = RESULTADOS / "s3-calibracao-abstencao.json"
ENTRADA_OOS = RESULTADOS / "s3-perguntas-novas-out-of-sample.json"
SAIDA = RESULTADOS / "s2s3-abstencao-teste.json"
LIMIARES = (0.20, 0.25, LIMIAR_PADRAO)


def _previsoes(
    indice: IndiceHibrido, itens: list[dict[str, Any]], limiares: tuple[float, ...]
) -> dict[float, list[bool]]:
    tops = [
        indice.buscar(
            i["pergunta"],
            data_referencia=date.fromisoformat(i["data_referencia"]),
            top_k=5,
            um_por_dispositivo=True,
        )
        for i in itens
    ]
    return {lim: [responder(top, limiar=lim).abstencao for top in tops] for lim in limiares}


def _metricas(
    itens: list[dict[str, Any]], previsoes: dict[float, list[bool]]
) -> dict[str, dict[str, Any]]:
    esperado = [bool(i["abstencao_esperada"]) for i in itens]
    return {f"limiar={lim}": metricas_abstencao(prev, esperado) for lim, prev in previsoes.items()}


def _por_grupo(
    itens: list[dict[str, Any]], previsoes: dict[float, list[bool]], campo: str
) -> dict[str, Any]:
    grupos: dict[str, list[int]] = defaultdict(list)
    for pos, item in enumerate(itens):
        grupos[str(item[campo])].append(pos)
    saida: dict[str, Any] = {}
    for nome, posicoes in sorted(grupos.items()):
        esperado = [bool(itens[p]["abstencao_esperada"]) for p in posicoes]
        saida[nome] = {
            "n": len(posicoes),
            "abstencoes_esperadas": sum(esperado),
            **{
                f"limiar={lim}": {
                    "acuracia": sum(prev[p] == e for p, e in zip(posicoes, esperado, strict=True))
                    / len(posicoes),
                    "abstencoes_previstas": sum(prev[p] for p in posicoes),
                }
                for lim, prev in previsoes.items()
            },
        }
    return saida


def rodar() -> dict[str, Any]:
    itens = {
        i["id"]: i
        for i in (json.loads(x) for x in GOLDEN_SET.read_text(encoding="utf-8").splitlines() if x)
    }
    splits = json.loads(ENTRADA_SPLITS.read_text(encoding="utf-8"))["splits"]
    cal = [itens[i] for i in splits["ids_calibracao"]]
    teste = [itens[i] for i in splits["ids_teste"]]
    assert not {i["id"] for i in cal} & {i["id"] for i in teste}, "splits devem ser disjuntos"

    indice = IndiceHibrido.do_corpus()
    resultados: dict[str, Any] = {}
    for nome, conjunto in (("calibracao", cal), ("teste", teste)):
        prev = _previsoes(indice, conjunto, LIMIARES)
        resultados[nome] = {
            "n": len(conjunto),
            "global": _metricas(conjunto, prev),
            "por_tipo": _por_grupo(conjunto, prev, "tipo"),
            "por_categoria": _por_grupo(conjunto, prev, "categoria"),
        }

    oos = json.loads(ENTRADA_OOS.read_text(encoding="utf-8"))
    resultados["fora_da_amostra_resumo_historico"] = {
        "n": oos["n_total"],
        "abstencao_limiar_025": oos["abstencao_limiar_025"],
        "abstencao_limiar_030": oos["abstencao_limiar_030"],
        "nota": "copiado do JSON histórico, sem recomputar; fora do golden set",
    }
    return {
        "cabecalho": cabecalho(indice, limiar=LIMIAR_PADRAO, top_k=5),
        "protocolo": {
            "origem_dos_splits": str(ENTRADA_SPLITS.name),
            "limitacao": (
                "O limiar 0,30 foi escolhido após observar o split de teste e o fora da amostra; "
                "as métricas de teste do 0,30 são descritivas, não independentes. A estimativa "
                "independente exige perguntas novas anotadas por pessoas."
            ),
            "tau_0_48": "não existe no código; 0,48x são scores em s2-recall-gate.json",
        },
        "resultados": resultados,
    }


def main() -> int:
    saida = rodar()
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    teste = saida["resultados"]["teste"]["global"]
    for chave, m in teste.items():
        print(f"teste {chave}: F1={m['f1']:.3f} acc={m['acuracia']:.3f}")
    print(f"Gravado em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
