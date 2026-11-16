"""Testes da rodada S4 (B4 × B5) com o cliente falso: sem rede, sem LLM e sem gravar resultado."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest
import rodada_s3 as rs3
import rodada_s4 as rs

from fa_agentes import AnalistaNormativo, Auditor, ClienteFalso
from fa_rag import IndiceHibrido

TEXTO_177 = "Família inscrita no CadÚnico com renda por pessoa de até meio salário-mínimo."


@pytest.fixture(scope="module")
def indice() -> IndiceHibrido:
    return IndiceHibrido.do_corpus()


@pytest.fixture(scope="module")
def perguntas() -> list[dict[str, Any]]:
    return rs3.ler_jsonl(rs.GOLDEN / "perguntas.jsonl")


def _resposta(*afirmacoes: tuple[str, list[str]]) -> str:
    return json.dumps({"afirmacoes": [{"texto": t, "fontes": f} for t, f in afirmacoes]})


def _doc_texto(indice: IndiceHibrido, doc_id: str) -> str:
    return " ".join(next(d for d in indice.documentos if d.id == doc_id).texto.split())


def _avaliar(
    indice: IndiceHibrido, p: dict[str, Any], bruto: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cliente = rs.ClienteRobusto(ClienteFalso(resposta=bruto))
    reg = rs.registrar_analise(AnalistaNormativo(indice, cliente), cliente, p)
    docs = {d.id: d for d in indice.documentos}
    rel = rs.reconstruir(reg, docs, p)
    medidor = Auditor(None)
    b4 = rs.avaliar_braco("B4", rel, p, medidor)
    b5 = rs.avaliar_braco("B5", rel, p, medidor)
    return reg, b4, b5


def test_afirmacao_fiel_passa_nos_dois_bracos(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]]
) -> None:
    p = perguntas[1]  # GS-Q002: canônico ren1000-art-177
    fiel = _doc_texto(indice, "ren1000-art-177")[:160]
    _, b4, b5 = _avaliar(indice, p, _resposta((fiel, ["ren1000-art-177"])))
    assert not b4["abstencao"] and not b5["abstencao"]
    assert b4["acerto"] and b5["acerto"]
    assert not b4["emitiu_sem_suporte"] and not b5["emitiu_sem_suporte"]


def test_citacao_inventada_o_b4_emite_e_o_b5_se_abstem(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]]
) -> None:
    p = perguntas[1]
    bruto = _resposta((TEXTO_177, ["ren1000-art-999"]))
    reg, b4, b5 = _avaliar(indice, p, bruto)
    assert reg["valido"] and reg["json_valido"] and reg["chamou_llm"]
    assert not b4["abstencao"] and b4["emitiu_sem_suporte"] and b4["citacao_inventada"]
    assert b5["abstencao"] and not b5["emitiu_sem_suporte"] and not b5["acerto"]
    assert b5["n_afirmacoes"] == 0


def test_json_invalido_conta_como_abstencao_e_fica_marcado(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]]
) -> None:
    reg, b4, b5 = _avaliar(indice, perguntas[1], "isto não é json")
    assert reg["json_valido"] is False
    assert b4["abstencao"] and b5["abstencao"]


def test_pergunta_que_exige_abstencao_acerta_ao_abster(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]]
) -> None:
    p = next(x for x in perguntas if x["abstencao_esperada"])
    _, b4, b5 = _avaliar(indice, p, _resposta())
    assert b4["acerto"] and b5["acerto"]


def test_comparar_mede_reducao_e_mcnemar() -> None:
    def item(sem: bool, acerto: bool) -> dict[str, Any]:
        return {"emitiu_sem_suporte": sem, "acerto": acerto}

    b4 = [item(i < 20, True) for i in range(100)]
    b5 = [item(False, i >= 10) for i in range(100)]  # perde 10 acertos
    c = rs.comparar(b4, b5)
    assert c["sem_suporte_reducao_relativa"]["estimativa"] == 1.0
    assert c["sem_suporte_B5_nao_pior_que_B4"] and c["reducao_de_30pct_atingida"]
    assert c["acerto_mcnemar_B4_vs_B5"]["n10_B4_acerta_B5_erra"] == 10
    assert c["perda_de_acerto_significativa"] and not c["gate_s4_aprovado"]


def test_reducao_sem_nenhum_caso_no_b4_nao_inventa_estimativa() -> None:
    r = rs.bootstrap_reducao([False] * 10, [False] * 10)
    assert r["estimativa"] is None and r["reamostras_validas"] == 0


def test_cliente_robusto_refaz_so_falha_de_comunicacao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rs3, "PAUSA_NOVA_TENTATIVA_S", 0.0)
    falhas: list[Exception] = [TimeoutError("timed out"), OSError("conexão recusada")]

    class Instavel:
        provedor, modelo = "falso", "x"

        def versao(self) -> str:
            return "v"

        def gerar(self, **kw: Any) -> Any:
            if falhas:
                raise falhas.pop(0)
            return ClienteFalso(resposta="{}").gerar(**kw)

    cliente = rs.ClienteRobusto(Instavel())
    assert cliente.gerar(sistema="s", prompt="p").texto == "{}"
    assert cliente.tentativas == 3

    class Quebrado:
        provedor, modelo = "falso", "x"

        def versao(self) -> str:
            return "v"

        def gerar(self, **_: Any) -> Any:
            raise ValueError("erro do cliente")

    robusto = rs.ClienteRobusto(Quebrado())
    with pytest.raises(ValueError):
        robusto.gerar(sistema="s", prompt="p")
    assert robusto.tentativas == 1  # erro de cliente não é refeito


def _args(saida: Path, limite: int | None, etapa: str = "tudo") -> argparse.Namespace:
    return argparse.Namespace(saida=saida, limite=limite, etapa=etapa)


def test_rodada_e_retomavel_e_nao_toca_nos_resultados_reais(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = rs.SAIDA
    antes = real.read_bytes() if real.exists() else None
    cliente = ClienteFalso(resposta=_resposta(("texto sem lastro algum aqui", ["ren1000-art-999"])))
    monkeypatch.setattr(rs, "criar_cliente", lambda *a, **k: cliente)
    saida = tmp_path / "s4.json"

    assert rs.executar(_args(saida, 3), lambda _: None) == 0
    dados = json.loads(saida.read_text(encoding="utf-8"))
    chamadas = len(cliente.chamadas)
    assert chamadas >= 1 and len(dados["registros"]) == 3 and dados["parcial"] is True
    assert dados["cabecalho"]["semente_llm"] == 42 and dados["cabecalho"]["limite"] == 3
    assert dados["cabecalho"]["sha256_checksums_golden_set"]
    assert dados["metricas"]["cobertura"]["concluidos"] == 3
    assert (tmp_path / "s4-comparacao.json").exists()

    assert rs.executar(_args(saida, 3), lambda _: None) == 0  # retoma: nada a refazer
    assert len(cliente.chamadas) == chamadas
    assert rs.executar(_args(saida, 5), lambda _: None) == 0  # completa só as 2 que faltam
    assert len(json.loads(saida.read_text(encoding="utf-8"))["registros"]) == 5

    assert (real.read_bytes() if real.exists() else None) == antes


def test_retomada_recusa_mudanca_de_prompt_ou_modelo() -> None:
    antigo = {"sha256_checksums_golden_set": "a", "sha256_prompt_analista": "p", "limiar": 0.3,
              "top_k": 5, "modelos": {"gerador": {"versao": "1"}}}  # fmt: skip
    rs.conferir_cabecalho(antigo, antigo)
    with pytest.raises(RuntimeError, match="prompt_analista"):
        rs.conferir_cabecalho(antigo, {**antigo, "sha256_prompt_analista": "q"})
    with pytest.raises(RuntimeError, match="modelo"):
        rs.conferir_cabecalho(antigo, {**antigo, "modelos": {"gerador": {"versao": "2"}}})


def test_cobertura_por_id() -> None:
    regs = [{"id": "a", "valido": True}, {"id": "b", "valido": False}, {"id": "a", "valido": True}]
    c = rs.cobertura(regs, ["a", "b", "c"])
    assert c["duplicados"] == ["a"] and c["invalidos"] == ["b"] and c["pendentes"] == ["a", "c"]
    assert not c["completo"]
