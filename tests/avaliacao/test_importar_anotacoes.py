"""Importador das anotações humanas: validação, tudo-ou-nada, idempotência e conflito."""

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_spec = importlib.util.spec_from_file_location(
    "importar_anotacoes", Path(__file__).resolve().parents[2] / "scripts" / "importar_anotacoes.py"
)
assert _spec and _spec.loader
imp = importlib.util.module_from_spec(_spec)
sys.modules["importar_anotacoes"] = imp
_spec.loader.exec_module(imp)


def _csv(caminho: Path, colunas: list[str], linhas: list[dict[str, str]]) -> None:
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)


@pytest.fixture()
def base(tmp_path: Path) -> dict[str, Path]:
    pasta = tmp_path / "anot"
    pasta.mkdir()
    cols = ["id", "tipo", "enunciado", "gabarito_proposto", "concorda", "correcao", "comentario"]
    for g in imp.PESSOAS:
        _csv(
            pasta / f"{g}.csv",
            cols,
            [
                {
                    "id": f"GS-{g[:2]}1",
                    "tipo": "pergunta",
                    "enunciado": "e",
                    "gabarito_proposto": "g",
                    "concorda": "",
                    "correcao": "",
                    "comentario": "",
                },
            ],
        )
    rcols = ["id", "categoria", "concorda", "correcao", "comentario"]
    _csv(
        pasta / "revisao.csv",
        rcols,
        [
            {"id": "GS-Q001", "categoria": "x", "concorda": "", "correcao": "", "comentario": ""},
            {"id": "GS-Q002", "categoria": "x", "concorda": "", "correcao": "", "comentario": ""},
        ],
    )
    blocos: dict[str, list[str]] = {g: [] for g in imp.PESSOAS}
    blocos["pedrohpsantos"] = ["GS-Q001"]
    blocos["NatyEvelin"] = ["GS-Q002"]
    (pasta / "distribuicao-revisao.json").write_text(json.dumps({"semente": 1, "blocos": blocos}))
    jcols = [
        "item_id",
        "tipo",
        "anotador_1",
        "anotador_2",
        "saida_do_sistema",
        "evidencia",
        "proposicoes_juiz",
        "veredito_humano_1",
        "veredito_humano_2",
        "veredito_juiz",
    ]
    _csv(
        pasta / "juiz.csv",
        jcols,
        [
            {
                "item_id": "JZ-1",
                "tipo": "pergunta",
                "anotador_1": "pedrohpsantos",
                "anotador_2": "NatyEvelin",
                "saida_do_sistema": "s",
                "evidencia": "e",
                "proposicoes_juiz": "",
                "veredito_humano_1": "",
                "veredito_humano_2": "",
                "veredito_juiz": "",
            },
        ],
    )
    return {"pasta": pasta, "rev": pasta / "revisao.csv", "juiz": pasta / "juiz.csv"}


def _export(**entregas: Any) -> dict[str, Any]:
    return {
        "esquema_versao": 1,
        "exportado_em": "t",
        "versao_pagina": "1",
        "entregas": [{"github": g, **v} for g, v in entregas.items()],
    }


def _plano(base: dict[str, Path], dados: dict[str, Any]) -> Any:
    return imp.planejar(dados, base["pasta"], base["rev"], base["juiz"])


OK = {"concorda": "sim", "correcao": "", "comentario": ""}


def test_aceita_resposta_valida_e_conta_o_que_falta(base: dict[str, Path]) -> None:
    d = _export(
        pedrohpsantos={
            "golden": {"GS-pe1": OK},
            "revisao": {"GS-Q001": OK},
            "juiz": {"JZ-1": {"veredito": "suportada"}},
        }
    )
    p = _plano(base, d)
    assert p.erros == []
    assert p.novos == {"golden": 1, "revisao": 1, "juiz": 1}
    assert p.ausentes["pedrohpsantos"] == {"golden": 0, "revisao": 0, "juiz": 0}


def test_juiz_vai_para_a_coluna_do_avaliador_certo(base: dict[str, Path]) -> None:
    d = _export(NatyEvelin={"juiz": {"JZ-1": {"veredito": "sem_suporte"}}})
    p = _plano(base, d)
    assert "sem_suporte" in p.arquivos[base["juiz"]]
    linha = p.arquivos[base["juiz"]].splitlines()[1].split(",")
    assert linha[-3:] == ["", "sem_suporte", ""]


