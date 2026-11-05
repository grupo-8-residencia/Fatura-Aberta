#!/usr/bin/env python3
"""Mapeia os layouts de fatura com `pdftotext -layout` (issue #9). Roda só localmente.

Lê os PDFs de `faturas-reais/` (fora do Git), separa as faturas pelo layout (corte em
maio/2026) e grava em `faturas-reais/mapa/`:

    - um esqueleto mascarado de cada fatura (`<layout>/fatura-NN.txt`): dígitos viram 9 e as
      linhas com rótulo pessoal perdem o valor, para estudar a posição de cada campo;
    - `resumo.md`: em que página, linha e coluna cada rótulo aparece, por layout.

PRIVACIDADE: o esqueleto ainda pode ter nome ou endereço sem rótulo (ex.: no cabeçalho).
A saída fica em `faturas-reais/`, que o `.gitignore` exclui. Para `docs/frentes/f4.md` só vão
rótulos e posições, nunca trechos do esqueleto.

Uso:
    uv run python scripts/mapear_layouts.py [pasta_das_faturas] [pasta_de_saida]
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fa_extracao.anonimizacao import anonimizar
from fa_extracao.layouts import CORTE_NOVO_LAYOUT

# Rótulos candidatos para cada campo do contrato `Fatura` e para os dados pessoais que o parser
# descarta. São amplos de propósito: o objetivo é achar onde o rótulo real está.
ROTULOS: dict[str, re.Pattern[str]] = {
    campo: re.compile(padrao, re.IGNORECASE)
    for campo, padrao in {
        "mes_referencia": r"refer[eê]ncia|m[eê]s/ano",
        "leitura_anterior": r"leitura anterior|anterior",
        "leitura_atual": r"leitura atual|atual",
        "consumo_kwh": r"consumo|kwh",
        "bandeira": r"bandeira",
        "aliquota_icms": r"icms",
        "total": r"total a pagar|valor a pagar|valor total|\btotal\b",
        "itens": r"itens da fatura|descri[cç][aã]o",
        "pii_nome": r"\bnome\b|cliente|titular",
        "pii_endereco": r"endere[cç]o|\bcep\b",
        "pii_instalacao": r"instala[cç][aã]o|unidade consumidora|\buc\b",
        "pii_documento": r"\bcpf\b|\bcnpj\b",
    }.items()
}

_MES_ANO = re.compile(r"\b(0[1-9]|1[0-2])/(20\d{2})\b")
_REFERENCIA = ROTULOS["mes_referencia"]


@dataclass(frozen=True)
class Posicao:
    pagina: int
    linha: int
    coluna: int


def mes_referencia(texto: str) -> date | None:
    """Primeiro MM/AAAA na linha do rótulo de referência ou logo abaixo dele."""
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if _REFERENCIA.search(linha):
            for candidata in linhas[i : i + 3]:
                achado = _MES_ANO.search(candidata)
                if achado:
                    return date(int(achado.group(2)), int(achado.group(1)), 1)
    return None


def layout_de(mes: date | None) -> str:
    if mes is None:
        return "indefinido"
    return "posterior" if mes >= CORTE_NOVO_LAYOUT else "anterior"


def mascarar(texto: str) -> str:
    """Remove linhas com rótulo pessoal, CPF, CNPJ e e-mail, e troca todo dígito por 9."""
    return re.sub(r"\d", "9", anonimizar(texto))


def localizar_rotulos(texto: str) -> dict[str, list[Posicao]]:
    """Posições (1-based) de cada rótulo candidato. Páginas são separadas por form feed."""
    posicoes: dict[str, list[Posicao]] = defaultdict(list)
    for p, pagina in enumerate(texto.split("\f"), start=1):
        for n, linha in enumerate(pagina.splitlines(), start=1):
            for campo, padrao in ROTULOS.items():
                for achado in padrao.finditer(linha):
                    posicoes[campo].append(Posicao(p, n, achado.start() + 1))
    return dict(posicoes)


def resumo(mapas: dict[str, list[dict[str, list[Posicao]]]]) -> str:
    """Tabela por layout: em quantas faturas cada rótulo aparece e as posições mais comuns."""
    partes = ["# Resumo dos layouts (local, não versionar)\n"]
    for layout, faturas in sorted(mapas.items()):
        partes.append(f"\n## Layout {layout} ({len(faturas)} faturas)\n")
        partes.append("| Campo | Faturas com o rótulo | Posições mais comuns (pág:linha:col) |")
        partes.append("|---|---|---|")
        for campo in ROTULOS:
            contagem: dict[Posicao, int] = defaultdict(int)
            presentes = 0
            for mapa in faturas:
                if campo in mapa:
                    presentes += 1
                    for pos in mapa[campo]:
                        contagem[pos] += 1
            comuns = sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0].pagina, kv[0].linha))
            texto = ", ".join(f"{p.pagina}:{p.linha}:{p.coluna} ({n}x)" for p, n in comuns[:3])
            partes.append(f"| {campo} | {presentes}/{len(faturas)} | {texto or '—'} |")
    return "\n".join(partes) + "\n"


def pdftotext(pdf: Path) -> str:
    try:
        saida = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("pdftotext não encontrado. Instale o Poppler (no Git Bash já vem em /mingw64).")
    except subprocess.CalledProcessError:
        # Não mostra o nome do arquivo: ele pode ter o nome do titular.
        print("Aviso: um PDF não pôde ser lido e foi ignorado.", file=sys.stderr)
        return ""
    return saida.stdout.decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    entrada = Path(argv[0]) if argv else Path("faturas-reais")
    saida = Path(argv[1]) if len(argv) > 1 else entrada / "mapa"
    pdfs = sorted(p for p in entrada.glob("*.pdf") if p.is_file())
    if not pdfs:
        print(f"Nenhum PDF em {entrada}/.", file=sys.stderr)
        return 1

    mapas: dict[str, list[dict[str, list[Posicao]]]] = defaultdict(list)
    for i, pdf in enumerate(pdfs, start=1):
        texto = pdftotext(pdf)
        if not texto:
            continue
        layout = layout_de(mes_referencia(texto))
        destino = saida / layout / f"fatura-{i:02d}.txt"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(mascarar(texto), encoding="utf-8")
        mapas[layout].append(localizar_rotulos(texto))

    (saida / "resumo.md").write_text(resumo(mapas), encoding="utf-8")
    contagem = ", ".join(f"{layout}: {len(f)}" for layout, f in sorted(mapas.items()))
    print(f"{sum(len(f) for f in mapas.values())} faturas mapeadas ({contagem}) em {saida}/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
