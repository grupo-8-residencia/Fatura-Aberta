#!/usr/bin/env python3
"""Demonstração do RAG normativo (F2): recuperação, filtro de vigência e resposta fundamentada.

Roda offline (embedder determinístico). Uso: ``.venv/bin/python scripts/demonstrar_rag.py``.
"""

from __future__ import annotations

import sys
from datetime import date

from fa_rag import IndiceHibrido, Resposta, responder

DATA_REFERENCIA = date(2026, 11, 9)
CONSULTAS = [
    "Posso ser cobrado por estimativa de consumo, sucessivamente, sem leitura do medidor?",
    "A bandeira tarifária se aplica na tarifa social de baixa renda?",
    "Corte de energia sem notificação prévia, é permitido?",
    "Como declarar criptomoedas no imposto de renda?",  # fora do escopo: deve abster-se
]


def _imprimir_fontes(resposta: Resposta) -> None:
    print("  Fontes:")
    if not resposta.citacoes:
        print("    (nenhuma: abstenção)")
    for c in resposta.citacoes:
        fim = c.vigencia_fim.isoformat() if c.vigencia_fim else "em vigor"
        print(f"    - Ato: {c.ato}")
        print(f"      Dispositivo: {c.dispositivo}")
        print(f"      Vigência: {c.vigencia_inicio.isoformat()} a {fim}")
        print(f"      Link oficial: {c.url}")


def main() -> int:
    indice = IndiceHibrido.do_corpus()
    print(f"Corpus: {len(indice.documentos)} chunks por dispositivo (alpha={indice.alpha}).")
    print(f"Data de referência: {DATA_REFERENCIA.isoformat()} | subgrupo: B1\n")
    abstencoes = 0
    for numero, consulta in enumerate(CONSULTAS, start=1):
        print(f"[{numero}] Pergunta: {consulta}")
        topo = indice.buscar(
            consulta, data_referencia=DATA_REFERENCIA, top_k=3, um_por_dispositivo=True
        )
        for r in topo:
            print(
                f"  score={r.score:.2f} (vetorial={r.score_vetorial:.2f}, "
                f"léxico={r.score_lexico:.2f})  {r.documento.citacao.dispositivo}"
            )
        resposta = responder(topo)
        abstencoes += resposta.abstencao
        print(f"  Resposta: {resposta.texto}")
        _imprimir_fontes(resposta)
        print()

    antes = date(2021, 6, 1)
    total = len(indice.documentos)
    vigentes = sum(d.vigente_em(antes) for d in indice.documentos)
    print(f"Prova do filtro de vigência (data {antes.isoformat()}, antes da REN 1.000/2021):")
    print(f"  {vigentes} de {total} chunks vigentes; só o CDC existia.")
    sem_filtro = indice.buscar(CONSULTAS[2], data_referencia=antes, filtrar_vigencia=False, top_k=1)
    com_filtro = indice.buscar(CONSULTAS[2], data_referencia=antes, top_k=1)
    print(
        f"  Sem filtro (B2): {sem_filtro[0].documento.citacao.dispositivo if sem_filtro else '-'}"
    )
    print(
        f"  Com filtro (B3): {com_filtro[0].documento.citacao.dispositivo if com_filtro else '-'}"
    )
    if abstencoes < 1:
        print("ERRO: a consulta fora do escopo deveria gerar abstenção.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
