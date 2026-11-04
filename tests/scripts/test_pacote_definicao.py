import pacote_definicao as pd


def test_contar_palavras_ignora_comentarios_html() -> None:
    assert pd.contar_palavras("um dois <!-- tres quatro --> cinco") == 3


def test_todas_as_secoes_do_pacote_existem() -> None:
    dados = pd.analisar()
    assert set(dados) == set(pd.SECOES)
    assert all(item["existe"] for item in dados.values())


def test_pagina_consolidada_inclui_todas_as_secoes() -> None:
    pagina = (pd.RAIZ / "docs" / "produto" / "pacote-de-definicao.md").read_text(encoding="utf-8")
    for nome in pd.SECOES:
        assert f"docs/produto/definicao/{nome}" in pagina
