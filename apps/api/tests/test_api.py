from fastapi.testclient import TestClient

from fa_api.main import app


def test_saude_responde_ok() -> None:
    resposta = TestClient(app).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_analisar_devolve_achados_nivel_a_sem_cache() -> None:
    resposta = TestClient(app).post(
        "/analisar",
        json={
            "distribuidora": "Distribuidora Sintética",
            "mes_referencia": "2026-03-01",
            "leitura_anterior": "100",
            "leitura_atual": "150",
            "consumo_kwh": "50",
            "itens": [{"descricao": "Energia", "valor": "40"}],
            "total": "40",
        },
    )
    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "no-store"
    assert {achado["item"] for achado in resposta.json()["achados"]} == {
        "Consumo medido",
        "Total da fatura",
    }
