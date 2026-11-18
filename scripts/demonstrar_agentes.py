#!/usr/bin/env python3
"""Demonstração do fluxo multiagente (F5): Analista Normativo e Auditor, ponta a ponta.

Mostra, passo a passo, quatro perguntas sobre a REN 1.000/2021 e o CDC:

1. uma pergunta respondida: o Analista redige uma afirmação fiel e o Auditor a aprova;
2. uma afirmação com erro: o Auditor reprova e a resposta vira abstenção;
3. uma pergunta fora do corpus: nenhum dispositivo passa do limiar e o LLM nem é chamado;
4. uma data sem norma vigente: o filtro de vigência não deixa nada passar.

Dois modos de LLM:

- ``--llm simulado`` (padrão): roda offline, sem modelo. O Analista é um **cliente simulado** que
  copia um trecho do dispositivo recuperado (cenário 1) ou erra um número de propósito (cenário 2).
  Serve para mostrar a colaboração e as regras do Auditor, não a qualidade de um modelo.
- ``--llm ollama``: usa o modelo local do experimento (``gpt-oss:20b``, ver ADR-002). O Ollama
  precisa estar rodando com o modelo baixado. Os cenários 2 a 4 não são forçados: o que o modelo
  responder é o que aparece.

Uso: ``uv run python scripts/demonstrar_agentes.py [--llm simulado|ollama] [--com-juiz]``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from fa_agentes import (
    AnalistaNormativo,
    Auditor,
    ClienteFalso,
    ClienteLLM,
    ResultadoAuditoria,
    criar_cliente,
)
from fa_rag import DocumentoNormativo, IndiceHibrido
from fa_rag.sintese import LIMIAR_PADRAO

DATA_ATUAL = date(2026, 11, 9)
DATA_ANTIGA = date(2021, 6, 1)


@dataclass(frozen=True, slots=True)
class Cenario:
    rotulo: str
    pergunta: str
    data_referencia: date
    esperado: str  # "respondida" ou "abstencao" (só vale no modo simulado)
    comportamento: str  # como o Analista simulado age: "fiel" ou "erra_numero"
    fonte: str | None = None  # dispositivo que o Analista simulado escolhe entre os recuperados


CENARIOS = (
    Cenario(
        "1. Pergunta respondida",
        "Posso ser cobrado pela média quando a distribuidora não consegue ler o medidor?",
        DATA_ATUAL,
        "respondida",
        "fiel",
        "ren1000-art-289",
    ),
    Cenario(
        "2. Afirmação com erro, barrada pelo Auditor",
        "Qual a multa máxima por atraso no pagamento?",
        DATA_ATUAL,
        "abstencao",
        "erra_numero",
    ),
    Cenario(
        "3. Pergunta fora do corpus",
        "Como declarar criptomoedas no imposto de renda?",
        DATA_ATUAL,
        "abstencao",
        "fiel",
    ),
    Cenario(
        "4. Data sem norma vigente",
        "Quantos ciclos entram na média quando o medidor não foi lido?",
        DATA_ANTIGA,
        "abstencao",
        "fiel",
    ),
)

_IDS_NO_PROMPT = re.compile(r"\[id: ([^\]]+)\]")
_NUMEROS = re.compile(r"\d+(?:[.,]\d+)?")


def _trecho(texto: str, limite: int = 420) -> str:
    plano = " ".join(texto.split())
    if len(plano) <= limite:
        return plano
    corte = plano[:limite]
    ponto = max(corte.rfind(". "), corte.rfind("; "))
    return corte[: ponto + 1] if ponto > 80 else corte.rstrip()


def _numero_ausente(fontes: str) -> str:
    presentes = set(_NUMEROS.findall(fontes))
    return next(str(n) for n in (7, 9, 13, 17, 19, 23, 29, 31) if str(n) not in presentes)


def analista_simulado(
    por_id: dict[str, DocumentoNormativo], comportamento: str, fonte: str | None
) -> Callable[[str, str], str]:
    """Respostas do Analista simulado, no formato JSON que o Analista Normativo espera."""

    def gerar(_sistema: str, prompt: str) -> str:
        ids = _IDS_NO_PROMPT.findall(prompt)
        if not ids:
            return json.dumps({"afirmacoes": []})
        escolhido = fonte if fonte is not None and fonte in ids else ids[0]
        doc = por_id[escolhido]
        texto = _trecho(doc.texto)
        if comportamento == "erra_numero":
            falso = _numero_ausente(f"{doc.titulo} {doc.texto}")
            texto = (
                re.sub(r"\d+\s?%", f"{falso}%", texto, count=1)
                if re.search(r"\d+\s?%", texto)
                else f"{texto} Prazo de {falso} dias."
            )
        afirmacao = {"texto": texto, "fontes": [escolhido]}
        return json.dumps({"afirmacoes": [afirmacao]}, ensure_ascii=False)

    return gerar


MOTIVOS = {
    "sem_citacao": "afirmação sem fonte",
    "citacao_inventada": "fonte que não foi recuperada",
    "citacao_divergente": "citação diferente da do dispositivo",
    "fora_de_vigencia": "dispositivo não vigente na data",
    "sem_suporte": "número ou termo sem lastro no dispositivo citado",
    "linguagem_proibida": "expressão proibida pelo RF-15",
    "juiz_rejeitou": "o juiz LLM não aprovou",
}


def _linha(titulo: str, valor: str = "") -> None:
    print(f"  {titulo:<22}{valor}")


def _mostrar_resultado(resultado: ResultadoAuditoria) -> None:
    for p in resultado.problemas:
        detalhe = f" ({p.detalhe})" if p.detalhe else ""
        _linha("  reprovada:", f"{p.motivo.value}{detalhe}: {MOTIVOS[p.motivo.value]}")
        print(f"{'':<24}«{p.afirmacao}»")
    for a in resultado.afirmacoes_aprovadas:
        _linha("  aprovada:", f"«{a.texto}»")


def _rodar(
    cenario: Cenario,
    indice: IndiceHibrido,
    gerador: ClienteLLM,
    juiz: ClienteLLM | None,
) -> bool:
    print(f"\n=== {cenario.rotulo} ===")
    print(f"Pergunta: {cenario.pergunta}")
    print(f"Data de referência: {cenario.data_referencia.isoformat()}\n")

    topo = indice.buscar(
        cenario.pergunta, data_referencia=cenario.data_referencia, subgrupos=("B1",), top_k=5
    )
    melhor = f"{topo[0].score:.2f}" if topo else "nenhum"
    print("[Agente 1: Analista Normativo]")
    _linha("busca vigente (RAG):", f"melhor score {melhor}, limiar {LIMIAR_PADRAO:.2f}")

    relatorio = AnalistaNormativo(indice, gerador).analisar(
        cenario.pergunta, data_referencia=cenario.data_referencia
    )
    if not relatorio.dispositivos:
        _linha("dispositivos:", "nenhum passou do limiar; o LLM não foi chamado")
    for d in relatorio.dispositivos:
        _linha("dispositivo:", f"{d.id} ({d.citacao.dispositivo})")
    for a in relatorio.afirmacoes:
        _linha("afirmação proposta:", f"«{a.texto}»")
        _linha("  fontes citadas:", ", ".join(a.ids_fontes))

    print("\n[Agente 2: Auditor]")
    resultado = Auditor(juiz).auditar(relatorio)
    if relatorio.afirmacoes:
        _mostrar_resultado(resultado)
    else:
        _linha("sem afirmações:", "nada a conferir")

    print("\n[Resposta final]")
    if resultado.abstencao:
        print(f"  ABSTENÇÃO. {resultado.resposta.texto}")
    else:
        for linha in resultado.resposta.texto.splitlines():
            print(f"  {linha}")
    return resultado.abstencao


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--llm", choices=("simulado", "ollama"), default="simulado")
    parser.add_argument("--com-juiz", action="store_true", help="liga o juiz LLM do Auditor")
    args = parser.parse_args(argv)

    indice = IndiceHibrido.do_corpus()
    por_id = {d.id: d for d in indice.documentos}
    print(f"Corpus: {len(indice.documentos)} chunks por dispositivo.")
    print(f"LLM: {'simulado (offline, sem modelo)' if args.llm == 'simulado' else 'ollama'}")

    juiz: ClienteLLM | None = None
    gerador_ollama: ClienteLLM | None = None
    if args.llm == "ollama":
        ambiente = {**os.environ, "FA_LLM_PROVEDOR": "ollama"}
        gerador_ollama = criar_cliente("gerador", ambiente)
        juiz = criar_cliente("juiz", ambiente) if args.com_juiz else None
    elif args.com_juiz:
        print("--com-juiz só vale com --llm ollama; ignorado.", file=sys.stderr)

    divergencias = 0
    for cenario in CENARIOS:
        gerador: ClienteLLM
        if gerador_ollama is None:
            falso = analista_simulado(por_id, cenario.comportamento, cenario.fonte)
            gerador = ClienteFalso(resposta=falso)
        else:
            gerador = gerador_ollama
        abstencao = _rodar(cenario, indice, gerador, juiz)
        if args.llm == "simulado" and abstencao != (cenario.esperado == "abstencao"):
            divergencias += 1
            print(f"ERRO: esperado {cenario.esperado} em «{cenario.rotulo}».", file=sys.stderr)

    print(
        "\nResumo: o Analista propõe, o Auditor só deixa passar o que tem fonte vigente e lastro."
    )
    return 1 if divergencias else 0


if __name__ == "__main__":
    sys.exit(main())
