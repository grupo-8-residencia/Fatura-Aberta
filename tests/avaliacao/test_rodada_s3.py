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


def test_cita_dispositivo_reconhece_ato_e_artigo_em_texto_livre() -> None:
    assert rs.cita_dispositivo("REN ANEEL 1.000/2021, art. 323, § 2º", {"ren1000-art-323"})
    assert rs.cita_dispositivo("Resolução Normativa 1000, artigo 360", {"ren1000-art-360"})
    assert rs.cita_dispositivo("CDC art. 42, parágrafo único", {"cdc-art-42-pu"})
    assert rs.cita_dispositivo("Lei Distrital 7.888/2026, art. 4º", {"df7888-art-4"})
    assert not rs.cita_dispositivo("REN 1.000/2021, art. 324", {"ren1000-art-323"})  # outro artigo
    assert not rs.cita_dispositivo("art. 323 do Código Civil", {"ren1000-art-323"})  # outro ato
    assert not rs.cita_dispositivo("sem citação", {"ren1000-art-323"})


def test_llm_puro_nao_recebe_dispositivos_e_cita_de_memoria(
    perguntas: list[dict[str, Any]],
) -> None:
    normativa = next(p for p in perguntas if p["tipo"] == "normativa")
    cliente = ClienteFalso(
        resposta=json.dumps(
            {
                "analise": "",
                "resposta": "ok",
                "abstencao": False,
                "citacoes": ["REN ANEEL 1.000/2021, art. 999"],
            }
        )
    )
    r = rs.rodar_llm_puro_perguntas(cliente, [normativa], _silencio)[0]
    assert "DISPOSITIVOS" not in cliente.chamadas[0][1]
    assert r["baseline"] == "LLM" and r["acerto"] is False and r["cita_algo_errado"] is True


def test_rag_extrativo_nao_usa_llm_e_se_abstem_fora_do_corpus(
    indice: IndiceHibrido, perguntas: list[dict[str, Any]]
) -> None:
    r = rs.rodar_rag_extrativo_perguntas(indice, perguntas)
    assert len(r) == 120 and all(i["baseline"] == "RAG" and i["valido"] for i in r)
    assert all(not i["linguagem"] for i in r)
    normativas = [i for i in r if i["tipo"] == "normativa"]
    assert sum(i["acerto"] for i in normativas) / len(normativas) > 0.7
    m = rs.metricas_perguntas({"RAG": r})
    assert m["RAG"]["n"] == 120 and m["RAG"]["respostas_invalidas"] == 0


def _item(
    acerto: bool, *, tipo: str = "normativa", dur: float = 1.0, rf15: bool = False
) -> dict[str, Any]:
    return {
        "id": "x", "tipo": tipo, "acerto": acerto, "valido": True, "duracao_s": dur,
        "linguagem": ["ilegal"] if rf15 else [], "citacoes_inventadas": [],
        "citacoes_fora_de_vigencia": [],
    }  # fmt: skip


def test_relatorio_escolhe_por_acerto_e_desempata_por_latencia() -> None:
    import relatorio_s3 as rel

    perguntas = {
        "LLM": [_item(False) for _ in range(50)],
        "RAG": [_item(True, dur=0.001) for _ in range(50)],
        "B2": [_item(True, dur=30.0) for _ in range(50)],
        "B3": [_item(True, dur=40.0) for _ in range(50)],
    }
    r = rel.comparar(
        {"perguntas": {k: perguntas[k] for k in ("B2", "B3")}},
        {"perguntas": {"LLM": perguntas["LLM"], "RAG": perguntas["RAG"]}},
    )
    esc = r["escolha_perguntas"]
    assert esc["escolhido"] == "RAG" and set(esc["empatados"]) == {"RAG", "B2", "B3"}
    assert r["mcnemar_perguntas"]["RAG_vs_LLM"]["significativo_5pct"] is True
    assert r["perguntas"]["LLM"]["acerto"]["estimativa"] == 0.0


def test_relatorio_exclui_quem_viola_rf15_ou_tem_resposta_invalida() -> None:
    import relatorio_s3 as rel

    bom = [_item(True) for _ in range(20)]
    ruim = [_item(True, rf15=(k == 0)) for k in range(20)]
    invalido = [{**_item(True), "valido": False} for _ in range(20)]
    t = rel.tabela_perguntas({"B2": ruim, "B3": invalido, "RAG": bom})
    assert rel.escolher(t, ("B2", "B3", "RAG"))["escolhido"] == "RAG"
    assert rel.escolher(rel.tabela_perguntas({"B2": ruim}), ("B2",))["escolhido"] is None


# ------------------------------------------------- falhas, trava, escrita atômica e cegamento


class _ClienteQueFalha:
    """Falha `falhas` vezes com o erro dado e depois responde com um JSON válido."""

    def __init__(self, erro: Exception, falhas: int) -> None:
        self.erro, self.falhas, self.chamadas = erro, falhas, 0

    def versao(self) -> str:
        return "falso"

    def gerar(self, **_: Any) -> Any:
        from fa_agentes.llm import RespostaLLM

        self.chamadas += 1
        if self.chamadas <= self.falhas:
            raise self.erro
        return RespostaLLM(
            texto='{"ok": true}', modelo="falso", digest="d", duracao_s=0.1, tokens_saida=3
        )


