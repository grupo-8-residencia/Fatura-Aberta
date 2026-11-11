"""O conversor gera candidatos sempre como "A verificar" e separa por artigo."""

import json
from pathlib import Path

import converter_norma as conv
import pytest

HTML = """<html><head><style>p{color:red}</style></head><body>
<p>Art. 1º Esta norma trata de faturas sintéticas.</p>
<p>§ 1º Primeiro parágrafo.</p>
<p>Art. 2º Segunda regra.<br>I - item um;</p>
<p>Art. 2º Texto repetido de uma citação, que deve ser ignorado.</p>
<p>Art. 3º-A Regra com sufixo.</p>
</body></html>"""


def test_separa_artigos_e_ignora_repetido() -> None:
    artigos = conv.separar_artigos(
        conv.limpar(conv.html_para_texto(HTML.encode()), religar_linhas=False)
    )
    assert list(artigos) == ["1", "2", "3-A"]
    assert "§ 1º Primeiro parágrafo." in artigos["1"]
    assert "I - item um;" in artigos["2"]
    assert "repetido" not in artigos["2"]
    assert "color" not in artigos["1"]


def test_religa_linhas_quebradas_de_pdf() -> None:
    texto = "Art. 5º A leitura deve ser feita\nem intervalos de 30 dias.\n§ 1º Outro texto."
    artigos = conv.separar_artigos(conv.limpar(texto, religar_linhas=True))
    assert (
        artigos["5"].splitlines()[0] == "Art. 5º A leitura deve ser feita em intervalos de 30 dias."
    )
    assert artigos["5"].splitlines()[1] == "§ 1º Outro texto."


def test_cp1252_e_decodificado() -> None:
    assert conv.decodificar("Art. 1º é válido".encode("cp1252")) == "Art. 1º é válido"


def test_saida_no_formato_do_corpus_e_nunca_conferida(tmp_path: Path) -> None:
    fonte = tmp_path / "norma.html"
    fonte.write_text(HTML, encoding="utf-8")
    saida = tmp_path / "saida.json"
    codigo = conv.main(
        [
            "--arquivo", str(fonte),
            "--url-oficial", "https://exemplo.gov.br/norma",
            "--ato", "Norma Sintética nº 1/2026",
            "--prefixo", "sint",
            "--vigencia-inicio", "2026-01-01",
            "--artigos", "2,99",
            "--saida", str(saida),
        ]
    )  # fmt: skip
    assert codigo == 0
    itens = json.loads(saida.read_text(encoding="utf-8"))
    assert [i["id"] for i in itens] == ["sint-art-2"]
    item = itens[0]
    assert item["conferido"] == "A verificar"
    assert item["citacao"]["dispositivo"] == "art. 2"
    assert item["citacao"]["url"] == "https://exemplo.gov.br/norma"
    assert item["subgrupos"] == ["B1"]


def test_url_com_esquema_invalido_e_recusada() -> None:
    with pytest.raises(SystemExit):
        conv.ler_fonte("file:///etc/passwd", None)


def test_sem_artigos_retorna_erro(tmp_path: Path) -> None:
    fonte = tmp_path / "vazio.txt"
    fonte.write_text("nada de artigos aqui", encoding="utf-8")
    codigo = conv.main(
        [
            "--arquivo", str(fonte),
            "--url-oficial", "https://exemplo.gov.br/x",
            "--ato", "X", "--prefixo", "x", "--vigencia-inicio", "2026-01-01",
        ]
    )  # fmt: skip
    assert codigo == 1


def test_html_com_quebra_de_linha_no_meio_da_frase_e_religado(tmp_path: Path) -> None:
    fonte = tmp_path / "quebrada.html"
    fonte.write_text(
        "<p>Art. 6º São direitos básicos\ndo consumidor:\nI - a proteção da vida,\nsaúde.</p>",
        encoding="utf-8",
    )
    saida = tmp_path / "saida.json"
    argumentos = ["--arquivo", str(fonte), "--url-oficial", "https://exemplo.gov.br/x"]
    argumentos += ["--ato", "X", "--prefixo", "x", "--vigencia-inicio", "2026-01-01"]
    assert conv.main([*argumentos, "--saida", str(saida)]) == 0
    texto = json.loads(saida.read_text(encoding="utf-8"))[0]["texto"]
    assert texto == "Art. 6º São direitos básicos do consumidor:\nI - a proteção da vida, saúde."


