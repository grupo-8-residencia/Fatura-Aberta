"""Chunking mínimo de texto normativo para a frente F2."""

from __future__ import annotations

import re
from dataclasses import replace

from fa_rag.models import DocumentoNormativo


def chunkar_texto(texto: str, *, max_chars: int = 400) -> list[str]:
    """Quebra um texto normativo em blocos menores e auditáveis.

    A estratégia base é separar por parágrafos e por pontuação final, preservando a ordem e
    evitando blocos excessivamente grandes.
    """

    if not texto or not texto.strip():
        return []

    partes = re.split(r"\n\s*\n+|\n+", texto.strip())
    chunks: list[str] = []

    for parte in partes:
        valor = " ".join(parte.split())
        if not valor:
            continue

        if len(valor) <= max_chars:
            chunks.append(valor)
            continue

        palavras = valor.split()
        atual = ""
        for palavra in palavras:
            if not atual:
                atual = palavra
                continue

            if len(atual) + 1 + len(palavra) <= max_chars:
                atual = f"{atual} {palavra}"
                continue

            chunks.append(atual)
            atual = palavra

        if atual:
            chunks.append(atual)

    return chunks


# --- Chunking por dispositivo (artigo, parágrafo, inciso) ---------------------------------

_RE_CAPUT = re.compile(r"^Art\.\s*\d+")
_RE_PARAGRAFO = re.compile(r"^(?:§\s*(\d+)\s*º|Parágrafo\s+único\.)")
_RE_INCISO = re.compile(r"^([IVXLCDM]+)(\s*-\s*A)?\s*[-–]\s")


def _rotulo_paragrafo(linha: str) -> tuple[str, str]:
    m = _RE_PARAGRAFO.match(linha)
    assert m is not None
    if m.group(1):
        return f"§ {m.group(1)}º", f"p{m.group(1)}"
    return "parágrafo único", "pu"


def chunkar_dispositivo(doc: DocumentoNormativo) -> list[DocumentoNormativo]:
    """Quebra um dispositivo em caput, parágrafos e incisos, cada um com a sua ``Citacao``.

    Incisos e alíneas ficam junto do caput ou do parágrafo a que pertencem; incisos soltos
    (sem caput transcrito) viram chunks próprios. Sem estrutura reconhecível, devolve ``[doc]``.
    """
    base = doc.citacao.dispositivo.split(",")[0].strip()
    unidades: list[tuple[str, str, list[str]]] = []
    for bruta in doc.texto.split("\n"):
        linha = bruta.strip()
        if not linha:
            continue
        if _RE_CAPUT.match(linha):
            unidades.append(("caput", "caput", [linha]))
        elif _RE_PARAGRAFO.match(linha):
            rotulo, chave = _rotulo_paragrafo(linha)
            unidades.append((rotulo, chave, [linha]))
        elif (inc := _RE_INCISO.match(linha)) and (
            not unidades or unidades[-1][1].startswith("inc-")
        ):
            romano = inc.group(1) + ("-A" if inc.group(2) else "")
            unidades.append((f"inciso {romano}", f"inc-{romano.lower()}", [linha]))
        elif unidades:
            unidades[-1][2].append(linha)
        else:
            return [doc]
    if len(unidades) <= 1 and not (unidades and unidades[0][1].startswith("inc-")):
        return [doc]
    chunks: list[DocumentoNormativo] = []
    for rotulo, chave, linhas in unidades:
        citacao = doc.citacao.model_copy(update={"dispositivo": f"{base}, {rotulo}"})
        chunks.append(
            replace(doc, id=f"{doc.id}::{chave}", texto="\n".join(linhas), citacao=citacao)
        )
    return chunks
