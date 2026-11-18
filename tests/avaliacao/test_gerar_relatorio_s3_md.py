"""Testes do gerador do relatório da S3 (markdown)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_CAMINHO = Path(__file__).resolve().parents[2] / "avaliacao" / "gerar_relatorio_s3_md.py"
_spec = importlib.util.spec_from_file_location("gerar_relatorio_s3_md", _CAMINHO)
assert _spec and _spec.loader
gr = importlib.util.module_from_spec(_spec)
sys.modules["gerar_relatorio_s3_md"] = gr
_spec.loader.exec_module(gr)


def _base() -> dict[str, Any]:
    return {
        "cabecalho": {
            "data_utc": "2026-11-16T00:00:00Z",
            "commit": "abc1234",
            "temperatura": 0.0,
            "modelos": {
                "gerador": {"modelo": "g", "versao": "1"},
                "juiz": {"modelo": "j", "versao": "2"},
            },
            "semente_llm": 42,
            "semente_bootstrap": 42,
            "sha256_checksums_golden_set": "x",
        },
        "perguntas": {},
        "faturas": {},
        "mcnemar_perguntas": {},
        "mcnemar_faturas": {},
        "cobertura": {"baselines": {}},
        "completo": False,
        "recomendacao_final": None,
    }


def test_nenhum_baseline_elegivel_nao_quebra_o_relatorio() -> None:
    c = _base()
    sem = {"escolhido": None, "motivo": "nenhum baseline elegível (inválidas ou RF-15)"}
    c["escolha_perguntas"] = sem
    c["escolha_faturas"] = sem
    texto = gr.gerar(c)
    assert "Nenhum baseline é elegível nas perguntas" in texto
    assert "Nenhum baseline é elegível nas faturas" in texto
    assert "Sem recomendação final" in texto


def test_escolha_normal_mostra_elegiveis_e_escolhido() -> None:
    c = _base()
    ok = {"escolhido": "RAG", "elegiveis": ["RAG"], "empatados": ["RAG"], "acerto": 0.8}
    c["escolha_perguntas"] = ok
    c["escolha_faturas"] = {**ok, "escolhido": "B1", "elegiveis": ["B1", "B2"]}
    texto = gr.gerar(c)
    assert "Elegíveis nas perguntas: RAG. Escolhido: **RAG** (acerto 80.0%)" in texto
    assert "Elegíveis nas faturas: B1, B2. Escolhido: **B1**" in texto
