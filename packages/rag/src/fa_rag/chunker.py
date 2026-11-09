"""Chunking de texto normativo para a frente F2."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from fa_contratos import Citacao
from fa_rag.models import DocumentoNormativo

_PADRAO_ARTIGO = re.compile(
    r"(?=(?:^|\n)\s*Art(?:\.|igo)?\s*(\d+[ºo\.]?)\s*[-–—.]?\s*)",
    re.IGNORECASE,
)
_PADRAO_PARAGRAFO = re.compile(
    r"(?=(?:^|\n)\s*(§\s*\d+[ºo\.]?|Parágrafo\s+único)\s*[-–—.]?\s*)",
    re.IGNORECASE,
)
_PADRAO_INCISO = re.compile(
    r"(?=(?:^|\n)\s*([IVXLCDM]+\s*[-–—])\s*)",
)


def _slugificar(texto: str) -> str:
    limpo = re.sub(r"[^\w\s-]", "", texto.lower())
    return re.sub(r"[-\s]+", "-", limpo).strip("-")


def chunkar_texto(texto: str, *, max_chars: int = 400) -> list[str]:
    """Quebra um texto normativo em blocos menores e auditáveis."""
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


def _extrair_blocos_artigo(artigo_texto: str) -> list[tuple[str, str]]:
    """Divide o corpo de um artigo em caput, parágrafos e incisos."""
    linhas = [linha.strip() for linha in artigo_texto.strip().splitlines() if linha.strip()]
    if not linhas:
        return []

    artigo_header = linhas[0]
    m_art = re.match(
        r"^Art(?:\.|igo)?\s*(\d+[ºo\.]?)\s*[-–—.]?\s*(.*)$",
        artigo_header,
        re.IGNORECASE,
    )
    numero_artigo = m_art.group(1) if m_art else "1º"
    art_prefix = f"Art. {numero_artigo}"

    restante_linhas: list[str] = []
    if m_art and m_art.group(2).strip():
        restante_linhas.append(m_art.group(2).strip())
    restante_linhas.extend(linhas[1:])

    if not restante_linhas:
        return [(art_prefix, artigo_header)]

    sub_dispositivos: list[tuple[str, str]] = []
    bloco_atual_disp = f"{art_prefix}, caput"
    bloco_atual_texto: list[str] = []

    for linha in restante_linhas:
        m_par = re.match(
            r"^(§\s*\d+[ºo\.]?|Parágrafo\s+único)\s*[-–—.]?\s*(.*)$",
            linha,
            re.IGNORECASE,
        )
        m_inc = re.match(r"^([IVXLCDM]+)\s*[-–—]\s*(.*)$", linha)

        if m_par:
            if bloco_atual_texto:
                sub_dispositivos.append((bloco_atual_disp, " ".join(bloco_atual_texto)))
                bloco_atual_texto = []
            rotulo_par = (
                "parágrafo único"
                if "único" in m_par.group(1).lower()
                else re.sub(r"§\s*", "§ ", m_par.group(1).strip())
            )
            bloco_atual_disp = f"{art_prefix}, {rotulo_par}"
            if m_par.group(2).strip():
                bloco_atual_texto.append(m_par.group(2).strip())
            continue

        if m_inc:
            if bloco_atual_texto:
                sub_dispositivos.append((bloco_atual_disp, " ".join(bloco_atual_texto)))
                bloco_atual_texto = []
            rotulo_inc = f"inc. {m_inc.group(1)}"
            bloco_atual_disp = f"{art_prefix}, {rotulo_inc}"
            if m_inc.group(2).strip():
                bloco_atual_texto.append(m_inc.group(2).strip())
            continue

        bloco_atual_texto.append(linha)

    if bloco_atual_texto:
        sub_dispositivos.append((bloco_atual_disp, " ".join(bloco_atual_texto)))

    if len(sub_dispositivos) == 1 and sub_dispositivos[0][0] == f"{art_prefix}, caput":
        return [(art_prefix, sub_dispositivos[0][1])]

    return sub_dispositivos


def chunkar_dispositivos(
    texto: str,
    *,
    ato: str,
    vigencia_inicio: date,
    vigencia_fim: date | None = None,
    url: Any = "https://www2.aneel.gov.br/cedoc/ren20211000.html",
    subgrupos: tuple[str, ...] = ("B1",),
    tags: tuple[str, ...] = (),
) -> list[DocumentoNormativo]:
    """Segmenta o texto normativo por dispositivo (artigo, parágrafo, inciso).

    Cada chunk gerado encapsula sua Citação canônica (`ato`, `dispositivo`,
    `vigencia_inicio`, `vigencia_fim` e `url`) e metadados de subgrupo.
    """
    if not texto or not texto.strip():
        return []

    artigo_splits = _PADRAO_ARTIGO.split(texto.strip())
    # Se o texto não contiver a estrutura 'Art. X', trata por parágrafos/blocos
    if len(artigo_splits) <= 1:
        blocos_texto = chunkar_texto(texto)
        chunks: list[DocumentoNormativo] = []
        for i, bloco in enumerate(blocos_texto, start=1):
            disp = f"Dispositivo {i}"
            citacao = Citacao(
                ato=ato,
                dispositivo=disp,
                vigencia_inicio=vigencia_inicio,
                vigencia_fim=vigencia_fim,
                url=url,
            )
            chunks.append(
                DocumentoNormativo(
                    id=f"{_slugificar(ato)}-disp-{i}",
                    titulo=f"{ato} — {disp}",
                    texto=bloco,
                    citacao=citacao,
                    subgrupos=subgrupos,
                    tags=tags,
                )
            )
        return chunks

    resultado: list[DocumentoNormativo] = []
    artigos_encontrados = re.findall(
        r"(Art(?:\.|igo)?\s*\d+[ºo\.]?[\s\S]*?)(?=(?:^|\n)\s*Art(?:\.|igo)?\s*\d+[ºo\.]?|\Z)",
        texto.strip(),
        re.IGNORECASE,
    )

    if not artigos_encontrados:
        artigos_encontrados = [texto.strip()]

    for bloco_art in artigos_encontrados:
        sub_dispositivos = _extrair_blocos_artigo(bloco_art)
        for disp_nome, disp_texto in sub_dispositivos:
            if not disp_texto.strip():
                continue
            citacao = Citacao(
                ato=ato,
                dispositivo=disp_nome,
                vigencia_inicio=vigencia_inicio,
                vigencia_fim=vigencia_fim,
                url=url,
            )
            chunk_id = f"{_slugificar(ato)}-{_slugificar(disp_nome)}"
            resultado.append(
                DocumentoNormativo(
                    id=chunk_id,
                    titulo=f"{ato} — {disp_nome}",
                    texto=disp_texto.strip(),
                    citacao=citacao,
                    subgrupos=subgrupos,
                    tags=tags,
                )
            )

    return resultado
