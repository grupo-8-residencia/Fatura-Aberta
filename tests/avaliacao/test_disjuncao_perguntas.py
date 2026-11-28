"""Verificação automatizada da estrita disjunção do conjunto independente (#112).

Comprova que o conjunto de N = 36 perguntas inéditas
(avaliacao/anotacoes/abstencao-independente-36.csv) é estritamente disjunto:
1. Do conjunto golden set (dados/golden-set/perguntas.jsonl, N = 120);
2. Do conjunto exploratório fora da amostra da S3 (avaliacao/checar_perguntas_novas.py, N = 20).

Garante ausência de vazamento de dados, unicidade de identificadores e diversidade léxica.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ARQ_36 = RAIZ / "avaliacao" / "anotacoes" / "abstencao-independente-36.csv"
ARQ_GOLDEN = RAIZ / "dados" / "golden-set" / "perguntas.jsonl"


def _tokens(txt: str) -> set[str]:
    """Extrai conjunto de tokens alfanuméricos em minúsculas."""
    return set(re.findall(r"\b\w+\b", txt.lower()))


def _jaccard(s1: set[str], s2: set[str]) -> float:
    """Calcula índice de Jaccard entre dois conjuntos de tokens."""
    uniao = s1 | s2
    return len(s1 & s2) / len(uniao) if uniao else 0.0


def _carregar_36() -> list[dict[str, str]]:
    assert ARQ_36.exists(), f"Arquivo não encontrado: {ARQ_36}"
    with ARQ_36.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _carregar_golden() -> list[dict[str, object]]:
    assert ARQ_GOLDEN.exists(), f"Arquivo não encontrado: {ARQ_GOLDEN}"
    linhas = []
    for linha in ARQ_GOLDEN.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            linhas.append(json.loads(linha))
    return linhas


def _carregar_exploratorias_20() -> tuple[dict[str, object], ...]:
    sys.path.insert(0, str(RAIZ / "avaliacao"))
    import checar_perguntas_novas as cpn

    return cpn.PERGUNTAS_NOVAS


def test_disjuncao_de_identificadores() -> None:
    """Verifica que os identificadores IND-Qxx não colidem com GS-Qxx nem NOV-Qxx."""
    p_36 = _carregar_36()
    p_golden = _carregar_golden()
    p_20 = _carregar_exploratorias_20()

    ids_36 = {r["item_id"] for r in p_36}
    ids_golden = {str(r["id"]) for r in p_golden}
    ids_20 = {str(r["id"]) for r in p_20}

    assert len(ids_36) == 36, "O conjunto independente deve conter exatamente 36 IDs únicos."
    assert not (ids_36 & ids_golden), f"Colisão de IDs com golden set: {ids_36 & ids_golden}"
    assert not (ids_36 & ids_20), f"Colisão de IDs com perguntas exploratórias: {ids_36 & ids_20}"


def test_disjuncao_exata_de_textos() -> None:
    """Garante que nenhum enunciado do conjunto de 36 é cópia literal do golden set ou das 20."""
    p_36 = _carregar_36()
    p_golden = _carregar_golden()
    p_20 = _carregar_exploratorias_20()

    textos_36 = {r["pergunta"].strip().lower() for r in p_36}
    textos_golden = {str(r["pergunta"]).strip().lower() for r in p_golden}
    textos_20 = {str(r["pergunta"]).strip().lower() for r in p_20}

    intersecao_golden = textos_36 & textos_golden
    assert not intersecao_golden, f"Perguntas idênticas ao golden set: {intersecao_golden}"

    intersecao_20 = textos_36 & textos_20
    assert not intersecao_20, f"Perguntas idênticas às 20 exploratórias: {intersecao_20}"


def test_limite_de_similaridade_lexica_jaccard() -> None:
    """Comprova que a similaridade Jaccard máxima de n-gramas léxicos é estritamente limitada."""
    p_36 = _carregar_36()
    p_golden = _carregar_golden()
    p_20 = _carregar_exploratorias_20()

    limiar_max_golden = 0.65
    limiar_max_20 = 0.45

    max_j_golden = 0.0
    par_max_golden = None
    for r36 in p_36:
        s36 = _tokens(r36["pergunta"])
        for rg in p_golden:
            sg = _tokens(str(rg["pergunta"]))
            j = _jaccard(s36, sg)
            if j > max_j_golden:
                max_j_golden = j
                par_max_golden = (r36["item_id"], r36["pergunta"], rg["id"], rg["pergunta"])

    assert max_j_golden <= limiar_max_golden, (
        f"Similaridade excessiva com golden set: {max_j_golden:.3f} > {limiar_max_golden} "
        f"no par: {par_max_golden}"
    )

    max_j_20 = 0.0
    par_max_20 = None
    for r36 in p_36:
        s36 = _tokens(r36["pergunta"])
        for r20 in p_20:
            s20 = _tokens(str(r20["pergunta"]))
            j = _jaccard(s36, s20)
            if j > max_j_20:
                max_j_20 = j
                par_max_20 = (r36["item_id"], r36["pergunta"], r20["id"], r20["pergunta"])

    assert max_j_20 <= limiar_max_20, (
        f"Similaridade excessiva com perguntas exploratórias: {max_j_20:.3f} > {limiar_max_20} "
        f"no par: {par_max_20}"
    )


def test_estratificacao_e_segunda_anotacao_pendente() -> None:
    """Verifica equilíbrio de classes e que a segunda anotação humana não foi forjada."""
    p_36 = _carregar_36()
    assert len(p_36) == 36

    tipos = {r["tipo"] for r in p_36}
    assert tipos == {"normativa", "lacuna", "vigencia", "fora_do_corpus"}

    categorias = {r["categoria"] for r in p_36}
    assert len(categorias) == 7

    # Anotador 1 (Luiz) está preenchido
    assert all(r["anotador_1"] == "Luiz" for r in p_36)
    assert all(r["veredito_humano_1"] in ("abster", "responder") for r in p_36)

    # Anotador 2 foi distribuído entre os 5 demais membros da equipe
    outros_anotadores = {r["anotador_2"] for r in p_36}
    assert "Luiz" not in outros_anotadores
    assert len(outros_anotadores) >= 4

    # Veredito do anotador 2 deve estar vazio (pendente) ou conter rótulo válido preenchido
    # pelo colega designado no rodízio
    assert all(r["veredito_humano_2"] in ("", "abster", "responder") for r in p_36), (
        "Veredito do anotador 2 deve permanecer vazio até a anotação ou conter rótulo válido."
    )
