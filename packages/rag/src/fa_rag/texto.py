"""Normalização de texto em português para busca lexical e embeddings."""

from __future__ import annotations

import re
import unicodedata

_STOPWORDS = frozenset(
    {
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "por",
        "para",
        "com",
        "sem",
        "sob",
        "sobre",
        "e",
        "ou",
        "que",
        "se",
        "ao",
        "aos",
        "à",
        "às",
        "pelo",
        "pela",
        "pelos",
        "pelas",
        "como",
        "eu",
        "me",
        "meu",
        "minha",
        "posso",
        "pode",
        "podem",
        "ser",
        "sao",
        "foi",
        "esta",
        "este",
        "esse",
        "essa",
        "isso",
        "ha",
        "mais",
        "menos",
        "muito",
        "ja",
        "nao",
        "sim",
        "qual",
        "quais",
        "quando",
        "onde",
        "deve",
        "devem",
        "tem",
        "ter",
        "seu",
        "sua",
        "seus",
        "suas",
        "entre",
        "ate",
        "apos",
        "desta",
        "deste",
        "dessa",
        "desse",
    }
)


def sem_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def tokenizar(texto: str, *, radical: int = 5) -> list[str]:
    """Minúsculas, sem acentos, sem stopwords, com radical truncado (stemming leve)."""
    bruto = re.findall(r"[a-z0-9]+", sem_acentos(texto).lower())
    saida: list[str] = []
    for token in bruto:
        if token in _STOPWORDS or (len(token) < 2 and not token.isdigit()):
            continue
        saida.append(token[:radical] if len(token) > radical else token)
    return saida
