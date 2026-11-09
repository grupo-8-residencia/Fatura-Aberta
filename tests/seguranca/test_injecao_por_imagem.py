from pathlib import Path

from fa_extracao import higienizar_texto_extraido

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[2]
CASOS = RAIZ_REPOSITORIO / "dados/benchmark/sinteticas/ataques-injecao"


def test_casos_de_injecao_nao_chegam_com_instrucoes_de_controle() -> None:
    caminhos = sorted(CASOS.glob("*.txt"))
    assert caminhos, "Os cenários sintéticos de injeção devem permanecer versionados."

    for caminho in caminhos:
        texto_seguro = higienizar_texto_extraido(caminho.read_text(encoding="utf-8"))
        assert "ignore instruções anteriores" not in texto_seguro.lower()
        assert "ignore all previous instructions" not in texto_seguro.lower()
        assert "system prompt" not in texto_seguro.lower()
        assert "you are now" not in texto_seguro.lower()


def test_caso_misto_preserva_valor_legitimo() -> None:
    texto = (CASOS / "03-misto.txt").read_text(encoding="utf-8")

    texto_seguro = higienizar_texto_extraido(texto)

    assert "Leitura atual: 150" in texto_seguro
