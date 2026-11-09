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
    """Texto sintético na ordem em que o `pypdf` lê a fatura da Neoenergia Brasília (B1)."""
    return [
        "Consumo-TUSD kWh 120,00 0,50000000 60,00 2,50 60,00 12,00 7,20 0,42000000",
        "Consumo-TE kWh 120,00 0,47000000 56,40 2,35 56,40 12,00 6,77 0,40000000",
        "Acrés. Band. AMARELA 3,00 0,10 3,00 12,00 0,36",
        "Ilum. Púb. Distrital 12,00",
        "CREDITO-TESTE-01/02 1,00-",
        "NEOENERGIA DISTRIBUIÇÃO BRASÍLIA S.A",
        "CLASSIFICAÇÃO: B1 RESIDENCIAL -RESIDENCIAL",
        "NOME DO CLIENTE:",
        _PII["nome"],
        f"CPF: {_PII['cpf']}",
        "ENDEREÇO:",
        _PII["endereco"],
        "CÓDIGO DA INSTALAÇÃO",
        _PII["instalacao"],
        "DATAS DE LEITURAS LEITURA ANTERIOR 01/06/2026 LEITURA ATUAL 01/07/2026",
        "REF:MÊS/ANO",
        referencia,
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
