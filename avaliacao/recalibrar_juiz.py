#!/usr/bin/env python3
"""Recalibração do juiz LLM contra os 40 itens humanos já anotados (issue #33, plano da S4).

Reaproveita `saida_do_sistema` e `evidencia` do `juiz-40.csv` (as saídas do B3 já gravadas), sem
refazer o gerador. Roda uma variante do prompt do juiz e compara com o veredito humano.

Para não calibrar e testar no mesmo conjunto, os 40 itens são divididos de forma determinística e
estratificada pelo veredito humano: metade **desenvolvimento** (onde se pode olhar os erros do juiz
e ajustar o prompt) e metade **retida** (só medida, nunca inspecionada). A decisão vale pela retida.

Uso:
    FA_LLM_PROVEDOR=ollama python avaliacao/recalibrar_juiz.py --variante v1 --saida v1.json
    FA_LLM_PROVEDOR=ollama python avaliacao/recalibrar_juiz.py --variante v2 --saida v2.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rodada_s3 as rs  # noqa: E402
from calibrar_juiz import LIMIAR_KAPPA, ler_csv  # noqa: E402
from estatistica import SEMENTE_PADRAO, acuracia, bootstrap_ic, kappa_cohen  # noqa: E402

from fa_agentes import criar_cliente  # noqa: E402

TIMEOUT_JUIZ_S = 120.0
CSV = Path(__file__).resolve().parent / "anotacoes" / "juiz-40.csv"

SISTEMA_V2 = (
    "Você é um auditor de lastro. Receba a EVIDÊNCIA (dados da fatura e/ou dispositivos "
    "normativos) "
    "e a SAÍDA de um sistema. Decomponha em proposições atômicas SOMENTE o que a SAÍDA afirma: "
    "nunca transforme o texto da evidência em proposição. Marque cada proposição como suportada ou "
    "não. Regras: (1) é suportada se está nos dispositivos, está nos dados da fatura ou decorre "
    "deles por conta aritmética simples (soma, produto, diferença) que você refaz com os números "
    "da evidência: se o sistema aponta uma divergência (total, consumo, ICMS) e a conta com os "
    "números da evidência a confirma, a proposição é suportada; (2) abstenção, 'não há dados' ou "
    "'não é possível confirmar' é suportada quando a evidência de fato não traz a informação; "
    "(3) só marque sem suporte uma afirmação que a evidência contradiz ou que traz fato, número, "
    "prazo ou dispositivo que não aparece nela; (4) não penalize estilo, resumo, ordem ou ausência "
    "de detalhes. Na dúvida entre as duas, marque suportada."
)
VARIANTES = {"v1": rs.SISTEMA_JUIZ, "v2": SISTEMA_V2}


def dividir(linhas: list[dict[str, str]]) -> tuple[set[str], set[str]]:
    """Estratifica pelo veredito humano e alterna ordenado por id: desenvolvimento e retida."""
    dev: set[str] = set()
    retida: set[str] = set()
    for rotulo in ("suportada", "sem_suporte"):
        ids = sorted(x["item_id"] for x in linhas if x["veredito_humano_1"] == rotulo)
        for n, i in enumerate(ids):
            (dev if n % 2 == 0 else retida).add(i)
    return dev, retida


def rotular(props: list[dict[str, Any]]) -> str:
    return "sem_suporte" if any(not p.get("suportada", False) for p in props) else "suportada"


def metricas(humano: list[str], juiz: list[str]) -> dict[str, Any]:
    n = len(humano)
    if n == 0:
        return {"n": 0}
    iguais = [int(h == j) for h, j in zip(humano, juiz, strict=True)]
    ic = bootstrap_ic(iguais, semente=SEMENTE_PADRAO)
    return {
        "n": n,
        "kappa": kappa_cohen(humano, juiz),
        "acuracia": acuracia(humano, juiz),
        "acuracia_ic95": [ic.inferior, ic.superior],
        "sem_suporte_humano": humano.count("sem_suporte"),
        "sem_suporte_juiz": juiz.count("sem_suporte"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--variante", choices=sorted(VARIANTES), required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument(
        "--so", choices=["todos", "dev"], default="todos", help="'dev' não toca a retida"
    )
    args = ap.parse_args(argv)

    linhas = ler_csv(CSV)
    dev, retida = dividir(linhas)
    alvo = [x for x in linhas if args.so == "todos" or x["item_id"] in dev]
    juiz = criar_cliente("juiz", cache_dir=rs.CACHE)
    if hasattr(juiz, "timeout_s"):
        # o GS-Q114 trava o juiz: 2 min por tentativa, não 10
        juiz = dataclasses.replace(cast(Any, juiz), timeout_s=TIMEOUT_JUIZ_S)
    itens: dict[str, dict[str, Any]] = {}
    for n, linha in enumerate(alvo, 1):
        r = rs._chamar(
            juiz,
            VARIANTES[args.variante],
            f"EVIDÊNCIA\n{linha['evidencia']}\n\nSAÍDA DO SISTEMA\n{linha['saida_do_sistema']}\n",
            rs.ESQUEMA_JUIZ,
        )
        props = [p for p in (r.get("dados") or {}).get("proposicoes", []) if isinstance(p, dict)]
        itens[linha["item_id"]] = {
            "valido": bool(r["valido"]),
            "veredito": rotular(props) if r["valido"] else None,
            "proposicoes": props,
        }
        print(
            f"{n}/{len(alvo)} {linha['item_id']} -> {itens[linha['item_id']]['veredito']}",
            flush=True,
        )

    args.saida.write_text(json.dumps({"itens": itens}, ensure_ascii=False, indent=1), "utf-8")

    def pares(ids: set[str]) -> tuple[list[str], list[str]]:
        # Item sem veredito válido do juiz conta como erro (oposto do humano), nunca é excluído.
        h = [
            x["veredito_humano_1"] for x in linhas if x["item_id"] in ids and x["item_id"] in itens
        ]
        j = [
            itens[x["item_id"]]["veredito"]
            or ("suportada" if x["veredito_humano_1"] == "sem_suporte" else "sem_suporte")
            for x in linhas
            if x["item_id"] in ids and x["item_id"] in itens
        ]
        return h, j

    resultado = {
        "variante": args.variante,
        "prompt_sha256": __import__("hashlib")
        .sha256(VARIANTES[args.variante].encode())
        .hexdigest(),
        "limiar_kappa": LIMIAR_KAPPA,
        "humanos_concordam": all(x["veredito_humano_1"] == x["veredito_humano_2"] for x in linhas),
        "invalidos": sorted(i for i, v in itens.items() if not v["valido"]),
        "todos": metricas(*pares({x["item_id"] for x in linhas})),
        "desenvolvimento": metricas(*pares(dev)),
        "retida": metricas(*pares(retida)) if args.so == "todos" else "não medida",
        "itens": itens,
    }
    args.saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(json.dumps({k: v for k, v in resultado.items() if k != "itens"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
