"""Fluxo multimodal (S5-05): pergunta em texto + PDF/fatura confirmada na mesma análise.

Todos os PDFs são sintéticos, gerados em memória, sem nenhum dado pessoal.
"""

import asyncio
import base64
import json
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

VISTOS: list[dict[str, Any]] = []


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    yield TestClient(app)


def _post(cliente: TestClient, corpo: dict[str, Any]) -> dict[str, Any]:
    r = cliente.post("/perguntar", json=corpo)
    assert r.status_code == 200, r.text
    dados: dict[str, Any] = r.json()
    VISTOS.append(dados)
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


def test_2_pdf_digital_sintetico_extrai_e_roda_o_motor(cliente: TestClient) -> None:
    d = _post(cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(_pdf(LINHAS))})
    assert d["modo"] == "pdf"
    assert d["campos_fatura"]["mes_referencia"] == "06/2026"
    assert d["campos_fatura"]["consumo_kwh"] == "120.00"
    assert d["achados_motor"]
    agentes = [(p["agente"], p["acao"]) for p in d["rastro"]]
    assert ("Motor", "analisar_nivel_a") in agentes
    assert any(a == "Pesquisador" for a, _ in agentes)


def test_3_texto_mais_pdf_cita_campo_do_pdf_e_a_pergunta(cliente: TestClient) -> None:
    d = _post(cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(_pdf(LINHAS))})
    assert PERGUNTA in d["resposta"]
    assert "120" in d["resposta"] and "06/2026" in d["resposta"]
    assert "Consumo medido" in d["resposta"]
    assert d["citacoes"], "resposta sem citação normativa"
    assert not d["abstencao"]


def test_4_pdf_corrompido_devolve_mensagem_clara_sem_conclusao(cliente: TestClient) -> None:
    d = _post(
        cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog")}
    )
    assert d["abstencao"] is True
    assert d["origem"] == "falha_extracao" and d["motivo_abstencao"] == "pdf_invalido"
    assert "corrompido" in d["mensagem"]
    assert d["achados_motor"] == [] and d["citacoes"] == []


def test_4b_arquivo_sem_assinatura_de_pdf_e_rejeitado_com_422(cliente: TestClient) -> None:
    r = cliente.post(
        "/perguntar", json={"pergunta": PERGUNTA, "pdf_base64": _b64(b"isto nao e um pdf")}
    )
    assert r.status_code == 422


def test_4c_pdf_protegido_por_senha(cliente: TestClient) -> None:
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter(clone_from=PdfReader(BytesIO(_pdf(LINHAS))))
    escritor.encrypt("senha-de-teste")
    saida = BytesIO()
    escritor.write(saida)
    d = _post(cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(saida.getvalue())})
    assert d["abstencao"] is True and d["motivo_abstencao"] == "pdf_protegido"
    assert "senha" in d["mensagem"]


def test_4d_pdf_com_paginas_demais(cliente: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "PDF_PAGINAS_MAXIMAS", 1)
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    for _ in range(2):
        pagina.drawString(50, 800, "pagina")
        pagina.showPage()
    pagina.save()
    d = _post(cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(buffer.getvalue())})
    assert d["motivo_abstencao"] == "pdf_muitas_paginas" and d["abstencao"] is True


def test_5_pdf_sem_camada_de_texto(cliente: TestClient) -> None:
    d = _post(cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(_pdf_vazio())})
    assert d["abstencao"] is True and d["motivo_abstencao"] == "pdf_sem_texto"
    assert "camada de texto" in d["mensagem"]
    assert d["achados_motor"] == []


def test_6_campo_errado_corrigido_pelo_usuario_reflete_no_motor(cliente: TestClient) -> None:
    sem = _post(cliente, {"pergunta": PERGUNTA, "pdf_base64": _b64(_pdf(LINHAS))})
    com = _post(
        cliente,
        {
            "pergunta": PERGUNTA,
            "pdf_base64": _b64(_pdf(LINHAS)),
            "correcoes": {"consumo_kwh": "150"},
        },
    )
    assert com["campos_fatura"]["consumo_kwh"] == "150"
    assert "150" in com["resposta"]
    consumo = next(a for a in com["achados_motor"] if a["item"] == "Consumo medido")
    assert consumo["valor_cobrado"] == "150" or consumo["valor_cobrado"] == "150.00"
    assert sem["campos_fatura"]["consumo_kwh"] != com["campos_fatura"]["consumo_kwh"]


def test_6b_correcao_invalida_vira_abstencao_estruturada(cliente: TestClient) -> None:
    d = _post(
        cliente,
        {
            "pergunta": PERGUNTA,
            "pdf_base64": _b64(_pdf(LINHAS)),
            "correcoes": {"consumo_kwh": "abc"},
        },
    )
    assert d["abstencao"] is True and d["motivo_abstencao"] == "correcao_invalida"
    assert "consumo_kwh" in d["mensagem"] and "abc" not in d["mensagem"]


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


def test_10_rf15_e_ausencia_de_pii_em_todas_as_saidas() -> None:
    assert len(VISTOS) >= 8
    for d in VISTOS:
        literal = bool(d["citacoes"])
        for texto in _textos(d):
            assert not verificar_linguagem(texto, permitir_citacao_literal=literal), texto
        bruto = json.dumps(d, ensure_ascii=False)
        for padrao in PADROES_PII:
            assert padrao not in bruto
    assert not any(p in "\n".join(LINHAS) for p in PADROES_PII)


def test_extrair_devolve_campos_para_confirmacao_sem_rodar_agentes(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def proibido() -> Any:
        raise AssertionError("agentes não devem rodar antes da confirmação")

    monkeypatch.setattr(api_main, "obter_orquestrador", proibido)
    r = cliente.post("/extrair", json={"pdf_base64": _b64(_pdf(LINHAS))})
    corpo = r.json()
    assert r.status_code == 200 and corpo["erro"] is None
    assert corpo["fatura"]["consumo_kwh"] in ("120", "120.00")
    sem = cliente.post("/extrair", json={"pdf_base64": _b64(_pdf_vazio())}).json()
    assert sem["fatura"] is None and sem["motivo"] == "pdf_sem_texto"
    assert cliente.post("/extrair", json={"pdf_base64": _b64(b"x")}).status_code == 422
