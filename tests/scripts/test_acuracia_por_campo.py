import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import acuracia_por_campo as ap
import pytest

# Valores FICTÍCIOS. O "7777,77" serve para provar que o relatório não mostra valores.
GABARITO: dict[str, dict[str, Any]] = {
    "f1": {
        "mes_referencia": "10/2026",
        "consumo_kwh": "77,00",
        "total": "7777,77",
        "aliquota_icms": "12,00",
        "bandeira": "Amarela",
        "itens": [
            {"descricao": "Consumo-TUSD", "valor": "7000,00"},
            {"descricao": "Consumo-TE", "valor": "777,77"},
        ],
    },
    "f2": {
        "mes_referencia": "09/2026",
        "consumo_kwh": "1.050,00",
        "total": "100,00",
        "aliquota_icms": "20,00",
        "bandeira": "Verde",
        "itens": [{"descricao": "Energia", "valor": "100,00"}],
    },
}


def _por_campo(previsto: Mapping[str, Mapping[str, Any]]) -> dict[str, ap.Resultado]:
    return {r.campo: r for r in ap.avaliar(previsto, GABARITO)}


def test_tudo_certo_da_100_por_cento_e_passa_o_gate() -> None:
    resultados = ap.avaliar(GABARITO, GABARITO)
    texto, passou = ap.relatorio(resultados, ap.CAMPOS_CHAVE, 0.90)

    assert all(r.taxa == 1.0 for r in resultados)
    assert passou
    assert "Gate: **PASSOU**" in texto


def test_acerto_e_contado_por_campo_e_nao_pela_foto_inteira() -> None:
    previsto = {
        "f1": {**GABARITO["f1"], "total": "1,00"},  # só o total erra
        "f2": GABARITO["f2"],
    }

    por_campo = _por_campo(previsto)

    assert (por_campo["total"].acertos, por_campo["total"].avaliados) == (1, 2)
    assert por_campo["consumo_kwh"].taxa == 1.0
    assert por_campo["mes_referencia"].taxa == 1.0


def test_formatos_equivalentes_contam_como_acerto() -> None:
    previsto = {
        "f1": {**GABARITO["f1"], "consumo_kwh": "77", "bandeira": "  AMARELA "},
        "f2": {**GABARITO["f2"], "consumo_kwh": "R$ 1050,00", "mes_referencia": "9/2026"},
    }

    por_campo = _por_campo(previsto)

    assert por_campo["consumo_kwh"].taxa == 1.0
    assert por_campo["bandeira"].taxa == 1.0
    assert por_campo["mes_referencia"].taxa == 1.0


def test_foto_sem_previsao_ou_com_valor_invalido_conta_como_erro() -> None:
    previsto = {"f1": {**GABARITO["f1"], "total": "12.5"}}  # f2 ausente; "12.5" é ambíguo

    por_campo = _por_campo(previsto)

    assert por_campo["total"].acertos == 0
    assert por_campo["total"].avaliados == 2
    assert por_campo["bandeira"].acertos == 1


def test_campo_ausente_no_gabarito_nao_se_aplica() -> None:
    gabarito = {"f1": {"total": "10,00"}}

    resultados = {r.campo: r for r in ap.avaliar(gabarito, gabarito)}

    assert "bandeira" not in resultados
    assert resultados["total"].avaliados == 1


def test_itens_por_linha_e_soma_dos_itens() -> None:
    previsto = {
        "f1": {
            **GABARITO["f1"],
            "itens": [
                {"descricao": "consumo-tusd", "valor": "7.000,00"},
                {"descricao": "Ilum. Púb.", "valor": "1,00"},  # linha a mais
            ],
        },
        "f2": GABARITO["f2"],
    }

    por_campo = _por_campo(previsto)

    linhas = por_campo["itens (linhas corretas)"]
    assert (linhas.acertos, linhas.avaliados) == (2, 3)  # TUSD e Energia; TE faltou
    soma = por_campo["itens (soma igual ao total previsto)"]
    assert (soma.acertos, soma.avaliados) == (1, 2)  # f1: 7001,00 != 7777,77


def test_gate_falha_quando_um_campo_chave_fica_abaixo_da_meta() -> None:
    previsto = {"f1": {**GABARITO["f1"], "bandeira": "Verde"}, "f2": GABARITO["f2"]}

    texto, passou = ap.relatorio(ap.avaliar(previsto, GABARITO), ap.CAMPOS_CHAVE, 0.90)

    assert not passou
    assert "abaixo da meta" in texto
    assert "Gate: **FALHOU**" in texto


def test_relatorio_nao_mostra_valores_lidos() -> None:
    texto, _ = ap.relatorio(ap.avaliar(GABARITO, GABARITO), ap.CAMPOS_CHAVE, 0.90)

    for valor in ("7777,77", "7000,00", "Amarela", "Consumo-TUSD"):
        assert valor not in texto


def test_main_grava_relatorio_e_devolve_codigo_de_saida(tmp_path: Path) -> None:
    (tmp_path / "g.json").write_text(json.dumps(GABARITO), encoding="utf-8")
    (tmp_path / "p.json").write_text(json.dumps(GABARITO), encoding="utf-8")
    saida = tmp_path / "relatorio.md"

    codigo = ap.main([str(tmp_path / "p.json"), str(tmp_path / "g.json"), "--saida", str(saida)])

    assert codigo == 0
    assert "Gate: **PASSOU**" in saida.read_text(encoding="utf-8")


def test_main_com_entrada_invalida_nao_vaza_conteudo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "ruim.json").write_text('{"f1": "7777,77 nome secreto"', encoding="utf-8")
    (tmp_path / "g.json").write_text(json.dumps(GABARITO), encoding="utf-8")

    codigo = ap.main([str(tmp_path / "ruim.json"), str(tmp_path / "g.json")])

    assert codigo == 2
    saida = capsys.readouterr()
    assert "7777,77" not in saida.out + saida.err
    assert "secreto" not in saida.out + saida.err
