#!/usr/bin/env python3
"""Compara o hashing lexical atual com um embedder semântico local (débito S2/S3, issue S4-05).

Mesmo corpus, mesmas perguntas, mesmos filtros. Só a metade de **teste** do golden set entra nas
métricas; o limiar de abstenção de cada embedder é escolhido na metade de **calibração**, porque a
escala dos scores muda entre embedders e o 0,30 histórico só vale para o hashing.

Modos: léxico puro (α = 0, igual nos dois embedders), vetorial puro (α = 1) e híbrido (α = 0,5).
Chunking, α e filtros ficam como estão: só o embedder muda.

O modelo semântico roda no Ollama local (`/api/embed`); nada é baixado pelo script nem pelo CI.
Sem o modelo ou sem o servidor, o script registra E2 como bloqueado e mede só o hashing.

Uso: .venv/bin/python avaliacao/comparar_embedders.py [--modelo bge-m3]
"""

from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from cabecalho_reprodutivel import GOLDEN_SET, cabecalho
from metricas_recuperacao import metricas_abstencao, metricas_ranking, ranking_artigos

from fa_rag import EmbedderHash, IndiceHibrido, responder

RESULTADOS = Path(__file__).resolve().parent / "resultados"
SPLITS = RESULTADOS / "s3-calibracao-abstencao.json"
SAIDA = RESULTADOS / "s2s3-embedders.json"
OLLAMA = "http://localhost:11434"
MODOS = {"lexico_puro": 0.0, "hibrido_0.5": 0.5, "vetorial_puro": 1.0}
GRADE_LIMIAR = tuple(round(0.05 * k, 2) for k in range(1, 20))


