"""B5: Analista Normativo seguido do Auditor, em uma chamada."""

from __future__ import annotations

from datetime import date

from fa_agentes.analista import AnalistaNormativo
from fa_agentes.auditor import Auditor, ResultadoAuditoria
from fa_agentes.llm import ClienteLLM
from fa_contratos import Achado
from fa_rag import IndiceHibrido
from fa_rag.sintese import LIMIAR_PADRAO


def responder_com_auditoria(
    pergunta: str | None = None,
    *,
    data_referencia: date,
    indice: IndiceHibrido,
    gerador: ClienteLLM,
    juiz: ClienteLLM | None = None,
    achado: Achado | None = None,
    limiar: float = LIMIAR_PADRAO,
) -> ResultadoAuditoria:
    """Pergunta (ou achado do motor) -> afirmações citadas -> resposta auditada ou abstenção."""
    analista = AnalistaNormativo(indice, gerador, limiar=limiar)
    relatorio = analista.analisar(pergunta, data_referencia=data_referencia, achado=achado)
    return Auditor(juiz).auditar(relatorio)
