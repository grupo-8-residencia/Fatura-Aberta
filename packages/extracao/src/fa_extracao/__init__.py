"""Funções seguras de fronteira para a extração documental e multimodal (F4)."""

from fa_extracao.anonimizacao import anonimizar
from fa_extracao.candidata import ExtratorDeFoto, FaturaCandidata, ItemCandidato, extrair_candidata
from fa_extracao.confirmacao import (
    Confirmacao,
    ConfirmacaoPendente,
    analisar_foto,
    campos_pendentes,
    confirmar,
)
from fa_extracao.erros import ErroExtracao
from fa_extracao.higienizacao import higienizar_texto_extraido
from fa_extracao.parser import parse_pdf, parse_texto

__version__ = "0.1.0"
FRENTE = "F4"

__all__ = [
    "Confirmacao",
    "ConfirmacaoPendente",
    "ErroExtracao",
    "ExtratorDeFoto",
    "FRENTE",
    "FaturaCandidata",
    "ItemCandidato",
    "analisar_foto",
    "anonimizar",
    "campos_pendentes",
    "confirmar",
    "extrair_candidata",
    "higienizar_texto_extraido",
    "parse_pdf",
    "parse_texto",
]
