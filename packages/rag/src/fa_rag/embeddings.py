"""Extratores de embeddings configuráveis, com fallback determinístico e offline."""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Sequence
from typing import Protocol

from fa_rag.texto import sem_acentos, tokenizar

DIM_PADRAO = 384


class Embedder(Protocol):
    """Contrato mínimo: vetores L2-normalizados de dimensão fixa."""

    dim: int

    def embed(self, textos: Sequence[str]) -> list[list[float]]: ...


class EmbedderHash:
    """Hashing de unigramas, bigramas e trigramas de caracteres (determinístico, sem rede).

    Usa blake2b (estável entre execuções, ao contrário de ``hash()``) e pesos não negativos,
    de modo que o cosseno fica em [0, 1]. Não é semântico: captura sobreposição lexical e
    morfológica. É o padrão do CI; um modelo multilíngue pt-BR entra pelo mesmo contrato.
    """

    def __init__(self, dim: int = DIM_PADRAO) -> None:
        if dim < 8:
            raise ValueError("dim deve ser >= 8")
        self.dim = dim

    def _indice(self, caracteristica: str) -> int:
        digest = hashlib.blake2b(caracteristica.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dim

    def _vetor(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dim
        tokens = tokenizar(texto)
        for token in tokens:
            vetor[self._indice(f"u:{token}")] += 1.0
        for a, b in zip(tokens, tokens[1:], strict=False):
            vetor[self._indice(f"b:{a}_{b}")] += 0.7
        limpo = " ".join(sem_acentos(texto).lower().split())
        for i in range(len(limpo) - 2):
            trecho = limpo[i : i + 3]
            if trecho.strip() and " " not in trecho:
                vetor[self._indice(f"c:{trecho}")] += 0.2
        norma = math.sqrt(sum(x * x for x in vetor))
        return [x / norma for x in vetor] if norma > 0 else vetor

    def embed(self, textos: Sequence[str]) -> list[list[float]]:
        return [self._vetor(t) for t in textos]


def criar_embedder(nome: str | None = None) -> Embedder:
    """Escolhe o extrator por ``FA_RAG_EMBEDDER`` (padrão ``hash``).

    Modelos externos (por exemplo um sentence-transformer multilíngue) devem implementar
    ``Embedder`` e ser registrados aqui; o CI nunca depende deles.
    """
    escolhido = (nome or os.environ.get("FA_RAG_EMBEDDER") or "hash").lower()
    if escolhido == "hash":
        return EmbedderHash()
    raise ValueError(f"Embedder desconhecido: {escolhido!r} (disponível: hash)")
