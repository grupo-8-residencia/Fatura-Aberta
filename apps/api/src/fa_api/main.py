"""API para a conferência determinística de nível A."""

from fastapi import FastAPI, Response
from pydantic import BaseModel

from fa_api import __version__
from fa_contratos import Achado, Fatura
from fa_motor import analisar_nivel_a


class RespostaAnalise(BaseModel):
    """Achados determinísticos para a fatura recebida."""

    achados: list[Achado]


app = FastAPI(title="Fatura Aberta - API", version=__version__)


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok", "versao": __version__}


@app.post("/analisar", response_model=RespostaAnalise)
def analisar(fatura: Fatura, response: Response) -> RespostaAnalise:
    """Confere apenas dados presentes na própria fatura, sem persistência."""
    response.headers["Cache-Control"] = "no-store"
    return RespostaAnalise(achados=analisar_nivel_a(fatura))
