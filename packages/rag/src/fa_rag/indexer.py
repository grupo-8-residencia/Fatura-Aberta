"""Índice simples para o corpus normativo da frente F2."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import date
from typing import Any

from fa_rag.core import buscar_normas


class IndiceNormativo:
    """Mantém uma lista de documentos normativos e executa busca ordenada."""

    def __init__(self, documentos: Sequence[Any]) -> None:
        self.documentos = list(documentos)

    def buscar(
        self,
        consulta: str,
        *,
        data_referencia: date,
        subgrupos: Collection[str] | None = None,
        top_k: int = 5,
    ) -> list[Any]:
        return buscar_normas(
            consulta,
            corpus=self.documentos,
            data_referencia=data_referencia,
            subgrupos=subgrupos,
            top_k=top_k,
        )