def test_lote_converte_manual_pula_excluido_e_aponta_o_que_falta(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def ato(prefixo: str, status: str, vigencia: str | None) -> dict[str, object]:
        return {
            "prefixo": prefixo,
            "ato": f"Ato {prefixo}",
            "vigencia_inicio": vigencia,
            "url_oficial": "https://exemplo.gov.br/x",
            "url_download": None,
            "status": status,
        }

    manifesto = tmp_path / "manifesto.json"
    atos = [ato("a", "ok", "2026-01-01"), ato("b", "a_confirmar", None), ato("c", "excluido", None)]
    manifesto.write_text(json.dumps(atos), encoding="utf-8")
    pasta = tmp_path / "manual"
    pasta.mkdir()
    (pasta / "a.html").write_text("<p>Art. 1º Texto.</p>", encoding="utf-8")
    saida = tmp_path / "saida"

    assert (
        conv.main(
            ["--manifesto", str(manifesto), "--pasta-manual", str(pasta)]
            + ["--saida-dir", str(saida)]
        )
        == 0
    )
    texto = capsys.readouterr().out
    assert "CONVERTIDO     a: 1 artigos" in texto
    assert "FALTA ARQUIVO  b" in texto
    assert "c:" not in texto
    assert "Atos contados: 2 de 3" in texto
    assert (saida / "a.json").exists()
    assert not (saida / "c.json").exists()


def test_vigencia_ausente_gera_item_com_aviso(tmp_path: Path) -> None:
    fonte = tmp_path / "n.html"
    fonte.write_text("<p>Art. 1º Texto.</p>", encoding="utf-8")
    saida = tmp_path / "s.json"
    argumentos = ["--arquivo", str(fonte), "--url-oficial", "https://exemplo.gov.br/x"]
    argumentos += ["--ato", "X", "--prefixo", "x", "--vigencia-inicio", "2026-01-01"]
    assert conv.main([*argumentos, "--saida", str(saida)]) == 0
    itens = conv.montar_itens(
        {"1": "Art. 1º Texto."},
        ato="X",
        prefixo="x",
        url="u",
        vigencia_inicio=None,
        subgrupos=["B1"],
    )
    assert itens[0]["citacao"]["vigencia_inicio"] is None  # type: ignore[index]
    assert "Vigência não informada" in str(itens[0]["observacoes"])


def _montar(texto: str, **extra: bool) -> dict[str, object]:
    artigos = conv.separar_artigos(conv.limpar(texto, religar_linhas=True))
    return conv.montar_itens(
        artigos, ato="X", prefixo="x", url="u", vigencia_inicio=None, subgrupos=["B1"], **extra
    )[0]


def test_notas_de_redacao_saem_do_texto_e_ficam_nas_observacoes() -> None:
    item = _montar(
        "Art. 39. É vedado ao fornecedor: (“Caput” do artigo com redação dada pela Lei nº 8.884, "
        "de 11/6/1994)\nI - condicionar o fornecimento; (Incluído pela Lei nº 8.884)"
    )
    assert "redação dada" not in str(item["texto"]) and "Incluído" not in str(item["texto"])
    assert "I - condicionar o fornecimento;" in str(item["texto"])
    assert "redação dada pela Lei nº 8.884" in str(item["observacoes"])
    assert "conferir a vigência" in str(item["observacoes"])


def test_manter_notas_preserva_o_texto_original() -> None:
    item = _montar("Art. 1º Regra. (Redação dada pela Lei nº 1/2020)", manter_notas=True)
    assert "Redação dada pela Lei" in str(item["texto"])


def test_trecho_revogado_fica_no_texto_e_e_sinalizado() -> None:
    item = _montar("Art. 5º Regra antiga. (Revogado pela Lei nº 2/2021)")
    assert "(Revogado pela Lei nº 2/2021)" in str(item["texto"])
    assert "revogado ou vetado" in str(item["observacoes"])


def test_cabecalho_rodape_e_numero_de_pagina_sao_removidos() -> None:
    cab = "09/11/2026, 15:01 Resolução Homologatória N° 3542/2025 - Leis.org"
    rod = "https://www.leis.org/aneel/reh3542 1/12"
    corpo = ["Art. 1º Primeira regra.", "Texto do artigo um.", "Art. 2º Segunda regra."]
    linhas = [cab, corpo[0], "Página 1 de 12", rod, cab, corpo[1], "- 2 -", rod, cab, corpo[2], rod]
    saida = conv.limpar("\n".join(linhas), religar_linhas=True)
    assert "Leis.org" not in saida and "leis.org" not in saida and "Página" not in saida
    assert (
        "Art. 1º Primeira regra. Texto do artigo um." in saida and "Art. 2º Segunda regra." in saida
    )


def test_cabecalho_longo_repetido_e_removido_mas_celula_de_tabela_fica() -> None:
    cab = "AGÊNCIA NACIONAL DE ENERGIA ELÉTRICA - ANEEL RESOLUÇÃO HOMOLOGATÓRIA"
    texto = "\n".join(
        ["Art. 1º Valores:", cab, "B1", "0,80", cab, "B1", "0,81", cab, "B1", "0,82", cab, "B1"]
    )
    saida = conv.limpar(texto, religar_linhas=False)
    assert "AGÊNCIA" not in saida
    assert saida.count("B1") == 4 and "0,80" in saida and "0,82" in saida


def test_rodape_do_diario_oficial_e_removido_no_ultimo_artigo() -> None:
    item = _montar(
        "Art. 3º Esta Resolução entra em vigor em 1º de abril de 2024. Este texto não substitui "
        "o publicado no D.O. de 14.03.2024, seção 1, p. 50, v. 161, n. 51."
    )
    assert item["texto"] == "Art. 3º Esta Resolução entra em vigor em 1º de abril de 2024."