class EmbedderOllama:
    """Vetores L2-normalizados vindos do `/api/embed` do Ollama local."""

    def __init__(self, modelo: str, *, digest: str = "") -> None:
        self.nome = f"ollama:{modelo}"
        self.versao = digest
        self.modelo = modelo
        self.dim = len(self.embed(["dimensão"])[0])

    def embed(self, textos: Sequence[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for i in range(0, len(textos), 16):
            corpo = json.dumps({"model": self.modelo, "input": list(textos[i : i + 16])})
            req = urllib.request.Request(
                f"{OLLAMA}/api/embed",
                data=corpo.encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resposta:  # noqa: S310
                bruto = json.loads(resposta.read())["embeddings"]
            for v in bruto:
                norma = math.sqrt(sum(x * x for x in v)) or 1.0
                vetores.append([x / norma for x in v])
        return vetores


def _info_modelo(modelo: str) -> dict[str, Any]:
    """Digest, tamanho em disco e licença, direto do Ollama; vazio se indisponível."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=10) as r:  # noqa: S310
            tags = json.loads(r.read())["models"]
        achado = next(m for m in tags if m["name"].split(":")[0] == modelo)
        req = urllib.request.Request(
            f"{OLLAMA}/api/show",
            data=json.dumps({"model": modelo}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            show = json.loads(r.read())
        return {
            "modelo": achado["name"],
            "digest": achado["digest"],
            "tamanho_bytes": achado["size"],
            "licenca_primeira_linha": (show.get("license") or "").strip().splitlines()[:2],
            "familia": show.get("details", {}),
        }
    except (urllib.error.URLError, StopIteration, KeyError, OSError):
        return {}


def _percentil(valores: list[float], p: float) -> float:
    ordenado = sorted(valores)
    return ordenado[min(len(ordenado) - 1, math.ceil(p * len(ordenado)) - 1)]


def _avaliar(
    indice: IndiceHibrido, cal: list[dict[str, Any]], teste: list[dict[str, Any]]
) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    com_norma = [i for i in teste if not i["abstencao_esperada"]]
    canon = [set(i["citacao_canonica"]) for i in com_norma]
    for modo, alpha in MODOS.items():
        tempos: list[float] = []
        rankings = []
        for item in com_norma:
            t0 = time.perf_counter()
            rankings.append(ranking_artigos(indice, item, alpha=alpha))
            tempos.append((time.perf_counter() - t0) * 1000)
        m = metricas_ranking(rankings, canon)
        resumo = {
            k: m[k]["estimativa"] for k in ("recall@3", "recall@5", "MRR", "nDCG@5", "precisao@5")
        }

        def previsoes(itens: list[dict[str, Any]], limiar: float, a: float = alpha) -> list[bool]:
            return [
                responder(
                    indice.buscar(
                        i["pergunta"],
                        data_referencia=date.fromisoformat(i["data_referencia"]),
                        top_k=5,
                        um_por_dispositivo=True,
                        alpha=a,
                    ),
                    limiar=limiar,
                ).abstencao
                for i in itens
            ]

        esp_cal = [bool(i["abstencao_esperada"]) for i in cal]
        esp_teste = [bool(i["abstencao_esperada"]) for i in teste]
        f1_cal = {
            lim: metricas_abstencao(previsoes(cal, lim), esp_cal)["f1"] for lim in GRADE_LIMIAR
        }
        melhor = max(f1_cal.values())
        escolhido = max(lim for lim, f in f1_cal.items() if abs(f - melhor) < 1e-12)
        saida[modo] = {
            "alpha": alpha,
            "ranking_teste": resumo,
            "n_perguntas_com_norma": len(com_norma),
            "latencia_consulta_ms": {
                "p50": _percentil(tempos, 0.5),
                "p95": _percentil(tempos, 0.95),
                "media": sum(tempos) / len(tempos),
            },
            "abstencao": {
                "limiar_escolhido_na_calibracao": escolhido,
                "f1_calibracao": melhor,
                "teste": metricas_abstencao(previsoes(teste, escolhido), esp_teste),
                "teste_limiar_0.30_fixo": metricas_abstencao(previsoes(teste, 0.30), esp_teste),
            },
        }
    return saida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default="bge-m3")
    args = parser.parse_args()

    itens = {
        i["id"]: i
        for i in (json.loads(x) for x in GOLDEN_SET.read_text(encoding="utf-8").splitlines() if x)
    }
    splits = json.loads(SPLITS.read_text(encoding="utf-8"))["splits"]
    cal = [itens[i] for i in splits["ids_calibracao"]]
    teste = [itens[i] for i in splits["ids_teste"]]

    resultados: dict[str, Any] = {}
    cab: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        t0 = time.perf_counter()
        e1 = IndiceHibrido.do_corpus(embedder=EmbedderHash(), arquivo_vetores=base / "e1.json")
        resultados["E1_hash_lexical"] = {
            "construcao_indice_s": time.perf_counter() - t0,
            **_avaliar(e1, cal, teste),
        }
        cab = cabecalho(e1, limiar=None, top_k=5)

        info = _info_modelo(args.modelo)
        if not info:
            resultados["E2_semantico"] = {
                "status": "bloqueado",
                "motivo": f"modelo {args.modelo} ou servidor Ollama indisponível",
            }
        else:
            t0 = time.perf_counter()
            emb = EmbedderOllama(args.modelo, digest=info["digest"])
            e2 = IndiceHibrido.do_corpus(embedder=emb, arquivo_vetores=base / "e2.json")
            construcao = time.perf_counter() - t0
            resultados["E2_semantico"] = {
                "modelo": info,
                "dim": emb.dim,
                "construcao_indice_s": construcao,
                **_avaliar(e2, cal, teste),
            }

    saida = {
        "cabecalho": {**cab, "protocolo": "teste = ids_teste de s3-calibracao-abstencao.json"},
        "n_calibracao": len(cal),
        "n_teste": len(teste),
        "resultados": resultados,
    }
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nome, r in resultados.items():
        if "hibrido_0.5" in r:
            h = r["hibrido_0.5"]["ranking_teste"]
            print(f"{nome} híbrido: recall@5={h['recall@5']:.3f} MRR={h['MRR']:.3f}")
        else:
            print(nome, r)
    print(f"Gravado em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
