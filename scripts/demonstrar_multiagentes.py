#!/usr/bin/env python3
"""Demonstração ponta a ponta do sistema multiagentes da S4.

Quatro agentes colaboram, coordenados pelo Orquestrador:

    Pesquisador  →  Analista (LLM)  →  Auditor  →  Comunicador
    (busca com      (redige afirmações  (confere      (adapta à persona
     citação)        com fonte)          lastro)       e se autoconfere)

Cenários:

1. pergunta respondida (o Auditor aprova o rascunho do Analista);
2. rascunho com número errado: o Auditor barra e entra a resposta extrativa do Pesquisador;
3. pergunta fora do corpus: o Pesquisador abstém e o LLM nem é chamado;
4. data anterior à vigência da norma: abstenção explicada;
5. fatura sintética com total divergente: o motor decide, os agentes explicam e o Comunicador
   escreve a minuta de pedido de esclarecimento.

Modos de LLM:

- ``--llm simulado`` (padrão, offline): o Analista é um cliente simulado que copia a primeira
  frase do dispositivo recuperado (cenários 1 e 5) ou troca um número (cenário 2). Mostra a
  colaboração e as regras, não a qualidade de um modelo.
- ``--llm ollama``: o modelo local do experimento (``gpt-oss:20b``, ADR-002). Nada é forçado.

Uso: ``uv run python scripts/demonstrar_multiagentes.py [--llm simulado|ollama] [--persona P]``.
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
from decimal import Decimal

from fa_agentes import (
    ClienteFalso,
    ClienteLLM,
    Orquestrador,
    Passo,
    Persona,
    criar_cliente,
)
from fa_contratos import Fatura, ItemFatura
from fa_motor import analisar_nivel_a
from fa_rag import IndiceHibrido

DATA = date(2026, 11, 9)
_TEXTO_DO_ID = re.compile(r"\[id: ([^\]]+)\][^\n]*\n([^\n]+)")


@dataclass(frozen=True, slots=True)
class Cenario:
    rotulo: str
    pergunta: str
    data_referencia: date
    comportamento: str  # do Analista simulado: "fiel" ou "erra_numero"
    fonte: str | None = None  # dispositivo que o Analista simulado prefere, se recuperado


CENARIOS = (
    Cenario(
        "1. Pergunta respondida",
        "Posso ser cobrado pela média quando a distribuidora não consegue ler o medidor?",
        DATA,
        "fiel",
        "ren1000-art-289",
    ),
    Cenario(
        "2. Rascunho com número errado (Auditor barra)",
        "Posso ser cobrado pela média quando a distribuidora não consegue ler o medidor?",
        DATA,
        "erra_numero",
        "ren1000-art-289",
    ),
    Cenario("3. Fora do corpus", "Como declarar criptomoedas no imposto de renda?", DATA, "fiel"),
    Cenario(
        "4. Antes da vigência da norma",
        "Quantos ciclos entram na média quando o medidor não foi lido?",
        date(2021, 6, 1),
        "fiel",
    ),
)


def _primeira_frase(texto: str) -> str:
    plano = re.sub(r"^Art\. \d+[º°]?\.?\s*", "", " ".join(texto.split()))
    corte = re.split(r"(?<=[;:])\s|(?<=\.)\s(?=[A-ZÀ-Ú])", plano, maxsplit=1)[0]
    return corte[:300]


def analista_simulado(comportamento: str, fonte: str | None = None) -> Callable[[str, str], str]:
    """Copia a primeira frase de um dispositivo recebido (ou troca um número dela)."""

    def gerar(_sistema: str, prompt: str) -> str:
        achados = _TEXTO_DO_ID.findall(prompt)
        if not achados:
            return json.dumps({"afirmacoes": []})
        id_, texto = next((a for a in achados if a[0] == fonte), achados[0])
        frase = _primeira_frase(texto)
        if comportamento == "erra_numero":
            frase = (
                re.sub(r"\d+", "99", frase, count=1) if re.search(r"\d", frase) else frase + " 99"
            )
        return json.dumps({"afirmacoes": [{"texto": frase, "fontes": [id_]}]}, ensure_ascii=False)

    return gerar


def fatura_divergente() -> Fatura:
    """Fatura sintética B1: a soma das linhas (R$ 400,00) não fecha com o total (R$ 431,00)."""
    return Fatura(
        distribuidora="Neoenergia Brasília (sintética)",
        mes_referencia=date(2026, 5, 1),
        leitura_anterior=Decimal("22160"),
        leitura_atual=Decimal("22660"),
        consumo_kwh=Decimal("500"),
        bandeira="verde",
        itens=[
            ItemFatura(
                descricao="Consumo de energia",
                quantidade=Decimal("500"),
                tarifa=Decimal("0.80"),
                valor=Decimal("400.00"),
            ),
        ],  # fmt: skip
        total=Decimal("431.00"),
    )


def _rastro(passos: tuple[Passo, ...]) -> None:
    for p in passos:
        print(f"   [{p.agente:<12}] {p.acao}: {p.detalhe}")


def _cliente(modo: str, comportamento: str, fonte: str | None = None) -> ClienteLLM:
    if modo == "ollama":
        os.environ.setdefault("FA_LLM_PROVEDOR", "ollama")
        return criar_cliente("gerador")
    return ClienteFalso(resposta=analista_simulado(comportamento, fonte))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--llm", choices=["simulado", "ollama"], default="simulado")
    ap.add_argument("--persona", choices=[p.value for p in Persona], default=None,
                    help="só uma persona (padrão: alterna entre as três)")  # fmt: skip
    args = ap.parse_args(argv)
    indice = IndiceHibrido.do_corpus()
    personas = [Persona(args.persona)] if args.persona else list(Persona)
    print(f"Sistema multiagentes do Fatura Aberta (LLM: {args.llm})")
    print("Agentes: Pesquisador → Analista → Auditor → Comunicador (Orquestrador, política T5)\n")
    for n, c in enumerate(CENARIOS):
        persona = personas[n % len(personas)]
        orq = Orquestrador(
            indice, _cliente(args.llm, c.comportamento, c.fonte), motor=analisar_nivel_a
        )
        r = orq.responder_pergunta(c.pergunta, data_referencia=c.data_referencia, persona=persona)
        print(f"== {c.rotulo} (persona: {persona.value}, data {c.data_referencia:%d/%m/%Y})")
        print(f"   Pergunta: {c.pergunta}")
        _rastro(r.rastro)
        print(f"   Origem da resposta: {r.origem}")
        print("   Mensagem final:")
        for linha in r.mensagem.texto.splitlines():
            print(f"     {linha}")
        print()
    persona = personas[-1] if args.persona else Persona.MARCIA
    orq = Orquestrador(indice, _cliente(args.llm, "fiel"), motor=analisar_nivel_a)
    res = orq.analisar_fatura(fatura_divergente(), persona=persona)
    print(f"== 5. Fatura com total divergente (persona: {persona.value})")
    _rastro(res.rastro)
    print(f"   Veredito do motor: {res.veredito}; explicações: {res.origens}")
    print("   Mensagem final:")
    for linha in res.mensagem.texto.splitlines():
        print(f"     {linha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
