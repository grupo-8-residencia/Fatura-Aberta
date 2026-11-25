import asyncio
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import fa_api.main as api_main
from fa_agentes import Persona
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


def test_perguntar_passa_pelos_quatro_agentes_e_cita_a_norma() -> None:
    resposta = TestClient(app).post(
        "/perguntar",
        json={
            "pergunta": "Posso ser cobrado pela média quando não conseguem ler o medidor?",
            "data_referencia": "2026-03-01",
            "persona": "celina",
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert resposta.headers["cache-control"] == "no-store"
    assert not corpo["abstencao"] and corpo["citacoes"]
    assert corpo["persona"] == "celina"
    agentes = [p["agente"] for p in corpo["rastro"]]
    assert agentes[0] == "Pesquisador" and agentes[-1] == "Comunicador"


def test_perguntar_abstem_antes_da_vigencia_da_norma() -> None:
    corpo = (
        TestClient(app)
        .post(
            "/perguntar",
            json={
                "pergunta": "Como se calcula o custo de disponibilidade?",
                "data_referencia": "2021-06-01",
            },
        )
        .json()
    )
    assert corpo["abstencao"] and corpo["origem"] == "abstencao"
    assert corpo["citacoes"] == []


def test_analisar_explica_item_divergente_sem_mudar_o_nivel_a() -> None:
    corpo = (
        TestClient(app)
        .post(
            "/analisar",
            json={
                "distribuidora": "Distribuidora Sintética",
                "mes_referencia": "2026-03-01",
                "leitura_anterior": "100",
                "leitura_atual": "150",
                "consumo_kwh": "50",
                "itens": [{"descricao": "Energia", "valor": "40"}],
                "total": "55",
            },
        )
        .json()
    )
    niveis = {(a["item"], a["nivel"]) for a in corpo["achados"]}
    assert ("Total da fatura", "A") in niveis
    explicacoes = [a for a in corpo["achados"] if a["nivel"] in ("B", "C")]
    assert explicacoes and all(a["item"] == "Total da fatura" for a in explicacoes)


def test_vaga_so_volta_quando_o_trabalho_termina_mesmo_apos_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chamadas que estouram o tempo não podem abrir mais threads que o limite de concorrência."""
    import threading
    import time

    ativas = 0
    pico = 0
    trava = threading.Lock()

    def lento() -> list[Achado]:
        nonlocal ativas, pico
        with trava:
            ativas += 1
            pico = max(pico, ativas)
        time.sleep(0.15)
        with trava:
            ativas -= 1
        return []

    async def agentes_lentos(_: Fatura) -> list[Achado]:
        return await asyncio.to_thread(lento)

    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        consumo_kwh=Decimal("50"),
        total=Decimal("40"),
    )

    async def cenario() -> list[str | None]:
        monkeypatch.setattr(api_main, "_VAGAS_AGENTES", asyncio.Semaphore(1))
        monkeypatch.setattr(api_main, "TEMPO_MAXIMO_AGENTES_SEGUNDOS", 0.03)
        avisos = []
        for _ in range(4):  # requisições sucessivas, todas estouram o tempo
            _, aviso = await _executar_agentes(fatura, agentes_lentos)
            avisos.append(aviso)
        await asyncio.sleep(0.4)  # deixa terminar o que já começou
        return avisos

    avisos = asyncio.run(cenario())
    assert all(a and "não respondeu a tempo" in a for a in avisos)
    assert pico == 1  # nunca mais de uma thread de agentes ativa com limite 1


def _fatura_json() -> dict[str, str | list[dict[str, str]]]:
    return {
        "distribuidora": "Distribuidora Sintética",
        "mes_referencia": "2026-03-01",
        "leitura_anterior": "100",
        "leitura_atual": "150",
        "consumo_kwh": "50",
        "itens": [{"descricao": "Energia", "valor": "50"}],
        "total": "50",
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"fatura": _fatura_json(), "pdf_base64": "QUJD"},  # fatura e PDF juntos
        {"pdf_base64": "não é base64!!"},
        {"pdf_base64": "QUJD", "correcoes": {"nome_do_cliente": "x"}},  # campo desconhecido
        {"correcoes": {"consumo_kwh": "10"}},  # correção sem PDF
    ],
)
def test_perguntar_rejeita_payload_malformado_com_422(extra: dict[str, object]) -> None:
    resposta = TestClient(api_main.app).post(
        "/perguntar", json={"pergunta": "O consumo confere?", **extra}
    )
    assert resposta.status_code == 422


def test_perguntar_rejeita_pdf_acima_do_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "PDF_TAMANHO_MAXIMO_BYTES", 3)
    resposta = TestClient(api_main.app).post(
        "/perguntar", json={"pergunta": "O consumo confere?", "pdf_base64": "QUJDRA=="}
    )
    assert resposta.status_code == 422


def test_perguntar_com_fatura_devolve_achados_e_campos_sem_quebrar_o_schema_antigo() -> None:
    resposta = TestClient(api_main.app).post(
        "/perguntar", json={"pergunta": "O consumo confere?", "fatura": _fatura_json()}
    )
    corpo = resposta.json()
    assert resposta.status_code == 200 and corpo["modo"] == "fatura"
    assert corpo["achados_motor"] and corpo["campos_fatura"]["consumo_kwh"] == "50"
    assert {"resposta", "mensagem", "persona", "citacoes", "abstencao", "rastro"} <= set(corpo)


def test_saida_com_termo_vedado_e_substituida_pela_guarda_rf15() -> None:
    bruto = api_main.RespostaPerguntaAPI(
        resposta="Isso é ilegal.",
        mensagem="Peça restituição.",
        persona=Persona.MARCIA,
        citacoes=[],
        abstencao=False,
        origem="x",
        motivo_abstencao="processar",
        rastro=[],
        aviso="ação judicial",
    )
    limpo = api_main._sanitizar_saida(bruto)
    for texto in (limpo.resposta, limpo.mensagem, limpo.motivo_abstencao, limpo.aviso):
        assert texto == api_main.MSG_SAIDA_BLOQUEADA
