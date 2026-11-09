"""Índice híbrido para o corpus normativo da frente F2."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import date
from typing import Any

from fa_rag.core import buscar_normas
from fa_rag.models import ResultadoBusca


class IndiceNormativo:
    """Mantém o corpus normativo e executa busca híbrida com filtros auditáveis."""

    def __init__(self, documentos: Sequence[Any]) -> None:
        self.documentos = list(documentos)

    def buscar(
        self,
        consulta: str,
        *,
        data_referencia: date,
        subgrupos: Collection[str] | None = None,
        top_k: int = 5,
        alfa: float = 0.5,
    ) -> list[Any]:
        """Busca híbrida retornando os documentos ordenados por relevância."""
        return buscar_normas(
            consulta,
            corpus=self.documentos,
            data_referencia=data_referencia,
            subgrupos=subgrupos,
            top_k=top_k,
            alfa=alfa,
            detalhado=False,
        )

    def buscar_detalhado(
        self,
        consulta: str,
        *,
        data_referencia: date,
        subgrupos: Collection[str] | None = None,
        top_k: int = 5,
        alfa: float = 0.5,
    ) -> list[ResultadoBusca]:
        """Busca híbrida retornando instâncias de ResultadoBusca com decomposição de score."""
        resultados = buscar_normas(
            consulta,
            corpus=self.documentos,
            data_referencia=data_referencia,
            subgrupos=subgrupos,
            top_k=top_k,
            alfa=alfa,
            detalhado=True,
        )
        return [r for r in resultados if isinstance(r, ResultadoBusca)]
