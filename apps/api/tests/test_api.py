import asyncio
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from fa_api.main import _executar_agentes, app
from fa_contratos import Achado, Fatura, ItemFatura


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


def test_falha_dos_agentes_preserva_analise_deterministica() -> None:
    async def falhar(_: Fatura) -> list[Achado]:
        raise RuntimeError("serviço indisponível")

    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        leitura_anterior=Decimal("100"),
        leitura_atual=Decimal("150"),
        consumo_kwh=Decimal("50"),
        itens=[ItemFatura(descricao="Energia", valor=Decimal("40"))],
        total=Decimal("40"),
    )

    adicionais, aviso = asyncio.run(_executar_agentes(fatura, falhar))

    assert adicionais == []
    assert aviso == "A análise adicional está indisponível; os achados A seguem disponíveis."
