"""Modelos mínimos para documentos normativos do RAG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class DocumentoNormativo:
    """Representa um dispositivo normativo com metadados e vigência."""

    id: str
    titulo: str
    texto: str
    citacao: Any
    subgrupos: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def vigente_em(self, dia: date) -> bool:
        return bool(self.citacao.vigente_em(dia))


@dataclass(frozen=True, slots=True)
class ResultadoBusca:
    """Resultado da busca com score de relevância."""

    documento: DocumentoNormativo
    score: float
