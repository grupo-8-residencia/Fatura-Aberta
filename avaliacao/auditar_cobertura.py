#!/usr/bin/env python3
"""Audita, por identificador, a cobertura dos 4 testes e do B1 da Sprint 3.

Cobertura exigida (golden set congelado):
- B1 (motor, sem LLM): 200 faturas.
- T1 `LLM`: 120 perguntas e 200 faturas.
- T2 `RAG`: 120 perguntas.
- T3 `B2`: 120 perguntas e 200 faturas.
- T4 `B3`: 120 perguntas e 200 faturas.

Um item só conta como concluído se o id está no golden set, aparece uma vez e o registro é válido
(`valido` ausente ou verdadeiro; no B1 o veredito não é "invalido"). Ids que não estão no
conjunto esperado do baseline (por exemplo, rodados só para o juiz) ficam em `fora_do_conjunto`.
Os pendentes saem calculados a partir dos ids, nunca de contagens.

Uso:
    python avaliacao/auditar_cobertura.py              # resumo e JSON de auditoria
    python avaliacao/auditar_cobertura.py --faltantes  # só os ids pendentes de cada baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = Path(__file__).resolve().parent / "resultados"
GOLDEN = RAIZ / "dados" / "golden-set"

# (conjunto, baseline) -> o que o resultado deve cobrir
EXIGIDO: tuple[tuple[str, str], ...] = (
    ("faturas", "B1"),
    ("perguntas", "LLM"),
    ("faturas", "LLM"),
    ("perguntas", "RAG"),
    ("perguntas", "B2"),
    ("faturas", "B2"),
    ("perguntas", "B3"),
    ("faturas", "B3"),
)


def ids_esperados(golden: Path = GOLDEN) -> dict[str, list[str]]:
    def ler(nome: str) -> list[str]:
        linhas = (golden / nome).read_text(encoding="utf-8").splitlines()
        return [json.loads(x)["id"] for x in linhas if x.strip()]

    return {"perguntas": ler("perguntas.jsonl"), "faturas": ler("faturas_sinteticas.jsonl")}


def _valido(conjunto: str, baseline: str, item: dict[str, Any]) -> bool:
    if conjunto == "faturas" and baseline == "B1":
        return item.get("veredito") != "invalido"
    return bool(item.get("valido", True))


def carregar(principal: Path, extra: Path | None) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Junta os arquivos da rodada; o B1 completo vem de `b1_200_faturas` quando houver."""
    saida: dict[str, dict[str, list[dict[str, Any]]]] = {"perguntas": {}, "faturas": {}}
    for caminho in (principal, extra):
        if caminho is None or not caminho.exists():
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        for conjunto in ("perguntas", "faturas"):
            for b, itens in dados.get(conjunto, {}).items():
                saida[conjunto][b] = itens
        if dados.get("b1_200_faturas"):
            saida["faturas"]["B1"] = dados["b1_200_faturas"]
    return saida


def auditar(
    resultados: dict[str, dict[str, list[dict[str, Any]]]], esperados: dict[str, list[str]]
) -> dict[str, Any]:
    linhas: dict[str, Any] = {}
    completo = True
    for conjunto, baseline in EXIGIDO:
        esperado = esperados[conjunto]
        itens = resultados.get(conjunto, {}).get(baseline, [])
        contagem = Counter(i["id"] for i in itens)
        validos = {i["id"] for i in itens if _valido(conjunto, baseline, i)}
        invalidos = sorted({i["id"] for i in itens} - validos)
        concluidos = [x for x in esperado if x in validos and contagem[x] == 1]
        pendentes = [x for x in esperado if x not in concluidos and x not in invalidos]
        linha = {
            "esperado": len(esperado),
            "concluidos": len(concluidos),
            "invalidos": invalidos,
            "duplicados": sorted(k for k, v in contagem.items() if v > 1),
            "pendentes": pendentes,
            "fora_do_conjunto": sorted(set(contagem) - set(esperado)),
            "completo": len(concluidos) + len(invalidos) == len(esperado) and not pendentes,
        }
        completo = completo and bool(linha["completo"])
        linhas[f"{conjunto}/{baseline}"] = linha
    return {"completo": completo, "baselines": linhas}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--principal", type=Path, default=RESULTADOS / "s3-rodada.json")
    ap.add_argument("--extra", type=Path, default=RESULTADOS / "s3-rodada-extra.json")
    ap.add_argument("--saida", type=Path, default=RESULTADOS / "s3-cobertura.json")
    ap.add_argument("--faltantes", action="store_true", help="imprime só os ids pendentes")
    ap.add_argument("--sem-gravar", action="store_true")
    args = ap.parse_args(argv)
    r = auditar(carregar(args.principal, args.extra), ids_esperados())
    if args.faltantes:
        for nome, linha in r["baselines"].items():
            print(nome, " ".join(linha["pendentes"]))
        return 0 if r["completo"] else 1
    if not args.sem_gravar:
        args.saida.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for nome, linha in r["baselines"].items():
        print(
            f"{nome:<14} {linha['concluidos']:>3}/{linha['esperado']}"
            f"  pendentes={len(linha['pendentes'])}  inválidos={len(linha['invalidos'])}"
            f"  fora={len(linha['fora_do_conjunto'])}"
        )
    print("COBERTURA COMPLETA" if r["completo"] else "COBERTURA INCOMPLETA: sem recomendação final")
    return 0 if r["completo"] else 1


if __name__ == "__main__":
    sys.exit(main())
