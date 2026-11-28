"""Nível B na API (#178): TUSD+TE conferido, bandeira e 10/2026 abstêm, nível A preservado."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

import fa_api.main as api_main
from fa_agentes import verificar_linguagem
from fa_api.main import MSG_TABELA_INDISPONIVEL, app
from fa_contratos import Fatura, ItemFatura


def _fatura(mes: date, tusd: str, te: str, *, aliquota: str | None = "0.12") -> dict[str, Any]:
    qtd = Decimal("100")
    fatura = Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=mes,
        leitura_anterior=Decimal("1000"),
        leitura_atual=Decimal("1100"),
        consumo_kwh=qtd,
        aliquota_icms=Decimal(aliquota) if aliquota is not None else None,
        bandeira="Verde",
        itens=[
            ItemFatura(
                descricao="Consumo-TUSD",
                quantidade=qtd,
                unidade="kWh",
                tarifa=Decimal(tusd),
                valor=(qtd * Decimal(tusd)).quantize(Decimal("0.01")),
            ),
            ItemFatura(
                descricao="Consumo-TE",
                quantidade=qtd,
                unidade="kWh",
                tarifa=Decimal(te),
                valor=(qtd * Decimal(te)).quantize(Decimal("0.01")),
            ),
        ],
        total=(qtd * (Decimal(tusd) + Decimal(te))).quantize(Decimal("0.01")),
    )
    return fatura.model_dump(mode="json")


def _b(achados: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in achados if a["nivel"] == "B"]


def test_tusd_te_divergente_gera_nivel_b_com_citacao() -> None:
    corpo = (
        TestClient(app)
        .post("/analisar", json=_fatura(date(2026, 6, 1), "0.50000", "0.40000"))
        .json()
    )
    tusd = next(a for a in _b(corpo["achados"]) if a["item"] == "Tarifa TUSD+TE")
    assert tusd["abstencao"] is False
    assert "diverge da tabela oficial que conseguimos obter" in tusd["descricao"]
    assert tusd["citacoes"], "nível B sem abstenção exige citação da tabela"


def test_bandeira_sempre_abstem_no_nivel_b() -> None:
    corpo = (
        TestClient(app)
        .post("/analisar", json=_fatura(date(2026, 6, 1), "0.42392", "0.40280"))
        .json()
    )
    bandeira = next(a for a in _b(corpo["achados"]) if a["item"] == "Bandeira tarifária")
    assert bandeira["abstencao"] is True
    assert "não é conferida nesta versão" in bandeira["descricao"]


def test_outubro_de_2026_abstem_no_tusd() -> None:
    corpo = (
        TestClient(app)
        .post("/analisar", json=_fatura(date(2026, 10, 1), "0.50000", "0.40000"))
        .json()
    )
    tusd = next(a for a in _b(corpo["achados"]) if a["item"] == "Tarifa TUSD+TE")
    assert tusd["abstencao"] is True
    assert "regra do mês de reajuste" in tusd["descricao"]


def test_textos_do_nivel_b_passam_no_rf15() -> None:
    corpo = (
        TestClient(app)
        .post("/analisar", json=_fatura(date(2026, 6, 1), "0.50000", "0.40000"))
        .json()
    )
    for achado in _b(corpo["achados"]):
        assert verificar_linguagem(achado["descricao"]) == [], achado["descricao"]


def test_nivel_a_segue_quando_a_tabela_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    def tabela_quebrada(_: Fatura) -> None:
        raise OSError("tabela ausente")

    monkeypatch.setattr(api_main, "analisar_nivel_b_api", tabela_quebrada)
    corpo = (
        TestClient(app)
        .post("/analisar", json=_fatura(date(2026, 6, 1), "0.42392", "0.40280"))
        .json()
    )
    assert corpo["aviso"] == MSG_TABELA_INDISPONIVEL
    assert corpo["achados"], "o nível A continua disponível"
    assert any(a["nivel"] == "A" for a in corpo["achados"])
    assert not _b(corpo["achados"]), "sem tabela, nenhum achado de nível B"


def test_perguntar_com_fatura_devolve_o_nivel_b_em_achados_motor() -> None:
    resposta = TestClient(app).post(
        "/perguntar",
        json={
            "pergunta": "O consumo informado confere com as leituras do medidor?",
            "data_referencia": "2026-06-01",
            "fatura": _fatura(date(2026, 6, 1), "0.42392", "0.40280"),
        },
    )
    assert resposta.status_code == 200, resposta.text
    itens = {a["item"] for a in _b(resposta.json()["achados_motor"])}
    assert {"Tarifa TUSD+TE", "Bandeira tarifária"} <= itens
