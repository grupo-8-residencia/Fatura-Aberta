"""Teste de fumaça: o pacote importa e enxerga o contrato compartilhado."""

import fa_extracao
from fa_contratos import Nivel


def test_pacote_importa_e_enxerga_contratos() -> None:
    assert fa_extracao.FRENTE == "F4"
    assert {n.value for n in Nivel} == {"A", "B", "C"}
