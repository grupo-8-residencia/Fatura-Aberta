"""Conhecimento e RAG da frente F2."""

from fa_rag.chunker import chunkar_dispositivos, chunkar_texto
from fa_rag.core import buscar_normas, filtra_vigentes, recall_at_5
from fa_rag.indexer import IndiceNormativo
from fa_rag.models import ChunkNormativo, DocumentoNormativo, ResultadoBusca

__version__ = "0.2.0"
FRENTE = "F2"

__all__ = [
    "ChunkNormativo",
    "DocumentoNormativo",
    "FRENTE",
    "IndiceNormativo",
    "ResultadoBusca",
    "__version__",
    "buscar_normas",
    "chunkar_dispositivos",
    "chunkar_texto",
    "filtra_vigentes",
    "recall_at_5",
]
