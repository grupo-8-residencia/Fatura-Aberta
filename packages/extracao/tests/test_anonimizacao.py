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
