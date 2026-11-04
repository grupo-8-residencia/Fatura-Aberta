"""Cinco cenários sintéticos exercitam API, motor e fallback de evidência."""

import pytest
from fastapi.testclient import TestClient

from fa_api.main import app


@pytest.mark.parametrize(
    ("anterior", "atual", "consumo", "total", "confere"),
    [
        ("100", "150", "50", "40", True),
        ("0", "80", "80", "80", True),
        ("200", "210", "11", "12", False),
        ("100", "100", "0", "0", True),
        ("300", "360", "60", "70", True),
    ],
    ids=[
        "leituras-conferem",
        "primeira-faixa",
        "divergencia-consumo",
        "sem-consumo",
        "total-conferente",
    ],
)
def test_cinco_cenarios_ponta_a_ponta(
    anterior: str, atual: str, consumo: str, total: str, confere: bool
) -> None:
    resposta = TestClient(app).post(
        "/analisar",
        json={
            "distribuidora": "Distribuidora Sintética",
            "mes_referencia": "2026-03-01",
            "leitura_anterior": anterior,
            "leitura_atual": atual,
            "consumo_kwh": consumo,
            "itens": [{"descricao": "Energia", "valor": total}],
            "total": total,
        },
    )
    assert resposta.status_code == 200
    achado = next(item for item in resposta.json()["achados"] if item["item"] == "Consumo medido")
    assert ("não confere" not in achado["descricao"]) is confere
