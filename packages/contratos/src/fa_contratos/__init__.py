"""Contratos de dados compartilhados por todas as frentes.

Mudanças neste pacote exigem 2 aprovações (ver CONTRIBUTING.md) e a label `contrato`.
"""

from fa_contratos.achado import Achado, Categoria, Nivel, categoria_derivada
from fa_contratos.citacao import Citacao
from fa_contratos.fatura import Fatura, ItemFatura
from fa_contratos.registro import RegistroAuditavel

__version__ = "1.1.0"
CONTRATO_VERSAO = "contratos-v1"

__all__ = [
    "CONTRATO_VERSAO",
    "Achado",
    "Categoria",
    "Citacao",
    "Fatura",
    "ItemFatura",
    "Nivel",
    "RegistroAuditavel",
    "__version__",
    "categoria_derivada",
]
