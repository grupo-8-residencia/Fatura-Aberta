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
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "dados" / "golden-set" / "anotacoes"
MODELO = Path(__file__).resolve().parent / "pagina.template.html"
SAIDA = Path(__file__).resolve().parent / "pagina.html"
JUIZ = RAIZ / "avaliacao" / "anotacoes" / "juiz-40.csv"
VERSAO = "4"
CODIGOS = Path(
    os.environ.get("FA_ANOT_CODIGOS", RAIZ / ".local" / "anotacao" / "codigos.json")
)  # fora do Git
ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O/1/I/L para evitar erro de digitação
ITERACOES = 100_000
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


def normalizar_codigo(codigo: str) -> str:
    return "".join(c for c in codigo.upper() if c.isalnum())


def chave(github: str, codigo: str) -> bytes:
    """Chave HMAC da pessoa: PBKDF2-SHA256 do código, com o usuário no sal (igual à da página)."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        normalizar_codigo(codigo).encode(),
        f"fa-anot:{github}".encode(),
        ITERACOES,
        32,
    )


def verificador(github: str, codigo: str) -> str:
    return hmac.new(chave(github, codigo), b"ok", hashlib.sha256).hexdigest()


def carregar_codigos(caminho: Path = CODIGOS) -> dict[str, str]:
    """Lê (ou cria) um código pessoal por anotador. O arquivo nunca vai para o Git."""
    existentes = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    mudou = False
    for p in PESSOAS:
        if p not in existentes:
            partes = ["".join(secrets.choice(ALFABETO) for _ in range(4)) for _ in range(3)]
            existentes[p] = "-".join(partes)
            mudou = True
    if mudou:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(existentes, indent=1), encoding="utf-8")
    return existentes


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


def construir(
    dados: dict[str, Any], modelo: Path = MODELO, codigos: dict[str, str] | None = None
) -> str:
    texto = modelo.read_text(encoding="utf-8")
    if codigos:  # a página só guarda o verificador, nunca o código
        dados = {p: {**d, "verificador": verificador(p, codigos[p])} for p, d in dados.items()}
    # "</" dentro de <script> fecharia a tag; escapa só esse caso.
    carga = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return texto.replace("__DADOS__", carga).replace("__VERSAO__", VERSAO)


def main() -> int:
    codigos = carregar_codigos()
    SAIDA.write_text(construir(montar_dados(), codigos=codigos), encoding="utf-8")
    print(f"Gravado {SAIDA} ({SAIDA.stat().st_size // 1024} KB)")
    print(f"Códigos pessoais (mande a cada pessoa em particular): {CODIGOS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
