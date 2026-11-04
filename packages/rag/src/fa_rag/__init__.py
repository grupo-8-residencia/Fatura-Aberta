"""Conhecimento e RAG da frente F2."""

from fa_rag.chunker import chunkar_texto
from fa_rag.core import buscar_normas, filtra_vigentes, recall_at_5
from fa_rag.indexer import IndiceNormativo
from fa_rag.models import DocumentoNormativo, ResultadoBusca

__version__ = "0.1.0"
FRENTE = "F2"

__all__ = [
    "DocumentoNormativo",
    "FRENTE",
    "IndiceNormativo",
    "ResultadoBusca",
    "buscar_normas",
    "chunkar_texto",
    "filtra_vigentes",
    "recall_at_5",
]
