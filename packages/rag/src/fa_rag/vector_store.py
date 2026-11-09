"""Índice vetorial em memória e busca híbrida (vetorial + lexical) com filtros estritos."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Sequence
from datetime import date
from pathlib import Path

from fa_rag.chunker import chunkar_dispositivo
from fa_rag.corpus import carregar_corpus
from fa_rag.embeddings import Embedder, criar_embedder
from fa_rag.models import DocumentoNormativo, ResultadoBusca
from fa_rag.texto import tokenizar


def _texto_indexavel(doc: DocumentoNormativo) -> str:
    return (
        f"{doc.titulo} {doc.citacao.ato} {doc.citacao.dispositivo} {doc.texto} {' '.join(doc.tags)}"
    )


class IndiceVetorial:
    """Vetores normalizados em memória; cosseno = produto interno."""

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._vetores: dict[str, list[float]] = {}

    def adicionar(self, ids: Sequence[str], textos: Sequence[str]) -> None:
        for chave, vetor in zip(ids, self.embedder.embed(textos), strict=True):
            self._vetores[chave] = vetor

    def similaridades(self, consulta: str, ids: Collection[str]) -> dict[str, float]:
        q = self.embedder.embed([consulta])[0]
        return {
            i: max(0.0, sum(a * b for a, b in zip(q, self._vetores[i], strict=True))) for i in ids
        }


class IndiceHibrido:
    """score = alpha * vetorial + (1 - alpha) * lexical, após filtrar vigência e subgrupo."""

    def __init__(
        self,
        documentos: Sequence[DocumentoNormativo],
        *,
        embedder: Embedder | None = None,
        alpha: float = 0.5,
    ) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha deve estar em [0, 1]")
        self.documentos = list(documentos)
        self.alpha = alpha
        self._vetorial = IndiceVetorial(embedder or criar_embedder())
        self._vetorial.adicionar(
            [d.id for d in self.documentos], [_texto_indexavel(d) for d in self.documentos]
        )
        self._tokens = {d.id: Counter(tokenizar(_texto_indexavel(d))) for d in self.documentos}
        n = len(self.documentos)
        df: Counter[str] = Counter()
        for contagem in self._tokens.values():
            df.update(contagem.keys())
        self._n = n
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._idf_ausente = math.log(1 + n)

    @classmethod
    def do_corpus(
        cls,
        caminho: Path | None = None,
        *,
        embedder: Embedder | None = None,
        alpha: float = 0.5,
    ) -> IndiceHibrido:
        """Carrega o corpus curado e indexa um chunk por dispositivo (caput, § e incisos)."""
        chunks = [c for doc in carregar_corpus(caminho) for c in chunkar_dispositivo(doc)]
        return cls(chunks, embedder=embedder, alpha=alpha)

    def _lexico(self, consulta_tokens: Sequence[str], doc_id: str) -> float:
        """Cobertura da consulta ponderada por IDF, em [0, 1]; termo ausente pesa contra."""
        unicos = set(consulta_tokens)
        if not unicos:
            return 0.0
        total = sum(self._idf.get(t, self._idf_ausente) for t in unicos)
        achado = sum(self._idf.get(t, 0.0) for t in unicos if t in self._tokens[doc_id])
        return achado / total if total > 0 else 0.0

    def buscar(
        self,
        consulta: str,
        *,
        data_referencia: date,
        subgrupos: Collection[str] = ("B1",),
        top_k: int = 5,
        alpha: float | None = None,
        filtrar_vigencia: bool = True,
        um_por_dispositivo: bool = False,
    ) -> list[ResultadoBusca]:
        """Filtra (vigência na data e subgrupo) e só então ordena. ``filtrar_vigencia=False``
        reproduz o baseline B2 (RAG sem filtro de vigência). ``um_por_dispositivo`` mantém só o
        melhor chunk de cada artigo (útil para medir recall por dispositivo)."""
        peso = self.alpha if alpha is None else alpha
        if not 0.0 <= peso <= 1.0:
            raise ValueError("alpha deve estar em [0, 1]")
        alvo = set(subgrupos)
        candidatos = [
            d
            for d in self.documentos
            if (not alvo or alvo & set(d.subgrupos))
            and (not filtrar_vigencia or d.vigente_em(data_referencia))
        ]
        if not candidatos:
            return []
        tokens = tokenizar(consulta)
        vetoriais = self._vetorial.similaridades(consulta, [d.id for d in candidatos])
        resultados: list[ResultadoBusca] = []
        for d in candidatos:
            vet = vetoriais[d.id]
            lex = self._lexico(tokens, d.id)
            score = peso * vet + (1.0 - peso) * lex
            if score > 0.0:
                resultados.append(ResultadoBusca(d, score, score_vetorial=vet, score_lexico=lex))
        resultados.sort(key=lambda r: (-r.score, r.documento.id))
        if um_por_dispositivo:
            vistos: set[str] = set()
            unicos: list[ResultadoBusca] = []
            for r in resultados:
                artigo = r.documento.id.split("::")[0]
                if artigo not in vistos:
                    vistos.add(artigo)
                    unicos.append(r)
            resultados = unicos
        return resultados[:top_k]
