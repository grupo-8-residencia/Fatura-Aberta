"""RF-15 contextual (#169): bloqueia a conclusão, não a palavra isolada."""

from datetime import date
from decimal import Decimal

import pytest

from fa_agentes.auditor import contradiz_motor
from fa_agentes.linguagem import linguagem_permitida, verificar_linguagem
from fa_contratos import Fatura, ItemFatura
from fa_motor import analisar_nivel_a


@pytest.mark.parametrize(
    "texto",
    [
        "A ferramenta não calcula restituição nem indenização.",
        "A análise não determina se houve fraude.",
        "Não é possível afirmar fraude apenas com esta fatura.",
        "A ferramenta não faz cálculo de ressarcimento.",
    ],
)
def test_negar_a_funcao_da_ferramenta_e_linguagem_permitida(texto: str) -> None:
    assert linguagem_permitida(texto), verificar_linguagem(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Essa cobrança é ilegal.",
        "Essas cobranças são ilegais.",
        "Você tem direito a restituição.",
        "A ferramenta não calcula restituição, mas você tem direito à restituição.",
        "Você pode processar a concessionária.",
        "Isso é um golpe da distribuidora.",
        "Há cobrança abusiva.",
        "O valor devido é R$ 50,00.",
        "Houve má-fé da distribuidora.",
        "Há débito inexistente na conta.",
    ],
)
def test_conclusao_continua_bloqueada(texto: str) -> None:
    assert verificar_linguagem(texto)


@pytest.mark.parametrize("texto", ["Não pague a fatura.", "Deixe de pagar a conta até decidir."])
def test_instrucao_ao_consumidor_e_sempre_bloqueada(texto: str) -> None:
    violacoes = verificar_linguagem(texto)
    assert [v.regra for v in violacoes] == ["instrucao_ao_consumidor"]


def test_citacao_literal_so_passa_com_a_excecao_ligada() -> None:
    texto = "Cabe “devolução em dobro” nesse caso."
    assert verificar_linguagem(texto)
    assert verificar_linguagem(texto, permitir_citacao_literal=True) == []


def test_textos_de_divergencia_do_motor_passam_no_rf15_e_no_auditor() -> None:
    fatura = Fatura(
        distribuidora="Distribuidora Sintética",
        mes_referencia=date(2026, 3, 1),
        leitura_anterior=Decimal("10"),
        leitura_atual=Decimal("20"),
        consumo_kwh=Decimal("11"),
        itens=[
            ItemFatura(
                descricao="Consumo-TUSD",
                valor=Decimal("12"),
                quantidade=Decimal("10"),
                tarifa=Decimal("1.00"),
            )
        ],
        total=Decimal("9"),
    )

    divergentes = [
        a
        for a in analisar_nivel_a(fatura)
        if a.valor_esperado is not None and a.valor_esperado != a.valor_cobrado
    ]

    assert {a.item for a in divergentes} == {
        "Consumo medido",
        "Linha: Consumo-TUSD",
        "Total da fatura",
    }
    for achado in divergentes:
        assert verificar_linguagem(achado.descricao) == [], achado.descricao
        assert not contradiz_motor(achado.descricao, achado), achado.descricao
    assert any("R$ 10,00" in a.descricao for a in divergentes)
