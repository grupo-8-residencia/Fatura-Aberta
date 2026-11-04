#!/usr/bin/env python3
"""Confere o pacote de definição: seções presentes, `TODO` pendentes e tamanho estimado.

    uv run python scripts/pacote_definicao.py

O documento final deve ter de 3 a 5 páginas. Como o número real de páginas só aparece no PDF,
este script estima com ~500 palavras por página de texto corrido (tabelas ocupam mais espaço:
sempre confira o PDF).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "docs" / "produto" / "definicao"
SECOES = [
    "cenario.md",
    "problema.md",
    "stakeholders.md",
    "personas.md",
    "requisitos-funcionais.md",
    "requisitos-nao-funcionais.md",
    "riscos.md",
    "premissas.md",
    "metricas.md",
    "guiding-questions.md",
    "essential-question.md",
]
PALAVRAS_POR_PAGINA = 500
MIN_PAGINAS, MAX_PAGINAS = 3, 5


def contar_palavras(texto: str) -> int:
    limpo = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)
    return len(re.findall(r"\w+", limpo, flags=re.UNICODE))


def analisar(pasta: Path = PASTA) -> dict[str, dict[str, int | bool]]:
    resultado: dict[str, dict[str, int | bool]] = {}
    for nome in SECOES:
        arquivo = pasta / nome
        if not arquivo.exists():
            resultado[nome] = {"existe": False, "palavras": 0, "todos": 0}
            continue
        texto = arquivo.read_text(encoding="utf-8")
        resultado[nome] = {
            "existe": True,
            "palavras": contar_palavras(texto),
            "todos": len(re.findall(r"TODO", texto)),
        }
    return resultado


def main() -> int:
    dados = analisar()
    total = sum(int(item["palavras"]) for item in dados.values())
    print(f"{'Seção':<34}{'palavras':>9}{'TODO':>6}")
    for nome, item in dados.items():
        marca = "" if item["existe"] else "  (ausente)"
        print(f"{nome:<34}{item['palavras']:>9}{item['todos']:>6}{marca}")
    paginas = total / PALAVRAS_POR_PAGINA
    pendentes = sum(int(item["todos"]) for item in dados.values())
    print(f"\nTotal: {total} palavras (~{paginas:.1f} páginas; meta {MIN_PAGINAS} a {MAX_PAGINAS})")
    print(f"TODO pendentes: {pendentes}")
    ausentes = [n for n, i in dados.items() if not i["existe"]]
    return 1 if ausentes else 0


if __name__ == "__main__":
    sys.exit(main())
