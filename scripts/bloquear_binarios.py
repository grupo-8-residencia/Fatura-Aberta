#!/usr/bin/env python3
"""Hook de pre-commit: bloqueia PDF e imagens fora das pastas permitidas.

Fatura real tem nome, endereço e número da instalação e nunca pode entrar no Git.
Arquivos `*.pdf`, `*.jpg`, `*.jpeg`, `*.png` e `*.heic` só podem existir em:
    - docs/assets/                 (capturas de tela e figuras da documentação)
    - dados/benchmark/sinteticas/  (faturas sintéticas geradas pelo projeto)
"""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

EXTENSOES_BLOQUEADAS = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
PASTAS_PERMITIDAS = ("docs/assets/", "dados/benchmark/sinteticas/")


def bloqueado(caminho: str) -> bool:
    normalizado = caminho.replace("\\", "/").removeprefix("./")
    if PurePosixPath(normalizado).suffix.lower() not in EXTENSOES_BLOQUEADAS:
        return False
    return not normalizado.startswith(PASTAS_PERMITIDAS)


def main(argv: list[str]) -> int:
    proibidos = [arquivo for arquivo in argv if bloqueado(arquivo)]
    if not proibidos:
        return 0
    print("ERRO: PDF ou imagem fora das pastas permitidas (risco de fatura real no Git):")
    for arquivo in proibidos:
        print(f"  - {arquivo}")
    print("Permitido apenas em: " + ", ".join(PASTAS_PERMITIDAS))
    print("Faturas reais ficam fora do repositório. Veja docs/conformidade/politica-de-dados.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
