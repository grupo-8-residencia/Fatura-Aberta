"""Contrato de integração dos agentes (F5)."""

from fa_agentes.analista import (
    Afirmacao,
    AnalistaNormativo,
    RelatorioAnalise,
    consulta_do_achado,
)
from fa_agentes.auditor import Auditor, Motivo, Problema, ResultadoAuditoria, para_achado
from fa_agentes.linguagem import Violacao, linguagem_permitida, verificar_linguagem
from fa_agentes.llm import (
    ClienteFalso,
    ClienteLLM,
    ClienteOllama,
    RespostaLLM,
    criar_cliente,
    metadados_rodada,
)
from fa_agentes.pipeline import responder_com_auditoria
from fa_contratos import Achado, Fatura

__version__ = "0.1.0"
FRENTE = "F5"


async def analisar_com_agentes(_: Fatura) -> list[Achado]:
    """Ponto de extensão para achados B/C, sem alterar o nível A."""
    return []


__all__ = [
    "Afirmacao",
    "AnalistaNormativo",
    "Auditor",
    "Motivo",
    "Problema",
    "RelatorioAnalise",
    "ResultadoAuditoria",
    "consulta_do_achado",
    "para_achado",
    "responder_com_auditoria",
    "ClienteFalso",
    "ClienteLLM",
    "ClienteOllama",
    "FRENTE",
    "RespostaLLM",
    "Violacao",
    "analisar_com_agentes",
    "criar_cliente",
    "linguagem_permitida",
    "metadados_rodada",
    "verificar_linguagem",
]
