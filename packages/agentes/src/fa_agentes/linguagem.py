"""Verificador de linguagem (RF-15): bloqueia expressões proibidas nos cartões de decisão.

As regras vêm de `docs/conformidade/fronteira-juridica.md`. O produto usa linguagem de evidência:
nunca declara cobrança "ilegal", nunca estima restituição e nunca orienta ação judicial.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

REGRAS: dict[str, tuple[str, ...]] = {
    "qualificacao_juridica": (
        "ilegal",
        "ilegalidade",
        "ilegalmente",
        "ilicito",
        "crime",
        "criminoso",
        "criminosa",
        "fraude",
        "roubo",
        "extorsao",
    ),  # fmt: skip
    "reparacao_financeira": (
        "restituicao",
        "ressarcimento",
        "ressarcido",
        "repeticao de indebito",
        "danos morais",
        "indenizacao",
        "devolucao em dobro",
    ),  # fmt: skip
    "aconselhamento_processual": (
        "acao judicial",
        "juizado especial",
        "peticao inicial",
        "causa ganha",
        "processar",
    ),  # fmt: skip
}


@dataclass(frozen=True, slots=True)
class Violacao:
    regra: str
    termo: str


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return sem_acento.lower()


def verificar_linguagem(texto: str) -> list[Violacao]:
    """Lista as violações do RF-15 encontradas no texto (vazia = texto permitido)."""
    base = _normalizar(texto)
    achadas: list[Violacao] = []
    for regra, termos in REGRAS.items():
        for termo in termos:
            if re.search(rf"\b{re.escape(termo)}\b", base):
                achadas.append(Violacao(regra, termo))
    return achadas


def linguagem_permitida(texto: str) -> bool:
    return not verificar_linguagem(texto)
