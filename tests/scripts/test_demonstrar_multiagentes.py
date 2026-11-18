"""A demonstração do sistema multiagentes roda offline e mostra os cinco cenários."""

from __future__ import annotations

import demonstrar_multiagentes as demo
import pytest


def test_demo_offline_mostra_os_quatro_agentes_e_os_cinco_cenarios(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert demo.main(["--llm", "simulado"]) == 0
    saida = capsys.readouterr().out
    for agente in ("Pesquisador", "Analista", "Auditor", "Comunicador", "Motor"):
        assert f"[{agente}" in saida
    blocos = saida.split("== ")[1:]
    assert len(blocos) == 5
    assert "Origem da resposta: analista_auditado" in blocos[0]
    assert "barrou o rascunho" in blocos[1] and "pesquisador_extrativo" in blocos[1]
    assert "Origem da resposta: abstencao" in blocos[2]
    assert "nenhum vigente na data" in blocos[3]
    assert "Veredito do motor: diverge_A" in blocos[4]
    assert "Minuta de pedido de esclarecimento" in blocos[4]


@pytest.mark.parametrize("persona", ["celina", "rafael", "marcia"])
def test_demo_aceita_uma_persona(persona: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert demo.main(["--persona", persona]) == 0
    assert f"persona: {persona}" in capsys.readouterr().out
