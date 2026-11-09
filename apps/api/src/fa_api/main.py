"""API para conferência determinística e análise complementar de agentes."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from threading import Lock
from time import perf_counter

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fa_agentes import analisar_com_agentes
from fa_api import __version__
from fa_contratos import Achado, Fatura
from fa_motor import analisar_nivel_a

logger = logging.getLogger("fa_api")
TEMPO_MAXIMO_AGENTES_SEGUNDOS = 15
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


app = FastAPI(title="Fatura Aberta - API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    adicionais, aviso = await _executar_agentes(fatura, analisar_com_agentes)
    metricas.registrar(perf_counter() - inicio)
    return RespostaAnalise(achados=[*achados, *adicionais], aviso=aviso)
