"""Testes do gerador e do congelamento do golden set (S3-01)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import gerar_golden_set as gs

FIXO = gs.PASTA


def test_golden_set_congelado_esta_integro() -> None:
    assert gs.verificar() == []


def test_geracao_e_deterministica() -> None:
    assert gs.gerar_faturas() == gs.gerar_faturas()
    assert gs.gerar_faturas(semente=1) != gs.gerar_faturas(semente=2)


def test_arquivo_congelado_bate_com_o_gerador() -> None:
    esperado = gs._jsonl(gs.gerar_faturas())
    assert (FIXO / "faturas_sinteticas.jsonl").read_text(encoding="utf-8") == esperado


def test_200_faturas_com_e_sem_anomalia_e_sem_dado_pessoal() -> None:
    faturas = gs.gerar_faturas()
    assert len(faturas) == 200
    assert len({f["id"] for f in faturas}) == 200
    com = sum(1 for f in faturas if f["anomalia_injetada"])
    assert 60 <= com <= 140
    bruto = json.dumps(faturas, ensure_ascii=False).lower()
    for proibido in ("cpf", "cnpj", "endereço", "instalação", "@"):
        assert proibido not in bruto
    assert all(f["parametros"] == "sinteticos" for f in faturas)


def test_120_perguntas_em_seis_categorias_e_citacoes_validas() -> None:
    perguntas = gs.ler_perguntas()
    assert len(perguntas) == 120
    assert len({p["id"] for p in perguntas}) == 120
    cats = Counter(p["categoria"] for p in perguntas)
    assert set(cats) >= {
        "tarifas_b1",
        "bandeiras",
        "medicao_estimada",
        "devolucao_dobro",
        "cip_cosip",
        "encargos_multas",
    }
    for p in perguntas:
        assert p["resposta_esperada"].strip()
        assert p["abstencao_esperada"] == (not p["citacao_canonica"])
        assert "ilegal" not in json.dumps(p, ensure_ascii=False).lower()


def test_distribuicao_30_itens_por_pessoa_sem_repeticao() -> None:
    dist = gs.distribuir(gs.ler_perguntas(), gs.gerar_faturas())
    assert len(dist) == 6
    todos = [i for ids in dist.values() for i in ids]
    assert all(len(ids) == 30 for ids in dist.values())
    assert len(todos) == len(set(todos)) == 180


def test_verificar_detecta_adulteracao(tmp_path: Path) -> None:
    for nome in (*gs.ARQUIVOS_CONGELADOS, "checksums.sha256"):
        (tmp_path / nome).write_bytes((FIXO / nome).read_bytes())
    assert gs.verificar(tmp_path) == []
    with (tmp_path / "perguntas.jsonl").open("a", encoding="utf-8") as f:
        f.write("\n")
    assert any("perguntas.jsonl" in p for p in gs.verificar(tmp_path))
