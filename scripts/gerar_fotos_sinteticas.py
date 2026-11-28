#!/usr/bin/env python3
"""Gera fotos sintéticas de faturas com gabarito conhecido (issue #41).

Entrada: as primeiras N faturas de `dados/golden-set/faturas_sinteticas.jsonl`, em ordem (sem
escolha por resultado). Cada fatura vira uma imagem JPEG com layout de fatura em pt-BR, com
degradações de câmera (rotação, desfoque, brilho, ruído e compressão). Todas as degradações usam
semente fixa, então o mesmo comando gera os mesmos bytes.

Saída, em `dados/benchmark/sinteticas/fotos/`:
    - `foto-01.jpg` ... `foto-40.jpg`;
    - `gabarito.json`: o valor que foi desenhado em cada foto, no formato que
      `scripts/acuracia_por_campo.py` compara.

Os dados são fictícios: nenhum nome, endereço ou número de instalação é desenhado. O gabarito é o
dado da fatura sintética, não uma conferência humana de foto real. Por isso a medição com estas
fotos tende a ser mais otimista do que com fotos reais (ver docs/avaliacao/acuracia-fotos.md).

Uso (na raiz do repositório):
    uv run python scripts/gerar_fotos_sinteticas.py
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "dados" / "golden-set" / "faturas_sinteticas.jsonl"
DESTINO = RAIZ / "dados" / "benchmark" / "sinteticas" / "fotos"
QUANTIDADE = 40
SEMENTE_BASE = 41

LARGURA, ALTURA = 1240, 1754  # A4 a 150 dpi
MARGEM = 80
# Bandeira como a candidata a reconhece (fa_extracao.candidata._BANDEIRAS).
BANDEIRAS = {
    "verde": "Verde",
    "amarela": "Amarela",
    "vermelha 1": "Vermelha 1",
    "vermelha 2": "Vermelha 2",
}


def _dec(valor: str | None) -> Decimal | None:
    return None if valor in (None, "") else Decimal(valor)


def _br(valor: Decimal, casas: int) -> str:
    """Número no formato brasileiro com as casas pedidas: 1234.5 -> '1.234,50'."""
    q = valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    inteiro, _, frac = f"{abs(q):f}".partition(".")
    grupos: list[str] = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    texto = ".".join(grupos)
    if casas:
        texto += "," + frac.ljust(casas, "0")
    return ("-" if q < 0 else "") + texto


def _mes(iso: str) -> str:
    ano, mes, _ = (int(p) for p in iso.split("-"))
    return f"{mes:02d}/{ano}"


def gabarito_de(fatura: Mapping[str, Any]) -> dict[str, Any]:
    """Valores que a foto desenha, no formato brasileiro do acuracia_por_campo."""
    itens = []
    for item in fatura["itens"]:
        quantidade, tarifa = _dec(item.get("quantidade")), _dec(item.get("tarifa"))
        itens.append(
            {
                "descricao": item["descricao"],
                "quantidade": None if quantidade is None else _br(quantidade, 0),
                "tarifa": None if tarifa is None else _br(tarifa, 5),
                "valor": _br(Decimal(item["valor"]), 2),
            }
        )
    return {
        "distribuidora": "Neoenergia Brasília",
        "grupo_tarifario": fatura["grupo_tarifario"],
        "mes_referencia": _mes(fatura["mes_referencia"]),
        "leitura_anterior": _br(Decimal(fatura["leitura_anterior"]), 0),
        "leitura_atual": _br(Decimal(fatura["leitura_atual"]), 0),
        "consumo_kwh": _br(Decimal(fatura["consumo_kwh"]), 0),
        "aliquota_icms": _br(Decimal(fatura["aliquota_icms"]) * 100, 2),
        "bandeira": BANDEIRAS[fatura["bandeira"]],
        "total": _br(Decimal(fatura["total"]), 2),
        "itens": itens,
    }


def _linhas_da_fatura(g: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Linhas de texto (rótulo, valor) da foto, na ordem em que aparecem na página."""
    return [
        ("SINTÉTICA: NÃO É FATURA REAL", ""),
        ("NEOENERGIA DISTRIBUIÇÃO BRASÍLIA S.A.", ""),
        ("CLASSIFICAÇÃO", f"{g['grupo_tarifario']} RESIDENCIAL"),
        ("REF: MÊS/ANO", g["mes_referencia"]),
        ("LEITURA ANTERIOR (kWh)", g["leitura_anterior"]),
        ("LEITURA ATUAL (kWh)", g["leitura_atual"]),
        ("CONSUMO (kWh)", g["consumo_kwh"]),
        ("BANDEIRA TARIFÁRIA", g["bandeira"]),
        ("ALÍQUOTA DO ICMS (%)", g["aliquota_icms"]),
    ]


