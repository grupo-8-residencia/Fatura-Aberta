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
from fa_extracao.erros import ErroExtracao, ForaDoEscopo, VlmIndisponivel
from fa_extracao.higienizacao import contem_instrucao_controle, higienizar_texto_extraido
from fa_extracao.parser import parse_pdf, parse_texto
from fa_extracao.vlm import ExtratorOllama, criar_extrator, formato_da_imagem

__version__ = "0.1.0"
FRENTE = "F4"

__all__ = [
    "Confirmacao",
    "ConfirmacaoPendente",
    "ErroExtracao",
    "ForaDoEscopo",
    "VlmIndisponivel",
    "ExtratorDeFoto",
    "ExtratorOllama",
    "FRENTE",
    "FaturaCandidata",
    "ItemCandidato",
    "analisar_foto",
    "anonimizar",
    "campos_pendentes",
    "confirmar",
    "contem_instrucao_controle",
    "criar_extrator",
    "extrair_candidata",
    "formato_da_imagem",
    "higienizar_texto_extraido",
    "parse_pdf",
    "parse_texto",
]
