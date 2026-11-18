"""A demo dos agentes roda offline e mostra os quatro cenários com o resultado esperado."""

import demonstrar_agentes as demo
import pytest


def test_demo_simulada_roda_e_cumpre_os_quatro_cenarios(capsys: pytest.CaptureFixture[str]) -> None:
    codigo = demo.main(["--llm", "simulado"])
    saida = capsys.readouterr().out
    assert codigo == 0
    # Cenário 1: o Auditor aprova e a resposta cita o dispositivo.
    assert "aprovada:" in saida
    assert "REN ANEEL nº 1.000/2021, art. 289" in saida
    # Cenário 2: o número errado é barrado e a resposta vira abstenção.
    assert "reprovada:" in saida and "sem_suporte" in saida
    # Cenários 3 e 4: nenhum dispositivo passa do limiar e o LLM não é chamado.
    assert saida.count("o LLM não foi chamado") == 2
    assert saida.count("ABSTENÇÃO.") == 3


def test_cenarios_cobrem_resposta_e_abstencao() -> None:
    esperados = [c.esperado for c in demo.CENARIOS]
    assert esperados.count("respondida") == 1
    assert esperados.count("abstencao") == 3
