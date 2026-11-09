"""Modelos mínimos para documentos normativos do RAG."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from fa_contratos import Citacao


@dataclass(frozen=True, slots=True)
class DocumentoNormativo:
    """Representa um dispositivo normativo com metadados e vigência."""

    id: str
    titulo: str
    texto: str
    citacao: Citacao | Any
    subgrupos: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    observacoes: str = ""

    def vigente_em(self, dia: date) -> bool:
        return bool(self.citacao.vigente_em(dia))


ChunkNormativo = DocumentoNormativo


@dataclass(frozen=True, slots=True)
class ResultadoBusca:
    """Resultado da busca com score de relevância e decomposição híbrida."""

    documento: DocumentoNormativo | Any
    score: float
    score_lexico: float = 0.0
    score_vetorial: float = 0.0
