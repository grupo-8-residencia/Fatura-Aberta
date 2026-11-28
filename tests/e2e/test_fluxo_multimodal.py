"""Fluxo multimodal (S5-05): extração de PDF com confirmação + pergunta em texto.

Todos os PDFs são sintéticos, gerados em memória, sem nenhum dado pessoal.
"""

import asyncio
import base64
import json
import logging
from collections.abc import Iterator
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import fa_api.main as api_main
from fa_agentes import verificar_linguagem
from fa_api.main import app

PERGUNTA = "O consumo informado confere com as leituras do medidor?"

LINHAS = [
    "Consumo-TUSD kWh 120,00 0,50000000 60,00 2,50 60,00 12,00 7,20 0,42000000",
    "Consumo-TE kWh 120,00 0,47000000 56,40 2,35 56,40 12,00 6,77 0,40000000",
    "Acrés. Band. AMARELA 3,00 0,10 3,00 12,00 0,36",
    "Ilum. Púb. Distrital 12,00",
    "CREDITO-TESTE-01/02 1,00-",
    "NEOENERGIA DISTRIBUIÇÃO BRASÍLIA S.A",
    "CLASSIFICAÇÃO: B1 RESIDENCIAL -RESIDENCIAL",
    "DATAS DE LEITURAS LEITURA ANTERIOR 01/06/2026 LEITURA ATUAL 01/07/2026",
    "REF:MÊS/ANO",
    "06/2026",
    "VENCIMENTO",
    "15/07/2026",
    "TOTAL A PAGAR R$",
    "130,40",
    "PIS 100,00 0,84 0,84",
    "COFINS 100,00 3,93 3,93",
    "ICMS 119,40 12,00 14,33",
    "MEDIDOR GRANDEZAS POSTOS LEITURA LEITURA CONST. CONSUMO",
    "1234567890 Energia Ativa Único 1.000,00 1.120,00 1,00000 120,00",
    "1234567890 Energia Ativa Único 1.000,00 1.000,00 1,00000 0,00",
    "Na data da leitura a bandeira em vigor é a Amarela.",
]
PADROES_PII = ("CPF", "123.456", "ENDEREÇO", "NOME DO CLIENTE", "INSTALAÇÃO 0")


def _pdf(linhas: list[str]) -> bytes:
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for linha in linhas:
        pagina.drawString(50, y, linha)
        y -= 18
    pagina.save()
    return buffer.getvalue()


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode()


def _pdf_vazio() -> bytes:
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    pagina.showPage()
    pagina.save()
    return buffer.getvalue()


FATURA_OK: dict[str, Any] = {
    "distribuidora": "Distribuidora Sintética",
    "mes_referencia": "2026-03-01",
    "leitura_anterior": "100",
    "leitura_atual": "150",
    "consumo_kwh": "50",
    "itens": [{"descricao": "Energia", "valor": "40"}],
    "total": "40",
}


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    yield TestClient(app)


def _extrair(cliente: TestClient, dados: bytes) -> dict[str, Any]:
    r = cliente.post("/extrair", json={"pdf_base64": _b64(dados)})
    assert r.status_code == 200, r.text
    corpo: dict[str, Any] = r.json()
    return corpo


def _post(cliente: TestClient, corpo: dict[str, Any]) -> dict[str, Any]:
    r = cliente.post("/perguntar", json=corpo)
    assert r.status_code == 200, r.text
    dados: dict[str, Any] = r.json()
    return dados


def _textos(d: dict[str, Any]) -> list[str]:
    saida = [d["resposta"], d["mensagem"], d["motivo_abstencao"], d.get("aviso") or ""]
    saida += [a["descricao"] for a in d["achados_motor"]]
    saida += [p["detalhe"] for p in d["rastro"]]
    return saida


def test_1_texto_sozinho_continua_retrocompativel(cliente: TestClient) -> None:
    d = _post(
        cliente,
        {
            "pergunta": "Posso ser cobrado pela média quando não conseguem ler o medidor?",
            "data_referencia": "2026-03-01",
            "persona": "celina",
        },
    )
    assert d["modo"] == "texto"
    assert d["citacoes"]
    assert d["achados_motor"] == [] and d["campos_fatura"] == {}


