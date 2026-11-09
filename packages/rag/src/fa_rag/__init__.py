"""Conhecimento e RAG da frente F2."""

from fa_rag.chunker import chunkar_dispositivo, chunkar_dispositivos, chunkar_texto
from fa_rag.core import buscar_normas, filtra_vigentes, recall_at_5
from fa_rag.corpus import carregar_corpus
from fa_rag.embeddings import Embedder, EmbedderHash, criar_embedder
from fa_rag.indexer import IndiceNormativo
from fa_rag.models import ChunkNormativo, DocumentoNormativo, ResultadoBusca
from fa_rag.sintese import Resposta, responder
from fa_rag.vector_store import IndiceHibrido, IndiceVetorial

__version__ = "0.2.0"
FRENTE = "F2"

__all__ = [
    "ChunkNormativo",
    "DocumentoNormativo",
    "Embedder",
    "EmbedderHash",
    "FRENTE",
    "IndiceHibrido",
    "IndiceNormativo",
    "IndiceVetorial",
    "Resposta",
    "ResultadoBusca",
    "__version__",
    "buscar_normas",
    "carregar_corpus",
    "chunkar_dispositivo",
    "chunkar_dispositivos",
    "chunkar_texto",
    "criar_embedder",
    "filtra_vigentes",
    "recall_at_5",
    "responder",
]
