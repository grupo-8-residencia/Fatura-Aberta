#!/usr/bin/env python3
"""Passa as fotos de fatura pelo modelo de visão local (issue #41). Roda só localmente.

Lê as fotos de `faturas-reais/fotos/` (fora do Git), extrai cada uma com o mesmo caminho do
produto (`ExtratorOllama` → `extrair_candidata`, que descarta e anonimiza dados pessoais) e grava
em `faturas-reais/avaliacao/`:

    - `previsto.json`: o que o modelo leu, por id da foto, no formato do
      `scripts/acuracia_por_campo.py`;
    - `metadados.json`: modelo, digest, data, falhas e latência. Não tem valores da fatura e pode
      ir para `docs/avaliacao/acuracia-fotos.md`;
    - `gabarito-modelo.json` (com `--gabarito-modelo`): um gabarito em branco com os ids, para
      preencher à mão olhando as fotos.

O id de cada foto é o nome do arquivo sem extensão. Nomeie as fotos como `foto-01.jpg`,
`foto-02.jpg`... e nunca com o nome do titular.

Uso:
    FA_VLM_MODELO=qwen2.5vl:7b uv run python scripts/extrair_fotos.py [pasta] [--saida pasta]
    uv run python scripts/acuracia_por_campo.py faturas-reais/avaliacao/previsto.json \\
        faturas-reais/avaliacao/gabarito.json --saida faturas-reais/avaliacao/relatorio.md
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fa_extracao import ErroExtracao, ExtratorDeFoto, extrair_candidata
from fa_extracao.candidata import CAMPOS, CAMPOS_ITEM
from fa_extracao.vlm import criar_extrator

EXTENSOES = {".jpg", ".jpeg", ".png", ".webp"}


def listar_fotos(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES)


def _percentil(valores: list[float], p: float) -> float:
    if len(valores) < 2:
        return valores[0] if valores else 0.0
    return statistics.quantiles(valores, n=100, method="inclusive")[int(p) - 1]


def extrair_todas(
    fotos: list[Path], extrator: ExtratorDeFoto
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Extrai cada foto. Falha vira `{}` (conta como erro em todos os campos na acurácia)."""
    previsto: dict[str, dict[str, Any]] = {}
    duracoes: list[float] = []
    falhas: dict[str, int] = {}
    for foto in fotos:
        inicio = time.perf_counter()
        try:
            candidata = extrair_candidata(foto.read_bytes(), extrator)
        except ErroExtracao as erro:
            # A mensagem é nossa (sem dado da fatura); agrupa por tipo para o relatório.
            falhas[str(erro)] = falhas.get(str(erro), 0) + 1
            previsto[foto.stem] = {}
            continue
        finally:
            duracoes.append(time.perf_counter() - inicio)
        previsto[foto.stem] = candidata.model_dump(mode="json")

    metadados = {
        "fotos": len(fotos),
        "extraidas": len(fotos) - sum(falhas.values()),
        "falhas": falhas,
        "latencia_s": {
            "p50": round(_percentil(duracoes, 50), 2),
            "p95": round(_percentil(duracoes, 95), 2),
            "max": round(max(duracoes, default=0.0), 2),
        },
    }
    return previsto, metadados


def gabarito_modelo(ids: list[str]) -> dict[str, dict[str, Any]]:
    vazio_item = {campo: None for campo in CAMPOS_ITEM}
    return {i: {**{campo: None for campo in CAMPOS}, "itens": [dict(vazio_item)]} for i in ids}


def _gravar(caminho: Path, dados: object) -> None:
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extrai as fotos com o VLM local (#41).")
    parser.add_argument("pasta", type=Path, nargs="?", default=Path("faturas-reais/fotos"))
    parser.add_argument("--saida", type=Path, default=Path("faturas-reais/avaliacao"))
    parser.add_argument(
        "--gabarito-modelo", action="store_true", help="grava também um gabarito em branco"
    )
    args = parser.parse_args(argv)

    if not args.pasta.is_dir() or not (fotos := listar_fotos(args.pasta)):
        print(f"Nenhuma foto (JPEG, PNG ou WEBP) em {args.pasta}/.", file=sys.stderr)
        return 2
    args.saida.mkdir(parents=True, exist_ok=True)

    if args.gabarito_modelo:
        destino = args.saida / "gabarito-modelo.json"
        _gravar(destino, gabarito_modelo([f.stem for f in fotos]))
        print(f"Gabarito em branco: {destino}")

    extrator = criar_extrator()
    try:
        digest = extrator.versao()
    except ErroExtracao as erro:
        print(f"{erro} Suba o Ollama e rode `ollama pull {extrator.modelo}`.", file=sys.stderr)
        return 2

    print(f"Extraindo {len(fotos)} fotos com {extrator.modelo} ({digest})...")
    previsto, metadados = extrair_todas(fotos, extrator)
    metadados = {
        "data_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modelo": extrator.modelo,
        "digest": digest,
        **metadados,
    }
    _gravar(args.saida / "previsto.json", previsto)
    _gravar(args.saida / "metadados.json", metadados)
    print(
        f"{metadados['extraidas']}/{metadados['fotos']} extraídas; "
        f"latência p50 {metadados['latencia_s']['p50']} s. Saída em {args.saida}/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
