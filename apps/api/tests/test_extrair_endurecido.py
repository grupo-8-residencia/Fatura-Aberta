"""POST /extrair endurecido (#179): PDF hostil sem 500, 422 sem eco, sem gravação, sem log."""

import base64
import logging
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

import fa_api.main as api_main
from fa_api.main import TAMANHO_MAXIMO_BASE64, app

PDF_DEMO = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "assets"
    / "demo-s5"
    / "fatura-sintetica-demo.pdf"
)


def _demo() -> bytes:
    return PDF_DEMO.read_bytes()


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode()


def _filtro_quebrado(dados: bytes) -> bytes:
    """Troca o filtro ASCII85 por um nome inexistente: o pypdf levanta NotImplementedError."""
    assert b"ASCII85Decode" in dados
    return dados.replace(b"ASCII85Decode", b"ACII85Decode", 1)


def test_pdf_com_filtro_invalido_devolve_motivo_e_nao_500() -> None:
    resposta = TestClient(app).post(
        "/extrair", json={"pdf_base64": _b64(_filtro_quebrado(_demo()))}
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["fatura"] is None
    assert corpo["motivo"] == "pdf_invalido"


def test_mutacoes_do_pdf_nunca_produzem_erro_interno() -> None:
    """Varredura determinística: nenhuma mutação de byte pode virar 500 (stacktrace ao cliente)."""
    dados = _demo()
    passo = max(1, len(dados) // 60)
    cliente = TestClient(app, raise_server_exceptions=False)
    for posicao in range(0, len(dados), passo):
        mutado = bytearray(dados)
        mutado[posicao] = 0x00
        resposta = cliente.post("/extrair", json={"pdf_base64": _b64(bytes(mutado))})
        assert resposta.status_code in (200, 422), (posicao, resposta.status_code)


def test_422_nao_ecoa_o_valor_recebido() -> None:
    resposta = TestClient(app).post("/extrair", json={"pdf_base64": "%SEGREDO-NAO-BASE64!"})
    assert resposta.status_code == 422
    assert "SEGREDO" not in resposta.text
    assert "input" not in resposta.text


def test_base64_acima_do_limite_e_rejeitado_sem_ecoar_o_corpo() -> None:
    tamanho_extra = TAMANHO_MAXIMO_BASE64 + 4 - len(_b64(_demo()))
    grande = _b64(_demo()) + "A" * tamanho_extra
    resposta = TestClient(app).post("/extrair", json={"pdf_base64": grande})
    assert resposta.status_code == 422
    assert len(resposta.text) < 2000


def test_leitura_que_estoura_o_tempo_devolve_504(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "TEMPO_MAXIMO_EXTRACAO_SEGUNDOS", 0.0)
    resposta = TestClient(app).post("/extrair", json={"pdf_base64": _b64(_demo())})
    assert resposta.status_code == 504
    assert "Traceback" not in resposta.text


def test_extrair_nao_grava_arquivos_em_disco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    antes = set(tmp_path.rglob("*"))
    cliente = TestClient(app)
    cliente.post("/extrair", json={"pdf_base64": _b64(_demo())})
    cliente.post("/extrair", json={"pdf_base64": _b64(_filtro_quebrado(_demo()))})
    assert set(tmp_path.rglob("*")) == antes


def test_extrair_nao_registra_linhas_da_fatura_em_log(caplog: pytest.LogCaptureFixture) -> None:
    texto = "\n".join(p.extract_text() for p in PdfReader(BytesIO(_demo())).pages)
    linhas = [linha.strip() for linha in texto.splitlines() if len(linha.strip()) >= 12]
    assert linhas, "o PDF de demo precisa ter texto para o teste fazer sentido"
    cliente = TestClient(app)
    with caplog.at_level(logging.DEBUG):
        cliente.post("/extrair", json={"pdf_base64": _b64(_demo())})
        cliente.post("/extrair", json={"pdf_base64": _b64(_filtro_quebrado(_demo()))})
        cliente.post("/extrair", json={"pdf_base64": "JVBERi0xLjQK"})
    for linha in linhas:
        assert linha not in caplog.text
