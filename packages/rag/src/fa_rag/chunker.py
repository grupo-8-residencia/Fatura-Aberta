"""Chunking mínimo de texto normativo para a frente F2."""

from __future__ import annotations

import re


def chunkar_texto(texto: str, *, max_chars: int = 400) -> list[str]:
    """Quebra um texto normativo em blocos menores e auditáveis.

    A estratégia base é separar por parágrafos e por pontuação final, preservando a ordem e
    evitando blocos excessivamente grandes.
    """

    if not texto or not texto.strip():
        return []

    partes = re.split(r"\n\s*\n+|\n+", texto.strip())
    chunks: list[str] = []

    for parte in partes:
        valor = " ".join(parte.split())
        if not valor:
            continue

        if len(valor) <= max_chars:
            chunks.append(valor)
            continue

        palavras = valor.split()
        atual = ""
        for palavra in palavras:
            if not atual:
                atual = palavra
                continue

            if len(atual) + 1 + len(palavra) <= max_chars:
                atual = f"{atual} {palavra}"
                continue

            chunks.append(atual)
            atual = palavra

        if atual:
            chunks.append(atual)

    return chunks
