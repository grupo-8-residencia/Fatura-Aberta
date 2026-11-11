#!/usr/bin/env python3
"""Falso alarme do motor de nível A nas faturas corretas (Gate da Sprint S2 - F3).

Critério do gate: nenhum falso alarme de nível A nas faturas corretas. Fórmula (TFA_A):
docs/avaliacao/metricas.md, seção 4.

Dois conjuntos sintéticos, sem dado pessoal:
- `dados/benchmark/sinteticas/faturas_v0.jsonl` (gerador v0 da F3, 30 faturas, 15 corretas);
- `dados/golden-set/faturas_sinteticas.jsonl` (200 faturas do golden set, 103 corretas).

Um "alarme" é um achado de nível A que não é abstenção e em que o valor esperado difere do cobrado.
Também mede a detecção nas faturas com erro injetado, para mostrar que o motor não "passa" só por
nunca acusar nada.

Uso: .venv/bin/python avaliacao/medir_falso_alarme_s2.py
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic

from fa_contratos import Achado, Fatura, ItemFatura, Nivel
from fa_motor import analisar_nivel_a

RAIZ = Path(__file__).resolve().parents[1]
BENCHMARK_V0 = RAIZ / "dados" / "benchmark" / "sinteticas" / "faturas_v0.jsonl"
GOLDEN = RAIZ / "dados" / "golden-set" / "faturas_sinteticas.jsonl"
SAIDA_PADRAO = Path(__file__).resolve().parent / "resultados" / "s2-falso-alarme.json"


def _dec(v: str | None) -> Decimal | None:
    return None if v is None else Decimal(v)


def _fatura_golden(r: dict[str, Any]) -> Fatura:
    return Fatura(
        distribuidora=r["distribuidora"],
        grupo_tarifario=r["grupo_tarifario"],
        mes_referencia=date.fromisoformat(r["mes_referencia"]),
        leitura_anterior=_dec(r["leitura_anterior"]),
        leitura_atual=_dec(r["leitura_atual"]),
        consumo_kwh=Decimal(r["consumo_kwh"]),
        bandeira=r["bandeira"],
        aliquota_icms=_dec(r["aliquota_icms"]),
        itens=[
            ItemFatura(
                descricao=i["descricao"],
                quantidade=_dec(i["quantidade"]),
                tarifa=_dec(i["tarifa"]),
                valor=Decimal(i["valor"]),
            )
            for i in r["itens"]
        ],
        total=Decimal(r["total"]),
    )


def alarme(a: Achado) -> bool:
    return (
        a.nivel == Nivel.A
        and not a.abstencao
        and a.valor_esperado is not None
        and a.valor_cobrado is not None
        and a.valor_esperado != a.valor_cobrado
    )


def _ler(caminho: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in caminho.read_text(encoding="utf-8").splitlines() if x.strip()]


def _carregar_v0() -> list[tuple[str, bool, Fatura]]:
    """Devolve (id, tem_erro, fatura) do benchmark v0."""
    return [
        (str(r["id"]), r["erro_injetado"] is not None, Fatura.model_validate(r["fatura"]))
        for r in _ler(BENCHMARK_V0)
    ]


def _carregar_golden() -> list[tuple[str, bool, Fatura]]:
    return [
        (str(r["id"]), r["anomalia_injetada"] is not None, _fatura_golden(r)) for r in _ler(GOLDEN)
    ]


def medir_conjunto(itens: list[tuple[str, bool, Fatura]]) -> dict[str, Any]:
    corretas = [(i, f) for i, erro, f in itens if not erro]
    com_erro = [(i, f) for i, erro, f in itens if erro]
    falsos = [i for i, f in corretas if any(alarme(a) for a in analisar_nivel_a(f))]
    detectadas = [i for i, f in com_erro if any(alarme(a) for a in analisar_nivel_a(f))]
    tfa = bootstrap_ic(
        [1.0 if i in falsos else 0.0 for i, _ in corretas], b=B_PADRAO, semente=SEMENTE_PADRAO
    )
    return {
        "n_faturas": len(itens),
        "n_corretas": len(corretas),
        "falsos_alarmes": len(falsos),
        "ids_com_falso_alarme": falsos,
        "tfa_a": {"estimativa": tfa.estimativa, "ic95_inf": tfa.inferior, "ic95_sup": tfa.superior},
        "n_com_erro_injetado": len(com_erro),
        "detectadas": len(detectadas),
        "ids_nao_detectadas": [i for i, _ in com_erro if i not in detectadas],
    }


def medir() -> dict[str, Any]:
    v0, golden = medir_conjunto(_carregar_v0()), medir_conjunto(_carregar_golden())
    total_corretas = v0["n_corretas"] + golden["n_corretas"]
    total_falsos = v0["falsos_alarmes"] + golden["falsos_alarmes"]
    return {
        "sprint": "S2",
        "frente": "F3",
        "criterio": "nenhum falso alarme de nível A nas faturas corretas",
        "benchmark_v0": v0,
        "golden_set": golden,
        "total_faturas_corretas": total_corretas,
        "total_falsos_alarmes": total_falsos,
        "passou_gate": total_falsos == 0,
        "ressalva": (
            "Faturas sintéticas: os tipos de erro injetados são os que o próprio motor checa, "
            "então a detecção é alta por construção; o que o gate mede aqui é a ausência de "
            "falso alarme. Não vale como taxa em faturas reais."
        ),
    }


def main() -> int:
    r = medir()
    SAIDA_PADRAO.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_PADRAO.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for nome in ("benchmark_v0", "golden_set"):
        c = r[nome]
        print(
            f"{nome}: {c['falsos_alarmes']} falsos alarmes em {c['n_corretas']} corretas; "
            f"{c['detectadas']} de {c['n_com_erro_injetado']} erros detectados"
        )
    print(
        f"Total: {r['total_falsos_alarmes']} falsos alarmes em {r['total_faturas_corretas']} "
        f"faturas corretas -> {'GATE APROVADO' if r['passou_gate'] else 'GATE REPROVADO'}"
    )
    return 0 if r["passou_gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
