#!/usr/bin/env python3
"""Gera e congela o golden set da S3 (issue S3-01).

- `dados/golden-set/perguntas.jsonl`: 120 perguntas escritas à mão (entrada deste script).
- `dados/golden-set/faturas_sinteticas.jsonl`: 200 faturas SINTÉTICAS (sem dado pessoal), cerca de
  metade com uma anomalia injetada. Os parâmetros tarifários são sintéticos: não são tarifas
  oficiais da Neoenergia Brasília (a planilha ANEEL versionada ainda não foi validada).
- `dados/golden-set/distribuicao_anotadores.md`: 30 itens para cada um dos 6 membros.
- `dados/golden-set/checksums.sha256`: hashes SHA-256 do conjunto congelado.

Uso:
    python scripts/gerar_golden_set.py            # gera tudo e congela os hashes
    python scripts/gerar_golden_set.py --verificar  # confere os hashes sem escrever
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "dados" / "golden-set"
SEMENTE = 20261109
N_FATURAS = 200
N_PERGUNTAS = 120
ARQUIVOS_CONGELADOS = ("perguntas.jsonl", "faturas_sinteticas.jsonl", "distribuicao_anotadores.md")

ANOTADORES = (
    "pedrohpsantos",
    "TalitaaNunes",
    "NatyEvelin",
    "luizoryone",
    "mariadenis",
    "RaissaOliveira19",
)
ITENS_POR_ANOTADOR = 30
PERGUNTAS_POR_ANOTADOR = 12  # 12 perguntas + 18 faturas = 30 itens

# Parâmetros SINTÉTICOS (não oficiais), só para gerar aritmética coerente.
TARIFA_KWH = Decimal("0.80")
ADICIONAL_BANDEIRA = {
    "verde": Decimal("0.00"),
    "amarela": Decimal("0.02"),
    "vermelha 1": Decimal("0.05"),
    "vermelha 2": Decimal("0.08"),
}
ALIQUOTA_ICMS = Decimal("0.20")
VALOR_CONTRIBUICAO = Decimal("12.00")  # linha sintética genérica, não é a CIP/COSIP real
ANOMALIAS = (
    "consumo_diverge_das_leituras",
    "total_nao_fecha",
    "item_energia_incoerente",
    "bandeira_adicional_incorreto",
    "item_duplicado",
    "aliquota_icms_incoerente",
)


def _c(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fatura(indice: int, rng: random.Random) -> dict[str, Any]:
    mes = date(2026, rng.randint(1, 10), 1)
    consumo = Decimal(rng.randint(60, 480))
    anterior = Decimal(rng.randint(1000, 90000))
    bandeira = rng.choice(list(ADICIONAL_BANDEIRA))
    energia = _c(consumo * TARIFA_KWH)
    adicional = _c(consumo * ADICIONAL_BANDEIRA[bandeira])
    itens: list[dict[str, Any]] = [
        {
            "descricao": "Consumo de energia",
            "quantidade": consumo,
            "tarifa": TARIFA_KWH,
            "valor": energia,
        },
        {
            "descricao": "Adicional de bandeira",
            "quantidade": consumo,
            "tarifa": ADICIONAL_BANDEIRA[bandeira],
            "valor": adicional,
        },
        {
            "descricao": "Contribuição municipal (sintética)",
            "quantidade": None,
            "tarifa": None,
            "valor": VALOR_CONTRIBUICAO,
        },
    ]
    gabarito = ["confere", "confere", "confere"]
    leitura_atual = anterior + consumo
    aliquota = ALIQUOTA_ICMS
    anomalia = None
    if rng.random() < 0.5:
        anomalia = rng.choice(ANOMALIAS)
        if anomalia == "consumo_diverge_das_leituras":
            leitura_atual = anterior + consumo + Decimal(rng.randint(15, 60))
            gabarito = ["diverge_A", "confere", "confere"]
        elif anomalia == "item_energia_incoerente":
            itens[0]["valor"] = _c(energia * Decimal("1.15"))
            gabarito = ["diverge_A", "confere", "confere"]
        elif anomalia == "bandeira_adicional_incorreto":
            itens[1]["valor"] = _c(adicional * 2 + Decimal("3.00"))
            gabarito = ["confere", "diverge_A", "confere"]
        elif anomalia == "item_duplicado":
            itens.append(dict(itens[2]))
            gabarito = ["confere", "confere", "confere", "diverge_A"]
        elif anomalia == "aliquota_icms_incoerente":
            aliquota = Decimal("0.35")
    total = _c(sum((i["valor"] for i in itens), Decimal(0)))
    if anomalia == "total_nao_fecha":
        total = _c(total + Decimal(rng.randint(5, 40)))
    return {
        "id": f"GS-F{indice:03d}",
        "distribuidora": "Neoenergia Brasília",
        "grupo_tarifario": "B1",
        "mes_referencia": mes.isoformat(),
        "leitura_anterior": str(anterior),
        "leitura_atual": str(leitura_atual),
        "consumo_kwh": str(consumo),
        "bandeira": bandeira,
        "aliquota_icms": str(aliquota),
        "itens": [{k: (None if v is None else str(v)) for k, v in item.items()} for item in itens],
        "total": str(total),
        "anomalia_injetada": anomalia,
        "gabarito_itens": gabarito,
        "gabarito_fatura": "diverge_A" if anomalia else "confere",
        "parametros": "sinteticos",
        "revisao_humana": "pendente",
    }


def gerar_faturas(semente: int = SEMENTE, n: int = N_FATURAS) -> list[dict[str, Any]]:
    rng = random.Random(semente)
    return [_fatura(i, rng) for i in range(1, n + 1)]


def ler_perguntas(pasta: Path = PASTA) -> list[dict[str, Any]]:
    linhas = (pasta / "perguntas.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(linha) for linha in linhas if linha.strip()]


def distribuir(
    perguntas: list[dict[str, Any]], faturas: list[dict[str, Any]], semente: int = SEMENTE
) -> dict[str, list[str]]:
    """30 itens por pessoa (12 perguntas + 18 faturas), sem repetição e embaralhados com seed."""
    rng = random.Random(semente + 1)
    ids_q = [p["id"] for p in perguntas]
    ids_f = [f["id"] for f in faturas]
    rng.shuffle(ids_q)
    rng.shuffle(ids_f)
    faturas_por = ITENS_POR_ANOTADOR - PERGUNTAS_POR_ANOTADOR
    saida: dict[str, list[str]] = {}
    for k, nome in enumerate(ANOTADORES):
        q = ids_q[k * PERGUNTAS_POR_ANOTADOR : (k + 1) * PERGUNTAS_POR_ANOTADOR]
        f = ids_f[k * faturas_por : (k + 1) * faturas_por]
        saida[nome] = sorted(q) + sorted(f)
    return saida


def texto_distribuicao(dist: dict[str, list[str]]) -> str:
    total = sum(len(v) for v in dist.values())
    linhas = [
        "# Distribuição de anotadores (golden set S3)",
        "",
        f"Cada pessoa anota **{ITENS_POR_ANOTADOR} itens** ({PERGUNTAS_POR_ANOTADOR} perguntas e "
        f"{ITENS_POR_ANOTADOR - PERGUNTAS_POR_ANOTADOR} faturas), sorteados com semente fixa "
        f"({SEMENTE + 1}) e sem repetição entre pessoas: {total} itens ao todo.",
        "",
        "> O conjunto tem 120 perguntas e 200 faturas (320 itens). Seis pessoas anotando 30 itens "
        "cobrem 180; o restante fica com o gabarito de construção (citação canônica e anomalia "
        "injetada) até uma segunda rodada. TODO: decidir se haverá segunda rodada de anotação.",
        "",
        "Cada anotador confere o gabarito do item e registra concordo/discordo com justificativa. "
        "Nenhuma fatura real entra no repositório.",
        "",
    ]
    for nome, ids in dist.items():
        linhas += [f"## {nome}", "", ", ".join(ids), ""]
    return "\n".join(linhas)


def _jsonl(linhas: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in linhas)


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def escrever_checksums(pasta: Path = PASTA) -> str:
    linhas = [f"{sha256(pasta / nome)}  {nome}" for nome in ARQUIVOS_CONGELADOS]
    conteudo = "\n".join(linhas) + "\n"
    (pasta / "checksums.sha256").write_text(conteudo, encoding="utf-8")
    return conteudo


def verificar(pasta: Path = PASTA) -> list[str]:
    """Devolve a lista de problemas (vazia = conjunto íntegro)."""
    problemas: list[str] = []
    arq = pasta / "checksums.sha256"
    if not arq.exists():
        return ["checksums.sha256 ausente"]
    esperados = {}
    for linha in arq.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            h, nome = linha.split("  ", 1)
            esperados[nome] = h
    for nome in ARQUIVOS_CONGELADOS:
        if nome not in esperados:
            problemas.append(f"{nome} sem hash registrado")
        elif not (pasta / nome).exists() or sha256(pasta / nome) != esperados[nome]:
            problemas.append(f"{nome} diverge do hash congelado")
    if len(ler_perguntas(pasta)) != N_PERGUNTAS:
        problemas.append(f"esperadas {N_PERGUNTAS} perguntas")
    n_f = len((pasta / "faturas_sinteticas.jsonl").read_text(encoding="utf-8").splitlines())
    if n_f != N_FATURAS:
        problemas.append(f"esperadas {N_FATURAS} faturas, encontradas {n_f}")
    return problemas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--verificar", action="store_true", help="só confere os hashes congelados")
    args = ap.parse_args(argv)
    if args.verificar:
        problemas = verificar()
        for p in problemas:
            print(f"ERRO: {p}", file=sys.stderr)
        print("Golden set íntegro." if not problemas else "Golden set com divergências.")
        return 1 if problemas else 0
    perguntas = ler_perguntas()
    if len(perguntas) != N_PERGUNTAS:
        print(f"ERRO: esperadas {N_PERGUNTAS} perguntas, há {len(perguntas)}.", file=sys.stderr)
        return 1
    faturas = gerar_faturas()
    (PASTA / "faturas_sinteticas.jsonl").write_text(_jsonl(faturas), encoding="utf-8")
    (PASTA / "distribuicao_anotadores.md").write_text(
        texto_distribuicao(distribuir(perguntas, faturas)), encoding="utf-8"
    )
    print(escrever_checksums(), end="")
    com_anomalia = sum(1 for f in faturas if f["anomalia_injetada"])
    print(f"{len(perguntas)} perguntas, {len(faturas)} faturas ({com_anomalia} com anomalia).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
