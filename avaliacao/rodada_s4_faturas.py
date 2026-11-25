#!/usr/bin/env python3
"""Rodada S4 nas 200 faturas sintéticas: o sistema multiagentes (T5) no fluxo de fatura.

O motor determinístico (nível A) decide o veredito de cada fatura; o Orquestrador aciona
Pesquisador → Analista (LLM) → Auditor → Comunicador para explicar, com norma citada, até 3 itens
divergentes ou sem dados por fatura. O que se mede aqui:

- acerto do veredito contra o gabarito (vem do motor; o LLM não tem como alterá-lo);
- de onde veio cada explicação (rascunho aprovado pelo Auditor, resposta extrativa ou abstenção);
- por que o Auditor barrou rascunhos, inclusive ``veredito_alterado`` (texto que contradiz o motor);
- expressões proibidas pelo RF-15 e números novos na mensagem final (autoconferência do
  Comunicador);
- latência por fatura.

Uso (Ollama local, ADR-002):
    FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s4_faturas.py
    .venv/bin/python avaliacao/rodada_s4_faturas.py --limite 5     # cliente falso, só tubulação
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rodada_s3 as rs  # noqa: E402
import rodada_s4 as r4  # noqa: E402
from estatistica import SEMENTE_PADRAO  # noqa: E402

from fa_agentes import Orquestrador, Persona, criar_cliente, metadados_rodada  # noqa: E402
from fa_agentes.linguagem import verificar_linguagem  # noqa: E402
from fa_motor import analisar_nivel_a  # noqa: E402
from fa_rag import IndiceHibrido  # noqa: E402

SAIDA = r4.RESULTADOS / "s4-t5-faturas.json"


def avaliar_fatura(orq: Orquestrador, r: dict[str, Any]) -> dict[str, Any]:
    fatura = rs.converter_fatura(r)
    inicio = time.perf_counter()
    res = orq.analisar_fatura(fatura, persona=Persona.MARCIA)
    duracao = round(time.perf_counter() - inicio, 3)
    return {
        "id": r["id"],
        "gabarito": r["gabarito_fatura"],
        "veredito": res.veredito,
        "acerto": res.veredito == r["gabarito_fatura"],
        "anomalia": r["anomalia_injetada"],
        "itens_explicados": len(res.explicacoes),
        "origens": res.origens,
        "motivos_auditor": {k: list(v) for k, v in res.motivos_auditor.items()},
        "nivel_explicacoes": [e.nivel.value for e in res.explicacoes],
        "mensagem_adaptada": res.mensagem.adaptada,
        "motivo_sem_adaptacao": res.mensagem.motivo,
        "linguagem_mensagem": [v.termo for v in verificar_linguagem(res.mensagem.texto)],
        "linguagem_explicacoes": [
            v.termo for e in res.explicacoes for v in verificar_linguagem(e.descricao)
        ],
        "chamadas_llm": sum(1 for p in res.rastro if p.agente == "Analista"),
        "duracao_s": duracao,
    }


def resumir(itens: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(itens)
    origens: Counter[str] = Counter(o for i in itens for o in i["origens"].values())
    motivos: Counter[str] = Counter(
        m for i in itens for ms in i["motivos_auditor"].values() for m in ms
    )
    com_llm = [i for i in itens if i["chamadas_llm"]]
    anomalas = [i for i in itens if i["gabarito"] != "confere"]
    corretas = [i for i in itens if i["gabarito"] == "confere"]
    return {
        "n": n,
        "acerto_veredito": rs._ic([i["acerto"] for i in itens]) if n else None,
        "deteccao_anomalia": sum(i["veredito"] != "confere" for i in anomalas)
        / max(len(anomalas), 1),
        "falso_alarme": sum(i["veredito"] != "confere" for i in corretas) / max(len(corretas), 1),
        "itens_explicados": sum(i["itens_explicados"] for i in itens),
        "origem_das_explicacoes": dict(origens),
        "motivos_do_auditor": dict(sorted(motivos.items())),
        "veredito_alterado_barrado": motivos["veredito_alterado"],
        "mensagens_nao_adaptadas": sum(not i["mensagem_adaptada"] for i in itens),
        "violacoes_rf15_mensagem": sum(1 for i in itens if i["linguagem_mensagem"]),
        "violacoes_rf15_explicacoes": sum(1 for i in itens if i["linguagem_explicacoes"]),
        "chamadas_llm": sum(i["chamadas_llm"] for i in itens),
        "latencia_media_s_faturas_com_llm": round(
            sum(i["duracao_s"] for i in com_llm) / max(len(com_llm), 1), 2
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args(argv)
    faturas = rs.ler_jsonl(rs.GOLDEN / "faturas_sinteticas.jsonl")[: args.limite]
    indice = IndiceHibrido.do_corpus()
    gerador = criar_cliente("gerador", cache_dir=r4.CACHE)
    orq = Orquestrador(indice, gerador, motor=analisar_nivel_a)
    dados = rs._carregar_saida(args.saida)
    cab = metadados_rodada(
        {"gerador": gerador}, checksums=rs.GOLDEN / "checksums.sha256", raiz=rs.RAIZ
    )
    cab.update(
        {
            "semente_bootstrap": SEMENTE_PADRAO,
            "persona": "marcia",
            "max_itens_explicados_por_fatura": 3,
            "sha256_corpus": r4.sha256_corpus(indice.documentos),
            "documentos_corpus": len(indice.documentos),
            "limite": args.limite,
        }
    )
    feitos = {i["id"]: i for i in dados.get("itens", [])}
    if dados.get("cabecalho", {}).get("sha256_corpus") not in (None, cab["sha256_corpus"]):
        raise RuntimeError("Não retomo: o corpus mudou desde a rodada gravada")
    dados["cabecalho"] = cab
    for n, r in enumerate(faturas, 1):
        if r["id"] in feitos:
            continue
        feitos[r["id"]] = avaliar_fatura(orq, r)
        i = feitos[r["id"]]
        print(
            f"T5 fatura {n}/{len(faturas)} {r['id']} -> {i['veredito']} "
            f"explicados={i['itens_explicados']} origens={sorted(i['origens'].values())} "
            f"{i['duracao_s']}s",
            flush=True,
        )
        if n % 5 == 0:
            dados["itens"] = [feitos[f["id"]] for f in faturas if f["id"] in feitos]
            rs._gravar(dados, args.saida)
    dados["itens"] = [feitos[f["id"]] for f in faturas if f["id"] in feitos]
    dados["resumo"] = resumir(dados["itens"])
    dados["parcial"] = len(dados["itens"]) < 200
    rs._gravar(dados, args.saida)
    print(dados["resumo"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
