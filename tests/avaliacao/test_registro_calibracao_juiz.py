"""O registro da calibração do juiz LLM precisa bater com as anotações versionadas (débito S2/S3).

O juiz não atingiu a meta (κ ≥ 0,75): o resultado negativo é o oficial. Estes testes impedem que
o JSON e o CSV divirjam sem que alguém perceba, e fixam o que dá e o que não dá para reproduzir
sem rodar o juiz de novo.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from estatistica import kappa_cohen

RAIZ = Path(__file__).resolve().parents[2]
ANOTACOES = RAIZ / "avaliacao" / "anotacoes" / "juiz-40.csv"
CALIBRACAO = RAIZ / "avaliacao" / "resultados" / "s3-calibracao-juiz.json"


def _linhas() -> list[dict[str, str]]:
    with ANOTACOES.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def test_kappa_entre_humanos_do_json_e_reproduzido_pelo_csv() -> None:
    registro = json.loads(CALIBRACAO.read_text(encoding="utf-8"))
    excluidos = set(registro["itens_excluidos"])
    linhas = [r for r in _linhas() if r["item_id"] not in excluidos]
    assert len(linhas) == registro["n"] == 39
    h1 = [r["veredito_humano_1"] for r in linhas]
    h2 = [r["veredito_humano_2"] for r in linhas]
    assert kappa_cohen(h1, h2) == registro["kappa_humano1_humano2"]


def test_resultado_oficial_do_juiz_e_negativo() -> None:
    registro = json.loads(CALIBRACAO.read_text(encoding="utf-8"))
    assert registro["aprovado"] is False
    assert registro["kappa_humano1_juiz"] < registro["limiar_kappa"] == 0.75


def test_vereditos_do_juiz_nao_estao_no_csv() -> None:
    """Limitação conhecida: sem os vereditos por item, κ humano × juiz só se reproduz rodando o
    juiz de novo. Quando o CSV passar a guardá-los, troque este teste por um recálculo."""
    assert all(not r["veredito_juiz"] for r in _linhas())
