#!/usr/bin/env python3
"""Gera `pagina.html` (página de anotação sem login) a partir do modelo e dos CSV do kit.

A página é estática: os itens de cada pessoa vão embutidos no HTML, as respostas ficam no navegador
e a entrega é um texto/arquivo JSON que o `scripts/importar_anotacoes.py` aceita. Nada de banco nem
conta, então qualquer pessoa com o link consegue responder.

Cegamento do juiz: só entram `saida_do_sistema` e `evidencia` dos itens atribuídos à pessoa. O
veredito e as proposições do juiz nunca são lidos.

Uso: python avaliacao/anotacao/construir_pagina.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "dados" / "golden-set" / "anotacoes"
MODELO = Path(__file__).resolve().parent / "pagina.template.html"
SAIDA = Path(__file__).resolve().parent / "pagina.html"
JUIZ = RAIZ / "avaliacao" / "anotacoes" / "juiz-40.csv"
VERSAO = "3"
PESSOAS = (
    "pedrohpsantos",
    "NatyEvelin",
    "RaissaOliveira19",
    "TalitaaNunes",
    "luizoryone",
    "mariadenis",
)
CAMPOS_GOLDEN = ("id", "tipo", "enunciado", "gabarito_proposto")
CAMPOS_REVISAO = (
    "id", "categoria", "tipo", "pergunta", "data_referencia", "resposta_esperada",
    "citacao_canonica", "abstencao_esperada",
)  # fmt: skip
CAMPOS_JUIZ = ("item_id", "tipo", "saida_do_sistema", "evidencia")


def _ler(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def montar_dados(
    pasta: Path = PASTA, juiz: Path = JUIZ
) -> dict[str, dict[str, list[dict[str, str]]]]:
    blocos = json.loads((pasta / "distribuicao-revisao.json").read_text(encoding="utf-8"))["blocos"]
    revisao = {r["id"]: r for r in _ler(pasta / "revisao-perguntas.csv")}
    juiz_linhas = _ler(juiz) if juiz.exists() else []
    dados: dict[str, dict[str, list[dict[str, str]]]] = {}
    for p in PESSOAS:
        golden = [{k: r[k] for k in CAMPOS_GOLDEN} for r in _ler(pasta / f"{p}.csv")]
        rev = [{k: revisao[i][k] for k in CAMPOS_REVISAO} for i in blocos[p]]
        jz = [
            {"id": r["item_id"], **{k: r[k] for k in CAMPOS_JUIZ if k != "item_id"}}
            for r in juiz_linhas
            if p in (r.get("anotador_1"), r.get("anotador_2")) and r.get("saida_do_sistema")
        ]
        dados[p] = {"golden": golden, "revisao": rev, "juiz": jz}
    return dados


def construir(dados: dict[str, Any], modelo: Path = MODELO) -> str:
    texto = modelo.read_text(encoding="utf-8")
    # "</" dentro de <script> fecharia a tag; escapa só esse caso.
    carga = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return texto.replace("__DADOS__", carga).replace("__VERSAO__", VERSAO)


def main() -> int:
    SAIDA.write_text(construir(montar_dados()), encoding="utf-8")
    print(f"Gravado {SAIDA} ({SAIDA.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
