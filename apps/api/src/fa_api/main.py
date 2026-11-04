"""API para conferência determinística e análise complementar de agentes."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Response
from pydantic import BaseModel

from fa_agentes import analisar_com_agentes
from fa_api import __version__
from fa_contratos import Achado, Fatura
from fa_motor import analisar_nivel_a

logger = logging.getLogger("fa_api")
TEMPO_MAXIMO_AGENTES_SEGUNDOS = 15
ExecutarAgentes = Callable[[Fatura], Awaitable[list[Achado]]]


class RespostaAnalise(BaseModel):
    """Achados determinísticos para a fatura recebida."""

    achados: list[Achado]
    aviso: str | None = None


app = FastAPI(title="Fatura Aberta - API", version=__version__)


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok", "versao": __version__}


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
    response.headers["Cache-Control"] = "no-store"
    achados = analisar_nivel_a(fatura)
    adicionais, aviso = await _executar_agentes(fatura, analisar_com_agentes)
    return RespostaAnalise(achados=[*achados, *adicionais], aviso=aviso)
