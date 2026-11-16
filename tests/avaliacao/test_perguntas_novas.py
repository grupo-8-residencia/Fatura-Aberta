"""Testes da avaliação fora da amostra (out-of-sample) em perguntas novas."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "avaliacao"))

from checar_perguntas_novas import PERGUNTAS_NOVAS, avaliar_perguntas_novas


def test_perguntas_novas_sao_disjuntas_do_golden_set() -> None:
    golden = (
        (Path(__file__).resolve().parents[2] / "dados" / "golden-set" / "perguntas.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    import json

    ids_golden = {json.loads(line)["id"] for line in golden if line.strip()}
    ids_novas = {p["id"] for p in PERGUNTAS_NOVAS}
    assert ids_novas.isdisjoint(ids_golden)
    assert len(PERGUNTAS_NOVAS) == 20


def test_avaliacao_perguntas_novas_executa_e_atinge_meta_gate() -> None:
    res = avaliar_perguntas_novas()
    assert res["n_total"] == 20
    rec = res["recuperacao_perguntas_com_norma"]
    # Meta de gate da S2 é >= 0.70; no conjunto novo e independente, hit@5 é >= 0.70
    assert rec["hit@5"]["estimativa"] >= 0.70
    assert res["abstencao_limiar_025"]["precisao"] >= 0.60
