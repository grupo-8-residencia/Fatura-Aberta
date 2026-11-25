"""Sistema multiagentes do Fatura Aberta (F5): Pesquisador, Analista, Auditor e Comunicador."""

import asyncio
from collections.abc import Sequence
from functools import lru_cache

from fa_agentes.analista import (
    Afirmacao,
    AnalistaNormativo,
    RelatorioAnalise,
    consulta_do_achado,
)
from fa_agentes.auditor import (
    Auditor,
    Motivo,
    Problema,
    ResultadoAuditoria,
    contradiz_motor,
    divergente,
    para_achado,
)
from fa_agentes.comunicador import Comunicador, Mensagem, Persona
from fa_agentes.linguagem import Violacao, linguagem_permitida, verificar_linguagem
from fa_agentes.llm import (
    ClienteFalso,
    ClienteLLM,
    ClienteOllama,
    RespostaLLM,
    criar_cliente,
    metadados_rodada,
)
from fa_agentes.orquestrador import (
    Origem,
    Orquestrador,
    Passo,
    RespostaPergunta,
    ResultadoFatura,
)
from fa_agentes.pesquisador import Evidencias, MotivoAbstencao, Pesquisador
from fa_agentes.pipeline import responder_com_auditoria
from fa_contratos import Achado, Fatura
from fa_rag import IndiceHibrido

__version__ = "0.1.0"
FRENTE = "F5"


@lru_cache(maxsize=1)
def obter_orquestrador() -> Orquestrador:
    """Orquestrador único do processo: índice do corpus e LLM escolhidos por ambiente.

    Sem ``FA_LLM_PROVEDOR`` o gerador é o cliente falso: o Analista não redige nada, o Auditor
    barra e o fluxo entrega a resposta extrativa do Pesquisador (modo offline, sem LLM).
    """
    return Orquestrador(IndiceHibrido.do_corpus(), criar_cliente("gerador"))


async def analisar_com_agentes(
    fatura: Fatura, achados_motor: Sequence[Achado] | None = None
) -> list[Achado]:
    """Explica, com norma citada, os itens que o motor marcou como divergentes ou sem dados.

    Não altera o nível A: devolve só achados de nível C (explicação com norma citada ou abstenção).
    O nível B (tabela da ANEEL) não é gerado aqui. Sem os achados do motor não há o que explicar.
    """
    if not achados_motor:
        return []
    resultado = await asyncio.to_thread(
        obter_orquestrador().analisar_fatura, fatura, achados_motor=list(achados_motor)
    )
    return list(resultado.explicacoes)


__all__ = [
    "Comunicador",
    "Evidencias",
    "Mensagem",
    "MotivoAbstencao",
    "Orquestrador",
    "Origem",
    "Passo",
    "Persona",
    "Pesquisador",
    "RespostaPergunta",
    "ResultadoFatura",
    "contradiz_motor",
    "divergente",
    "obter_orquestrador",
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
