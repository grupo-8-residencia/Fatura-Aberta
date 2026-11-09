"""Funções de recuperação híbrida e avaliação do conhecimento normativo."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from datetime import date
from typing import Any

from fa_rag.models import ResultadoBusca


def _normalizar_texto(texto: str) -> str:
    """Remove diacríticos e normaliza para minúsculas."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def _obter_citacao(item: Any) -> Any:
    if isinstance(item, dict):
        return item.get("citacao")
    return getattr(item, "citacao", None)


def _obter_subgrupos(item: Any) -> tuple[str, ...]:
    if isinstance(item, dict):
        subgrupos = item.get("subgrupos", ())
        if isinstance(subgrupos, Iterable) and not isinstance(subgrupos, str):
            return tuple(subgrupos)
        return ()
    return tuple(getattr(item, "subgrupos", ()))


def _obter_texto(item: Any) -> str:
    citacao = _obter_citacao(item)
    ato = getattr(citacao, "ato", "") if citacao else ""
    disp = getattr(citacao, "dispositivo", "") if citacao else ""

    if isinstance(item, dict):
        partes = [
            str(item.get("titulo", "")),
            str(item.get("texto", "")),
            str(ato),
            str(disp),
        ]
        return " ".join(partes)

    return " ".join(
        [
            str(getattr(item, "titulo", "")),
            str(getattr(item, "texto", "")),
            str(ato),
            str(disp),
        ]
    )


def _tokenizar(texto: str) -> list[str]:
    norm = _normalizar_texto(texto)
    return [token for token in re.findall(r"[a-z0-9]+", norm) if token]


def _extrair_ngrams(texto: str, n: int = 3) -> list[str]:
    norm = f" {_normalizar_texto(texto)} "
    if len(norm) < n:
        return [norm]
    return [norm[i : i + n] for i in range(len(norm) - n + 1)]


def filtra_vigentes(corpus: Sequence[Any], data: date) -> list[Any]:
    """Mantém apenas itens cujo dispositivo está vigente na data consultada."""
    vigentes: list[Any] = []
    for item in corpus:
        citacao = _obter_citacao(item)
        if citacao is None:
            continue
        if hasattr(citacao, "vigente_em") and citacao.vigente_em(data):
            vigentes.append(item)
    return vigentes


def recall_at_5(top_5: Sequence[str], relevantes: Collection[str]) -> float:
    """Calcula o recall do conjunto relevante considerando os primeiros 5 resultados."""
    relevantes_set = set(relevantes)
    if not relevantes_set:
        return 1.0

    top = set(list(top_5)[:5])
    return len(top & relevantes_set) / len(relevantes_set)


def _calcular_score_lexico(
    tokens_consulta: list[str],
    texto_doc: str,
    citacao_disp: str,
    idf_map: dict[str, float],
) -> float:
    if not tokens_consulta:
        return 0.0

    tokens_doc = _tokenizar(texto_doc)
    if not tokens_doc:
        return 0.0

    freq_doc = Counter(tokens_doc)
    total_tokens = len(tokens_doc)

    score = 0.0
    for t in set(tokens_consulta):
        if t in freq_doc:
            tf = freq_doc[t] / total_tokens
            idf = idf_map.get(t, 1.0)
            score += tf * idf

    # Boost para correspondência exata no dispositivo citado
    disp_tokens = set(_tokenizar(citacao_disp))
    tokens_comuns = set(tokens_consulta) & disp_tokens
    if tokens_comuns:
        score += len(tokens_comuns) * 0.5

    return score


def _calcular_score_vetorial(
    ngrams_consulta: list[str],
    ngrams_doc: list[str],
    idf_ngrams: dict[str, float],
) -> float:
    if not ngrams_consulta or not ngrams_doc:
        return 0.0

    counter_q = Counter(ngrams_consulta)
    counter_d = Counter(ngrams_doc)

    dot_product = 0.0
    norm_q_sq = 0.0
    for ng, fq in counter_q.items():
        w_q = fq * idf_ngrams.get(ng, 1.0)
        norm_q_sq += w_q * w_q
        if ng in counter_d:
            w_d = counter_d[ng] * idf_ngrams.get(ng, 1.0)
            dot_product += w_q * w_d

    norm_d_sq = sum((fd * idf_ngrams.get(ng, 1.0)) ** 2 for ng, fd in counter_d.items())

    if norm_q_sq <= 0.0 or norm_d_sq <= 0.0:
        return 0.0

    return dot_product / (math.sqrt(norm_q_sq) * math.sqrt(norm_d_sq))


