from fa_extracao import anonimizar


def test_remove_linhas_rotuladas_e_documentos(pii: dict[str, str]) -> None:
    texto = "\n".join(
        [
            f"Nome: {pii['nome']}",
            f"Endereço: {pii['endereco']}",
            f"Instalação: {pii['instalacao']}",
            f"CPF: {pii['cpf']}",
            "Contato fulano@exemplo.com e CNPJ 12.345.678/0001-90",
            "Consumo kWh: 150",
        ]
    )

    limpo = anonimizar(texto)

    for dado in [*pii.values(), "fulano@exemplo.com", "12.345.678/0001-90"]:
        assert dado not in limpo
    assert "Consumo kWh: 150" in limpo


def test_remove_dado_pessoal_sem_dois_pontos(pii: dict[str, str]) -> None:
    texto = "\n".join(
        [
            f"Nome {pii['nome']}",
            f"Endereço {pii['endereco']}",
            f"Instalação {pii['instalacao']}",
            f"CPF {pii['cpf']}",
            "Consumo kWh: 150",
        ]
    )

    limpo = anonimizar(texto)

    for dado in pii.values():
        assert dado not in limpo
    assert "Consumo kWh: 150" in limpo


def test_remove_valor_na_linha_seguinte_ao_rotulo(pii: dict[str, str]) -> None:
    texto = f"Nome\n{pii['nome']}\nInstalação:\n{pii['instalacao']}\nConsumo kWh: 150"

    limpo = anonimizar(texto)

    assert pii["nome"] not in limpo
    assert pii["instalacao"] not in limpo
    assert "Consumo kWh: 150" in limpo


def test_remove_rotulo_com_prefixo_numero_da(pii: dict[str, str]) -> None:
    limpo = anonimizar(f"Nº da instalação {pii['instalacao']}\nTotal a pagar: R$ 10,00")

    assert pii["instalacao"] not in limpo
    assert "Total a pagar: R$ 10,00" in limpo


def test_preserva_linhas_sem_rotulo_pessoal() -> None:
    texto = "Distribuidora: Neoenergia Brasilia\nNomeação de bandeira: amarela\nConsumo kWh: 150"

    assert anonimizar(texto) == texto
