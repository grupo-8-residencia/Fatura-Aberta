"""Exercita a API local com dados sintéticos, sem persistir faturas."""

import json
from concurrent.futures import ThreadPoolExecutor
from statistics import quantiles
from time import perf_counter
from urllib.request import Request, urlopen

URL = "http://127.0.0.1:8000/analisar"
REQUISICOES = 20

CORPO = {
    "distribuidora": "Distribuidora Sintética",
    "mes_referencia": "2026-03-01",
    "leitura_anterior": "100",
    "leitura_atual": "150",
    "consumo_kwh": "50",
    "itens": [{"descricao": "Energia", "valor": "40"}],
    "total": "40",
}


def executar_requisicao(_: int) -> tuple[int, float]:
    inicio = perf_counter()
    requisicao = Request(
        URL,
        data=json.dumps(CORPO).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlopen(requisicao, timeout=10) as resposta:  # noqa: S310 -- URL local fixa
        return resposta.status, perf_counter() - inicio


def main() -> None:
    with ThreadPoolExecutor(max_workers=5) as executor:
        resultados = list(executor.map(executar_requisicao, range(REQUISICOES)))

    codigos, duracoes = zip(*resultados, strict=True)
    sucesso = sum(codigo == 200 for codigo in codigos)
    p95 = quantiles(duracoes, n=20)[18]
    print(f"Requisições: {REQUISICOES}; sucesso: {sucesso}/{REQUISICOES}")
    print(f"Latência média: {sum(duracoes) / len(duracoes):.3f}s; p95: {p95:.3f}s")


if __name__ == "__main__":
    main()
