"""Índice vetorial em memória e busca híbrida (vetorial + lexical) com filtros estritos."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Collection, Sequence
from datetime import date
from pathlib import Path

from fa_rag.chunker import chunkar_dispositivo
from fa_rag.corpus import carregar_corpus
from fa_rag.embeddings import Embedder, criar_embedder
from fa_rag.models import DocumentoNormativo, ResultadoBusca
from fa_rag.texto import normalizar_texto, tokenizar

_ENTIDADES_DISTINTIVAS = frozenset(
    tok
    for termo in ("cip", "iluminacao", "icms", "pis", "cofins", "bandeira")
    for tok in tokenizar(termo)
)


def _fator_aderencia(
    consulta_norm: str,
    consulta_tokens: set[str],
    doc: DocumentoNormativo,
    doc_tokens: Counter[str],
) -> float:
    """Atenua trechos que omitem entidade específica da consulta ou que declaram ``nao_cobre``."""
    fator = 1.0
    if (_ENTIDADES_DISTINTIVAS & consulta_tokens) - set(doc_tokens):
        fator *= 0.35
    for padrao in doc.nao_cobre:
        alvo = normalizar_texto(padrao)
        if alvo and re.search(rf"\b{re.escape(alvo)}\b", consulta_norm):
            fator *= 0.25
            break
    return fator


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

    def assinatura(self, textos: dict[str, str]) -> str:
        """Hash do que foi indexado (ids, textos e dimensão): detecta um arquivo desatualizado."""
        bruto = json.dumps(
            {"dim": self.embedder.dim, "textos": textos}, sort_keys=True, ensure_ascii=False
        )
        return hashlib.sha256(bruto.encode("utf-8")).hexdigest()

    def salvar(self, caminho: Path, textos: dict[str, str]) -> None:
        """Grava os vetores em JSON, com a assinatura dos textos para validar na carga."""
        caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "dim": self.embedder.dim,
            "assinatura": self.assinatura(textos),
            "vetores": {k: [round(x, 8) for x in v] for k, v in self._vetores.items()},
        }
        caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    def carregar(self, caminho: Path, textos: dict[str, str]) -> bool:
        """Carrega os vetores se o arquivo existir e conferir com os textos; senão, False."""
        if not caminho.exists():
            return False
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        vetores = dados.get("vetores", {})
        if (
            dados.get("dim") != self.embedder.dim
            or dados.get("assinatura") != self.assinatura(textos)
            or set(vetores) != set(textos)
        ):
            return False
        self._vetores = {k: [float(x) for x in v] for k, v in vetores.items()}
        return True

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
        arquivo_vetores: Path | None = None,
    ) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha deve estar em [0, 1]")
        self.documentos = list(documentos)
        self.alpha = alpha
        self._vetorial = IndiceVetorial(embedder or criar_embedder())
        textos = {d.id: _texto_indexavel(d) for d in self.documentos}
        # Com `arquivo_vetores`, o índice é durável: reaproveita os vetores salvos se o corpus e o
        # embedder não mudaram; caso contrário, recalcula e grava de novo.
        if arquivo_vetores is None or not self._vetorial.carregar(arquivo_vetores, textos):
            self._vetorial.adicionar(list(textos), list(textos.values()))
            if arquivo_vetores is not None:
                self._vetorial.salvar(arquivo_vetores, textos)
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
        arquivo_vetores: Path | None = None,
    ) -> IndiceHibrido:
        """Carrega o corpus curado e indexa um chunk por dispositivo (caput, § e incisos)."""
        chunks = [c for doc in carregar_corpus(caminho) for c in chunkar_dispositivo(doc)]
        return cls(chunks, embedder=embedder, alpha=alpha, arquivo_vetores=arquivo_vetores)

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
        consulta_unicos = set(tokens)
        consulta_norm = normalizar_texto(consulta)
        vetoriais = self._vetorial.similaridades(consulta, [d.id for d in candidatos])
        resultados: list[ResultadoBusca] = []
        for d in candidatos:
            fator = _fator_aderencia(consulta_norm, consulta_unicos, d, self._tokens[d.id])
            vet = vetoriais[d.id] * fator
            lex = self._lexico(tokens, d.id) * fator
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
