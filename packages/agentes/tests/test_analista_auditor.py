"""Analista Normativo e Auditor com LLM simulado: sem rede, sem modelo, sem chave."""

from __future__ import annotations

import json
from datetime import date

import pytest

from fa_agentes import (
    Afirmacao,
    AnalistaNormativo,
    Auditor,
    ClienteFalso,
    Motivo,
    RelatorioAnalise,
    para_achado,
    responder_com_auditoria,
)
from fa_contratos import Achado, Citacao, Nivel
from fa_rag import DocumentoNormativo, IndiceHibrido
from fa_rag.sintese import TEXTO_ABSTENCAO

DATA = date(2024, 5, 10)
PERGUNTA = "Qual o prazo para a distribuidora emitir a fatura de energia?"


def _doc(
    id_: str, texto: str, *, ato: str = "REN 1.000/2021", disp: str, inicio: date, fim: date | None
) -> DocumentoNormativo:
    citacao = Citacao(
        ato=ato,
        dispositivo=disp,
        vigencia_inicio=inicio,
        vigencia_fim=fim,
        url="https://exemplo.invalid/ato",
    )
    return DocumentoNormativo(
        id=id_, titulo=disp, texto=texto, citacao=citacao, subgrupos=("B1",), tags=()
    )


FATURA_VIGENTE = _doc(
    "ren1000-art-318",
    "A distribuidora deve emitir a fatura de energia elétrica com antecedência mínima de "
    "5 dias úteis em relação ao vencimento.",
    disp="art. 318",
    inicio=date(2022, 1, 3),
    fim=None,
)
FATURA_REVOGADA = _doc(
    "ren414-art-113",
    "A distribuidora deve emitir a fatura de energia elétrica com antecedência mínima de "
    "10 dias úteis em relação ao vencimento.",
    ato="REN 414/2010",
    disp="art. 113",
    inicio=date(2010, 9, 9),
    fim=date(2022, 1, 2),
)
OUTRO = _doc(
    "ren1000-art-98",
    "O consumidor pode pedir religação de urgência da unidade consumidora.",
    disp="art. 98",
    inicio=date(2022, 1, 3),
    fim=None,
)

TEXTO_OK = "A fatura deve ser emitida com antecedência mínima de 5 dias úteis do vencimento."


def _indice() -> IndiceHibrido:
    return IndiceHibrido([FATURA_VIGENTE, FATURA_REVOGADA, OUTRO])


def _llm(*afirmacoes: tuple[str, list[str]]) -> ClienteFalso:
    corpo = {"afirmacoes": [{"texto": t, "fontes": f} for t, f in afirmacoes]}
    return ClienteFalso(resposta=json.dumps(corpo, ensure_ascii=False))


def _relatorio(*afirmacoes: Afirmacao, docs: tuple[DocumentoNormativo, ...]) -> RelatorioAnalise:
    return RelatorioAnalise(PERGUNTA, DATA, docs, afirmacoes)


def _afirmacao(texto: str, doc: DocumentoNormativo) -> Afirmacao:
    return Afirmacao(texto, (doc.id,), (doc.citacao,))


def test_analista_afirmacoes_trazem_citacao_completa() -> None:
    cliente = _llm((TEXTO_OK, [FATURA_VIGENTE.id]))
    rel = AnalistaNormativo(_indice(), cliente, limiar=0.0).analisar(PERGUNTA, data_referencia=DATA)
    assert rel.afirmacoes
    for a in rel.afirmacoes:
        assert a.citacoes
        for c in a.citacoes:
            assert c.ato and c.dispositivo and c.vigencia_inicio
            assert c.vigente_em(DATA)
    assert FATURA_REVOGADA.id not in {d.id for d in rel.dispositivos}
    assert FATURA_REVOGADA.id not in cliente.chamadas[0][1]


def test_analista_aceita_achado_do_motor() -> None:
    achado = Achado(item="Prazo de emissão", nivel=Nivel.C, descricao="fatura de energia emitida")
    cliente = _llm((TEXTO_OK, [FATURA_VIGENTE.id]))
    rel = AnalistaNormativo(_indice(), cliente, limiar=0.0).analisar(
        data_referencia=DATA, achado=achado
    )
    assert rel.consulta.startswith("Prazo de emissão")
    assert rel.afirmacoes


