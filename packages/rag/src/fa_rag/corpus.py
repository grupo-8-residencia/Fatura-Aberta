"""Carga do corpus normativo curado (``dados/normas/corpus_b1.json``)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fa_contratos import Citacao
from fa_rag.models import DocumentoNormativo

_OBRIGATORIOS = ("id", "titulo", "texto", "citacao", "subgrupos", "tags")


def caminho_padrao() -> Path:
    """Localiza o corpus na raiz do repositório (3 níveis acima de ``packages/rag/src``)."""
    return Path(__file__).resolve().parents[4] / "dados" / "normas" / "corpus_b1.json"


def _documento(item: dict[str, Any]) -> DocumentoNormativo:
    faltando = [c for c in _OBRIGATORIOS if c not in item]
    if faltando:
        raise ValueError(f"Item {item.get('id', '?')!r} sem campos obrigatórios: {faltando}")
    cit = item["citacao"]
    citacao = Citacao(
        ato=cit["ato"],
        dispositivo=cit["dispositivo"],
        vigencia_inicio=date.fromisoformat(cit["vigencia_inicio"]),
        vigencia_fim=date.fromisoformat(cit["vigencia_fim"]) if cit.get("vigencia_fim") else None,
        url=cit["url"],
    )
    return DocumentoNormativo(
        id=str(item["id"]),
        titulo=str(item["titulo"]),
        texto=str(item["texto"]),
        citacao=citacao,
        subgrupos=tuple(item["subgrupos"]),
        tags=tuple(item["tags"]),
        observacoes=str(item.get("observacoes") or ""),
    )


def carregar_corpus(
    caminho: Path | None = None, *, so_conferidos: bool = True
) -> list[DocumentoNormativo]:
    """Lê o corpus validando ``Citacao``. Itens não conferidos ficam de fora por padrão."""
    dados = json.loads((caminho or caminho_padrao()).read_text(encoding="utf-8"))
    docs = [_documento(i) for i in dados if not so_conferidos or i.get("conferido") == "sim"]
    ids = [d.id for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError("ids duplicados no corpus")
    return docs
