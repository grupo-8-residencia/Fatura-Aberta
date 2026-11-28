"""Gera o PDF sintético da demonstração da S5 (docs/assets/demo-s5/).

Documento 100% fictício, com camada de texto e sem nenhum dado pessoal. Usa o mesmo layout que o
parser de `fa_extracao` lê. A saída é determinística (`invariant=1`): o mesmo script gera sempre
os mesmos bytes, e um teste confere que o arquivo versionado é idêntico.

Uso: uv run python scripts/gerar_pdf_demo.py
"""

from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DESTINO = Path(__file__).resolve().parents[1] / "docs/assets/demo-s5/fatura-sintetica-demo.pdf"

LINHAS = [
    "DOCUMENTO SINTETICO - DEMONSTRACAO - SEM VALOR FISCAL",
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
    "0000000000 Energia Ativa Único 1.000,00 1.120,00 1,00000 120,00",
    "0000000000 Energia Ativa Único 1.000,00 1.000,00 1,00000 0,00",
    "Na data da leitura a bandeira em vigor é a Amarela.",
]


def gerar() -> bytes:
    buffer = BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4, invariant=1)
    y = 800
    for linha in LINHAS:
        pagina.drawString(50, y, linha)
        y -= 18
    pagina.save()
    return buffer.getvalue()


if __name__ == "__main__":
    DESTINO.write_bytes(gerar())
    print(f"PDF sintético gravado em {DESTINO.relative_to(DESTINO.parents[3])}")
