"""Cabeçalho de reprodutibilidade para as avaliações do RAG (débitos S2/S3).

Registra, em cada resultado novo, o que as rodadas históricas não gravavam: hash do corpus e do
golden set, contagens nas três unidades (atos, dispositivos e chunks), embedder, α, limiar e top_k.
Os JSON históricos não são alterados; só as avaliações novas usam este cabeçalho.
"""

from __future__ import annotations

import hashlib
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rodada_s4 import sha256_corpus as sha256_chunks

from fa_rag import IndiceHibrido, carregar_corpus, chunkar_dispositivo

RAIZ = Path(__file__).resolve().parents[1]
CORPUS = RAIZ / "dados" / "normas" / "corpus_b1.json"
GOLDEN_SET = RAIZ / "dados" / "golden-set" / "perguntas.jsonl"


def sha256_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def contagens_corpus() -> dict[str, int]:
    """Atos oficiais distintos, dispositivos indexados e chunks gerados (unidades diferentes)."""
    docs = carregar_corpus()
    chunks = [c for d in docs for c in chunkar_dispositivo(d)]
    return {
        "atos_distintos": len({d.citacao.ato for d in docs}),
        "dispositivos": len(docs),
        "chunks": len(chunks),
    }


def cabecalho(
    indice: IndiceHibrido, *, limiar: float | None, top_k: int, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    embedder = indice._vetorial.embedder
    saida: dict[str, Any] = {
        "gerado_em_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        # mesmo cálculo do cabeçalho histórico da S4 (hash dos chunks indexados)
        "sha256_corpus": sha256_chunks(indice.documentos),
        "sha256_corpus_arquivo": sha256_arquivo(CORPUS),
        "sha256_perguntas_golden_set": sha256_arquivo(GOLDEN_SET),
        **contagens_corpus(),
        "embedder": {
            "nome": getattr(embedder, "nome", type(embedder).__name__),
            "versao": getattr(embedder, "versao", ""),
            "dim": embedder.dim,
        },
        "alpha": indice.alpha,
        "limiar_abstencao": limiar,
        "top_k": top_k,
    }
    if extra:
        saida.update(extra)
    return saida
