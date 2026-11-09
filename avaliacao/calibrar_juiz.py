#!/usr/bin/env python3
"""Calibração do juiz LLM contra 40 itens anotados por 2 avaliadores humanos (issue #33).

O que o juiz e os humanos rotulam: a SAÍDA do B3 para o item (resposta a uma pergunta ou cartão de
uma fatura) como `suportada` (toda afirmação tem lastro nos dispositivos ou nos dados da fatura
fornecidos) ou `sem_suporte` (há ao menos uma afirmação sem lastro).

O juiz roda em `avaliacao/rodada_s3.py` e preenche `veredito_juiz`, `saida_do_sistema`,
`evidencia` e `proposicoes_juiz`. Este script só lê o CSV e calcula acurácia e Kappa de Cohen
(humano 1 × juiz, humano 2 × juiz e humano 1 × humano 2), com IC de 95% por bootstrap (B = 10.000).

Critério de aceite: κ ≥ 0,75 nos dois pares humano × juiz. Sem as três colunas preenchidas nos 40
itens, o script não produz número nenhum.

Uso:
    python avaliacao/calibrar_juiz.py --gerar-modelo      # cria o CSV com os 40 itens sorteados
    python avaliacao/calibrar_juiz.py                     # calcula, se o CSV estiver preenchido
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_golden_set as gs  # noqa: E402
from estatistica import (  # noqa: E402
    B_PADRAO,
    SEMENTE_PADRAO,
    acuracia,
    bootstrap_ic,
    kappa_cohen,
)

ARQUIVO_PADRAO = Path(__file__).resolve().parent / "anotacoes" / "juiz-40.csv"
N_ITENS = 40
LIMIAR_KAPPA = 0.75
ROTULOS = ("suportada", "sem_suporte")
COLUNAS = [
    "item_id",
    "tipo",
    "anotador_1",
    "anotador_2",
    "saida_do_sistema",
    "evidencia",
    "proposicoes_juiz",
    "veredito_humano_1",
    "veredito_humano_2",
    "veredito_juiz",
]


def selecionar_itens(n: int = N_ITENS) -> list[dict[str, str]]:
    """Sorteia n itens entre os 180 anotados, em rodízio entre as seis pessoas (semente fixa).

    O segundo avaliador é a pessoa seguinte na lista de anotadores, para que os dois julguem de
    forma independente.
    """
    dist = gs.distribuir(gs.ler_perguntas(), gs.gerar_faturas())
    nomes = list(dist)
    rng = random.Random(SEMENTE_PADRAO + 2)
    filas = {nome: rng.sample(ids, len(ids)) for nome, ids in dist.items()}
    escolhidos: list[tuple[str, str]] = []
    while len(escolhidos) < n:
        for nome, fila in filas.items():
            if fila and len(escolhidos) < n:
                escolhidos.append((fila.pop(), nome))
    linhas = []
    for item_id, a1 in sorted(escolhidos):
        a2 = nomes[(nomes.index(a1) + 1) % len(nomes)]
        tipo = "fatura" if item_id.startswith("GS-F") else "pergunta"
        linhas.append({"item_id": item_id, "tipo": tipo, "anotador_1": a1, "anotador_2": a2})
    return linhas


def ler_csv(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escrever_csv(caminho: Path, linhas: list[dict[str, str]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for linha in linhas:
            w.writerow({c: linha.get(c, "") for c in COLUNAS})


def gerar_modelo(caminho: Path) -> None:
    escrever_csv(caminho, selecionar_itens())


def calcular(caminho: Path) -> dict[str, Any]:
    linhas = ler_csv(caminho)
    colunas = ("veredito_humano_1", "veredito_humano_2", "veredito_juiz")
    completas = [r for r in linhas if all(r.get(c, "").strip() in ROTULOS for c in colunas)]
    if len(completas) < N_ITENS:
        raise ValueError(
            f"Anotação incompleta: {len(completas)} de {N_ITENS} itens com os três vereditos "
            f"({', '.join(ROTULOS)}) em {caminho.name}."
        )
    h1, h2, j = ([r[c].strip() for r in completas] for c in colunas)
    ic1 = bootstrap_ic(
        [float(a == b) for a, b in zip(h1, j, strict=True)], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    ic2 = bootstrap_ic(
        [float(a == b) for a, b in zip(h2, j, strict=True)], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    k1, k2, k12 = kappa_cohen(h1, j), kappa_cohen(h2, j), kappa_cohen(h1, h2)
    return {
        "n": len(completas),
        "kappa_humano1_juiz": k1,
        "kappa_humano2_juiz": k2,
        "kappa_humano1_humano2": k12,
        "acuracia_humano1_juiz": acuracia(h1, j),
        "acuracia_humano1_juiz_ic95": (ic1.inferior, ic1.superior),
        "acuracia_humano2_juiz": acuracia(h2, j),
        "acuracia_humano2_juiz_ic95": (ic2.inferior, ic2.superior),
        "limiar_kappa": LIMIAR_KAPPA,
        "referencia_humana_confiavel": k12 >= LIMIAR_KAPPA,
        "aprovado": min(k1, k2) >= LIMIAR_KAPPA,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--arquivo", type=Path, default=ARQUIVO_PADRAO)
    ap.add_argument("--gerar-modelo", action="store_true")
    args = ap.parse_args(argv)
    if args.gerar_modelo:
        gerar_modelo(args.arquivo)
        print(f"Modelo com {N_ITENS} itens gravado em {args.arquivo}")
        return 0
    try:
        r = calcular(args.arquivo)
    except (ValueError, FileNotFoundError) as erro:
        print(f"Sem resultado: {erro}", file=sys.stderr)
        return 2
    print(
        f"n={r['n']} κ(h1×juiz)={r['kappa_humano1_juiz']:.3f} "
        f"κ(h2×juiz)={r['kappa_humano2_juiz']:.3f} κ(h1×h2)={r['kappa_humano1_humano2']:.3f} "
        f"(limiar {LIMIAR_KAPPA}) -> {'APROVADO' if r['aprovado'] else 'REPROVADO'}"
    )
    return 0 if r["aprovado"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
