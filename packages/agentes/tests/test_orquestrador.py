"""Sistema multiagentes (S4): Pesquisador, Analista, Auditor, Comunicador e Orquestrador.

LLM simulado (``ClienteFalso``): sem rede e sem modelo. Cada teste fixa um papel do fluxo.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from fa_agentes import (
    ClienteFalso,
    Comunicador,
    MotivoAbstencao,
    Origem,
    Orquestrador,
    Persona,
    Pesquisador,
    contradiz_motor,
    verificar_linguagem,
)
from fa_contratos import Achado, Citacao, Fatura, ItemFatura, Nivel
from fa_rag import DocumentoNormativo, IndiceHibrido

DATA = date(2024, 5, 10)


def _doc(
    id_: str, texto: str, disp: str, inicio: date, fim: date | None = None
) -> DocumentoNormativo:
    c = Citacao(
        ato="REN ANEEL nº 1.000/2021",
        dispositivo=disp,
        vigencia_inicio=inicio,
        vigencia_fim=fim,
        url="https://exemplo.invalid/ato",
    )
    return DocumentoNormativo(id=id_, titulo=disp, texto=texto, citacao=c, subgrupos=("B1",))


PRAZO = _doc(
    "ren1000-art-318",
    "A distribuidora deve emitir a fatura de energia elétrica com antecedência mínima de "
    "5 dias úteis em relação ao vencimento.",
    "art. 318",
    date(2022, 1, 3),
)
TOTAL = _doc(
    "ren1000-art-327",
    "A fatura de energia elétrica deve conter o valor total devido e a data de vencimento, "
    "e a soma dos valores das linhas da fatura deve corresponder ao valor total devido.",
    "art. 327",
    date(2022, 1, 3),
)
PERGUNTA = "Qual o prazo para a distribuidora emitir a fatura de energia?"
TEXTO_OK = "A fatura deve ser emitida com antecedência mínima de 5 dias úteis do vencimento."


def _indice() -> IndiceHibrido:
    return IndiceHibrido([PRAZO, TOTAL])


def _llm(*afirmacoes: tuple[str, list[str]]) -> ClienteFalso:
    corpo = {"afirmacoes": [{"texto": t, "fontes": f} for t, f in afirmacoes]}
    return ClienteFalso(resposta=json.dumps(corpo, ensure_ascii=False))


def _fatura(total: str) -> Fatura:
    return Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=DATA,
        leitura_anterior=Decimal("100"),
        leitura_atual=Decimal("150"),
        consumo_kwh=Decimal("50"),
        itens=[ItemFatura(descricao="Energia", valor=Decimal("40"))],
        total=Decimal(total),
    )


def _motor(f: Fatura) -> list[Achado]:
    soma = sum((i.valor for i in f.itens), start=Decimal("0"))
    return [
        Achado(
            item="Total da fatura",
            nivel=Nivel.A,
            descricao=(
                "A soma das linhas confere com o total informado."
                if soma == f.total
                else "A soma das linhas não confere com o total informado."
            ),
            valor_esperado=soma,
            valor_cobrado=f.total,
        )
    ]


# --------------------------------------------------------------------- Pesquisador


def test_pesquisador_entrega_dispositivo_vigente_com_citacao() -> None:
    ev = Pesquisador(_indice()).buscar_com_citacao(PERGUNTA, data_referencia=DATA)
    assert ev.dispositivos[0].id == "ren1000-art-318"
    assert not ev.abstencao and not ev.resposta_extrativa.abstencao
    assert ev.resposta_extrativa.citacoes[0].dispositivo == "art. 318"


def test_pesquisador_distingue_fora_de_vigencia_de_fora_do_corpus() -> None:
    p = Pesquisador(_indice())
    antes = p.buscar_com_citacao(PERGUNTA, data_referencia=date(2021, 6, 1))
    assert antes.abstencao and antes.motivo_abstencao == MotivoAbstencao.FORA_DE_VIGENCIA
    fora = p.buscar_com_citacao("Qual a alíquota da CIP no DF?", data_referencia=DATA)
    assert fora.abstencao and fora.motivo_abstencao == MotivoAbstencao.FORA_DO_CORPUS


# --------------------------------------------------------------------- Orquestrador (pergunta)


def test_rascunho_aprovado_pelo_auditor_e_entregue() -> None:
    orq = Orquestrador(_indice(), _llm((TEXTO_OK, ["ren1000-art-318"])))
    r = orq.responder_pergunta(PERGUNTA, data_referencia=DATA)
    assert r.origem == Origem.ANALISTA_AUDITADO and not r.abstencao
    assert [p.agente for p in r.rastro] == ["Pesquisador", "Analista", "Auditor", "Comunicador"]
    assert "art. 318" in r.mensagem.texto


def test_rascunho_barrado_cai_na_resposta_extrativa_e_nao_abstem() -> None:
    orq = Orquestrador(_indice(), _llm(("O prazo é de 10 dias úteis.", ["ren1000-art-318"])))
    r = orq.responder_pergunta(PERGUNTA, data_referencia=DATA)
    assert r.origem == Origem.PESQUISADOR_EXTRATIVO and not r.abstencao
    assert any(p.motivo.value == "sem_suporte" for p in r.problemas)
    assert "fallback" in [p.acao for p in r.rastro]
    assert "10 dias" not in r.mensagem.texto


def test_citacao_inventada_tambem_cai_no_extrativo() -> None:
    orq = Orquestrador(_indice(), _llm((TEXTO_OK, ["ren1000-art-999"])))
    r = orq.responder_pergunta(PERGUNTA, data_referencia=DATA)
    assert r.origem == Origem.PESQUISADOR_EXTRATIVO
    assert r.resposta.citacoes[0].dispositivo == "art. 318"


def test_sem_evidencia_abstem_sem_chamar_o_llm() -> None:
    llm = _llm((TEXTO_OK, ["ren1000-art-318"]))
    r = Orquestrador(_indice(), llm).responder_pergunta(PERGUNTA, data_referencia=date(2021, 6, 1))
    assert r.origem == Origem.ABSTENCAO and r.abstencao
    assert llm.chamadas == []
    assert [p.agente for p in r.rastro] == ["Pesquisador", "Comunicador"]


@pytest.mark.parametrize("persona", list(Persona))
def test_comunicador_adapta_sem_numero_novo_nem_linguagem_proibida(persona: Persona) -> None:
    orq = Orquestrador(_indice(), _llm((TEXTO_OK, ["ren1000-art-318"])))
    r = orq.responder_pergunta(PERGUNTA, data_referencia=DATA, persona=persona)
    assert r.mensagem.adaptada and r.mensagem.persona is persona
    assert verificar_linguagem(r.mensagem.texto) == []


def test_comunicador_recusa_adaptacao_que_acrescenta_numero() -> None:
    c = Comunicador()
    msg = c._conferir(Persona.CELINA, "São 7 dias.", {"5"}, "original", ())
    assert not msg.adaptada and msg.texto == "original" and "7" in msg.motivo


# --------------------------------------------------------------------- Orquestrador (fatura)


def test_fatura_que_confere_nao_aciona_os_agentes() -> None:
    llm = _llm()
    res = Orquestrador(_indice(), llm, motor=_motor).analisar_fatura(_fatura("40"))
    assert res.veredito == "confere" and res.explicacoes == ()
    assert llm.chamadas == []


def test_fatura_divergente_recebe_norma_e_minuta_sem_mudar_o_veredito() -> None:
    texto = "A soma dos valores das linhas da fatura deve corresponder ao valor total devido."
    orq = Orquestrador(_indice(), _llm((texto, ["ren1000-art-327"])), motor=_motor)
    res = orq.analisar_fatura(_fatura("55"), persona=Persona.MARCIA)
    assert res.veredito == "diverge_A"
    assert res.origens["Total da fatura"] == Origem.ANALISTA_AUDITADO
    explic = res.explicacoes[0]
    assert explic.nivel is Nivel.C and explic.citacoes[0].dispositivo == "art. 327"
    assert "Minuta de pedido de esclarecimento" in res.mensagem.texto
    assert "40" in res.mensagem.texto and "55" in res.mensagem.texto


def test_auditor_barra_texto_que_contradiz_o_motor() -> None:
    achado = _motor(_fatura("55"))[0]
    assert contradiz_motor("O total confere com a soma das linhas.", achado)
    assert not contradiz_motor("O total não confere com a soma das linhas.", achado)
    orq = Orquestrador(
        _indice(),
        _llm(
            ("A soma das linhas da fatura confere com o valor total devido.", ["ren1000-art-327"])
        ),
        motor=_motor,
    )
    res = orq.analisar_fatura(_fatura("55"))
    assert res.origens["Total da fatura"] == Origem.PESQUISADOR_EXTRATIVO
    assert res.veredito == "diverge_A"


def test_orquestrador_sem_motor_exige_achados() -> None:
    with pytest.raises(ValueError, match="motor"):
        Orquestrador(_indice(), _llm()).analisar_fatura(_fatura("40"))


DOBRO = _doc(
    "ren1000-art-323::p2",
    "A distribuidora deve fazer a devolução em dobro do valor pago a maior pelo consumidor.",
    "art. 323, § 2º",
    date(2022, 1, 3),
)


def test_fallback_transcreve_trecho_literal_com_termo_da_norma_entre_aspas() -> None:
    """Exceção do RF-15 (18/11/2026): citação literal entre aspas, com a referência, é permitida."""
    indice = IndiceHibrido([DOBRO])
    pergunta = "O que a distribuidora deve fazer com o valor pago a maior pelo consumidor?"
    for persona in Persona:
        r = Orquestrador(indice, _llm()).responder_pergunta(
            pergunta, data_referencia=DATA, persona=persona
        )
        assert r.origem == Origem.PESQUISADOR_EXTRATIVO and not r.abstencao
        assert "“" in r.resposta.texto and "devolução em dobro" in r.resposta.texto
        assert verificar_linguagem(r.resposta.texto, permitir_citacao_literal=True) == []
        assert verificar_linguagem(r.mensagem.texto, permitir_citacao_literal=True) == []
        assert r.resposta.citacoes[0].dispositivo == "art. 323, § 2º"


def test_termo_vedado_fora_das_aspas_continua_bloqueado() -> None:
    assert verificar_linguagem("Cabe devolução em dobro.", permitir_citacao_literal=True)
    assert verificar_linguagem("“devolução em dobro”")  # sem a exceção ligada, bloqueia
    assert verificar_linguagem(
        "O texto diz “devolução em dobro”, logo é ilegal.", permitir_citacao_literal=True
    )


def test_comunicador_nunca_devolve_original_com_termo_vedado() -> None:
    c = DOBRO.citacao
    msg = Comunicador().comunicar_resposta(
        Persona.CELINA,
        pergunta="Valor pago a maior?",
        afirmacoes=[("Cabe devolução em dobro do valor pago a maior.", (c,))],
        texto_original="Cabe devolução em dobro do valor pago a maior.",
        abstencao=False,
    )
    assert not msg.adaptada and "linguagem proibida" in msg.motivo
    assert verificar_linguagem(msg.texto) == [] and "art. 323" in msg.texto


def test_comunicador_sem_afirmacao_trata_como_abstencao() -> None:
    msg = Comunicador().comunicar_resposta(
        Persona.RAFAEL, pergunta="?", afirmacoes=[], texto_original="", abstencao=False
    )
    assert "absteve" in msg.texto


def test_itens_alem_do_limite_ficam_registrados_no_rastro() -> None:
    achados = _motor(_fatura("55")) * 2
    achados = [achados[0], achados[0].model_copy(update={"item": "Outro total"})]
    res = Orquestrador(_indice(), _llm()).analisar_fatura(
        _fatura("55"), achados_motor=achados, max_itens=1
    )
    assert any(p.acao == "limite" and "Outro total" in p.detalhe for p in res.rastro)