def buscar_normas(
    consulta: str,
    *,
    corpus: Sequence[Any],
    data_referencia: date,
    subgrupos: Collection[str] | None = None,
    top_k: int = 5,
    alfa: float = 0.5,
    detalhado: bool = False,
) -> list[Any]:
    """Busca híbrida (léxica + vetorial) filtrando estritamente por vigência e subgrupo.

    - `alfa=1.0`: puramente léxico
    - `alfa=0.0`: puramente vetorial
    - `alfa=0.5`: fusão ponderada padrão
    """
    tokens_consulta = _tokenizar(consulta)
    if not tokens_consulta:
        return []

    ngrams_consulta = _extrair_ngrams(consulta)

    # 1. Filtro estrito de vigência
    candidatos_vigentes = filtra_vigentes(corpus, data_referencia)
    if not candidatos_vigentes:
        return []

    # 2. Filtro de subgrupo tarifário (ex.: 'B1')
    subgrupos_set = set(subgrupos) if subgrupos else None
    candidatos: list[Any] = []
    for item in candidatos_vigentes:
        if subgrupos_set:
            item_sub = set(_obter_subgrupos(item))
            if item_sub and not (item_sub & subgrupos_set):
                continue
        candidatos.append(item)

    if not candidatos:
        return []

    # Preparação de IDFs sobre os candidatos
    n_docs = len(candidatos)
    doc_tokens_list = [_tokenizar(_obter_texto(it)) for it in candidatos]
    doc_ngrams_list = [_extrair_ngrams(_obter_texto(it)) for it in candidatos]

    idf_tokens: dict[str, float] = {}
    for t in set(tokens_consulta):
        df = sum(1 for dtok in doc_tokens_list if t in dtok)
        idf_tokens[t] = math.log((n_docs + 1) / (df + 1)) + 1.0

    idf_ngrams: dict[str, float] = {}
    for ng in set(ngrams_consulta):
        df_ng = sum(1 for dng in doc_ngrams_list if ng in dng)
        idf_ngrams[ng] = math.log((n_docs + 1) / (df_ng + 1)) + 1.0

    # 3. Cálculo dos scores léxico e vetorial
    raw_scores: list[tuple[float, float, Any]] = []
    for idx, item in enumerate(candidatos):
        texto = _obter_texto(item)
        citacao = _obter_citacao(item)
        disp = getattr(citacao, "dispositivo", "") if citacao else ""

        score_lex = _calcular_score_lexico(tokens_consulta, texto, disp, idf_tokens)
        score_vet = _calcular_score_vetorial(ngrams_consulta, doc_ngrams_list[idx], idf_ngrams)

        raw_scores.append((score_lex, score_vet, item))

    # Normalização min-max
    max_lex = max((s[0] for s in raw_scores), default=0.0)
    max_vet = max((s[1] for s in raw_scores), default=0.0)

    resultados: list[ResultadoBusca] = []
    for s_lex, s_vet, item in raw_scores:
        norm_lex = s_lex / max_lex if max_lex > 0 else 0.0
        norm_vet = s_vet / max_vet if max_vet > 0 else 0.0

        score_final = (alfa * norm_lex) + ((1.0 - alfa) * norm_vet)
        if score_final > 0.0:
            resultados.append(
                ResultadoBusca(
                    documento=item,
                    score=float(score_final),
                    score_lexico=float(norm_lex),
                    score_vetorial=float(norm_vet),
                )
            )

    resultados.sort(key=lambda r: r.score, reverse=True)
    top_resultados = resultados[:top_k]

    if detalhado:
        return top_resultados

    return [r.documento for r in top_resultados]
