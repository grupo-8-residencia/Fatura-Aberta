"""Gerador de fotos sintéticas (#41): formato brasileiro do gabarito e reprodutibilidade."""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar() -> ModuleType:
    caminho = RAIZ / "scripts" / "gerar_fotos_sinteticas.py"
    spec = importlib.util.spec_from_file_location("gerar_fotos_sinteticas", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


gerador = _carregar()


@pytest.mark.parametrize(
    ("valor", "casas", "esperado"),
    [
        (Decimal("1234.5"), 2, "1.234,50"),
        (Decimal("65200"), 0, "65.200"),
        (Decimal("0.8"), 5, "0,80000"),
        (Decimal("20"), 2, "20,00"),
        (Decimal("-0.88"), 2, "-0,88"),
    ],
)
def test_formato_brasileiro(valor: Decimal, casas: int, esperado: str) -> None:
    assert gerador._br(valor, casas) == esperado


def test_gabarito_converte_a_fatura_sintetica_para_o_formato_da_foto() -> None:
    fatura = {
        "aliquota_icms": "0.20",
        "bandeira": "vermelha 1",
        "consumo_kwh": "84",
        "distribuidora": "Neoenergia Brasília",
        "grupo_tarifario": "B1",
        "itens": [
            {
                "descricao": "Consumo de energia",
                "quantidade": "84",
                "tarifa": "0.80",
                "valor": "67.20",
            },
            {
                "descricao": "Contribuição municipal (sintética)",
                "quantidade": None,
                "tarifa": None,
                "valor": "12.00",
            },
        ],
        "leitura_anterior": "65200",
        "leitura_atual": "65284",
        "mes_referencia": "2026-03-01",
        "total": "83.40",
    }

    g = gerador.gabarito_de(fatura)

    assert g["mes_referencia"] == "03/2026"
    assert g["leitura_anterior"] == "65.200"
    assert g["consumo_kwh"] == "84"
    assert g["aliquota_icms"] == "20,00"
    assert g["bandeira"] == "Vermelha 1"
    assert g["total"] == "83,40"
    assert g["itens"][0] == {
        "descricao": "Consumo de energia",
        "quantidade": "84",
        "tarifa": "0,80000",
        "valor": "67,20",
    }
    assert g["itens"][1]["quantidade"] is None


def test_mesma_semente_gera_os_mesmos_bytes(tmp_path: Path) -> None:
    origem = tmp_path / "faturas.jsonl"
    origem.write_text(
        "\n".join(
            json.dumps(
                {
                    "aliquota_icms": "0.12",
                    "bandeira": "amarela",
                    "consumo_kwh": "120",
                    "distribuidora": "Neoenergia Brasília",
                    "grupo_tarifario": "B1",
                    "itens": [{"descricao": "Energia", "valor": "40.00"}],
                    "leitura_anterior": "1000",
                    "leitura_atual": "1120",
                    "mes_referencia": "2026-06-01",
                    "total": "40.00",
                }
            )
            for _ in range(2)
        ),
        encoding="utf-8",
    )
    primeira, segunda = tmp_path / "a", tmp_path / "b"

    gerador.gerar(origem, primeira, quantidade=2)
    gerador.gerar(origem, segunda, quantidade=2)

    for nome in ("foto-01.jpg", "foto-02.jpg"):
        assert (primeira / nome).read_bytes() == (segunda / nome).read_bytes()
    assert (
        json.loads((primeira / "gabarito.json").read_text(encoding="utf-8"))["foto-01"]["total"]
        == "40,00"
    )
