"""Auditoria de cobertura por id da rodada S3."""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "avaliacao"))

import auditar_cobertura as ac  # noqa: E402

ESPERADOS = {"perguntas": ["Q1", "Q2", "Q3"], "faturas": ["F1", "F2"]}


def _res(perg: dict[str, Any], fat: dict[str, Any]) -> dict[str, Any]:
    return {"perguntas": perg, "faturas": fat}


def test_pendentes_vem_dos_ids_e_nao_de_contagens() -> None:
    r = ac.auditar(
        _res({"B2": [{"id": "Q1"}, {"id": "Q3"}]}, {"B2": [{"id": "F9"}, {"id": "F1"}]}), ESPERADOS
    )
    assert r["baselines"]["perguntas/B2"]["pendentes"] == ["Q2"]
    f = r["baselines"]["faturas/B2"]
    assert f["pendentes"] == ["F2"]
    assert f["fora_do_conjunto"] == ["F9"]  # rodado só para o juiz: não conta
    assert f["concluidos"] == 1
    assert r["completo"] is False


def test_invalido_conta_como_coberto_mas_nao_como_concluido() -> None:
    itens = [{"id": "Q1"}, {"id": "Q2", "valido": False}, {"id": "Q3"}]
    r = ac.auditar(_res({"B3": itens}, {}), ESPERADOS)
    linha = r["baselines"]["perguntas/B3"]
    assert linha["invalidos"] == ["Q2"]
    assert linha["concluidos"] == 2
    assert linha["pendentes"] == []
    assert linha["completo"] is True


def test_duplicado_nao_conta_como_concluido() -> None:
    r = ac.auditar(
        _res({"RAG": [{"id": "Q1"}, {"id": "Q1"}, {"id": "Q2"}, {"id": "Q3"}]}, {}), ESPERADOS
    )
    linha = r["baselines"]["perguntas/RAG"]
    assert linha["duplicados"] == ["Q1"]
    assert linha["pendentes"] == ["Q1"]


def test_completo_so_com_todos_os_baselines() -> None:
    perg = {b: [{"id": i} for i in ESPERADOS["perguntas"]] for b in ("LLM", "RAG", "B2", "B3")}
    fat = {
        b: [{"id": i, "veredito": "ok"} for i in ESPERADOS["faturas"]]
        for b in ("B1", "LLM", "B2", "B3")
    }
    assert ac.auditar(_res(perg, fat), ESPERADOS)["completo"] is True
    fat["LLM"].pop()
    assert ac.auditar(_res(perg, fat), ESPERADOS)["completo"] is False


def test_golden_set_real_tem_120_e_200() -> None:
    e = ac.ids_esperados()
    assert (len(e["perguntas"]), len(e["faturas"])) == (120, 200)


def test_carregar_usa_b1_de_200(tmp_path: Path) -> None:
    p = tmp_path / "r.json"
    p.write_text(
        json.dumps(
            {"faturas": {"B1": [{"id": "F1"}]}, "b1_200_faturas": [{"id": "F1"}, {"id": "F2"}]}
        )
    )
    assert len(ac.carregar(p, None)["faturas"]["B1"]) == 2
