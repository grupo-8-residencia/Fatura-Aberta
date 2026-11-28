"""POST /extrair-foto (#40): foto -> campos para confirmação, sem análise e sem dado pessoal.

O extrator é um dublê (nenhum modelo real roda aqui). A medição com o VLM real fica em #41.
"""

import base64
import logging
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import fa_api.main as api_main
import fa_extracao
from fa_api.main import MSG_FOTO_NAO_LIDA, MSG_LEITOR_INDISPONIVEL, app
from fa_extracao import ErroExtracao, VlmIndisponivel

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
NOME = "MARIA FICTICIA DA SILVA"

LEITURA: dict[str, Any] = {
    "distribuidora": "Neoenergia Distribuição Brasília",
    "grupo_tarifario": "B1",
    "mes_referencia": "10/2026",
    "leitura_anterior": "4.390,00",
    "leitura_atual": "4.467,00",
    "consumo_kwh": "77,00",
    "bandeira": "Amarela",
    "aliquota_icms": "12,00",
    "total": "81,95",
    "itens": [
        {
            "descricao": "Consumo-TUSD",
            "quantidade": "77,00",
            "tarifa": "0,51192150",
            "valor": "39,41",
        },
        {"descricao": "Consumo-TE", "quantidade": "77,00", "valor": "36,55"},
        {"descricao": "Ilum. Púb. Distrital", "valor": "5,99"},
    ],
    # Campos fora do contrato que o modelo não deveria devolver:
    "nome": NOME,
}


class ExtratorFalso:
    def __init__(self, leitura: Mapping[str, Any] | None = None, erro: Exception | None = None):
        self.leitura = LEITURA if leitura is None else leitura
        self.erro = erro
        self.chamadas = 0

    def extrair(self, imagem: bytes) -> Mapping[str, Any]:
        self.chamadas += 1
        if self.erro is not None:
            raise self.erro
        return self.leitura


def _instalar(monkeypatch: pytest.MonkeyPatch, extrator: ExtratorFalso) -> ExtratorFalso:
    monkeypatch.setattr(fa_extracao, "criar_extrator", lambda *_a, **_k: extrator)
    return extrator


def _foto(dados: bytes) -> dict[str, str]:
    return {"imagem_base64": base64.b64encode(dados).decode()}


def test_foto_valida_devolve_fatura_para_o_usuario_conferir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extrator = _instalar(monkeypatch, ExtratorFalso())
    resposta = TestClient(app).post("/extrair-foto", json=_foto(PNG))
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["motivo"] is None and corpo["pendentes"] == []
    assert corpo["fatura"]["distribuidora"] == "Neoenergia Brasília"  # vocabulário fechado
    assert corpo["fatura"]["total"] in ("81.95", "81,95")
    assert extrator.chamadas == 1


def test_bandeira_e_icms_chegam_a_fatura(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, ExtratorFalso())
    corpo = TestClient(app).post("/extrair-foto", json=_foto(PNG)).json()
    assert corpo["fatura"]["bandeira"] == "Amarela"
    assert corpo["fatura"]["aliquota_icms"] in ("0.12", "0.1200")


def test_campo_obrigatorio_ausente_devolve_pendentes(monkeypatch: pytest.MonkeyPatch) -> None:
    leitura = {k: v for k, v in LEITURA.items() if k != "total"}
    _instalar(monkeypatch, ExtratorFalso(leitura=leitura))
    corpo = TestClient(app).post("/extrair-foto", json=_foto(PNG)).json()
    assert corpo["fatura"] is None
    assert corpo["motivo"] == "campos_pendentes"
    assert "total" in corpo["pendentes"]


def test_fora_do_escopo_b1_e_recusado_pelo_contrato(monkeypatch: pytest.MonkeyPatch) -> None:
    leitura = {**LEITURA, "distribuidora": "Outra Distribuidora"}
    _instalar(monkeypatch, ExtratorFalso(leitura=leitura))
    corpo = TestClient(app).post("/extrair-foto", json=_foto(PNG)).json()
    assert corpo["fatura"] is None
    assert corpo["motivo"] == "fora_do_contrato"


def test_dado_pessoal_devolvido_pelo_modelo_nao_chega_a_resposta_nem_a_log(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _instalar(monkeypatch, ExtratorFalso())
    with caplog.at_level(logging.DEBUG):
        resposta = TestClient(app).post("/extrair-foto", json=_foto(PNG))
    assert NOME not in resposta.text
    assert NOME not in caplog.text


def test_formato_nao_suportado_nao_chama_o_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    extrator = _instalar(monkeypatch, ExtratorFalso())
    gif = b"GIF89a" + b"\x00" * 64
    corpo = TestClient(app).post("/extrair-foto", json=_foto(gif)).json()
    assert corpo["motivo"] == "imagem_invalida"
    assert extrator.chamadas == 0


def test_leitor_indisponivel_vira_503_sem_detalhes_do_servidor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _instalar(monkeypatch, ExtratorFalso(erro=VlmIndisponivel("Ollama indisponível.")))
    resposta = TestClient(app).post("/extrair-foto", json=_foto(PNG))
    assert resposta.status_code == 503
    assert resposta.json()["detail"] == MSG_LEITOR_INDISPONIVEL
    assert "Traceback" not in resposta.text


def test_falha_de_leitura_nao_repete_o_texto_do_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(
        monkeypatch,
        ExtratorFalso(erro=ErroExtracao("O modelo de visão não devolveu JSON.")),
    )
    corpo = TestClient(app).post("/extrair-foto", json=_foto(PNG)).json()
    assert corpo["motivo"] == "foto_nao_lida"
    assert corpo["erro"] == MSG_FOTO_NAO_LIDA


def test_tempo_esgotado_vira_504(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, ExtratorFalso())
    monkeypatch.setattr(api_main, "TEMPO_MAXIMO_FOTO_SEGUNDOS", 0.0)
    resposta = TestClient(app).post("/extrair-foto", json=_foto(PNG))
    assert resposta.status_code == 504


def test_base64_invalido_e_422_sem_eco(monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, ExtratorFalso())
    resposta = TestClient(app).post("/extrair-foto", json={"imagem_base64": "%SEGREDO%"})
    assert resposta.status_code == 422
    assert "SEGREDO" not in resposta.text


def test_nada_e_gravado_em_disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _instalar(monkeypatch, ExtratorFalso())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    antes = set(tmp_path.rglob("*"))
    TestClient(app).post("/extrair-foto", json=_foto(PNG))
    assert set(tmp_path.rglob("*")) == antes