def test_analista_exige_pergunta_ou_achado() -> None:
    with pytest.raises(ValueError):
        AnalistaNormativo(_indice(), _llm()).analisar(data_referencia=DATA)


def test_analista_sem_dispositivo_acima_do_limiar_nem_chama_o_llm() -> None:
    cliente = _llm((TEXTO_OK, [FATURA_VIGENTE.id]))
    rel = AnalistaNormativo(_indice(), cliente).analisar("xyzzy plugh quux", data_referencia=DATA)
    assert rel.afirmacoes == ()
    assert cliente.chamadas == []


def test_analista_saida_ilegivel_nao_gera_afirmacao() -> None:
    cliente = ClienteFalso(resposta="isto não é json")
    rel = AnalistaNormativo(_indice(), cliente, limiar=0.0).analisar(PERGUNTA, data_referencia=DATA)
    assert rel.afirmacoes == ()
    assert Auditor().auditar(rel).abstencao


def test_auditor_aprova_afirmacao_com_suporte() -> None:
    res = Auditor().auditar(
        _relatorio(_afirmacao(TEXTO_OK, FATURA_VIGENTE), docs=(FATURA_VIGENTE,))
    )
    assert not res.abstencao
    assert res.problemas == ()
    assert res.resposta.citacoes == (FATURA_VIGENTE.citacao,)
    assert "REN 1.000/2021" in res.resposta.texto and "art. 318" in res.resposta.texto
    assert "2022-01-03" in res.resposta.texto
    assert res.resposta.ids_fontes == (FATURA_VIGENTE.id,)


def test_auditor_abstem_sem_afirmacao() -> None:
    res = Auditor().auditar(_relatorio(docs=()))
    assert res.abstencao and res.resposta.texto == TEXTO_ABSTENCAO
    assert res.resposta.citacoes == ()


def test_auditor_abstem_sem_citacao() -> None:
    sem_fonte = Afirmacao(TEXTO_OK, (), ())
    res = Auditor().auditar(_relatorio(sem_fonte, docs=(FATURA_VIGENTE,)))
    assert res.abstencao
    assert [p.motivo for p in res.problemas] == [Motivo.SEM_CITACAO]


def test_auditor_abstem_com_citacao_inventada() -> None:
    inventada = Afirmacao(TEXTO_OK, ("ren1000-art-999",), ())
    res = Auditor().auditar(_relatorio(inventada, docs=(FATURA_VIGENTE,)))
    assert res.abstencao and res.resposta.texto == TEXTO_ABSTENCAO
    assert res.problemas[0].motivo == Motivo.CITACAO_INVENTADA
    assert "ren1000-art-999" in res.problemas[0].detalhe


def test_auditor_abstem_com_citacao_fora_de_vigencia() -> None:
    antiga = "A fatura deve ser emitida com antecedência mínima de 10 dias úteis do vencimento."
    rel = _relatorio(_afirmacao(antiga, FATURA_REVOGADA), docs=(FATURA_REVOGADA,))
    res = Auditor().auditar(rel)
    assert res.abstencao
    assert Motivo.FORA_DE_VIGENCIA in {p.motivo for p in res.problemas}


def test_auditor_abstem_com_citacao_adulterada() -> None:
    falsa = Afirmacao(TEXTO_OK, (FATURA_VIGENTE.id,), (OUTRO.citacao,))
    res = Auditor().auditar(_relatorio(falsa, docs=(FATURA_VIGENTE,)))
    assert res.abstencao
    assert Motivo.CITACAO_DIVERGENTE in {p.motivo for p in res.problemas}


def test_auditor_abstem_quando_numero_nao_esta_no_dispositivo() -> None:
    errada = "A fatura deve ser emitida com antecedência mínima de 15 dias úteis do vencimento."
    res = Auditor().auditar(_relatorio(_afirmacao(errada, FATURA_VIGENTE), docs=(FATURA_VIGENTE,)))
    assert res.abstencao
    assert res.problemas[0].motivo == Motivo.SEM_SUPORTE