@pytest.mark.parametrize(
    "d",
    [
        _export(pedrohpsantos={"golden": {"GS-OUTRO": OK}}),
        _export(pedrohpsantos={"golden": {"GS-pe1": {"concorda": "talvez"}}}),
        _export(
            pedrohpsantos={
                "golden": {"GS-pe1": {"concorda": "não", "correcao": "", "comentario": ""}}
            }
        ),
        _export(pedrohpsantos={"revisao": {"GS-Q002": OK}}),
        _export(pedrohpsantos={"juiz": {"JZ-1": {"veredito": "ok"}}}),
        _export(luiz={"golden": {}}),
        {"esquema_versao": 2, "entregas": [{"github": "pedrohpsantos"}]},
        {"esquema_versao": 1, "entregas": []},
    ],
)
def test_rejeita_entradas_invalidas(base: dict[str, Path], d: dict[str, Any]) -> None:
    assert _plano(base, d).erros


def test_juiz_de_quem_nao_e_avaliador_do_item_e_erro(base: dict[str, Path]) -> None:
    d = _export(mariadenis={"juiz": {"JZ-1": {"veredito": "suportada"}}})
    assert any("não atribuído" in e for e in _plano(base, d).erros)


def test_entrega_duplicada_e_erro(base: dict[str, Path]) -> None:
    d = {"esquema_versao": 1, "entregas": [{"github": "NatyEvelin"}, {"github": "NatyEvelin"}]}
    assert any("mais de uma entrega" in e for e in _plano(base, d).erros)


def test_aplicar_grava_faz_backup_e_e_idempotente(base: dict[str, Path], tmp_path: Path) -> None:
    d = _export(
        pedrohpsantos={
            "golden": {"GS-pe1": {"concorda": "não", "correcao": "c", "comentario": "j"}}
        }
    )
    bruto = json.dumps(d).encode()
    log = tmp_path / "log.jsonl"
    imp.aplicar(_plano(base, d), bruto, d, log=log, backup_em=tmp_path / "bk")
    linhas = list(csv.DictReader((base["pasta"] / "pedrohpsantos.csv").open(encoding="utf-8-sig")))
    assert (linhas[0]["concorda"], linhas[0]["correcao"]) == ("não", "c")
    assert list((tmp_path / "bk").rglob("pedrohpsantos.csv"))
    p2 = _plano(base, d)  # segunda vez: nada novo, nenhum erro
    assert p2.erros == [] and p2.novos["golden"] == 0 and p2.iguais == 1
    assert json.loads(log.read_text().splitlines()[0])["novos"]["golden"] == 1


def test_nao_sobrescreve_anotacao_diferente(base: dict[str, Path], tmp_path: Path) -> None:
    d1 = _export(pedrohpsantos={"golden": {"GS-pe1": OK}})
    imp.aplicar(_plano(base, d1), b"1", d1, log=tmp_path / "l", backup_em=tmp_path / "b")
    d2 = _export(
        pedrohpsantos={
            "golden": {"GS-pe1": {"concorda": "não", "correcao": "x", "comentario": "y"}}
        }
    )
    assert any("não sobrescrevo" in e for e in _plano(base, d2).erros)


def test_erro_em_uma_pessoa_nao_grava_nada(base: dict[str, Path], tmp_path: Path) -> None:
    antes = (base["pasta"] / "pedrohpsantos.csv").read_bytes()
    d = _export(pedrohpsantos={"golden": {"GS-pe1": OK}}, NatyEvelin={"golden": {"GS-ERRADO": OK}})
    p = _plano(base, d)
    assert p.erros
    with pytest.raises(imp.ErroImportacao):
        imp.aplicar(p, b"x", d, log=tmp_path / "l", backup_em=tmp_path / "b")
    assert (base["pasta"] / "pedrohpsantos.csv").read_bytes() == antes


def test_distribuicao_real_cobre_120_sem_repeticao() -> None:
    d = json.loads(imp.DISTRIBUICAO.read_text(encoding="utf-8"))["blocos"]
    todos = [i for ids in d.values() for i in ids]
    assert len(todos) == 120 and len(set(todos)) == 120
    assert {len(v) for v in d.values()} == {20}


def test_arquivos_individuais_viram_um_export(base: dict[str, Path]) -> None:
    a = {"esquema_versao": 1, "github": "pedrohpsantos", "golden": {"GS-pe1": OK}}
    b = {"esquema_versao": 1, "github": "NatyEvelin", "juiz": {"JZ-1": {"veredito": "suportada"}}}
    junto = imp.juntar_exports([a, b])
    assert [e["github"] for e in junto["entregas"]] == ["pedrohpsantos", "NatyEvelin"]
    p = _plano(base, junto)
    assert p.erros == [] and p.novos["golden"] == 1 and p.novos["juiz"] == 1


def test_mesmo_arquivo_duas_vezes_e_erro(base: dict[str, Path]) -> None:
    a = {"esquema_versao": 1, "github": "NatyEvelin", "golden": {}}
    assert any("mais de uma entrega" in e for e in _plano(base, imp.juntar_exports([a, a])).erros)


def test_arquivo_estranho_e_recusado() -> None:
    with pytest.raises(imp.ErroImportacao):
        imp.juntar_exports([{"qualquer": 1}])
