import bloquear_binarios as bb
import pytest


@pytest.mark.parametrize(
    "caminho",
    [
        "fatura.pdf",
        "dados/golden-set/foto.JPG",
        "dados/benchmark/real.png",
        "packages/extracao/tests/foto.heic",
        "./docs/fatura.jpeg",
        "docs/assets2/x.png",
    ],
)
def test_bloqueia_binarios_fora_das_pastas_permitidas(caminho: str) -> None:
    assert bb.bloqueado(caminho) is True


@pytest.mark.parametrize(
    "caminho",
    [
        "docs/assets/captura.png",
        "docs/assets/img/logo.PNG",
        "dados/benchmark/sinteticas/fatura-001.pdf",
        "README.md",
        "docs/assets/css/tema.css",
        "docs/assets/logo.svg",
    ],
)
def test_permite_pastas_liberadas_e_outros_formatos(caminho: str) -> None:
    assert bb.bloqueado(caminho) is False


def test_main_devolve_codigo_de_saida(capsys: pytest.CaptureFixture[str]) -> None:
    assert bb.main(["README.md", "docs/assets/a.png"]) == 0
    assert bb.main(["README.md", "fatura.pdf"]) == 1
    assert "fatura.pdf" in capsys.readouterr().out
