#!/usr/bin/env python3
"""Diagnóstico das respostas inválidas do T3 (B2) e do T4 (B3) na rodada S3.

1. Classifica as inválidas gravadas em ``s3-rodada.json``: conteúdo vazio, JSON truncado (sem
   fechamento), JSON malformado com conteúdo, ou chave fora do esquema.
2. Reexecuta só essas perguntas com outra configuração do gerador (``--pensar``, nível de
   raciocínio do gpt-oss) e mede quantas passam a ser válidas e quantas acertam, sobre o MESMO
   corpus da rodada S3 (extraído do commit da rodada) e o mesmo prompt.

É uma nova tentativa só nas inválidas, não uma rodada nova: o número resultante é rotulado assim no
relatório e não substitui o resultado da rodada padrão.

Uso:
    FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/diagnosticar_invalidas_s3.py --pensar medium
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rodada_s3 as rs  # noqa: E402

from fa_agentes import ClienteOllama  # noqa: E402
from fa_rag import IndiceHibrido  # noqa: E402

SAIDA = Path(__file__).resolve().parent / "resultados" / "s3-diagnostico-invalidas.json"
CHAVES = {"analise", "resposta", "abstencao", "citacoes"}


def classificar(bruto: str) -> str:
    texto = (bruto or "").strip()
    if not texto:
        return "conteudo_vazio"
    try:
        dados = json.loads(texto)
    except ValueError:
        return "json_truncado" if texto.count("{") > texto.count("}") else "json_malformado"
    if not isinstance(dados, dict) or not set(dados) >= CHAVES:
        return "chave_fora_do_esquema"
    return "valido_no_texto"


def corpus_do_commit(commit: str, raiz: Path) -> Path:
    bruto = subprocess.run(
        ["git", "show", f"{commit}:dados/normas/corpus_b1.json"],
        cwd=raiz, capture_output=True, check=True,
    ).stdout  # fmt: skip
    destino = Path(tempfile.mkdtemp()) / "corpus_b1.json"
    destino.write_bytes(bruto)
    return destino


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--pensar", default="medium", help="think do gpt-oss: low, medium ou high")
    ap.add_argument(
        "--entrada",
        type=Path,
        default=Path(__file__).resolve().parent / "resultados" / "s3-rodada.json",
    )
    ap.add_argument("--saida", type=Path, default=SAIDA)
    ap.add_argument("--so-classificar", action="store_true")
    args = ap.parse_args(argv)

    rodada = json.loads(args.entrada.read_text(encoding="utf-8"))
    commit = rodada["cabecalho"]["commit"]
    perguntas = {p["id"]: p for p in rs.ler_jsonl(rs.GOLDEN / "perguntas.jsonl")}
    resultado: dict[str, Any] = {
        "commit_da_rodada": commit,
        "configuracao_original": "gpt-oss:20b, think=low, temp. 0, semente 42, format=esquema",
        "nova_tentativa": f"mesmo prompt e corpus, think={args.pensar}",
        "bracos": {},
    }
    indice = None
    if not args.so_classificar:
        indice = IndiceHibrido.do_corpus(corpus_do_commit(commit, rs.RAIZ))
        cliente = ClienteOllama(pensar=args.pensar, cache_dir=rs.CACHE)
    for braco, nome in (("B2", "T3"), ("B3", "T4")):
        itens = rodada["perguntas"][braco]
        invalidas = [i for i in itens if not i.get("valido")]
        causas = Counter(classificar(i.get("bruto", "")) for i in invalidas)
        info: dict[str, Any] = {
            "teste": nome,
            "invalidas": len(invalidas),
            "causas": dict(causas),
            "tokens_saida_das_invalidas": sorted(
                int(i.get("tokens_saida") or 0) for i in invalidas
            ),
            "ids": [i["id"] for i in invalidas],
            "acertos_rodada_padrao": sum(bool(i["acerto"]) for i in itens),
        }
        if indice is not None:
            novos = rs.rodar_llm_perguntas(
                cliente, indice, [perguntas[i["id"]] for i in invalidas], braco,
                lambda m: print(m, flush=True), 1,
            )  # fmt: skip
            info["nova_tentativa"] = {
                "validas": sum(bool(n["valido"]) for n in novos),
                "acertos": sum(bool(n["acerto"]) for n in novos),
                "ainda_invalidas": [n["id"] for n in novos if not n["valido"]],
                "acerto_total_se_aplicado": (
                    info["acertos_rodada_padrao"] + sum(bool(n["acerto"]) for n in novos)
                ),
                "itens": [
                    {
                        k: n.get(k)
                        for k in (
                            "id",
                            "valido",
                            "acerto",
                            "abstencao",
                            "citacoes",
                            "tokens_saida",
                            "duracao_s",
                        )
                    }
                    for n in novos
                ],
            }
        resultado["bracos"][nome] = info
        print(
            nome,
            json.dumps(
                {k: v for k, v in info.items() if k != "nova_tentativa"}, ensure_ascii=False
            ),
            flush=True,
        )
    if indice is not None:
        rs._gravar(resultado, args.saida)
    else:
        print(json.dumps(resultado, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
