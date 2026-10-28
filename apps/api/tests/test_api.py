from fastapi.testclient import TestClient

from fa_api.main import app


def test_saude_responde_ok() -> None:
    resposta = TestClient(app).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"
