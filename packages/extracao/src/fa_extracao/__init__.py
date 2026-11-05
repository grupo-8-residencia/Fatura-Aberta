"""Funções seguras de fronteira para a extração documental e multimodal (F4)."""

import re

from fa_extracao.anonimizacao import anonimizar
from fa_extracao.erros import ErroExtracao
from fa_extracao.parser import parse_pdf, parse_texto

__version__ = "0.1.0"
FRENTE = "F4"

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


__all__ = [
    "ErroExtracao",
    "FRENTE",
    "anonimizar",
    "higienizar_texto_extraido",
    "parse_pdf",
    "parse_texto",
]
