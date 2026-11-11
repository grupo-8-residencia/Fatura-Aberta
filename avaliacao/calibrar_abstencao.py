#!/usr/bin/env python3
"""Calibração do limiar de abstenção sem vazamento entre calibração e teste (S3-07).

Divide as 120 perguntas do golden set em dois subconjuntos disjuntos e estratificados por
``(tipo, categoria)`` (60 calibração / 60 teste, semente fixa):

1. Varre os limiares candidatos **exclusivamente** no split de ``calibracao`` e escolhe
   o limiar de maior F1 (desempatando pela maior margem de segurança em ``calibracao``).
2. Congela o limiar escolhido e mede Precisão, Recall, F1, Acurácia (com IC 95% por
   bootstrap), ranking ``recall@5`` e comparação pareada contra o limiar anterior (0,30)
   no split cego ``teste``.

Uso: .venv/bin/python avaliacao/calibrar_abstencao.py
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from estatistica import B_PADRAO, SEMENTE_PADRAO, mcnemar
from metricas_recuperacao import (
    PERGUNTAS as PERGUNTAS,
)
from metricas_recuperacao import (
    metricas_abstencao,
    metricas_ranking,
    ranking_artigos,
)

from fa_rag import IndiceHibrido, responder
from fa_rag.sintese import LIMIAR_PADRAO

SAIDA = Path(__file__).resolve().parent / "resultados" / "s3-calibracao-abstencao.json"
LIMIARES_CANDIDATOS = (0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
LIMIAR_ANTERIOR = 0.30


def dividir_estratificado(
    itens: list[dict[str, Any]], *, semente: int = SEMENTE_PADRAO
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Divide ``itens`` em metades disjuntas estratificadas por ``(tipo, categoria)``."""
    rng = random.Random(semente)
    grupos: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in sorted(itens, key=lambda x: x["id"]):
        grupos[(str(item["tipo"]), str(item["categoria"]))].append(item)

    calibracao: list[dict[str, Any]] = []
    teste: list[dict[str, Any]] = []
    prox_para_cal = False
    for chave in sorted(grupos):
        grupo = grupos[chave]
        rng.shuffle(grupo)
        metade = len(grupo) // 2
        if len(grupo) % 2 == 1:
            corte = metade + (1 if prox_para_cal else 0)
            prox_para_cal = not prox_para_cal
        else:
            corte = metade
        calibracao.extend(grupo[:corte])
        teste.extend(grupo[corte:])

    calibracao.sort(key=lambda x: x["id"])
    teste.sort(key=lambda x: x["id"])
    return calibracao, teste


def _varrer_limiares(
    indice: IndiceHibrido, itens: list[dict[str, Any]], limiares: tuple[float, ...]
) -> tuple[dict[str, dict[str, float]], list[float], list[bool]]:
    """Executa busca uma vez por item e avalia todos os limiares candidatos sobre os scores."""
    top_scores: list[float] = []
    tops = []
    for item in itens:
        top = indice.buscar(
            item["pergunta"],
            data_referencia=date.fromisoformat(item["data_referencia"]),
            top_k=5,
            um_por_dispositivo=True,
        )
        tops.append(top)
        top_scores.append(top[0].score if top else 0.0)

    esperado = [bool(i["abstencao_esperada"]) for i in itens]
    varredura: dict[str, dict[str, float]] = {}
    for lim in limiares:
        prev = [responder(top, limiar=lim).abstencao for top in tops]
        varredura[f"limiar={lim}"] = metricas_abstencao(prev, esperado)
    return varredura, top_scores, esperado


def escolher_limiar(
    varredura: dict[str, dict[str, float]],
    top_scores: list[float],
    esperado: list[bool],
    candidatos: tuple[float, ...] = LIMIARES_CANDIDATOS,
) -> float:
    """Seleciona o limiar de maior F1 na calibração, desempatando por maior margem local."""
    melhor_f1 = max(varredura[f"limiar={c}"]["f1"] for c in candidatos)
    empatados = [c for c in candidatos if abs(varredura[f"limiar={c}"]["f1"] - melhor_f1) <= 1e-12]
    if len(empatados) == 1:
        return empatados[0]

    def _margem(lim: float) -> float:
        # Considera apenas os casos sem erro para medir a folga dos exemplos separados na borda.
        corretos_abaixo = [s for s, e in zip(top_scores, esperado, strict=True) if e and s < lim]
        corretos_acima = [
            s for s, e in zip(top_scores, esperado, strict=True) if not e and s >= lim
        ]
        if not corretos_abaixo or not corretos_acima:
            return 0.0
        return min(lim - max(corretos_abaixo), min(corretos_acima) - lim)

    return max(empatados, key=lambda c: (_margem(c), c))


def _ic_abstencao(
    previsto: list[bool],
    esperado: list[bool],
    *,
    b: int = B_PADRAO,
    semente: int = SEMENTE_PADRAO,
    nivel: float = 0.95,
) -> dict[str, dict[str, float]]:
    """IC 95% por bootstrap pareado para precisão, recall, F1 e acurácia da abstenção."""
    rng = random.Random(semente)
    n = len(previsto)
    amostras: dict[str, list[float]] = {k: [] for k in ("precisao", "recall", "f1", "acuracia")}
    for _ in range(b):
        idx = [rng.randrange(n) for _ in range(n)]
        m = metricas_abstencao([previsto[k] for k in idx], [esperado[k] for k in idx])
        for chave in amostras:
            amostras[chave].append(m[chave])

    base = metricas_abstencao(previsto, esperado)
    cauda = (1 - nivel) / 2
    saida: dict[str, dict[str, float]] = {}
    for chave, vals in amostras.items():
        ordenado = sorted(vals)
        inf = ordenado[max(0, math.floor(cauda * b))]
        sup = ordenado[min(b - 1, math.ceil((1 - cauda) * b) - 1)]
        saida[chave] = {"estimativa": base[chave], "ic95_inf": inf, "ic95_sup": sup}
    return saida


