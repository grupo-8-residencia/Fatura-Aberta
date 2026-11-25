import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import acuracia_por_campo as ac
import extrair_fotos as ef
import pytest

from fa_extracao import ErroExtracao

# Leitura FICTÍCIA devolvida pelo dublê do modelo de visão.
_LEITURA: dict[str, Any] = {
    "mes_referencia": "10/2026",
    "consumo_kwh": "77",
    "total": "81,95",
    "aliquota_icms": "12,00",
    "bandeira": "Amarela",
    "itens": [{"descricao": "Consumo-TUSD", "valor": "81,95"}],
    "nome": "MARIA FICTICIA DA SILVA",
}


class _Extrator:
    def extrair(self, imagem: bytes) -> Mapping[str, Any]:
        if imagem == b"ruim":
            raise ErroExtracao("O modelo de visão não devolveu JSON.")
        return _LEITURA


def _fotos(pasta: Path) -> list[Path]:
    for nome, conteudo in (("foto-01.jpg", b"ok"), ("foto-02.PNG", b"ruim"), ("leia.txt", b"x")):
        (pasta / nome).write_bytes(conteudo)
    return ef.listar_fotos(pasta)


def test_lista_so_imagens_em_ordem(tmp_path: Path) -> None:
    assert [f.name for f in _fotos(tmp_path)] == ["foto-01.jpg", "foto-02.PNG"]


def test_extrai_todas_e_falha_conta_como_vazia(tmp_path: Path) -> None:
    previsto, meta = ef.extrair_todas(_fotos(tmp_path), _Extrator())

    assert previsto["foto-02"] == {}
    assert previsto["foto-01"]["total"] == "81,95"
    assert "nome" not in previsto["foto-01"]  # descartado pela candidata
    assert meta["fotos"] == 2
    assert meta["extraidas"] == 1
    assert meta["falhas"] == {"O modelo de visão não devolveu JSON.": 1}
    assert set(meta["latencia_s"]) == {"p50", "p95", "max"}


def test_metadados_nao_tem_valores_da_fatura(tmp_path: Path) -> None:
    _, meta = ef.extrair_todas(_fotos(tmp_path), _Extrator())
    texto = json.dumps(meta, ensure_ascii=False)
    for valor in ("81,95", "MARIA", "10/2026"):
        assert valor not in texto


def test_previsto_alimenta_a_acuracia_por_campo(tmp_path: Path) -> None:
    previsto, _ = ef.extrair_todas(_fotos(tmp_path), _Extrator())
    gabarito = {
        "foto-01": {"mes_referencia": "10/2026", "consumo_kwh": "77", "total": "81,95"},
        "foto-02": {"mes_referencia": "09/2026", "consumo_kwh": "80", "total": "90,00"},
    }
    por_campo = {r.campo: r for r in ac.avaliar(previsto, gabarito)}

    assert (por_campo["total"].avaliados, por_campo["total"].acertos) == (2, 1)
    assert por_campo["mes_referencia"].taxa == pytest.approx(0.5)


def test_gabarito_modelo_tem_todos_os_campos_vazios() -> None:
    modelo = ef.gabarito_modelo(["foto-01"])
    assert modelo["foto-01"]["total"] is None
    assert modelo["foto-01"]["itens"][0] == {
        "descricao": None, "quantidade": None, "unidade": None, "tarifa": None, "valor": None
    }  # fmt: skip


def test_sem_fotos_devolve_codigo_2(tmp_path: Path) -> None:
    assert ef.main([str(tmp_path)]) == 2
