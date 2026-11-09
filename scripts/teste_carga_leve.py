"""Mede carga leve da API com uma fatura inteiramente sintética."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

CORPO = {
    "distribuidora": "Distribuidora Sintética",
    "mes_referencia": "2026-03-01",
    "leitura_anterior": "100",
    "leitura_atual": "150",
    "consumo_kwh": "50",
    "itens": [{"descricao": "Energia", "valor": "40"}],
    "total": "40",
}


def executar_requisicao(url: str) -> tuple[int | None, float]:
    inicio = perf_counter()
    requisicao = Request(
        url,
        data=json.dumps(CORPO).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(requisicao, timeout=20) as resposta:  # noqa: S310 -- URL do operador
            codigo = resposta.status
    except HTTPError as erro:
        codigo = erro.code
    except URLError:
        codigo = None
    return codigo, perf_counter() - inicio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="URL base da API")
    parser.add_argument("--requisicoes", type=int, default=100)
    parser.add_argument("--concorrencia", type=int, default=5)
    parser.add_argument("--p95-max-ms", type=float, default=2000)
    args = parser.parse_args(argv)
    if urlparse(args.url).scheme not in {"http", "https"}:
        parser.error("a URL deve começar com http:// ou https://")
    if args.requisicoes < 1 or args.concorrencia < 1 or args.p95_max_ms <= 0:
        parser.error("requisições, concorrência e limite de p95 devem ser positivos")

    url = f"{args.url.rstrip('/')}/analisar"
    with ThreadPoolExecutor(max_workers=args.concorrencia) as executor:
        resultados = list(executor.map(executar_requisicao, [url] * args.requisicoes))

    codigos, duracoes = zip(*resultados, strict=True)
    sucesso = sum(codigo == 200 for codigo in codigos)
    p95_ms = sorted(duracoes)[ceil(0.95 * len(duracoes)) - 1] * 1000
    aprovado = sucesso == args.requisicoes and p95_ms <= args.p95_max_ms
    print(f"Requisições: {args.requisicoes}; simultâneas: {args.concorrencia}")
    print(f"Sucesso: {sucesso}/{args.requisicoes}; p95: {p95_ms:.0f} ms")
    estado = "aprovada" if aprovado else "não atingida"
    print(f"Meta: 100% de sucesso e p95 ≤ {args.p95_max_ms:.0f} ms — {estado}")
    return 0 if aprovado else 1


if __name__ == "__main__":
    raise SystemExit(main())
