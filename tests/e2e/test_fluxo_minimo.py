"""Teste ponta a ponta mínimo: contrato -> JSON -> API no ar.

Roda sempre no CI. Cresce a cada sprint (motor na S2, agentes na S4, 5 cenários na S6).
"""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from fa_api.main import app
from fa_contratos import Achado, Fatura, Nivel


def test_fatura_sintetica_atravessa_json_e_api_responde() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        consumo_kwh=Decimal("100"),
        total=Decimal("80.00"),
    )
    assert Fatura.model_validate_json(fatura.model_dump_json()) == fatura

    achado = Achado(item="Total", nivel=Nivel.A, descricao="Soma das linhas confere.")
    assert achado.nivel is Nivel.A

    assert TestClient(app).get("/saude").status_code == 200
