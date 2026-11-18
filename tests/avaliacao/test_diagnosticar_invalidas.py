"""Classificação das respostas inválidas da rodada S3 (sem LLM)."""

from __future__ import annotations

import diagnosticar_invalidas_s3 as diag


def test_classifica_as_causas_de_resposta_invalida() -> None:
    assert diag.classificar("") == "conteudo_vazio"
    assert diag.classificar('{"analise": "x", "resposta": "y"') == "json_truncado"
    assert diag.classificar("resposta sem json") == "json_malformado"
    assert (
        diag.classificar('{"analise": "", "resposta": "", "citacao": []}')
        == "chave_fora_do_esquema"
    )
    ok = '{"analise": "", "resposta": "", "abstencao": false, "citacoes": []}'
    assert diag.classificar(ok) == "valido_no_texto"
