"""Higienização do texto lido de imagem: remove instruções de controle embutidas."""

import re
import unicodedata


def _sem_acentos(texto: str) -> str:
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(caractere)
    ).lower()


_INSTRUCAO_CONTROLE = re.compile(
    r"(?:\b(?:ignore|desconsidere|esqueca|disregard|forget)\b.{0,70}"
    r"\b(?:instrucoes|instructions|regras|rules|diretrizes|guidelines)\b|"
    r"\b(?:system\s+prompt|prompt\s+(?:de|do)\s+sistema|"
    r"role\s*:\s*system|(?:voce|you)\s+(?:agora\s+e|are\s+now))\b|"
    r"\[inst\]|<\|im_start\|>|"
    r"\b(?:revele|mostre|exiba|reveal|print)\b.{0,50}\b(?:prompt|instrucoes|instructions)\b|"
    r"\b(?:omita|oculte|suprima|ignore|hide|suppress)\b.{0,60}"
    r"\b(?:achados|divergencias|findings|discrepancies|erros)\b|"
    r"\b(?:responda|diga|declare|say|answer)\b.{0,60}"
    r"\b(?:aprovad[oa]|sem\s+divergencia|no\s+discrepancy)\b)",
    re.DOTALL,
)


def contem_instrucao_controle(texto: str) -> bool:
    """Detecta comandos para alterar o comportamento dos agentes em entrada não confiável.

    A detecção é uma barreira conservadora para comandos explícitos, não uma prova de que
    textos que passam são seguros. O conteúdo nunca é registrado em logs.
    """
    return bool(_INSTRUCAO_CONTROLE.search(_sem_acentos(texto)))


_PADROES_INJECAO = re.compile(
    r"(?i)(ignore\s+(?:all\s+)?previous\s+instructions|"
    r"ignore\s+(?:as\s+)?instruções(?:\s+(?:anteriores|acima))?|"
    r"desconsidere\s+(?:as\s+)?instruções(?:\s+(?:anteriores|acima))?|"
    r"system\s+prompt|você\s+agora\s+é|you\s+are\s+now)"
)


def higienizar_texto_extraido(texto: str) -> str:
    """Remove instruções de controle antes de qualquer uso por agentes.

    O texto preservado deve ser tratado exclusivamente como dado de fatura; a
    remoção é uma defesa complementar, não autorização para executar instruções
    presentes na imagem.
    """
    return _PADROES_INJECAO.sub("[conteúdo de controle removido]", texto)
