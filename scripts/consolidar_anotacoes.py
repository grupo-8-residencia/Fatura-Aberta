#!/usr/bin/env python3
"""Consolida os CSV de anotação do golden set (issue #32).

Lê os CSV preenchidos em `dados/golden-set/anotacoes/` e mostra:
- progresso por pessoa (itens anotados / total);
- divergências (`concorda = não`), com a correção e o comentário de quem anotou;
- itens sem anotação e valores inválidos em `concorda`.

Nunca inventa valores e nunca altera o golden set. `--aplicar` apenas IMPRIME o que mudaria;
o recongelamento dos hashes é decisão do time.

Uso:
    python scripts/consolidar_anotacoes.py
    python scripts/consolidar_anotacoes.py --aplicar
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

from gerar_kit_anotacao import ARQ_REVISAO, PASTA_ANOTACOES

SIM = {"sim", "s"}
NAO = {"não", "nao", "n"}


@dataclass
class Resumo:
    arquivo: str
    total: int = 0
    anotados: int = 0
    pendentes: list[str] = field(default_factory=list)
    divergencias: list[dict[str, str]] = field(default_factory=list)
    invalidos: list[str] = field(default_factory=list)

    @property
    def pessoa(self) -> str:
        return self.arquivo.removesuffix(".csv")


def normalizar(valor: str) -> str | None:
    """'sim' / 'não' normalizados; vazio -> '' ; qualquer outra coisa -> None (inválido)."""
    v = valor.strip().lower()
    if not v:
        return ""
    if v in SIM:
        return "sim"
    if v in NAO:
        return "não"
    return None


def ler_csv(caminho: Path) -> Resumo:
    resumo = Resumo(arquivo=caminho.name)
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            resumo.total += 1
            item = (linha.get("id") or "").strip()
            concorda = normalizar(linha.get("concorda") or "")
            if concorda is None:
                resumo.invalidos.append(f"{item}: concorda={linha.get('concorda')!r}")
            elif concorda == "":
                resumo.pendentes.append(item)
            else:
                resumo.anotados += 1
                if concorda == "não":
                    resumo.divergencias.append(
                        {
                            "id": item,
                            "correcao": (linha.get("correcao") or "").strip(),
                            "comentario": (linha.get("comentario") or "").strip(),
                        }
                    )
    return resumo


def consolidar(pasta: Path = PASTA_ANOTACOES) -> list[Resumo]:
    return [ler_csv(c) for c in sorted(pasta.glob("*.csv"))]


def relatorio(resumos: list[Resumo], aplicar: bool = False) -> str:
    linhas = ["# Progresso da anotação", ""]
    for r in resumos:
        pct = 100 * r.anotados / r.total if r.total else 0.0
        linhas.append(f"- {r.pessoa}: {r.anotados}/{r.total} ({pct:.0f}%)")
    linhas += ["", "# Divergências (concorda = não)", ""]
    divergencias = [(r, d) for r in resumos for d in r.divergencias]
    if not divergencias:
        linhas.append("(nenhuma)")
    for r, d in divergencias:
        correcao = d["correcao"] or "(sem correção informada)"
        linhas.append(f"- {d['id']} [{r.pessoa}]: {correcao} | {d['comentario']}")
    linhas += ["", "# Itens sem anotação", ""]
    if not any(r.pendentes for r in resumos):
        linhas.append("(nenhum)")
    for r in resumos:
        if r.pendentes:
            linhas.append(f"- {r.pessoa} ({len(r.pendentes)}): {', '.join(r.pendentes)}")
    invalidos = [(r, i) for r in resumos for i in r.invalidos]
    if invalidos:
        linhas += ["", "# Valores inválidos em `concorda` (use sim ou não)", ""]
        linhas += [f"- {r.pessoa}: {i}" for r, i in invalidos]
    if aplicar:
        linhas += ["", "# --aplicar (simulação: nada é alterado)", ""]
        com_correcao = [(r, d) for r, d in divergencias if d["correcao"]]
        if not com_correcao:
            linhas.append("Nenhuma correção a aplicar.")
        for r, d in com_correcao:
            linhas.append(f"- {d['id']}: mudaria para «{d['correcao']}» (proposta de {r.pessoa})")
        linhas += [
            "",
            "Nada foi gravado. Depois de decidir as correções, o time edita os arquivos de "
            "origem e refaz o congelamento com `scripts/gerar_golden_set.py`.",
        ]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pasta", type=Path, default=PASTA_ANOTACOES, help="pasta com os CSV")
    ap.add_argument("--aplicar", action="store_true", help="só imprime o que mudaria")
    args = ap.parse_args(argv)
    if not args.pasta.is_dir():
        print(f"ERRO: pasta {args.pasta} não existe.", file=sys.stderr)
        return 1
    resumos = consolidar(args.pasta)
    if not resumos:
        print(f"ERRO: nenhum CSV em {args.pasta} (revisão: {ARQ_REVISAO}).", file=sys.stderr)
        return 1
    print(relatorio(resumos, aplicar=args.aplicar), end="")
    return 1 if any(r.invalidos for r in resumos) else 0


if __name__ == "__main__":
    raise SystemExit(main())
