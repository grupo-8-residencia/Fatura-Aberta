#!/usr/bin/env python3
"""Acurácia por campo da leitura de foto (issue #41). Pode rodar com dados reais, só localmente.

Compara o que foi extraído das fotos com o gabarito conferido à mão e calcula o acerto **por
campo**, para o gate da S5 (≥ 90% nos campos-chave). Os dois arquivos são JSON no formato
`{"<id da foto>": {"total": "81,95", "itens": [{"descricao": "...", "valor": "39,41"}], ...}}`,
com os mesmos nomes de campo do contrato `Fatura`.

PRIVACIDADE: o relatório mostra só contagens e percentuais, nunca os valores lidos. Mesmo assim,
mantenha os arquivos de entrada fora do Git: com fotos reais eles têm dados da fatura.

Uso:
    uv run python scripts/acuracia_por_campo.py previsto.json gabarito.json [--saida relatorio.md]

Código de saída: 0 se todos os campos-chave passaram, 1 se algum ficou abaixo da meta, 2 se os
arquivos de entrada não puderam ser lidos.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

NUMERICOS = ("leitura_anterior", "leitura_atual", "consumo_kwh", "aliquota_icms", "total")
TEXTOS = ("distribuidora", "grupo_tarifario", "bandeira")
CAMPOS = ("mes_referencia", *NUMERICOS, *TEXTOS)
# TODO: confirmar a lista de campos-chave com o Pedro (F5).
CAMPOS_CHAVE = ("mes_referencia", "consumo_kwh", "total", "aliquota_icms", "bandeira")
META_PADRAO = 0.90
TOLERANCIA_SOMA = Decimal("0.01")

_NUMERO = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")
_MES_ANO = re.compile(r"^(\d{1,2})/(\d{4})$")

Foto = Mapping[str, Any]


@dataclass(frozen=True)
class Resultado:
    campo: str
    avaliados: int
    acertos: int

    @property
    def taxa(self) -> float:
        return self.acertos / self.avaliados if self.avaliados else 0.0


def _numero(valor: object) -> Decimal | None:
    """Número no formato brasileiro; `None` se vazio ou inválido (conta como erro)."""
    if valor is None:
        return None
    limpo = re.sub(r"\s|R\$|%", "", str(valor))
    if limpo.endswith("-"):
        limpo = "-" + limpo[:-1]
    if not _NUMERO.match(limpo):
        return None
    return Decimal(limpo.replace(".", "").replace(",", "."))


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    limpo = " ".join(str(valor).split()).casefold()
    return "neoenergia" if "neoenergia" in limpo else (limpo or None)


def normalizar(campo: str, valor: object) -> object | None:
    """Forma comparável do valor de um campo; `None` quando ausente ou inválido."""
    if campo in NUMERICOS:
        return _numero(valor)
    if campo == "mes_referencia":
        achado = _MES_ANO.match(str(valor).strip()) if valor is not None else None
        return (int(achado.group(2)), int(achado.group(1))) if achado else None
    return _texto(valor)


def _linhas(foto: Foto) -> list[tuple[str, Decimal]]:
    """Itens como (descrição normalizada, valor), ignorando linhas incompletas ou inválidas."""
    itens = foto.get("itens")
    linhas = []
    for item in itens if isinstance(itens, list) else []:
        if not isinstance(item, Mapping):
            continue
        descricao, valor = _texto(item.get("descricao")), _numero(item.get("valor"))
        if descricao and valor is not None:
            linhas.append((descricao, valor))
    return linhas


def avaliar(previsto: Mapping[str, Foto], gabarito: Mapping[str, Foto]) -> list[Resultado]:
    """Acerto por campo, por linha de item e por soma dos itens. Foto sem previsão erra tudo."""
    contagem: dict[str, list[int]] = {campo: [0, 0] for campo in CAMPOS}
    linhas_total = linhas_certas = soma_avaliadas = soma_certas = 0

    for id_foto, esperado in gabarito.items():
        obtido: Foto = previsto.get(id_foto, {})
        for campo in CAMPOS:
            certo = normalizar(campo, esperado.get(campo))
            if certo is None:  # o gabarito não tem o campo: não se aplica
                continue
            contagem[campo][0] += 1
            contagem[campo][1] += normalizar(campo, obtido.get(campo)) == certo

        restantes = _linhas(obtido)
        for linha in _linhas(esperado):
            linhas_total += 1
            if linha in restantes:
                restantes.remove(linha)  # cada linha prevista vale uma vez
                linhas_certas += 1

        previstas, total = _linhas(obtido), _numero(obtido.get("total"))
        if previstas and total is not None:
            soma_avaliadas += 1
            soma_certas += (
                abs(sum((v for _, v in previstas), Decimal(0)) - total) <= TOLERANCIA_SOMA
            )

    resultados = [Resultado(campo, n, a) for campo, (n, a) in contagem.items() if n]
    resultados.append(Resultado("itens (linhas corretas)", linhas_total, linhas_certas))
    resultados.append(
        Resultado("itens (soma igual ao total previsto)", soma_avaliadas, soma_certas)
    )
    return resultados


def relatorio(
    resultados: Sequence[Resultado], chave: Sequence[str], meta: float
) -> tuple[str, bool]:
    """Tabela em Markdown (só contagens) e se todos os campos-chave passaram."""
    por_campo = {r.campo: r for r in resultados}
    linhas = [
        "| Campo | Avaliados | Acertos | Acerto | Campo-chave | Situação |",
        "|---|---|---|---|---|---|",
    ]
    passou = True
    for r in resultados:
        eh_chave = r.campo in chave
        situacao = "—"
        if eh_chave:
            ok = r.taxa >= meta
            passou &= ok
            situacao = "passou" if ok else "abaixo da meta"
        linhas.append(
            f"| `{r.campo}` | {r.avaliados} | {r.acertos} | {r.taxa:.0%} "
            f"| {'sim' if eh_chave else 'não'} | {situacao} |"
        )
    for campo in chave:
        if campo not in por_campo:
            passou = False
            linhas.append(f"| `{campo}` | 0 | 0 | — | sim | sem dados no gabarito |")
    veredito = "PASSOU" if passou else "FALHOU"
    linhas.append(f"\nGate: **{veredito}** (todos os campos-chave com acerto ≥ {meta:.0%}).")
    return "\n".join(linhas) + "\n", passou


def _carregar(caminho: Path) -> dict[str, Foto]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, dict) or not all(isinstance(v, dict) for v in dados.values()):
        raise ValueError("formato inesperado")
    return dados


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Acurácia por campo da leitura de foto (#41).")
    parser.add_argument("previsto", type=Path, help="JSON com o que foi extraído")
    parser.add_argument("gabarito", type=Path, help="JSON com o gabarito conferido à mão")
    parser.add_argument("--saida", type=Path, help="grava o relatório neste arquivo")
    parser.add_argument("--meta", type=float, default=META_PADRAO, help="acerto mínimo (0 a 1)")
    parser.add_argument("--campos-chave", nargs="+", default=list(CAMPOS_CHAVE))
    args = parser.parse_args(argv)

    try:
        previsto, gabarito = _carregar(args.previsto), _carregar(args.gabarito)
    except (OSError, ValueError):
        # Não mostra o conteúdo nem o motivo detalhado: o arquivo pode ter dados de fatura.
        print("Não foi possível ler os arquivos de entrada (JSON de fotos).", file=sys.stderr)
        return 2

    texto, passou = relatorio(avaliar(previsto, gabarito), args.campos_chave, args.meta)
    if args.saida:
        args.saida.write_text(texto, encoding="utf-8")
    print(texto)
    return 0 if passou else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
