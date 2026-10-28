"""Esqueleto da API. O `POST /analisar` entra na Sprint 2 (motor nível A)."""

from fastapi import FastAPI

from fa_api import __version__

app = FastAPI(title="Fatura Aberta - API", version=__version__)


@app.get("/saude")
def saude() -> dict[str, str]:
    """Verificação de saúde para o docker compose e para o CI."""
    return {"status": "ok", "versao": __version__}
