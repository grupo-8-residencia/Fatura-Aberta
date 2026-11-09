"""Conhecimento e RAG da frente F2."""

from fa_rag.chunker import chunkar_dispositivo, chunkar_texto
from fa_rag.core import buscar_normas, filtra_vigentes, recall_at_5
from fa_rag.corpus import carregar_corpus
from fa_rag.embeddings import Embedder, EmbedderHash, criar_embedder
from fa_rag.indexer import IndiceNormativo
from fa_rag.models import DocumentoNormativo, ResultadoBusca
from fa_rag.sintese import Resposta, responder
from fa_rag.vector_store import IndiceHibrido, IndiceVetorial

__version__ = "0.1.0"
FRENTE = "F2"

__all__ = [
    "DocumentoNormativo",
    "Embedder",
    "EmbedderHash",
    "FRENTE",
    "IndiceHibrido",
    "IndiceNormativo",
    "IndiceVetorial",
    "Resposta",
    "ResultadoBusca",
    "buscar_normas",
    "carregar_corpus",
    "chunkar_dispositivo",
    "chunkar_texto",
    "criar_embedder",
    "filtra_vigentes",
    "recall_at_5",
    "responder",
]