def test_2_extrair_pdf_devolve_campos_sem_rodar_motor_nem_agentes(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def proibido(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("análise não pode iniciar antes da confirmação do usuário")

    monkeypatch.setattr(api_main, "analisar_nivel_a", proibido)
    monkeypatch.setattr(api_main, "obter_orquestrador", proibido)
    extraido = _extrair(cliente, _pdf(LINHAS))
    assert extraido["erro"] is None
    fatura = extraido["fatura"]
    assert fatura is not None
    assert fatura["mes_referencia"] == "2026-06-01"
    assert fatura["consumo_kwh"] in ("120", "120.00")


def test_2b_perguntar_rejeita_pdf_nao_confirmado_com_422(cliente: TestClient) -> None:
    r = cliente.post("/perguntar", json={"pergunta": PERGUNTA, "pdf_base64": _b64(_pdf(LINHAS))})
    assert r.status_code == 422


def test_3_fluxo_confirmado_pdf_para_perguntar_cita_campos_e_pergunta(cliente: TestClient) -> None:
    extraido = _extrair(cliente, _pdf(LINHAS))
    fatura = extraido["fatura"]
    assert fatura is not None
    d = _post(cliente, {"pergunta": PERGUNTA, "fatura": fatura})
    assert d["modo"] == "fatura"
    assert d["campos_fatura"]["mes_referencia"] == "06/2026"
    assert d["campos_fatura"]["consumo_kwh"] == "120.00"
    assert d["achados_motor"]
    agentes = [(p["agente"], p["acao"]) for p in d["rastro"]]
    assert ("Motor", "analisar_nivel_a") in agentes
    assert any(a == "Pesquisador" for a, _ in agentes)
    assert PERGUNTA in d["resposta"]
    assert "120" in d["resposta"] and "06/2026" in d["resposta"]
    assert "Consumo medido" in d["resposta"]
    assert d["citacoes"], "resposta sem citação normativa"
    assert not d["abstencao"]


def test_4_pdf_corrompido_devolve_mensagem_clara_sem_conclusao(cliente: TestClient) -> None:
    d = _extrair(cliente, b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog")
    assert d["fatura"] is None and d["motivo"] == "pdf_invalido"
    assert d["erro"] and "corrompido" in d["erro"]


def test_4b_arquivo_sem_assinatura_de_pdf_e_rejeitado_com_422(cliente: TestClient) -> None:
    r = cliente.post("/extrair", json={"pdf_base64": _b64(b"isto nao e um pdf")})
    assert r.status_code == 422


def test_4c_pdf_protegido_por_senha(cliente: TestClient) -> None:
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter(clone_from=PdfReader(BytesIO(_pdf(LINHAS))))
    escritor.encrypt("senha-de-teste")
    saida = BytesIO()
    escritor.write(saida)
    d = _extrair(cliente, saida.getvalue())
    assert d["fatura"] is None and d["motivo"] == "pdf_protegido"
    assert d["erro"] and "senha" in d["erro"]


def test_4d_pdf_com_paginas_demais(cliente: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "PDF_PAGINAS_MAXIMAS", 1)
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    for _ in range(2):
        pagina.drawString(50, 800, "pagina")
        pagina.showPage()
    pagina.save()
    d = _extrair(cliente, buffer.getvalue())
    assert d["fatura"] is None and d["motivo"] == "pdf_muitas_paginas"


def test_5_pdf_sem_camada_de_texto(cliente: TestClient) -> None:
    d = _extrair(cliente, _pdf_vazio())
    assert d["fatura"] is None and d["motivo"] == "pdf_sem_texto"
    assert d["erro"] and "camada de texto" in d["erro"]


def test_6_campo_errado_corrigido_na_confirmacao_reflete_no_motor(cliente: TestClient) -> None:
    extraido = _extrair(cliente, _pdf(LINHAS))
    fatura_original = extraido["fatura"]
    assert fatura_original is not None
    sem = _post(cliente, {"pergunta": PERGUNTA, "fatura": fatura_original})
    fatura_corrigida = {**fatura_original, "consumo_kwh": "150"}
    com = _post(cliente, {"pergunta": PERGUNTA, "fatura": fatura_corrigida})
    assert com["campos_fatura"]["consumo_kwh"] == "150"
    assert "150" in com["resposta"]
    consumo = next(a for a in com["achados_motor"] if a["item"] == "Consumo medido")
    assert consumo["valor_cobrado"] in ("150", "150.00")
    assert sem["campos_fatura"]["consumo_kwh"] != com["campos_fatura"]["consumo_kwh"]


def test_7_agentes_indisponiveis_preserva_achados_do_motor(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def quebrar() -> Any:
        raise RuntimeError("serviço indisponível")

    monkeypatch.setattr(api_main, "obter_orquestrador", quebrar)
    d = _post(cliente, {"pergunta": PERGUNTA, "fatura": FATURA_OK})
    assert d["abstencao"] is True and d["origem"] == "agentes_indisponiveis"
    assert d["achados_motor"], "achados determinísticos devem ser preservados"
    assert d["aviso"] and "indisponível" in d["aviso"]
    assert d["citacoes"] == []
    assert any(p["agente"] == "Motor" for p in d["rastro"])


def test_7b_timeout_dos_agentes_tambem_preserva_achados(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Lento:
        def responder_sobre_fatura(self, *a: Any, **k: Any) -> Any:
            import time

            time.sleep(0.3)

    monkeypatch.setattr(api_main, "obter_orquestrador", lambda: Lento())
    monkeypatch.setattr(api_main, "TEMPO_MAXIMO_AGENTES_SEGUNDOS", 0.01)
    monkeypatch.setattr(api_main, "_VAGAS_AGENTES", asyncio.Semaphore(2))
    d = _post(cliente, {"pergunta": PERGUNTA, "fatura": FATURA_OK})
    assert d["abstencao"] is True and d["achados_motor"]


def test_8_dados_insuficientes_geram_abstencao_explicita(cliente: TestClient) -> None:
    fatura = {
        "distribuidora": "Distribuidora Sintética",
        "mes_referencia": "2026-03-01",
        "consumo_kwh": "50",
        "total": "40",
    }
    d = _post(cliente, {"pergunta": PERGUNTA, "fatura": fatura})
    assert d["abstencao"] is True
    assert d["motivo_abstencao"] == "dados_insuficientes"
    assert "leitura_anterior" in d["resposta"] and "leitura_atual" in d["resposta"]
    assert d["citacoes"] == []


def test_9_pergunta_com_termo_vedado_nao_volta_na_saida(cliente: TestClient) -> None:
    d = _post(
        cliente,
        {"pergunta": "Essa cobrança é ilegal? Tenho direito a restituição?", "fatura": FATURA_OK},
    )
    for texto in _textos(d):
        assert not verificar_linguagem(texto, permitir_citacao_literal=bool(d["citacoes"]))
    assert "ilegal" not in d["resposta"].lower()


def test_10_rf15_e_ausencia_de_pii_em_todas_as_saidas(
    cliente: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    linhas_com_pii = [
        "NOME DO CLIENTE: FULANA FICTICIA DA SILVA",
        "CPF: 123.456.789-00",
        "ENDEREÇO: QUADRA 99 CASA 7",
        *LINHAS,
    ]
    with caplog.at_level(logging.DEBUG):
        extraido = _extrair(cliente, _pdf(linhas_com_pii))
    assert extraido["fatura"] is not None
    assert "FULANA" not in json.dumps(extraido, ensure_ascii=False)
    assert "FULANA" not in caplog.text and "123.456.789-00" not in caplog.text

    # Respostas geradas aqui mesmo: o teste não depende de outros testes terem rodado antes.
    respostas = [
        _post(cliente, {"pergunta": PERGUNTA, "fatura": extraido["fatura"]}),
        _post(
            cliente,
            {
                "pergunta": "Essa cobrança é ilegal? Tenho direito a restituição?",
                "fatura": extraido["fatura"],
            },
        ),
        _post(cliente, {"pergunta": PERGUNTA}),
    ]
    for d in respostas:
        literal = bool(d["citacoes"])
        for texto in _textos(d):
            assert not verificar_linguagem(texto, permitir_citacao_literal=literal), texto
        bruto = json.dumps(d, ensure_ascii=False)
        for padrao in PADROES_PII:
            assert padrao not in bruto
    assert not any(p in "\n".join(LINHAS) for p in PADROES_PII)