def test_auditor_abstem_quando_texto_nao_tem_lastro() -> None:
    solta = "A tarifa social garante desconto automático para famílias de baixa renda."
    res = Auditor().auditar(_relatorio(_afirmacao(solta, FATURA_VIGENTE), docs=(FATURA_VIGENTE,)))
    assert res.abstencao
    assert res.problemas[0].motivo == Motivo.SEM_SUPORTE


def test_auditor_barra_linguagem_proibida_rf15() -> None:
    ilegal = TEXTO_OK + " A cobrança fora do prazo é ilegal."
    res = Auditor().auditar(_relatorio(_afirmacao(ilegal, FATURA_VIGENTE), docs=(FATURA_VIGENTE,)))
    assert res.abstencao
    assert Motivo.LINGUAGEM_PROIBIDA in {p.motivo for p in res.problemas}


def test_auditor_estrito_uma_reprovacao_derruba_a_resposta_inteira() -> None:
    boa = _afirmacao(TEXTO_OK, FATURA_VIGENTE)
    inventada = Afirmacao(TEXTO_OK, ("nao-existe",), ())
    res = Auditor().auditar(_relatorio(boa, inventada, docs=(FATURA_VIGENTE,)))
    assert res.abstencao
    assert res.afirmacoes_aprovadas == ()


def test_juiz_pode_rejeitar_mas_nao_aprovar_o_que_o_auditor_barrou() -> None:
    nega = ClienteFalso(resposta='{"suportada": false}')
    rel = _relatorio(_afirmacao(TEXTO_OK, FATURA_VIGENTE), docs=(FATURA_VIGENTE,))
    res = Auditor(nega).auditar(rel)
    assert res.abstencao and res.problemas[0].motivo == Motivo.JUIZ_REJEITOU

    aprova = ClienteFalso(resposta='{"suportada": true}')
    inventada = Afirmacao(TEXTO_OK, ("nao-existe",), ())
    assert Auditor(aprova).auditar(_relatorio(inventada, docs=(FATURA_VIGENTE,))).abstencao
    assert aprova.chamadas == []  # reprovada antes: o juiz nem foi consultado
    assert not Auditor(aprova).auditar(rel).abstencao

    ilegivel = ClienteFalso(resposta="talvez")
    assert Auditor(ilegivel).auditar(rel).abstencao


def test_pipeline_responde_com_citacao_vigente() -> None:
    res = responder_com_auditoria(
        PERGUNTA,
        data_referencia=DATA,
        indice=_indice(),
        gerador=_llm((TEXTO_OK, [FATURA_VIGENTE.id])),
        limiar=0.0,
    )
    assert not res.abstencao
    assert all(c.vigente_em(DATA) for c in res.resposta.citacoes)


def test_pipeline_llm_cita_dispositivo_revogado_vira_abstencao() -> None:
    # O índice filtra a REN 414 pela data; o modelo a cita mesmo assim (anacronismo).
    antiga = "A fatura deve ser emitida com antecedência mínima de 10 dias úteis do vencimento."
    res = responder_com_auditoria(
        PERGUNTA,
        data_referencia=DATA,
        indice=_indice(),
        gerador=_llm((antiga, [FATURA_REVOGADA.id])),
        limiar=0.0,
    )
    assert res.abstencao and res.resposta.texto == TEXTO_ABSTENCAO
    assert res.problemas[0].motivo == Motivo.CITACAO_INVENTADA


def test_pipeline_pergunta_fora_do_corpus_se_abstem() -> None:
    res = responder_com_auditoria(
        "xyzzy plugh quux",
        data_referencia=DATA,
        indice=_indice(),
        gerador=_llm((TEXTO_OK, [FATURA_VIGENTE.id])),
    )
    assert res.abstencao


def test_para_achado_abstencao_vira_nivel_c_e_resposta_vira_nivel_b() -> None:
    abst = para_achado("Prazo", Auditor().auditar(_relatorio(docs=())))
    assert abst.abstencao and abst.nivel == Nivel.C and not abst.citacoes
    ok = para_achado(
        "Prazo",
        Auditor().auditar(_relatorio(_afirmacao(TEXTO_OK, FATURA_VIGENTE), docs=(FATURA_VIGENTE,))),
    )
    assert not ok.abstencao and ok.nivel == Nivel.C and ok.citacoes == [FATURA_VIGENTE.citacao]
