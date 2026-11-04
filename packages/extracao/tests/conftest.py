"""PDFs sintéticos gerados em memória: nenhum binário é versionado."""

from collections.abc import Callable
from io import BytesIO

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# Dados pessoais FICTÍCIOS, usados só para provar que não saem do parser.
_PII = {
    "nome": "MARIA FICTICIA DA SILVA",
    "endereco": "QUADRA 99 CONJUNTO Z CASA 7",
    "instalacao": "0099887766",
    "cpf": "123.456.789-09",
}


def _linhas_fatura(referencia: str = "06/2026") -> list[str]:
    return [
        "Distribuidora: Neoenergia Brasilia",
        f"Nome: {_PII['nome']}",
        f"Endereço: {_PII['endereco']}",
        f"Instalação: {_PII['instalacao']}",
        f"CPF: {_PII['cpf']}",
        f"Referência: {referencia}",
        "Leitura anterior: 1.000",
        "Leitura atual: 1.150",
        "Consumo kWh: 150",
        "Bandeira: Amarela",
        "ICMS: 20,00%",
        "Itens da fatura",
        "Energia ativa 120,50",
        "Bandeira tarifaria 8,25",
        "Contribuicao de iluminacao 14,00",
        "Total a pagar: R$ 142,75",
    ]


def _gerar_pdf(linhas: list[str]) -> bytes:
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for linha in linhas:
        pagina.drawString(50, y, linha)
        y -= 18
    pagina.save()
    return buffer.getvalue()


@pytest.fixture
def pii() -> dict[str, str]:
    return dict(_PII)


@pytest.fixture
def linhas_fatura() -> Callable[[str], list[str]]:
    return _linhas_fatura


@pytest.fixture
def gerar_pdf() -> Callable[[list[str]], bytes]:
    return _gerar_pdf


@pytest.fixture
def pdf_fatura() -> bytes:
    return _gerar_pdf(_linhas_fatura())