def test_classifica_os_tipos_de_falha() -> None:
    assert rs.classificar_erro(TimeoutError("x")) == "timeout"
    assert rs.classificar_erro(ConnectionError("recusou")) == "comunicacao"
    assert rs.classificar_erro(RuntimeError("Modelo 'm' não está instalado no Ollama")) == (
        "modelo_indisponivel"
    )
    assert rs.classificar_erro(ValueError("outra")) == "erro_cliente"


def test_falha_de_comunicacao_e_refeita_e_registrada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rs, "PAUSA_NOVA_TENTATIVA_S", 0)
    c = _ClienteQueFalha(ConnectionError("caiu"), falhas=2)
    r = rs._chamar(c, "s", "p", {})  # type: ignore[arg-type]
    assert r["valido"] is True and c.chamadas == 3
    assert [t["tipo"] for t in r["tentativas"]] == ["comunicacao", "comunicacao"]


def test_desiste_depois_das_tentativas_extras_e_conta_como_invalida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rs, "PAUSA_NOVA_TENTATIVA_S", 0)
    c = _ClienteQueFalha(TimeoutError("lento"), falhas=99)
    r = rs._chamar(c, "s", "p", {})  # type: ignore[arg-type]
    assert r["valido"] is False and r["erro_tipo"] == "timeout"
    assert c.chamadas == 1 + rs.TENTATIVAS_EXTRAS and len(r["tentativas"]) == c.chamadas


def test_modelo_indisponivel_nao_e_refeito() -> None:
    c = _ClienteQueFalha(RuntimeError("Modelo 'm' não está instalado no Ollama"), falhas=99)
    r = rs._chamar(c, "s", "p", {})  # type: ignore[arg-type]
    assert r["valido"] is False and c.chamadas == 1 and r["erro_tipo"] == "modelo_indisponivel"


def test_json_invalido_nunca_e_refeito() -> None:
    from fa_agentes.llm import RespostaLLM

    class Ruim:
        chamadas = 0

        def versao(self) -> str:
            return "x"

        def gerar(self, **_: Any) -> Any:
            Ruim.chamadas += 1
            return RespostaLLM(
                texto="não é json", modelo="x", digest="d", duracao_s=0.1, tokens_saida=1
            )

    r = rs._chamar(Ruim(), "s", "p", {})  # type: ignore[arg-type]
    assert r["valido"] is False and r["erro_tipo"] == "json_invalido" and Ruim.chamadas == 1


def test_trava_impede_segunda_rodada_e_limpa_ao_sair(tmp_path: Any) -> None:
    trava = tmp_path / "s3.lock"
    with rs.trava_de_rodada(trava):  # noqa: SIM117 (a segunda trava precisa abrir dentro da primeira)
        with pytest.raises(RuntimeError, match="em andamento"), rs.trava_de_rodada(trava):
            pass
    assert not trava.exists()


def test_trava_de_processo_morto_e_descartada(tmp_path: Any) -> None:
    trava = tmp_path / "s3.lock"
    trava.write_text("999999999")  # PID que não existe
    with rs.trava_de_rodada(trava):
        assert trava.read_text() != "999999999"


def test_gravar_e_atomico_e_nao_deixa_temporario(tmp_path: Any) -> None:
    alvo = tmp_path / "r.json"
    rs._gravar({"a": 1}, alvo)
    rs._gravar({"a": 2}, alvo)
    assert json.loads(alvo.read_text())["a"] == 2
    assert [p.name for p in tmp_path.iterdir()] == ["r.json"]


def test_separar_veredito_do_juiz_deixa_as_linhas_cegas() -> None:
    linhas = [
        {
            "item_id": "J1",
            "saida_do_sistema": "s",
            "veredito_juiz": "suportada",
            "proposicoes_juiz": "[1]",
            "veredito_humano_1": "",
        },
    ]
    cegas, privado = rs.separar_veredito_juiz(linhas)
    assert cegas[0]["veredito_juiz"] == "" and cegas[0]["proposicoes_juiz"] == ""
    assert cegas[0]["saida_do_sistema"] == "s"
    assert privado["J1"] == {"veredito_juiz": "suportada", "proposicoes_juiz": "[1]"}


def test_gravar_privado_nao_apaga_veredito_ja_guardado(tmp_path: Any) -> None:
    arq = tmp_path / "priv.json"
    rs.gravar_privado_juiz({"J1": {"veredito_juiz": "suportada", "proposicoes_juiz": ""}}, arq)
    rs.gravar_privado_juiz({"J1": {"veredito_juiz": "", "proposicoes_juiz": ""}}, arq)
    assert json.loads(arq.read_text())["J1"]["veredito_juiz"] == "suportada"
