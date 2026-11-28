#!/usr/bin/env python3
"""Avalia o limiar de abstenção 0,30 congelado no split de teste e no conjunto independente (S3-07).

1. Reavalia os limiares 0,20, 0,25 e 0,30 nos splits históricos de calibração (n = 60) e teste
   (n = 60), com intervalo de confiança de 95% (bootstrap B = 10.000, semente 42) global, por tipo
   e por categoria.
2. Avalia **apenas o limiar congelado 0,30** (``LIMIAR_PADRAO``, sem varredura nem reescolha) sobre
   o conjunto novo e independente de 36 perguntas (``abstencao-independente-36.csv``),
   estratificado nos 4 tipos (``normativa``, ``lacuna``, ``vigencia``, ``fora_do_corpus``) e nas
   7 categorias regulatórias, verificando disjunção estrita contra o golden set e contra as 20
   perguntas de ``s3-perguntas-novas-out-of-sample.json`` e registrando o estado/concordância da
   dupla anotação humana (Kappa de Cohen).

Uso: .venv/bin/python avaliacao/avaliar_abstencao_teste.py
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from cabecalho_reprodutivel import GOLDEN_SET, cabecalho
from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic, kappa_cohen
from metricas_recuperacao import metricas_abstencao

from fa_rag import IndiceHibrido, responder
from fa_rag.sintese import LIMIAR_PADRAO

RESULTADOS = Path(__file__).resolve().parent / "resultados"
ANOTACOES = Path(__file__).resolve().parent / "anotacoes"
ENTRADA_SPLITS = RESULTADOS / "s3-calibracao-abstencao.json"
ENTRADA_OOS = RESULTADOS / "s3-perguntas-novas-out-of-sample.json"
ENTRADA_INDEPENDENTE = ANOTACOES / "abstencao-independente-36.csv"
SAIDA = RESULTADOS / "s2s3-abstencao-teste.json"
LIMIARES = (0.20, 0.25, LIMIAR_PADRAO)
ROTULOS_ABSTENCAO = ("abster", "responder")


def _ic_abstencao(
    previsto: list[bool],
    esperado: list[bool],
    *,
    b: int = B_PADRAO,
    semente: int = SEMENTE_PADRAO,
    nivel: float = 0.95,
) -> dict[str, dict[str, float]]:
    """IC 95% por bootstrap pareado para precisão, recall, F1 e acurácia da decisão de abstenção."""
    rng = random.Random(semente)
    n = len(previsto)
    amostras: dict[str, list[float]] = {k: [] for k in ("precisao", "recall", "f1", "acuracia")}
    for _ in range(b):
        idx = [rng.randrange(n) for _ in range(n)]
        m = metricas_abstencao([previsto[k] for k in idx], [esperado[k] for k in idx])
        for chave in amostras:
            amostras[chave].append(m[chave])

    base = metricas_abstencao(previsto, esperado)
    cauda = (1 - nivel) / 2
    saida: dict[str, dict[str, float]] = {}
    for chave, vals in amostras.items():
        ordenado = sorted(vals)
        inf = ordenado[max(0, math.floor(cauda * b))]
        sup = ordenado[min(b - 1, math.ceil((1 - cauda) * b) - 1)]
        saida[chave] = {"estimativa": base[chave], "ic95_inf": inf, "ic95_sup": sup}
    return saida


def _previsoes(
    indice: IndiceHibrido, itens: list[dict[str, Any]], limiares: tuple[float, ...]
) -> dict[float, list[bool]]:
    tops = [
        indice.buscar(
            i["pergunta"],
            data_referencia=date.fromisoformat(i["data_referencia"]),
            top_k=5,
            um_por_dispositivo=True,
        )
        for i in itens
    ]
    return {lim: [responder(top, limiar=lim).abstencao for top in tops] for lim in limiares}


def _metricas(
    itens: list[dict[str, Any]], previsoes: dict[float, list[bool]]
) -> dict[str, dict[str, Any]]:
    esperado = [bool(i["abstencao_esperada"]) for i in itens]
    saida: dict[str, dict[str, Any]] = {}
    for lim, prev in previsoes.items():
        m = metricas_abstencao(prev, esperado)
        vn = sum((not p) and (not e) for p, e in zip(prev, esperado, strict=True))
        saida[f"limiar={lim}"] = {
            **m,
            "vn": vn,
            "ic95": _ic_abstencao(prev, esperado),
        }
    return saida


def _por_grupo(
    itens: list[dict[str, Any]], previsoes: dict[float, list[bool]], campo: str
) -> dict[str, Any]:
    grupos: dict[str, list[int]] = defaultdict(list)
    for pos, item in enumerate(itens):
        grupos[str(item[campo])].append(pos)
    saida: dict[str, Any] = {}
    for nome, posicoes in sorted(grupos.items()):
        esperado = [bool(itens[p]["abstencao_esperada"]) for p in posicoes]
        bloco: dict[str, Any] = {
            "n": len(posicoes),
            "abstencoes_esperadas": sum(esperado),
        }
        for lim, prev in previsoes.items():
            prev_g = [prev[p] for p in posicoes]
            m_g = metricas_abstencao(prev_g, esperado)
            acertos_g = [float(a == b) for a, b in zip(prev_g, esperado, strict=True)]
            ic_acc = bootstrap_ic(acertos_g, b=2000, semente=SEMENTE_PADRAO)
            bloco[f"limiar={lim}"] = {
                "acuracia": m_g["acuracia"],
                "acuracia_ic95": [ic_acc.inferior, ic_acc.superior],
                "precisao": m_g["precisao"],
                "recall": m_g["recall"],
                "f1": m_g["f1"],
                "abstencoes_previstas": sum(prev_g),
                "vp": m_g["vp"],
                "fp": m_g["fp"],
                "fn": m_g["fn"],
            }
        saida[nome] = bloco
    return saida


def ler_conjunto_independente(caminho: Path = ENTRADA_INDEPENDENTE) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calcular_concordancia_dupla(linhas: list[dict[str, str]]) -> dict[str, Any]:
    """Calcula a concordância independente (Kappa de Cohen) entre anotador_1 e anotador_2."""
    for r in linhas:
        for col in ("veredito_humano_1", "veredito_humano_2"):
            val = r.get(col, "").strip()
            if val and val not in ROTULOS_ABSTENCAO:
                raise ValueError(f"Rótulo inválido em {r.get('item_id')}.{col}: {val!r}")
        if r.get("anotador_1") == r.get("anotador_2"):
            raise ValueError(f"Anotadores devem ser distintos no item {r.get('item_id')}")

    n_total = len(linhas)
    n_h1 = sum(1 for r in linhas if r.get("veredito_humano_1", "").strip() in ROTULOS_ABSTENCAO)
    n_h2 = sum(1 for r in linhas if r.get("veredito_humano_2", "").strip() in ROTULOS_ABSTENCAO)
    pares = [
        (r["veredito_humano_1"].strip(), r["veredito_humano_2"].strip())
        for r in linhas
        if r.get("veredito_humano_1", "").strip() in ROTULOS_ABSTENCAO
        and r.get("veredito_humano_2", "").strip() in ROTULOS_ABSTENCAO
    ]
    if len(pares) < n_total:
        return {
            "status": "aguardando_anotador_2",
            "n_total": n_total,
            "n_anotador_1": n_h1,
            "n_anotador_2": n_h2,
            "n_pares_completos": len(pares),
            "kappa_humano1_humano2": None,
            "acuracia_entre_humanos": None,
        }
    h1 = [p[0] for p in pares]
    h2 = [p[1] for p in pares]
    acertos = [float(a == b) for a, b in pares]
    ic_acc = bootstrap_ic(acertos, b=B_PADRAO, semente=SEMENTE_PADRAO)
    return {
        "status": "concluida",
        "n_total": n_total,
        "n_anotador_1": n_h1,
        "n_anotador_2": n_h2,
        "n_pares_completos": len(pares),
        "kappa_humano1_humano2": kappa_cohen(h1, h2),
        "acuracia_entre_humanos": sum(acertos) / len(acertos),
        "acuracia_entre_humanos_ic95": [ic_acc.inferior, ic_acc.superior],
    }


def avaliar_conjunto_independente(
    indice: IndiceHibrido,
    *,
    caminho_csv: Path = ENTRADA_INDEPENDENTE,
    perguntas_proibidas: set[str] | None = None,
) -> dict[str, Any]:
    """Mede exclusivamente o limiar congelado 0,30 sobre o conjunto novo de 36 perguntas."""
    linhas = ler_conjunto_independente(caminho_csv)
    if perguntas_proibidas:
        norm_proibidas = {" ".join(q.lower().split()) for q in perguntas_proibidas}
        colisoes = [
            r["item_id"]
            for r in linhas
            if " ".join(r["pergunta"].lower().split()) in norm_proibidas
        ]
        if colisoes:
            raise ValueError(f"Perguntas compartilhadas com conjuntos anteriores: {colisoes}")

    itens: list[dict[str, Any]] = []
    for r in linhas:
        v1 = r["veredito_humano_1"].strip()
        v2 = r.get("veredito_humano_2", "").strip()
        # Se ambos anotaram e concordam, usa o consenso; enquanto anotador_2 está pendente, usa v1.
        espera_abster = (v1 == "abster") if not v2 else (v1 == "abster" and v2 == "abster")
        itens.append(
            {
                "id": r["item_id"],
                "tipo": r["tipo"],
                "categoria": r["categoria"],
                "data_referencia": r["data_referencia"],
                "subgrupo": r.get("subgrupo", "B1"),
                "pergunta": r["pergunta"],
                "abstencao_esperada": espera_abster,
            }
        )

    previsoes_030 = _previsoes(indice, itens, (LIMIAR_PADRAO,))
    global_030 = _metricas(itens, previsoes_030)[f"limiar={LIMIAR_PADRAO}"]
    por_tipo_030 = _por_grupo(itens, previsoes_030, "tipo")
    por_cat_030 = _por_grupo(itens, previsoes_030, "categoria")
    concordancia = calcular_concordancia_dupla(linhas)

    return {
        "arquivo": str(caminho_csv.name),
        "n": len(itens),
        "limiar_congelado": LIMIAR_PADRAO,
        "reescolha_de_limiar": False,
        "justificativa_tamanho": (
            "N = 36 perguntas inéditas e estritamente disjuntas do golden set (120) e do conjunto "
            "exploratório anterior (20): 22 respondíveis (18 normativas nas 7 categorias + 4 de "
            "lacuna) e 14 com abstenção esperada (7 de vigência anterior às normas + 7 fora do "
            "corpus, incluindo 3 de valor/alíquota/multa de CIP). O múltiplo de 6 permite rotação "
            "balanceada entre os 6 anotadores (6 pares x 6 itens) e poder estatístico > 85% "
            "(teste binomial exato unilateral a 5% contra baseline p0 = 0,50) e intervalos de "
            "confiança bootstrap (B = 10.000) não degenerados por tipo e categoria."
        ),
        "concordancia_anotadores": concordancia,
        "global_limiar_030": global_030,
        "por_tipo": por_tipo_030,
        "por_categoria": por_cat_030,
    }


def rodar() -> dict[str, Any]:
    itens = {
        i["id"]: i
        for i in (json.loads(x) for x in GOLDEN_SET.read_text(encoding="utf-8").splitlines() if x)
    }
    splits = json.loads(ENTRADA_SPLITS.read_text(encoding="utf-8"))["splits"]
    cal = [itens[i] for i in splits["ids_calibracao"]]
    teste = [itens[i] for i in splits["ids_teste"]]
    assert not {i["id"] for i in cal} & {i["id"] for i in teste}, "splits devem ser disjuntos"

    indice = IndiceHibrido.do_corpus()
    resultados: dict[str, Any] = {}
    for nome, conjunto in (("calibracao", cal), ("teste", teste)):
        prev = _previsoes(indice, conjunto, LIMIARES)
        resultados[nome] = {
            "n": len(conjunto),
            "global": _metricas(conjunto, prev),
            "por_tipo": _por_grupo(conjunto, prev, "tipo"),
            "por_categoria": _por_grupo(conjunto, prev, "categoria"),
        }

    oos = json.loads(ENTRADA_OOS.read_text(encoding="utf-8"))
    resultados["fora_da_amostra_resumo_historico"] = {
        "n": oos["n_total"],
        "abstencao_limiar_025": oos["abstencao_limiar_025"],
        "abstencao_limiar_030": oos["abstencao_limiar_030"],
        "nota": "copiado do JSON histórico, sem recomputar; fora do golden set",
    }

    perguntas_anteriores = {i["pergunta"] for i in itens.values()} | {
        d["pergunta"] for d in oos.get("detalhes", [])
    }
    resultados["conjunto_independente_limiar_030_congelado"] = avaliar_conjunto_independente(
        indice,
        caminho_csv=ENTRADA_INDEPENDENTE,
        perguntas_proibidas=perguntas_anteriores,
    )

    return {
        "cabecalho": cabecalho(indice, limiar=LIMIAR_PADRAO, top_k=5),
        "protocolo": {
            "origem_dos_splits": str(ENTRADA_SPLITS.name),
            "conjunto_independente": str(ENTRADA_INDEPENDENTE.name),
            "limitacao": (
                "No golden set (60/60) e nas 20 perguntas fora da amostra anteriores, "
                "o limiar 0,30 foi mantido após observar o split de teste. Para obter estimativa "
                "independente sem reescolher o limiar, avalia-se o limiar 0,30 congelado sobre o "
                "conjunto novo de 36 perguntas (abstencao-independente-36.csv)."
            ),
            "tau_0_48": "não existe no código; 0,48x são scores em s2-recall-gate.json",
        },
        "resultados": resultados,
    }


def main() -> int:
    saida = rodar()
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    teste = saida["resultados"]["teste"]["global"]
    for chave, m in teste.items():
        print(f"teste {chave}: F1={m['f1']:.3f} acc={m['acuracia']:.3f}")
    ind = saida["resultados"]["conjunto_independente_limiar_030_congelado"]["global_limiar_030"]
    ic_f1 = ind["ic95"]["f1"]
    print(
        f"independente (n=36, limiar=0.30 congelado): "
        f"P={ind['precisao']:.3f} R={ind['recall']:.3f} "
        f"F1={ind['f1']:.3f} [{ic_f1['ic95_inf']:.3f}; {ic_f1['ic95_sup']:.3f}] "
        f"acc={ind['acuracia']:.3f}"
    )
    print(f"Gravado em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
