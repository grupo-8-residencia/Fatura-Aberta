"""Página de anotação estática: itens certos por pessoa e nenhum dado do juiz."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_caminho = Path(__file__).resolve().parents[2] / "avaliacao" / "anotacao" / "construir_pagina.py"
_spec = importlib.util.spec_from_file_location("construir_pagina", _caminho)
assert _spec and _spec.loader
cp = importlib.util.module_from_spec(_spec)
sys.modules["construir_pagina"] = cp
_spec.loader.exec_module(cp)


def test_cada_pessoa_recebe_30_itens_e_20_perguntas() -> None:
    dados = cp.montar_dados()
    assert set(dados) == set(cp.PESSOAS)
    for d in dados.values():
        assert len(d["golden"]) == 30 and len(d["revisao"]) == 20
    todos = [i["id"] for d in dados.values() for i in d["revisao"]]
    assert len(todos) == 120 and len(set(todos)) == 120


def test_html_gerado_traz_os_dados_e_nao_usa_banco_nem_login() -> None:
    html = cp.construir(cp.montar_dados())
    assert "__DADOS__" not in html and "__VERSAO__" not in html
    # só a capacidade de download é usada; banco e usuário (que exigem login) ficam de fora
    assert 'use("db")' not in html and 'use("user")' not in html
    m = re.search(r"var DADOS = (\{.*?\});\n", html, re.S)
    assert m and set(json.loads(m.group(1))) == set(cp.PESSOAS)


def test_juiz_nao_expoe_veredito_do_juiz(tmp_path: Path) -> None:
    juiz = tmp_path / "juiz.csv"
    juiz.write_text(
        "item_id,tipo,anotador_1,anotador_2,saida_do_sistema,evidencia,proposicoes_juiz,"
        "veredito_humano_1,veredito_humano_2,veredito_juiz\n"
        "J1,pergunta,pedrohpsantos,NatyEvelin,SAIDA,EVID,SEGREDO_PROP,,,SEGREDO_JUIZ\n",
        encoding="utf-8",
    )
    dados = cp.montar_dados(juiz=juiz)
    assert [i["id"] for i in dados["pedrohpsantos"]["juiz"]] == ["J1"]
    assert [i["id"] for i in dados["NatyEvelin"]["juiz"]] == ["J1"]
    assert dados["luizoryone"]["juiz"] == []
    html = cp.construir(dados)
    assert "SAIDA" in html and "SEGREDO_JUIZ" not in html and "SEGREDO_PROP" not in html


def test_script_nao_e_fechado_por_conteudo_dos_itens() -> None:
    dados = {
        p: {"golden": [{"id": "x", "enunciado": "</script><b>"}], "revisao": [], "juiz": []}
        for p in cp.PESSOAS
    }
    html = cp.construir(dados)
    assert html.count("</script>") == 1


def test_pagina_guarda_so_o_verificador_e_ele_bate_com_o_do_importador() -> None:
    codigos = {p: "AAAA-BBBB-CCCC" for p in cp.PESSOAS}
    html = cp.construir(cp.montar_dados(), codigos=codigos)
    assert "AAAA-BBBB-CCCC" not in html and "AAAABBBBCCCC" not in html
    assert cp.verificador("NatyEvelin", "aaaa bbbb cccc") == cp.verificador(
        "NatyEvelin", "AAAA-BBBB-CCCC"
    )
    assert cp.verificador("NatyEvelin", "AAAA-BBBB-CCCC") in html
    assert cp.verificador("mariadenis", "AAAA-BBBB-CCCC") != cp.verificador(
        "NatyEvelin", "AAAA-BBBB-CCCC"
    )


def test_codigos_sao_criados_uma_vez_e_reaproveitados(tmp_path: Path) -> None:
    arq = tmp_path / "codigos.json"
    a = cp.carregar_codigos(arq)
    b = cp.carregar_codigos(arq)
    assert a == b and set(a) == set(cp.PESSOAS)
    assert all(len(v.replace("-", "")) == 12 for v in a.values())
    assert len(set(a.values())) == 6


def test_javascript_da_pagina_gera_o_mesmo_verificador_do_python() -> None:
    """Roda no node o trecho de criptografia da página: pegou um bug de hexadecimal em 11/11."""
    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node não instalado")
    modelo = cp.MODELO.read_text(encoding="utf-8")
    ini = modelo.index("  function normalizarCodigo")
    fim = modelo.index("function assinar(") + modelo[modelo.index("function assinar(") :].index(
        "\n"
    )
    trecho = modelo[ini:fim]
    script = (
        "const crypto = require('crypto').webcrypto;\n"
        + trecho
        + "\nderivarChave('NatyEvelin','ab12-cd34-ef56')"
        + ".then(k => assinar(k,'ok')).then(console.log);"
    )
    saida = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, timeout=60
    ).stdout.strip()
    assert saida == cp.verificador("NatyEvelin", "AB12-CD34-EF56")
