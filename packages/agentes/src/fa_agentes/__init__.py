"""Contrato de integração dos agentes (F5)."""

from fa_contratos import Achado, Fatura

__version__ = "0.1.0"
FRENTE = "F5"


async def analisar_com_agentes(_: Fatura) -> list[Achado]:
    """Ponto de extensão para achados B/C, sem alterar o nível A."""
    return []