def _avaliar_split(
    indice: IndiceHibrido, itens: list[dict[str, Any]], *, limiar: float
) -> dict[str, Any]:
    esperado = [bool(i["abstencao_esperada"]) for i in itens]
    tops = [
        indice.buscar(
            i["pergunta"],
            data_referencia=date.fromisoformat(i["data_referencia"]),
            top_k=5,
            um_por_dispositivo=True,
        )
        for i in itens
    ]
    prev_novo = [responder(top, limiar=limiar).abstencao for top in tops]
    prev_antigo = [responder(top, limiar=LIMIAR_ANTERIOR).abstencao for top in tops]

    com_norma = [i for i in itens if not i["abstencao_esperada"]]
    rankings = [ranking_artigos(indice, i) for i in com_norma]
    canonicos = [set(i["citacao_canonica"]) for i in com_norma]

    acertos_novo = [p == e for p, e in zip(prev_novo, esperado, strict=True)]
    acertos_antigo = [p == e for p, e in zip(prev_antigo, esperado, strict=True)]
    mc = mcnemar(acertos_antigo, acertos_novo)

    abst = metricas_abstencao(prev_novo, esperado)
    vn = sum((not p) and (not e) for p, e in zip(prev_novo, esperado, strict=True))
    return {
        "n_itens": len(itens),
        "n_abstencao_esperada": sum(esperado),
        "n_com_norma": len(com_norma),
        "limiar": limiar,
        "abstencao": {**abst, "vn": vn},
        "abstencao_ic95": _ic_abstencao(prev_novo, esperado),
        "comparacao_limiar_030": {
            "metricas_030": metricas_abstencao(prev_antigo, esperado),
            "mcnemar": {
                "n01_030_erra_calibrado_acerta": mc.n01,
                "n10_030_acerta_calibrado_erra": mc.n10,
                "p_exato": mc.p_exato,
                "significativo_5pct": mc.significativo,
            },
        },
        "ranking_com_norma": metricas_ranking(rankings, canonicos),
    }


def rodar() -> dict[str, Any]:
    """Executa calibração sem vazamento (calibra em 60 itens e mede uma vez em 60 de teste)."""
    itens = [json.loads(x) for x in PERGUNTAS.read_text(encoding="utf-8").splitlines() if x]
    calibracao, teste = dividir_estratificado(itens, semente=SEMENTE_PADRAO)
    indice = IndiceHibrido.do_corpus()

    varredura_cal, scores_cal, esp_cal = _varrer_limiares(indice, calibracao, LIMIARES_CANDIDATOS)
    limiar_escolhido = escolher_limiar(varredura_cal, scores_cal, esp_cal, LIMIARES_CANDIDATOS)

    return {
        "configuracao": {
            "semente": SEMENTE_PADRAO,
            "bootstrap_B": B_PADRAO,
            "estratificacao": ["tipo", "categoria"],
            "n_calibracao": len(calibracao),
            "n_teste": len(teste),
            "candidatos": list(LIMIARES_CANDIDATOS),
            "limiar_escolhido": limiar_escolhido,
            "limiar_padrao_pacote": LIMIAR_PADRAO,
            "limiar_anterior": LIMIAR_ANTERIOR,
        },
        "splits": {
            "ids_calibracao": [i["id"] for i in calibracao],
            "ids_teste": [i["id"] for i in teste],
        },
        "varredura_calibracao": varredura_cal,
        "calibracao": _avaliar_split(indice, calibracao, limiar=limiar_escolhido),
        "teste": _avaliar_split(indice, teste, limiar=limiar_escolhido),
    }


def main() -> int:
    resultado = rodar()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    cfg = resultado["configuracao"]
    cal_m = resultado["calibracao"]["abstencao"]
    tst_m = resultado["teste"]["abstencao"]
    tst_ic = resultado["teste"]["abstencao_ic95"]
    tst_rk = resultado["teste"]["ranking_com_norma"]
    print(
        f"Limiar escolhido na calibração (n={cfg['n_calibracao']}): {cfg['limiar_escolhido']:.2f}"
    )
    print(
        f"Calibração: P={cal_m['precisao']:.3f} R={cal_m['recall']:.3f} "
        f"F1={cal_m['f1']:.3f} Acc={cal_m['acuracia']:.3f} "
        f"(VP={cal_m['vp']} FP={cal_m['fp']} FN={cal_m['fn']} VN={cal_m['vn']})"
    )
    print(
        f"Teste cego (n={cfg['n_teste']}): P={tst_m['precisao']:.3f} R={tst_m['recall']:.3f} "
        f"F1={tst_m['f1']:.3f} [{tst_ic['f1']['ic95_inf']:.3f}; {tst_ic['f1']['ic95_sup']:.3f}] "
        f"Acc={tst_m['acuracia']:.3f} "
        f"(VP={tst_m['vp']} FP={tst_m['fp']} FN={tst_m['fn']} VN={tst_m['vn']})"
    )
    print(
        f"Ranking teste (n={tst_rk['n']}): recall@5={tst_rk['recall@5']['estimativa']:.3f} "
        f"MRR={tst_rk['MRR']['estimativa']:.3f}"
    )
    print(f"Gravado em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
