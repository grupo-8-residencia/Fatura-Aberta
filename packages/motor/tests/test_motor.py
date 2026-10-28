"""Teste de fumaça: o pacote importa e enxerga o contrato compartilhado."""

import fa_motor
from fa_contratos import Nivel


def test_pacote_importa_e_enxerga_contratos() -> None:
    assert fa_motor.FRENTE == "F3"
    assert {n.value for n in Nivel} == {"A", "B", "C"}
