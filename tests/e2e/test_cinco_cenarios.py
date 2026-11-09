"""Cinco cenários sintéticos exercitam API, motor e fallback de evidência."""

import pytest
from fastapi.testclient import TestClient

from fa_api.main import app


@pytest.mark.parametrize(
    (
        "anterior",
        "atual",
        "consumo",
        "valor_item",
        "total",
        "consumo_confere",
        "total_confere",
    ),
    [
        ("100", "150", "50", "40", "40", True, True),
        ("0", "80", "80", "80", "80", True, True),
        ("200", "210", "11", "12", "12", False, True),
        ("100", "100", "0", "20", "21", True, False),
        ("300", "360", "61", "70", "71", False, False),
    ],
    ids=[
        "leituras-conferem",
        "primeira-faixa",
        "divergencia-consumo",
        "divergencia-total",
        "divergencias-combinadas",
    ],
)
def test_cinco_cenarios_ponta_a_ponta(
    anterior: str,
    atual: str,
    consumo: str,
    valor_item: str,
    total: str,
    consumo_confere: bool,
    total_confere: bool,
) -> None:
    resposta = TestClient(app).post(
        "/analisar",
        json={
            "distribuidora": "Distribuidora Sintética",
            "mes_referencia": "2026-03-01",
            "leitura_anterior": anterior,
            "leitura_atual": atual,
            "consumo_kwh": consumo,
            "itens": [{"descricao": "Energia", "valor": valor_item}],
            "total": total,
        },
    )
    assert resposta.status_code == 200
    achados = {item["item"]: item for item in resposta.json()["achados"]}
    consumo_medido = achados["Consumo medido"]
    total_fatura = achados["Total da fatura"]

    assert (consumo_medido["valor_esperado"] == consumo_medido["valor_cobrado"]) is consumo_confere
    assert (total_fatura["valor_esperado"] == total_fatura["valor_cobrado"]) is total_confere
