"""O PDF sintético versionado da demonstração é o gerado pelo script, e a API o lê."""

import base64
from pathlib import Path

from fastapi.testclient import TestClient
from gerar_pdf_demo import DESTINO, gerar

from fa_api.main import app

RAIZ = Path(__file__).resolve().parents[2]


def test_pdf_versionado_e_identico_ao_gerado() -> None:
    assert DESTINO.read_bytes() == gerar()


def test_pdf_da_demo_passa_pelo_fluxo_real_e_a_pergunta_versionada_tem_resposta() -> None:
    pergunta = (RAIZ / "docs/assets/demo-s5/pergunta-demo.txt").read_text(encoding="utf-8").strip()
    pdf = base64.b64encode(DESTINO.read_bytes()).decode()
    cliente = TestClient(app)
    extraido = cliente.post("/extrair", json={"pdf_base64": pdf}).json()
    assert extraido["fatura"] is not None
    assert (
        cliente.post("/perguntar", json={"pergunta": pergunta, "pdf_base64": pdf}).status_code
        == 422
    )
    corpo = cliente.post(
        "/perguntar", json={"pergunta": pergunta, "fatura": extraido["fatura"]}
    ).json()
    assert corpo["modo"] == "fatura" and corpo["citacoes"] and not corpo["abstencao"]
    assert pergunta in corpo["resposta"] and "06/2026" in corpo["resposta"]
