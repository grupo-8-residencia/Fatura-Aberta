from datetime import date

import mapear_layouts as ml

# Texto no formato do `pdftotext -layout`, com dados pessoais FICTÍCIOS.
_TEXTO = (
    "NEOENERGIA BRASILIA\n"
    "Nome: MARIA FICTICIA DA SILVA          CPF: 123.456.789-09\n"
    "Endereço: QUADRA 99 CONJUNTO Z CASA 7\n"
    "Referência       Vencimento\n"
    "06/2026          15/07/2026\n"
    "Leitura anterior 1.000   Leitura atual 1.150\n"
    "\f"
    "Consumo kWh 150     ICMS 20,00%\n"
    "TOTAL A PAGAR   R$ 142,75\n"
)


def test_mes_referencia_na_linha_abaixo_do_rotulo() -> None:
    assert ml.mes_referencia(_TEXTO) == date(2026, 6, 1)
    assert ml.mes_referencia("sem data aqui") is None


def test_layout_pelo_corte_de_maio_2026() -> None:
    assert ml.layout_de(date(2026, 4, 1)) == "anterior"
    assert ml.layout_de(date(2026, 5, 1)) == "posterior"
    assert ml.layout_de(None) == "indefinido"


def test_mascarar_remove_pii_e_digitos() -> None:
    mascarado = ml.mascarar(_TEXTO)
    assert "MARIA" not in mascarado
    assert "QUADRA" not in mascarado
    assert "123" not in mascarado
    assert "99/9999" in mascarado  # mês de referência vira só formato
    assert "Leitura anterior" in mascarado


def test_localizar_rotulos_com_pagina_linha_e_coluna() -> None:
    mapa = ml.localizar_rotulos(_TEXTO)
    assert ml.Posicao(1, 4, 1) in mapa["mes_referencia"]
    assert ml.Posicao(1, 6, 26) in mapa["leitura_atual"]
    assert ml.Posicao(2, 1, 21) in mapa["aliquota_icms"]
    assert "pii_documento" in mapa


def test_resumo_nao_contem_valores() -> None:
    texto = ml.resumo({"posterior": [ml.localizar_rotulos(_TEXTO)]})
    assert "Layout posterior (1 faturas)" in texto
    assert "| total | 1/1 |" in texto
    for valor in ("MARIA", "142,75", "06/2026"):
        assert valor not in texto


def test_mascarar_nao_preserva_nome_sem_rotulo() -> None:
    texto = "JOAO DA SILVA\nRua das Flores 10\nLeitura atual 150\nConsumo kWh 150\n"

    mascarado = ml.mascarar(texto)

    for dado in ("JOAO", "SILVA", "Flores"):
        assert dado not in mascarado
    assert "Leitura atual" in mascarado
    assert "Consumo kWh" in mascarado
    # a largura é preservada, então as colunas continuam servindo para estudar o layout
    assert [len(a) for a in mascarado.splitlines()] == [len(b) for b in texto.splitlines()]


def test_mascarar_trata_o_rotulo_pessoal_na_primeira_linha_da_pagina() -> None:
    mascarado = ml.mascarar("Total 10,00\f" + "Nome Maria Silva\nTotal 20,00")

    assert "Maria" not in mascarado
    assert mascarado.count("\f") == 1


def test_data_pertence_ao_rotulo_de_referencia_em_colunas() -> None:
    texto = "Vencimento    Referência\n05/2026       04/2026\n"

    assert ml.mes_referencia(texto) == date(2026, 4, 1)
    assert ml.layout_de(ml.mes_referencia(texto)) == "anterior"


def test_data_na_mesma_linha_e_com_rotulo_invertido() -> None:
    assert ml.mes_referencia("Referência 04/2026   Vencimento 05/2026") == date(2026, 4, 1)
    assert ml.mes_referencia("Referência    Vencimento\n04/2026       05/2026") == date(2026, 4, 1)


def test_posicoes_do_resumo_batem_com_o_esqueleto() -> None:
    texto = "Nome\nMaria Silva\nTOTAL A PAGAR   10,00\n"

    esqueleto = ml.mascarar(texto)
    mapa = ml.localizar_rotulos(esqueleto)

    linha_no_arquivo = next(
        n for n, linha in enumerate(esqueleto.splitlines(), start=1) if "TOTAL" in linha
    )
    assert [p.linha for p in mapa["total"]] == [linha_no_arquivo]


def test_distribuidora_aparece_no_mapa() -> None:
    mapa = ml.localizar_rotulos("Distribuidora: Neoenergia Brasilia\n")

    assert "distribuidora" in mapa
