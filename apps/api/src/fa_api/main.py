"""API para conferência determinística e análise complementar de agentes."""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date
from threading import Lock
from time import perf_counter
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from fa_agentes import Persona, analisar_com_agentes, obter_orquestrador
from fa_api import __version__
from fa_contratos import Achado, Citacao, Fatura
from fa_motor import analisar_nivel_a

logger = logging.getLogger("fa_api")
# Com LLM local cada chamada leva ~25 s; sem LLM (padrão) os agentes respondem em milissegundos.
TEMPO_MAXIMO_AGENTES_SEGUNDOS = float(os.getenv("FA_AGENTES_TIMEOUT_S", "15"))
ExecutarAgentes = Callable[[Fatura], Awaitable[list[Achado]]]


class MetricasAnalise:
    """Contadores em memória para acompanhar a operação local da API."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requisicoes = 0
        self._duracao_total_segundos = 0.0

    def registrar(self, duracao_segundos: float) -> None:
        with self._lock:
            self._requisicoes += 1
            self._duracao_total_segundos += duracao_segundos

    def resumo(self) -> dict[str, float | int]:
        with self._lock:
            media = self._duracao_total_segundos / self._requisicoes if self._requisicoes else 0.0
            return {
                "requisicoes_analisadas": self._requisicoes,
                "duracao_media_segundos": round(media, 6),
            }


class RespostaAnalise(BaseModel):
    """Achados determinísticos para a fatura recebida."""

    achados: list[Achado]
    aviso: str | None = None


class PedidoPergunta(BaseModel):
    """Pergunta regulatória com a data em que a regra deve estar vigente."""

    pergunta: str = Field(min_length=3, max_length=500)
    data_referencia: date = Field(default_factory=date.today)
    persona: Persona = Persona.MARCIA


class PassoRastro(BaseModel):
    agente: str
    acao: str
    detalhe: str
    duracao_s: float


class RespostaPerguntaAPI(BaseModel):
    """Resposta dos agentes: texto para a persona, citações, origem e rastro da colaboração."""

    resposta: str
    mensagem: str
    persona: Persona
    citacoes: list[Citacao]
    abstencao: bool
    origem: str
    motivo_abstencao: str
    rastro: list[PassoRastro]


def origens_permitidas() -> list[str]:
    """Inclui a origem pública configurada sem liberar origens arbitrárias."""
    locais = ["http://localhost:3000", "http://127.0.0.1:3000"]
    publicas = []
    for valor in os.getenv("FA_CORS_ORIGINS", "").split(","):
        origem = valor.strip().rstrip("/")
        if not origem:
            continue
        partes = urlsplit(origem)
        if (
            partes.scheme != "https"
            or not partes.hostname
            or partes.username
            or partes.password
            or partes.path
            or partes.query
            or partes.fragment
        ):
            raise ValueError("FA_CORS_ORIGINS deve conter apenas origens HTTPS exatas")
        publicas.append(origem)
    return [*locais, *publicas]


app = FastAPI(title="Fatura Aberta - API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_permitidas(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)
metricas = MetricasAnalise()


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok", "versao": __version__}


@app.get("/metricas")
def obter_metricas() -> dict[str, float | int]:
    """Expõe métricas operacionais sem registrar conteúdo de faturas."""
    return metricas.resumo()


async def _executar_agentes(
    fatura: Fatura, executar: ExecutarAgentes
) -> tuple[list[Achado], str | None]:
    try:
        return await asyncio.wait_for(executar(fatura), timeout=TEMPO_MAXIMO_AGENTES_SEGUNDOS), None
    except TimeoutError:
        logger.warning("agentes excederam o tempo limite")
        return [], "A análise adicional não respondeu a tempo; os achados A seguem disponíveis."
    except Exception as erro:
        logger.warning("agentes indisponíveis: %s", type(erro).__name__)
        return [], "A análise adicional está indisponível; os achados A seguem disponíveis."


@app.post("/analisar", response_model=RespostaAnalise)
async def analisar(fatura: Fatura, response: Response) -> RespostaAnalise:
    """Preserva o nível A quando agentes falham ou excedem o tempo máximo."""
    inicio = perf_counter()
    response.headers["Cache-Control"] = "no-store"
    achados = analisar_nivel_a(fatura)
    adicionais, aviso = await _executar_agentes(fatura, lambda f: analisar_com_agentes(f, achados))
    metricas.registrar(perf_counter() - inicio)
    return RespostaAnalise(achados=[*achados, *adicionais], aviso=aviso)


@app.post("/perguntar", response_model=RespostaPerguntaAPI)
async def perguntar(pedido: PedidoPergunta, response: Response) -> RespostaPerguntaAPI:
    """Pergunta regulatória respondida pelos 4 agentes (Pesquisador a Comunicador)."""
    response.headers["Cache-Control"] = "no-store"
    try:
        r = await asyncio.wait_for(
            asyncio.to_thread(
                obter_orquestrador().responder_pergunta,
                pedido.pergunta,
                data_referencia=pedido.data_referencia,
                persona=pedido.persona,
            ),
            timeout=TEMPO_MAXIMO_AGENTES_SEGUNDOS,
        )
    except TimeoutError as erro:
        raise HTTPException(504, "Os agentes não responderam a tempo.") from erro
    return RespostaPerguntaAPI(
        resposta=r.resposta.texto,
        mensagem=r.mensagem.texto,
        persona=r.mensagem.persona,
        citacoes=list(r.resposta.citacoes),
        abstencao=r.abstencao,
        origem=r.origem,
        motivo_abstencao=r.motivo_abstencao,
        rastro=[
            PassoRastro(agente=p.agente, acao=p.acao, detalhe=p.detalhe, duracao_s=p.duracao_s)
            for p in r.rastro
        ],
    )
