import asyncio
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import fa_api.main as api_main
from fa_api.main import _executar_agentes, app
from fa_contratos import Achado, Fatura, ItemFatura


def test_saude_responde_ok() -> None:
    resposta = TestClient(app).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok"


def test_origens_publicas_configuradas_sem_coringa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FA_CORS_ORIGINS", " https://fatura.example/ , https://outra.example ")
    assert api_main.origens_permitidas() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://fatura.example",
        "https://outra.example",
    ]


@pytest.mark.parametrize(
    "origem",
    [
        "*",
        "http://fatura.example",
        "https://fatura.example/caminho",
        "https://usuario:senha@fatura.example",
    ],
)
def test_origens_publicas_invalidas_sao_rejeitadas(
    monkeypatch: pytest.MonkeyPatch, origem: str
) -> None:
    monkeypatch.setenv("FA_CORS_ORIGINS", origem)
    with pytest.raises(ValueError, match="HTTPS exatas"):
        api_main.origens_permitidas()


def test_metricas_nao_expoem_dados_da_fatura() -> None:
    resposta = TestClient(app).get("/metricas")
    assert resposta.status_code == 200
    assert set(resposta.json()) == {"requisicoes_analisadas", "duracao_media_segundos"}


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


def test_timeout_dos_agentes_preserva_analise_deterministica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def demorar(_: Fatura) -> list[Achado]:
        await asyncio.sleep(0.01)
        return []

    monkeypatch.setattr(api_main, "TEMPO_MAXIMO_AGENTES_SEGUNDOS", 0.001)
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        consumo_kwh=Decimal("50"),
        total=Decimal("40"),
    )

    adicionais, aviso = asyncio.run(_executar_agentes(fatura, demorar))

    assert adicionais == []
    assert aviso == "A análise adicional não respondeu a tempo; os achados A seguem disponíveis."
