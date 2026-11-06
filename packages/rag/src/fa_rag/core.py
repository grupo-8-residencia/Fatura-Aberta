"""Funções mínimas de recuperação e avaliação do conhecimento normativo."""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Sequence
from datetime import date
from typing import Any


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
    if isinstance(item, dict):
        partes = [
            str(item.get("titulo", "")),
            str(item.get("texto", "")),
            str(_obter_citacao(item).ato),
            str(_obter_citacao(item).dispositivo),
        ]
        return " ".join(partes)

    return " ".join(
        [
            str(getattr(item, "titulo", "")),
            str(getattr(item, "texto", "")),
            str(getattr(getattr(item, "citacao", None), "ato", "")),
            str(getattr(getattr(item, "citacao", None), "dispositivo", "")),
        ]
    )


def _tokenizar(texto: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9çãõáéíóúàêâîôûü]+", texto.lower()) if token}


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


def buscar_normas(
    consulta: str,
    *,
    corpus: Sequence[Any],
    data_referencia: date,
    subgrupos: Collection[str] | None = None,
    top_k: int = 5,
) -> list[Any]:
    """Busca lexical simples filtrando por vigência e subgrupo."""

    tokens = _tokenizar(consulta)
    if not tokens:
        return []

    subgrupos_set = set(subgrupos) if subgrupos else None
    resultados: list[tuple[float, Any]] = []

    for item in filtra_vigentes(corpus, data_referencia):
        if subgrupos_set:
            item_subgrupos = set(_obter_subgrupos(item))
            if item_subgrupos and not item_subgrupos & subgrupos_set:
                continue

        texto = _obter_texto(item).lower()
        score = sum(1 for token in tokens if token in texto)
        if score > 0:
            resultados.append((float(score), item))

    resultados.sort(key=lambda par: par[0], reverse=True)
    return [item for _, item in resultados[:top_k]]
