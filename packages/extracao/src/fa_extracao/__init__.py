"""Extração documental e multimodal (F4)."""

from fa_extracao.anonimizacao import anonimizar
from fa_extracao.erros import ErroExtracao
from fa_extracao.parser import parse_pdf, parse_texto

__version__ = "0.1.0"
FRENTE = "F4"

__all__ = ["ErroExtracao", "anonimizar", "parse_pdf", "parse_texto"]