# Fonte com acentos do português (a padrão do Pillow não tem Í, Ç, Ã e outras). Em outras máquinas,
# aponte para uma fonte TrueType equivalente com a variável FA_FONTE_FOTOS.
FONTE_PADRAO = os.getenv("FA_FONTE_FOTOS", "C:/Windows/Fonts/arial.ttf")


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(FONTE_PADRAO, tamanho)
    except OSError:
        return ImageFont.load_default(size=tamanho)


def _desenhar(g: Mapping[str, Any]) -> Image.Image:
    imagem = Image.new("RGB", (LARGURA, ALTURA), "white")
    desenho = ImageDraw.Draw(imagem)
    fonte = _fonte(34)
    fonte_pequena = _fonte(28)
    y = MARGEM
    for rotulo, valor in _linhas_da_fatura(g):
        desenho.text((MARGEM, y), rotulo, fill="black", font=fonte)
        if valor:
            desenho.text((700, y), valor, fill="black", font=fonte)
        y += 64
    y += 30
    colunas = (MARGEM, 700, 880, 1040)
    for titulo, x in zip(("DESCRIÇÃO", "QTD (kWh)", "TARIFA", "VALOR (R$)"), colunas, strict=True):
        desenho.text((x, y), titulo, fill="black", font=fonte_pequena)
    y += 56
    for item in g["itens"]:
        for valor, x in zip(
            (item["descricao"], item["quantidade"], item["tarifa"], item["valor"]),
            colunas,
            strict=True,
        ):
            if valor:
                desenho.text((x, y), valor, fill="black", font=fonte_pequena)
        y += 50
    y += 40
    desenho.text((MARGEM, y), "TOTAL A PAGAR (R$)", fill="black", font=fonte)
    desenho.text((700, y), g["total"], fill="black", font=fonte)
    return imagem


def _degradar(imagem: Image.Image, rng: random.Random) -> bytes:
    """Rotação leve, brilho, desfoque, ruído e compressão, como uma foto de celular."""
    imagem = imagem.rotate(
        rng.uniform(-2.5, 2.5), fillcolor="white", resample=Image.Resampling.BICUBIC
    )
    imagem = ImageEnhance.Brightness(imagem).enhance(rng.uniform(0.8, 1.1))
    imagem = imagem.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.1)))
    # Ruído com a mesma semente: Image.effect_noise usa um gerador interno sem semente.
    ruido = Image.frombytes("L", imagem.size, rng.randbytes(imagem.size[0] * imagem.size[1]))
    ruido = ruido.convert("RGB")
    imagem = Image.blend(imagem, ruido, rng.uniform(0.02, 0.06))
    saida = io.BytesIO()
    imagem.save(saida, format="JPEG", quality=rng.randint(35, 60))
    return saida.getvalue()


def gerar(origem: Path, destino: Path, quantidade: int) -> dict[str, dict[str, Any]]:
    faturas = [json.loads(linha) for linha in origem.read_text(encoding="utf-8").splitlines()]
    escolhidas = faturas[:quantidade]
    destino.mkdir(parents=True, exist_ok=True)
    gabarito: dict[str, dict[str, Any]] = {}
    for indice, fatura in enumerate(escolhidas, start=1):
        identificador = f"foto-{indice:02d}"
        rng = random.Random(SEMENTE_BASE + indice)
        g = gabarito_de(fatura)
        (destino / f"{identificador}.jpg").write_bytes(_degradar(_desenhar(g), rng))
        gabarito[identificador] = g
    (destino / "gabarito.json").write_text(
        json.dumps(gabarito, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return gabarito


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera fotos sintéticas com gabarito (#41).")
    parser.add_argument("--origem", type=Path, default=ORIGEM)
    parser.add_argument("--destino", type=Path, default=DESTINO)
    parser.add_argument("--quantidade", type=int, default=QUANTIDADE)
    args = parser.parse_args(argv)
    gabarito = gerar(args.origem, args.destino, args.quantidade)
    print(f"{len(gabarito)} fotos e gabarito em {args.destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
