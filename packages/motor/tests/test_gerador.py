import json
import random
from pathlib import Path

import pytest

from fa_contratos import Achado
from fa_motor import (
    CAMINHO_PADRAO_SINTETICAS,
    SEMENTE_PADRAO,
    TIPOS_ERRO_NIVEL_A,
    RegistroSintetico,
    TipoErroNivelA,
    analisar_nivel_a,
    gerar_conjunto_sintetico_v0,
    gerar_fatura_sintetica_valida,
    gravar_conjunto_sintetico_v0,
    injetar_erro_nivel_a,
)


def _achados_divergentes(achados: list[Achado]) -> list[Achado]:
    return [
        a
        for a in achados
        if not a.abstencao
        and a.valor_esperado is not None
        and a.valor_cobrado is not None
        and a.valor_esperado != a.valor_cobrado
    ]


def test_fatura_sintetica_valida_nao_dispara_alarme_falso() -> None:
    rng = random.Random(42)
    for com_parcela_80 in (False, True):
        fatura = gerar_fatura_sintetica_valida(rng, com_parcela_80=com_parcela_80)
        achados = analisar_nivel_a(fatura)
        assert _achados_divergentes(achados) == []
        assert all(not a.abstencao for a in achados)


@pytest.mark.parametrize("tipo_erro", TIPOS_ERRO_NIVEL_A)
def test_injeta_erro_rotulado_para_cada_checagem_do_nivel_a(
    tipo_erro: TipoErroNivelA,
) -> None:
    rng = random.Random(101)
    fatura_base = gerar_fatura_sintetica_valida(
        rng, com_parcela_80=(tipo_erro is TipoErroNivelA.PARCELA_80)
    )
    fatura_com_erro, item_esperado = injetar_erro_nivel_a(fatura_base, tipo_erro, rng)
    divergentes = _achados_divergentes(analisar_nivel_a(fatura_com_erro))
    assert [a.item for a in divergentes] == [item_esperado]


def test_reprodutibilidade_por_semente_e_cobertura_das_cinco_checagens() -> None:
    conjunto_a = gerar_conjunto_sintetico_v0(semente=SEMENTE_PADRAO, quantidade=20)
    conjunto_b = gerar_conjunto_sintetico_v0(semente=SEMENTE_PADRAO, quantidade=20)
    conjunto_c = gerar_conjunto_sintetico_v0(semente=SEMENTE_PADRAO + 1, quantidade=20)

    assert conjunto_a == conjunto_b
    assert conjunto_a != conjunto_c

    erros_presentes = {r.erro_injetado for r in conjunto_a if r.erro_injetado is not None}
    assert erros_presentes == set(TIPOS_ERRO_NIVEL_A)

    for registro in conjunto_a:
        divergentes = _achados_divergentes(analisar_nivel_a(registro.fatura))
        if registro.erro_injetado is None:
            assert divergentes == []
        else:
            assert [a.item for a in divergentes] == [registro.item_esperado_divergente]


def test_rejeita_quantidade_insuficiente_para_cobrir_todas_as_checagens() -> None:
    with pytest.raises(ValueError, match="pelo menos"):
        gerar_conjunto_sintetico_v0(semente=1, quantidade=4)


def test_grava_e_valida_conjunto_sintetico_em_dados_benchmark_sinteticas(
    tmp_path: Path,
) -> None:
    destino_temp = tmp_path / "faturas_v0.jsonl"
    caminho_gravado = gravar_conjunto_sintetico_v0(
        destino=destino_temp, semente=SEMENTE_PADRAO, quantidade=10
    )
    assert caminho_gravado == destino_temp
    linhas = destino_temp.read_text(encoding="utf-8").strip().splitlines()
    assert len(linhas) == 10
    registros_lidos = [RegistroSintetico.model_validate(json.loads(linha)) for linha in linhas]
    assert registros_lidos == gerar_conjunto_sintetico_v0(semente=SEMENTE_PADRAO, quantidade=10)

    assert CAMINHO_PADRAO_SINTETICAS.is_file()
    linhas_padrao = CAMINHO_PADRAO_SINTETICAS.read_text(encoding="utf-8").strip().splitlines()
    registros_padrao = [
        RegistroSintetico.model_validate(json.loads(linha)) for linha in linhas_padrao
    ]
    assert registros_padrao == gerar_conjunto_sintetico_v0()
