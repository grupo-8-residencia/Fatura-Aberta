"""Testes da rodada S3 (B1, B2, B3 e juiz) com o cliente falso: sem rede e sem LLM."""

from __future__ import annotations

import json
from typing import Any

import pytest
import rodada_s3 as rs

from fa_agentes import ClienteFalso
from fa_rag import IndiceHibrido


@pytest.fixture(scope="module")
def indice() -> IndiceHibrido:
    return IndiceHibrido.do_corpus()


@pytest.fixture(scope="module")
def faturas() -> list[dict[str, Any]]:
    return rs.ler_jsonl(rs.GOLDEN / "faturas_sinteticas.jsonl")


@pytest.fixture(scope="module")
def perguntas() -> list[dict[str, Any]]:
    return rs.ler_jsonl(rs.GOLDEN / "perguntas.jsonl")


def _silencio(_: str) -> None:
    return None


def test_b1_motor_acerta_as_200_faturas_e_nao_da_falso_alarme(
    faturas: list[dict[str, Any]],
) -> None:
    r = rs.rodar_b1(faturas)
    assert len(r) == 200
    assert all(i["acerto"] for i in r)
    assert not [i for i in r if i["anomalia"] is None and i["veredito"] == "diverge_A"]
    assert all(not i["linguagem"] for i in r)


def test_conversao_de_fatura_respeita_o_contrato(faturas: list[dict[str, Any]]) -> None:
    f = rs.converter_fatura(faturas[0])
    assert f.distribuidora == "Neoenergia Brasília" and f.grupo_tarifario == "B1"
    assert len(f.itens) == 3 and str(f.total) == faturas[0]["total"]


def test_b2_nao_filtra_vigencia_e_b3_filtra_e_injeta_o_motor(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]], faturas: list[dict[str, Any]]
) -> None:
    antigas = [p for p in perguntas if p["tipo"] == "vigencia"][:2]
    cliente = ClienteFalso(
        resposta=json.dumps({"analise": "", "resposta": "", "abstencao": True, "citacoes": []})
    )
    b2 = rs.rodar_llm_perguntas(cliente, indice, antigas, "B2", _silencio)
    b3 = rs.rodar_llm_perguntas(cliente, indice, antigas, "B3", _silencio)
    assert any(c.startswith("ren1000") for i in b2 for c in i["contexto_ids"])
    assert all(not c.startswith("ren1000") for i in b3 for c in i["contexto_ids"])
    assert all(i["acerto"] for i in b2 + b3)  # abster-se é o esperado nesses itens

    cf = ClienteFalso(resposta=json.dumps({"analise": "", "achados": []}))
    rs.rodar_llm_faturas(cf, indice, faturas[:1], "B2", _silencio)
    rs.rodar_llm_faturas(cf, indice, faturas[:1], "B3", _silencio)
    prompt_b2, prompt_b3 = cf.chamadas[0][1], cf.chamadas[1][1]
    assert "MOTOR DETERMINÍSTICO" not in prompt_b2 and "MOTOR DETERMINÍSTICO" in prompt_b3
    assert "temperatura" not in prompt_b2.lower()


def test_perguntas_citacao_canonica_abstencao_e_citacao_inventada(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]]
) -> None:
    normativa = next(p for p in perguntas if p["tipo"] == "normativa")
    canonico = normativa["citacao_canonica"][0]
    certo = ClienteFalso(
        resposta=json.dumps(
            {"analise": "", "resposta": "ok", "abstencao": False, "citacoes": [f"[{canonico}]"]}
        )
    )
    inventado = ClienteFalso(
        resposta=json.dumps(
            {
                "analise": "",
                "resposta": "ok",
                "abstencao": False,
                "citacoes": ["lei-que-nao-existe"],
            }
        )
    )
    abster = ClienteFalso(
        resposta=json.dumps({"analise": "", "resposta": "", "abstencao": True, "citacoes": []})
    )
    # o id do corpus pode vir com colchetes; o artigo canônico só conta se estiver no contexto
    a = rs.rodar_llm_perguntas(certo, indice, [normativa], "B3", _silencio)[0]
    b = rs.rodar_llm_perguntas(inventado, indice, [normativa], "B3", _silencio)[0]
    c = rs.rodar_llm_perguntas(abster, indice, [normativa], "B3", _silencio)[0]
    assert b["acerto"] is False and b["citacoes_inventadas"] == ["lei-que-nao-existe"]
    assert c["acerto"] is False  # abster-se onde havia norma esperada é erro
    assert isinstance(a["acerto"], bool)


def test_resposta_invalida_do_llm_vira_erro_registrado_e_nao_derruba_a_rodada(
    indice: IndiceHibrido, faturas: list[dict[str, Any]]
) -> None:
    ruim = ClienteFalso(resposta="isto não é JSON")
    r = rs.rodar_llm_faturas(ruim, indice, faturas[:2], "B3", _silencio)
    assert [i["veredito"] for i in r] == ["invalido", "invalido"]
    assert all(i["acerto"] is False and i["erro"] == "JSON inválido" for i in r)
    m = rs.metricas_faturas({"B3": r})
    assert m["B3"]["respostas_invalidas"] == 2


def test_rf15_e_contado_nos_cartoes_do_llm(
    indice: IndiceHibrido, faturas: list[dict[str, Any]]
) -> None:
    cliente = ClienteFalso(
        resposta=json.dumps(
            {
                "analise": "",
                "achados": [
                    {
                        "item": "Total",
                        "veredito": "diverge_A",
                        "descricao": "Isso é ilegal.",
                        "citacoes": [],
                    }
                ],
            }
        )
    )
    r = rs.rodar_llm_faturas(cliente, indice, faturas[:1], "B2", _silencio)[0]
    assert r["linguagem"] == ["ilegal"] and r["veredito"] == "diverge_A"


def test_execucao_paralela_mantem_a_ordem_dos_itens(
    indice: IndiceHibrido, faturas: list[dict[str, Any]]
) -> None:
    cliente = ClienteFalso(resposta=json.dumps({"analise": "", "achados": []}))
    r = rs.rodar_llm_faturas(cliente, indice, faturas[:8], "B2", _silencio, paralelo=4)
    assert [i["id"] for i in r] == [f["id"] for f in faturas[:8]]


def test_metricas_incluem_ic_mcnemar_e_deteccao_por_tipo(faturas: list[dict[str, Any]]) -> None:
    b1 = rs.rodar_b1(faturas)
    pior = [{**i, "acerto": False, "veredito": "confere"} for i in b1]
    m = rs.metricas_faturas({"B1": b1, "B2": pior, "B3": b1})
    assert m["B1"]["acerto_por_fatura"]["estimativa"] == 1.0
    assert m["B1"]["falso_alarme_nas_faturas_corretas"]["estimativa"] == 0.0
    assert m["B2"]["deteccao_nas_faturas_com_anomalia"]["estimativa"] == 0.0
    assert set(m["B1"]["deteccao_por_tipo"]) >= {"total_nao_fecha", "item_duplicado"}
    mc = m["mcnemar"]["B3_vs_B2"]
    assert mc["n10_primeiro_acerta_segundo_erra"] == 0
    assert mc["n01_primeiro_erra_segundo_acerta"] == 200 and mc["significativo_5pct"]
