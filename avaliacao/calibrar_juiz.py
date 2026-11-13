#!/usr/bin/env python3
"""Calibração do juiz LLM contra 40 itens com anotação humana (issue S3-02).

O script NÃO chama nenhum LLM. Ele lê um CSV com o veredito humano e o veredito do juiz para cada
item e calcula acurácia e Kappa de Cohen, com IC de 95% por bootstrap (B = 10.000).

Critério de aceite: kappa >= 0,75. Sem anotações preenchidas, o script não produz número nenhum.

Uso:
    python avaliacao/calibrar_juiz.py --gerar-modelo      # cria o CSV com os 40 itens sorteados
    python avaliacao/calibrar_juiz.py                     # calcula, se o CSV estiver preenchido
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_golden_set as gs  # noqa: E402
from estatistica import (  # noqa: E402
    B_PADRAO,
    SEMENTE_AMOSTRA,
    SEMENTE_PADRAO,
    acuracia,
    bootstrap_ic,
    kappa_cohen,
)

ARQUIVO_PADRAO = Path(__file__).resolve().parent / "anotacoes" / "juiz-40.csv"
N_ITENS = 40
LIMIAR_KAPPA = 0.75
COLUNAS = ["item_id", "anotador", "veredito_humano", "veredito_juiz"]


def selecionar_itens(n: int = N_ITENS) -> list[tuple[str, str]]:
    """Sorteia n itens entre os 180 anotados, em rodízio entre as seis pessoas (semente fixa)."""
    import random

    dist = gs.distribuir(gs.ler_perguntas(), gs.gerar_faturas())
    rng = random.Random(SEMENTE_AMOSTRA + 2)
    filas = {nome: rng.sample(ids, len(ids)) for nome, ids in dist.items()}
    escolhidos: list[tuple[str, str]] = []
    while len(escolhidos) < n:
        for nome, fila in filas.items():
            if fila and len(escolhidos) < n:
                escolhidos.append((fila.pop(), nome))
    return sorted(escolhidos)


def gerar_modelo(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUNAS)
        for item_id, anotador in selecionar_itens():
            w.writerow([item_id, anotador, "", ""])


def calcular(caminho: Path) -> dict[str, object]:
    with caminho.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    preenchidas = [r for r in linhas if r["veredito_humano"].strip() and r["veredito_juiz"].strip()]
    if len(preenchidas) < N_ITENS:
        raise ValueError(
            f"Anotação incompleta: {len(preenchidas)} de {N_ITENS} itens preenchidos "
            f"em {caminho.name}."
        )
    humano = [r["veredito_humano"].strip() for r in preenchidas]
    juiz = [r["veredito_juiz"].strip() for r in preenchidas]
    acertos = [float(h == j) for h, j in zip(humano, juiz, strict=True)]
    kappa = kappa_cohen(humano, juiz)
    ic = bootstrap_ic(acertos, b=B_PADRAO, semente=SEMENTE_PADRAO)
    return {
        "n": len(preenchidas),
        "acuracia": acuracia(humano, juiz),
        "acuracia_ic95": (ic.inferior, ic.superior),
        "kappa": kappa,
        "limiar_kappa": LIMIAR_KAPPA,
        "aprovado": kappa >= LIMIAR_KAPPA,
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
        f"n={r['n']} acuracia={r['acuracia']:.3f} IC95={r['acuracia_ic95']} "
        f"kappa={r['kappa']:.3f} (limiar {LIMIAR_KAPPA}) -> "
        f"{'APROVADO' if r['aprovado'] else 'REPROVADO'}"
    )
    return 0 if r["aprovado"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
