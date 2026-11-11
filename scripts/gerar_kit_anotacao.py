#!/usr/bin/env python3
"""Gera o kit de anotação humana do golden set (issue #32).

Para cada um dos 6 anotadores cria `dados/golden-set/anotacoes/<github>.csv` com 30 itens
(12 perguntas + 18 faturas) e cria `revisao-perguntas.csv` com as 120 perguntas. As colunas
humanas (`concorda`, `correcao`, `comentario`) nascem VAZIAS: este script nunca anota nada.

A saída é determinística (mesma entrada, mesmos bytes) e não altera os arquivos congelados do
golden set.

Uso:
    python scripts/gerar_kit_anotacao.py
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
from typing import Any

from gerar_golden_set import PASTA, distribuir, gerar_faturas, ler_perguntas

PASTA_ANOTACOES = PASTA / "anotacoes"
COLUNAS_HUMANAS = ("concorda", "correcao", "comentario")
COLUNAS_ANOTACAO = ("id", "tipo", "enunciado", "gabarito_proposto", *COLUNAS_HUMANAS)
COLUNAS_REVISAO = (
    "id",
    "categoria",
    "tipo",
    "pergunta",
    "data_referencia",
    "resposta_esperada",
    "citacao_canonica",
    "abstencao_esperada",
    *COLUNAS_HUMANAS,
)
ARQ_REVISAO = "revisao-perguntas.csv"


def _sim_nao(valor: bool) -> str:
    return "sim" if valor else "não"


def linha_pergunta(p: dict[str, Any]) -> dict[str, str]:
    """Linha de anotação de uma pergunta (gabarito = resposta, citação e abstenção)."""
    gabarito = (
        f"Resposta esperada: {p['resposta_esperada']} | "
        f"Citação canônica: {', '.join(p['citacao_canonica']) or '(nenhuma)'} | "
        f"Abstenção esperada: {_sim_nao(p['abstencao_esperada'])}"
    )
    enunciado = f"{p['pergunta']} (data de referência: {p['data_referencia']})"
    return {
        "id": p["id"],
        "tipo": "pergunta",
        "enunciado": enunciado,
        "gabarito_proposto": gabarito,
        **dict.fromkeys(COLUNAS_HUMANAS, ""),
    }


def linha_fatura(f: dict[str, Any]) -> dict[str, str]:
    """Linha de anotação de uma fatura sintética (resumo com itens e total)."""
    itens = "; ".join(
        f"{i + 1}) {it['descricao']}: R$ {it['valor']}" for i, it in enumerate(f["itens"])
    )
    enunciado = (
        f"Fatura sintética de {f['mes_referencia'][:7]}, grupo {f['grupo_tarifario']}, "
        f"bandeira {f['bandeira']}. Leituras {f['leitura_anterior']} -> {f['leitura_atual']}; "
        f"consumo informado {f['consumo_kwh']} kWh; ICMS {f['aliquota_icms']}. "
        f"Itens: {itens}. Total: R$ {f['total']}."
    )
    por_item = ", ".join(f"item {i + 1}: {g}" for i, g in enumerate(f["gabarito_itens"]))
    gabarito = (
        f"Fatura: {f['gabarito_fatura']} | {por_item} | "
        f"Anomalia injetada: {f['anomalia_injetada'] or 'nenhuma'}"
    )
    return {
        "id": f["id"],
        "tipo": "fatura",
        "enunciado": enunciado,
        "gabarito_proposto": gabarito,
        **dict.fromkeys(COLUNAS_HUMANAS, ""),
    }


def linha_revisao(p: dict[str, Any]) -> dict[str, str]:
    return {
        "id": p["id"],
        "categoria": p["categoria"],
        "tipo": p["tipo"],
        "pergunta": p["pergunta"],
        "data_referencia": p["data_referencia"],
        "resposta_esperada": p["resposta_esperada"],
        "citacao_canonica": ", ".join(p["citacao_canonica"]),
        "abstencao_esperada": _sim_nao(p["abstencao_esperada"]),
        **dict.fromkeys(COLUNAS_HUMANAS, ""),
    }


def _csv(colunas: tuple[str, ...], linhas: list[dict[str, str]]) -> str:
    saida = io.StringIO()
    escritor = csv.DictWriter(saida, fieldnames=colunas, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(linhas)
    return saida.getvalue()


def gerar_kit(
    pasta_golden: Path = PASTA,
) -> dict[str, str]:
    """Devolve {nome_do_arquivo: conteudo_csv} do kit completo, sem escrever em disco."""
    perguntas = ler_perguntas(pasta_golden)
    faturas = gerar_faturas()
    por_id: dict[str, dict[str, str]] = {}
    for p in perguntas:
        por_id[p["id"]] = linha_pergunta(p)
    for f in faturas:
        por_id[f["id"]] = linha_fatura(f)
    kit: dict[str, str] = {}
    for github, ids in distribuir(perguntas, faturas).items():
        kit[f"{github}.csv"] = _csv(COLUNAS_ANOTACAO, [por_id[i] for i in ids])
    kit[ARQ_REVISAO] = _csv(COLUNAS_REVISAO, [linha_revisao(p) for p in perguntas])
    return kit


def escrever_kit(destino: Path = PASTA_ANOTACOES, pasta_golden: Path = PASTA) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []
    for nome, conteudo in gerar_kit(pasta_golden).items():
        caminho = destino / nome
        # utf-8 com BOM: o Excel abre os acentos corretamente.
        caminho.write_text(conteudo, encoding="utf-8-sig", newline="")
        escritos.append(caminho)
    return escritos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        "--destino", type=Path, default=PASTA_ANOTACOES, help="pasta de saída dos CSV do kit"
    )
    args = ap.parse_args(argv)
    escritos = escrever_kit(args.destino)
    for caminho in escritos:
        print(caminho)
    print(f"{len(escritos)} arquivos gerados; colunas humanas vazias.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
