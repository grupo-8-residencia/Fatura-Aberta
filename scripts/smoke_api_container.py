"""Confere os agentes e o corpus normativo na API em execução no contêiner."""

import json
import os
from typing import Any, cast
from urllib.request import Request, urlopen

BASE = os.getenv("FA_API_BASE_URL", "http://127.0.0.1:8000")


def enviar(caminho: str, dados: dict[str, Any]) -> dict[str, Any]:
    req = Request(
        BASE + caminho,
        data=json.dumps(dados).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resposta:
        assert resposta.status == 200, f"{caminho}: HTTP {resposta.status}"
        return cast(dict[str, Any], json.load(resposta))


analise = enviar(
    "/analisar",
    {
        "distribuidora": "Distribuidora Sintética",
        "mes_referencia": "2026-03-01",
        "leitura_anterior": "100",
        "leitura_atual": "150",
        "consumo_kwh": "40",
        "itens": [{"descricao": "Energia", "valor": "40"}],
        "total": "40",
    },
)
assert analise["aviso"] is None, f"Agentes indisponíveis: {analise['aviso']}"
assert any(achado["nivel"] == "C" and achado["citacoes"] for achado in analise["achados"]), (
    "Faltou explicação de nível C com citação"
)

pergunta = enviar(
    "/perguntar",
    {
        "pergunta": "Posso ser cobrado pela média quando não conseguem ler o medidor?",
        "data_referencia": "2026-03-01",
        "persona": "celina",
    },
)
assert pergunta["citacoes"], "Resposta regulatória sem citação"
print("Smoke da API: análise de nível C e pergunta com citações aprovadas.")
