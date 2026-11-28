"""Higienização do texto lido de imagem ou PDF: remove instruções de controle embutidas.

Um único detector serve à higienização e à guarda da API. Antes de casar os padrões, o texto é
normalizado caractere a caractere: decomposição sem acentos, caixa baixa, caracteres invisíveis
removidos e letras de alfabetos parecidos (cirílico e grego) trocadas pela latina equivalente.
Cada caractere normalizado guarda de qual caractere original veio, então a remoção acontece no
texto original e não depende da normalização.

Limite conhecido: é uma lista de padrões. Paráfrases fora dela passam. Por isso a defesa principal
é tratar todo texto extraído como dado e nunca como instrução (ver docs/seguranca).
"""

import re
import unicodedata

MARCADOR_REMOVIDO = "[conteúdo de controle removido]"

# Caracteres invisíveis que sumiriam numa comparação visual mas mudam a string.
_INVISIVEIS = frozenset("​‌‍⁠﻿­")

# Letras de alfabetos parecidos com as latinas. Só as que aparecem em ataques comuns.
_HOMOGRAFOS = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "у": "y",
        "х": "x",
        "і": "i",
        "ј": "j",
        "ѕ": "s",
        "ԁ": "d",
        "һ": "h",
        "ο": "o",
        "α": "a",
        "ι": "i",
        "ν": "v",
        "ρ": "p",
        "τ": "t",
    }
)

_INSTRUCAO_CONTROLE = re.compile(
    r"(?:\b(?:ignor\w*|desconsider\w*|esquec\w*|disregard\w*|forget\w*)\b.{0,70}"
    r"\b(?:instrucoes|instructions|regras|rules|diretrizes|guidelines|tudo|anteriores?|"
    r"previous|directions)\b|"
    r"\bsystem\s*:|"
    r"\b(?:system\s+prompt|prompt\s+(?:de|do)\s+sistema|"
    r"role\s*:\s*system|(?:voce|you)\s+(?:agora\s+e|are\s+now))\b|"
    r"\[inst\]|<\|im_start\|>|"
    r"\b(?:revele|mostre|exiba|reveal|print)\b.{0,50}\b(?:prompt|instrucoes|instructions)\b|"
    r"\b(?:omita|oculte|suprima|ignore|hide|suppress)\b.{0,60}"
    r"\b(?:achados|divergencias|findings|discrepancies|erros)\b|"
    r"\b(?:responda|diga|declare|declarar|afirme|afirmar|say|answer|respond)\b.{0,60}"
    r"\b(?:aprovad[oa]|correta?o?|sem\s+divergencia|no\s+discrepancy)\b)",
    re.DOTALL,
)

_FIM_DE_FRASE = frozenset(".;!?\n")


def _normalizar(texto: str) -> tuple[str, list[int]]:
    """Texto normalizado e, para cada caractere dele, o índice do caractere original."""
    partes: list[str] = []
    origem: list[int] = []
    for indice, caractere in enumerate(texto):
        if caractere in _INVISIVEIS:
            continue
        for decomposto in unicodedata.normalize("NFKD", caractere):
            if unicodedata.combining(decomposto):
                continue
            for saida in decomposto.casefold().translate(_HOMOGRAFOS):
                partes.append(saida)
                origem.append(indice)
    return "".join(partes), origem


def _expandir_para_frase(norm: str, ini: int, fim: int) -> tuple[int, int]:
    """Estende o trecho até o início e o fim da frase, incluindo o pontuador final."""
    while ini > 0 and norm[ini - 1] not in _FIM_DE_FRASE:
        ini -= 1
    while fim < len(norm) and norm[fim] not in _FIM_DE_FRASE:
        fim += 1
    if fim < len(norm) and norm[fim] in _FIM_DE_FRASE and norm[fim] != "\n":
        fim += 1
    return ini, fim


def _trechos_de_controle(texto: str) -> list[tuple[int, int]]:
    """Intervalos do texto original que contêm instrução de controle (frase inteira)."""
    norm, origem = _normalizar(texto)
    trechos: list[tuple[int, int]] = []
    for casamento in _INSTRUCAO_CONTROLE.finditer(norm):
        ini, fim = _expandir_para_frase(norm, casamento.start(), casamento.end())
        trechos.append((origem[ini], origem[fim - 1] + 1))
    return trechos


def contem_instrucao_controle(texto: str) -> bool:
    """Detecta comandos para alterar o comportamento dos agentes em entrada não confiável.

    A detecção é uma barreira conservadora para comandos explícitos, não uma prova de que
    textos que passam são seguros. O conteúdo nunca é registrado em logs.
    """
    norm, _ = _normalizar(texto)
    return bool(_INSTRUCAO_CONTROLE.search(norm))


def higienizar_texto_extraido(texto: str) -> str:
    """Remove as frases com instrução de controle, preservando o resto do texto como dado.

    O texto preservado deve ser tratado exclusivamente como dado de fatura; a remoção é uma
    defesa complementar, não autorização para executar instruções presentes na imagem.
    """
    trechos = sorted(_trechos_de_controle(texto))
    if not trechos:
        return texto
    fundidos: list[list[int]] = []
    for ini, fim in trechos:
        if fundidos and ini <= fundidos[-1][1]:
            fundidos[-1][1] = max(fundidos[-1][1], fim)
        else:
            fundidos.append([ini, fim])
    partes: list[str] = []
    cursor = 0
    for ini, fim in fundidos:
        partes.append(texto[cursor:ini])
        partes.append(f" {MARCADOR_REMOVIDO} ")  # espaços: o marcador não pode colar em palavras
        cursor = fim
    partes.append(texto[cursor:])
    return "".join(partes)
