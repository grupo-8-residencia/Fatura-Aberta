#!/usr/bin/env python3
"""Compara os 4 testes da Sprint 3 e aplica a regra de escolha (entregável LLM × RAG).

Testes (rótulo no JSON; "T" é o número no relatório):
- T1 `LLM`: LLM sem RAG (cita de memória).
- T2 `RAG`: RAG sem LLM (resposta extrativa com abstenção). Só perguntas.
- T3 `B2`: LLM + RAG sem filtro de vigência.
- T4 `B3`: LLM + RAG com filtro de vigência (+ saídas do motor nas faturas).
Referência determinística nas faturas: `B1` (motor, sem LLM).

Entrada: `avaliacao/resultados/s3-rodada.json` e `s3-rodada-extra.json`. Saída:
`avaliacao/resultados/s3-comparacao.json`, com as tabelas e a recomendação.

Regra de escolha (declarada antes de ver os números):
1. Só concorre quem tem 0 respostas inválidas e 0 violações do RF-15.
2. Maior acerto; empate (diferença menor que 1 ponto percentual) vai para a menor latência média.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic, mcnemar  # noqa: E402

RESULTADOS = Path(__file__).resolve().parent / "resultados"
ROTULOS = {
    "LLM": "T1 LLM sem RAG",
    "RAG": "T2 RAG sem LLM",
    "B2": "T3 LLM + RAG",
    "B3": "T4 LLM + RAG + vigência",
}
ORDEM_PERGUNTAS = ("LLM", "RAG", "B2", "B3")
ORDEM_FATURAS = ("B1", "LLM", "B2", "B3")


def _ic(valores: list[bool]) -> dict[str, float]:
    ic = bootstrap_ic([float(v) for v in valores], b=B_PADRAO, semente=SEMENTE_PADRAO)
    return {"estimativa": ic.estimativa, "ic95_inf": ic.inferior, "ic95_sup": ic.superior}


def _media_s(itens: list[dict[str, Any]]) -> float:
    return round(sum(float(i.get("duracao_s", 0.0)) for i in itens) / max(len(itens), 1), 3)


def _mc(a: list[bool], b: list[bool]) -> dict[str, Any]:
    r = mcnemar(a, b)
    return {
        "n01_primeiro_erra_segundo_acerta": r.n01,
        "n10_primeiro_acerta_segundo_erra": r.n10,
        "p_valor": r.p_valor,
        "p_exato": r.p_exato,
        "significativo_5pct": r.significativo,
    }


def tabela_perguntas(res: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for b, itens in res.items():
        tipos = sorted({i["tipo"] for i in itens})
        saida[b] = {
            "n": len(itens),
            "acerto": _ic([bool(i["acerto"]) for i in itens]),
            "acerto_por_tipo": {
                t: sum(bool(i["acerto"]) for i in itens if i["tipo"] == t)
                / max(sum(1 for i in itens if i["tipo"] == t), 1)
                for t in tipos
            },
            "invalidas": sum(1 for i in itens if not i.get("valido", True)),
            "rf15": sum(1 for i in itens if i.get("linguagem")),
            "citacoes_inventadas": sum(1 for i in itens if i.get("citacoes_inventadas")),
            "cita_algo_errado": sum(1 for i in itens if i.get("cita_algo_errado")),
            "fora_de_vigencia": sum(1 for i in itens if i.get("citacoes_fora_de_vigencia")),
            "latencia_media_s": _media_s(itens),
        }
    return saida


def tabela_faturas(res: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for b, itens in res.items():
        com = [i for i in itens if i.get("anomalia")]
        sem = [i for i in itens if not i.get("anomalia")]
        saida[b] = {
            "n": len(itens),
            "acerto": _ic([bool(i["acerto"]) for i in itens]),
            "deteccao": _ic([i["veredito"] == "diverge_A" for i in com]) if com else None,
            "falso_alarme": _ic([i["veredito"] == "diverge_A" for i in sem]) if sem else None,
            "abstencoes": sum(1 for i in itens if i["veredito"] == "abstem"),
            "invalidas": sum(1 for i in itens if i["veredito"] == "invalido"),
            "rf15": sum(1 for i in itens if i.get("linguagem")),
            "latencia_media_s": _media_s(itens),
        }
    return saida


def pares(res: dict[str, list[dict[str, Any]]], quais: list[tuple[str, str]]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for a, b in quais:
        if a in res and b in res and len(res[a]) == len(res[b]):
            saida[f"{b}_vs_{a}"] = _mc(
                [bool(i["acerto"]) for i in res[a]], [bool(i["acerto"]) for i in res[b]]
            )
    return saida


def escolher(tabela: dict[str, Any], candidatos: tuple[str, ...]) -> dict[str, Any]:
    """Aplica a regra de escolha: elegíveis têm 0 inválidas e 0 violações do RF-15."""
    elegiveis = [
        b
        for b in candidatos
        if b in tabela and tabela[b]["invalidas"] == 0 and tabela[b]["rf15"] == 0
    ]
    if not elegiveis:
        return {"escolhido": None, "motivo": "nenhum baseline elegível (inválidas ou RF-15)"}
    melhor = max(tabela[b]["acerto"]["estimativa"] for b in elegiveis)
    empatados = [b for b in elegiveis if melhor - tabela[b]["acerto"]["estimativa"] < 0.01]
    escolhido = min(empatados, key=lambda b: tabela[b]["latencia_media_s"])
    return {
        "escolhido": escolhido,
        "elegiveis": elegiveis,
        "empatados": empatados,
        "acerto": tabela[escolhido]["acerto"]["estimativa"],
        "latencia_media_s": tabela[escolhido]["latencia_media_s"],
    }


def comparar(principal: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    pergs: dict[str, list[dict[str, Any]]] = {
        **principal.get("perguntas", {}),
        **extra.get("perguntas", {}),
    }
    fats: dict[str, list[dict[str, Any]]] = {
        **principal.get("faturas", {}),
        **extra.get("faturas", {}),
    }
    tp, tf = tabela_perguntas(pergs), tabela_faturas(fats)
    return {
        "cabecalho": principal.get("cabecalho"),
        "perguntas": tp,
        "faturas": tf,
        "mcnemar_perguntas": pares(
            pergs, [("LLM", "RAG"), ("LLM", "B2"), ("B2", "B3"), ("RAG", "B3"), ("RAG", "B2")]
        ),
        "mcnemar_faturas": pares(fats, [("LLM", "B2"), ("B2", "B3"), ("LLM", "B3"), ("B1", "B3")]),
        "escolha_perguntas": escolher(tp, ORDEM_PERGUNTAS),
        "escolha_faturas": escolher(tf, ORDEM_FATURAS),
        "juiz": principal.get("juiz_calibracao"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--principal", type=Path, default=RESULTADOS / "s3-rodada.json")
    ap.add_argument("--extra", type=Path, default=RESULTADOS / "s3-rodada-extra.json")
    ap.add_argument("--saida", type=Path, default=RESULTADOS / "s3-comparacao.json")
    args = ap.parse_args(argv)
    principal = json.loads(args.principal.read_text(encoding="utf-8"))
    extra = json.loads(args.extra.read_text(encoding="utf-8")) if args.extra.exists() else {}
    r = comparar(principal, extra)
    args.saida.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for nome, ordem in (("perguntas", ORDEM_PERGUNTAS), ("faturas", ORDEM_FATURAS)):
        print(f"\n{nome}:")
        for b in ordem:
            if b in r[nome]:
                t = r[nome][b]
                a = t["acerto"]
                print(
                    f"  {ROTULOS.get(b, 'B1 motor'):<26} acerto {a['estimativa']:.3f} "
                    f"[{a['ic95_inf']:.3f}; {a['ic95_sup']:.3f}]  rf15={t['rf15']} "
                    f"inválidas={t['invalidas']}  {t['latencia_media_s']}s"
                )
        print("  escolha:", r[f"escolha_{nome}"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
