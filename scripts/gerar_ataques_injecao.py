"""Gera os PDFs adversariais sintéticos e determinísticos da S5-03."""

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from gerar_pdf_demo import LINHAS
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DESTINO = Path(__file__).resolve().parents[1] / "dados/benchmark/sinteticas/ataques-injecao"


def casos() -> list[dict[str, Any]]:
    return json.loads((DESTINO / "casos.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def gerar_pdf(instrucao: str = "") -> bytes:
    """Fatura com erro de consumo conhecido: 130 kWh lidos, 120 kWh faturados."""
    linhas = [
        linha.replace("1.120,00 1,00000 120,00", "1.130,00 1,00000 120,00") for linha in LINHAS
    ]
    if instrucao:
        linhas.append(instrucao)
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    y = 800
    for linha in linhas:
        pagina.drawString(50, y, linha)
        y -= 18
    pagina.save()
    return buffer.getvalue()


def gerar_todos() -> dict[str, bytes]:
    pdfs = {"00-base.pdf": gerar_pdf()}
    for caso in casos():
        if caso["vetor"] == "pdf":
            pdfs[caso["pdf"]] = gerar_pdf(caso["instrucao"])
    return pdfs


if __name__ == "__main__":
    for nome, conteudo in gerar_todos().items():
        (DESTINO / nome).write_bytes(conteudo)
        print(nome)
