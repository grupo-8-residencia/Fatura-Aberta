"""Higienização do texto lido de imagem: remove instruções de controle embutidas."""

import re

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
