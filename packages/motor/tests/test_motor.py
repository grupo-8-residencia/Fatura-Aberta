"""Teste de fumaça: o pacote importa e enxerga o contrato compartilhado."""

from pathlib import Path

import fa_motor
from fa_contratos import Nivel


def test_pacote_importa_e_enxerga_contratos() -> None:
    assert fa_motor.FRENTE == "F3"
    assert {n.value for n in Nivel} == {"A", "B", "C"}


def test_constantes_do_motor_registram_fonte_data_e_classificacao() -> None:
    constantes_esperadas = {
        "LIMITE_PARCELA_ATE_80_KWH": str(fa_motor.LIMITE_PARCELA_ATE_80_KWH),
        "ALIQUOTA_ICMS_MAXIMA_B1": str(fa_motor.ALIQUOTA_ICMS_MAXIMA_B1),
    }
    for nome, valor in constantes_esperadas.items():
        assert nome in fa_motor.FONTES_CONSTANTES_MOTOR
        meta = fa_motor.FONTES_CONSTANTES_MOTOR[nome]
        assert meta["valor"] == valor
        assert meta["classificacao"] in {"parametro_do_projeto", "norma_oficial"}
        assert meta["fonte"].strip()
        assert meta["data_fonte"].strip()

    doc_f3 = (Path(__file__).resolve().parents[3] / "docs" / "frentes" / "f3.md").read_text(
        encoding="utf-8"
    )
    for nome in ("LIMITE_PARCELA_ATE_80_KWH", "ALIQUOTA_ICMS_MAXIMA_B1"):
        assert nome in doc_f3
    assert "Parâmetro do projeto" in doc_f3
    assert "12.212/2010" in doc_f3
    assert "1.254/1996" in doc_f3
