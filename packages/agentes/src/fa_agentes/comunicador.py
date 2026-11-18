"""Comunicador: adapta a resposta já auditada ao público-alvo (personas, RNF-08).

O Comunicador é o último agente do fluxo e não decide nada: ele reescreve o que o Auditor aprovou
(ou a resposta extrativa do Pesquisador, ou a abstenção) no formato que cada persona espera:

- ``celina``: resposta curta em linguagem simples e o que fazer (Dona Celina, 68 anos);
- ``rafael``: item a item, para conferir e compartilhar (Rafael, 24 anos);
- ``marcia``: citação completa com vigência e minuta neutra de pedido de esclarecimento
  (Márcia, 45 anos).

É determinístico (modelos de texto, sem LLM), para não reabrir o risco que o Auditor fechou. Antes
de entregar, ele mesmo confere duas coisas: o texto final não tem expressão proibida pelo RF-15 e
não contém número que não estivesse na entrada. Se uma das duas falhar, devolve a entrada sem
adaptação e registra o motivo.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fa_agentes.linguagem import verificar_linguagem
from fa_contratos import Achado, Citacao

ORIENTACAO = (
    "Se quiser contestar, peça esclarecimento por escrito à distribuidora (Neoenergia Brasília) "
    "e guarde o protocolo. Se não houver resposta, procure o Procon-DF ou a Defensoria Pública."
)


class Persona(StrEnum):
    CELINA = "celina"
    RAFAEL = "rafael"
    MARCIA = "marcia"


@dataclass(frozen=True, slots=True)
class Mensagem:
    """Texto final para a persona, com as citações e o resultado da autoconferência."""

    persona: Persona
    texto: str
    citacoes: tuple[Citacao, ...]
    adaptada: bool
    motivo: str = ""


def _numeros(texto: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", texto))


def formatar_citacao(c: Citacao) -> str:
    fim = f" até {c.vigencia_fim.strftime('%d/%m/%Y')}" if c.vigencia_fim else ""
    return f"{c.ato}, {c.dispositivo} (vigente desde {c.vigencia_inicio.strftime('%d/%m/%Y')}{fim})"


def _citacoes_unicas(citacoes: Sequence[Citacao]) -> tuple[Citacao, ...]:
    unicas: list[Citacao] = []
    for c in citacoes:
        if c not in unicas:
            unicas.append(c)
    return tuple(unicas)


def _fonte_curta(c: Citacao) -> str:
    return f"{c.ato}, {c.dispositivo}"


def _entrada_numeros(*textos: str, citacoes: Sequence[Citacao] = ()) -> set[str]:
    base = " ".join(textos) + " " + " ".join(formatar_citacao(c) for c in citacoes)
    return _numeros(base)


class Comunicador:
    """Adapta respostas e resultados de fatura às personas, sem acrescentar fato."""

    def _conferir(
        self,
        persona: Persona,
        texto: str,
        entrada: set[str],
        original: str,
        cit: tuple[Citacao, ...],
    ) -> Mensagem:
        proibidas = [v.termo for v in verificar_linguagem(texto)]
        novos = _numeros(texto) - entrada
        if proibidas or novos:
            motivo = (
                f"linguagem proibida: {', '.join(proibidas)}"
                if proibidas
                else f"número fora da entrada: {', '.join(sorted(novos))}"
            )
            return Mensagem(persona, original, cit, adaptada=False, motivo=motivo)
        return Mensagem(persona, texto, cit, adaptada=True)

    def comunicar_resposta(
        self,
        persona: Persona | str,
        *,
        pergunta: str,
        afirmacoes: Sequence[tuple[str, Sequence[Citacao]]],
        texto_original: str,
        abstencao: bool,
        motivo_abstencao: str = "",
        data_referencia: date | None = None,
    ) -> Mensagem:
        """Resposta a uma pergunta normativa, já auditada (ou extrativa, ou abstenção)."""
        p = Persona(persona)
        cit = _citacoes_unicas([c for _, cs in afirmacoes for c in cs])
        if abstencao:
            if p is Persona.CELINA:
                texto = (
                    "Não encontrei uma regra em vigor que responda a isso com segurança. "
                    "Para essa dúvida, procure a distribuidora ou o Procon-DF."
                )
            else:
                razao = f" ({motivo_abstencao})" if motivo_abstencao else ""
                texto = (
                    "O sistema se absteve: não há dispositivo vigente no corpus que sustente "
                    f"uma resposta{razao}. Não respondemos sem fonte."
                )
            entrada = _entrada_numeros(texto_original, motivo_abstencao, pergunta)
            return self._conferir(p, texto, entrada, texto_original, cit)

        if p is Persona.CELINA:
            principal, fontes = afirmacoes[0]
            linhas = [f"Em resumo: {principal}"]
            if fontes:
                linhas.append(f"Isso está na {_fonte_curta(fontes[0])}.")
            linhas.append("Se a sua conta não seguir essa regra, peça explicação à distribuidora.")
        elif p is Persona.RAFAEL:
            linhas = [f"Pergunta: {pergunta}", "O que a norma diz, ponto a ponto:"]
            for texto, fontes in afirmacoes:
                ref = f" [{_fonte_curta(fontes[0])}]" if fontes else ""
                linhas.append(f"- {texto}{ref}")
        else:
            linhas = [f"Pergunta: {pergunta}", "Fundamentação (texto da norma vigente):"]
            for texto, fontes in afirmacoes:
                refs = "; ".join(formatar_citacao(c) for c in fontes)
                linhas.append(f"- {texto} ({refs})")
            if data_referencia is not None:
                linhas.append(f"Data de referência considerada: {data_referencia:%d/%m/%Y}.")
            linhas.append("Isto é o texto da norma; não é parecer jurídico sobre o seu caso.")
        texto_final = "\n".join(linhas)
        entrada = _entrada_numeros(
            texto_original,
            pergunta,
            *(t for t, _ in afirmacoes),
            data_referencia.strftime("%d/%m/%Y") if data_referencia else "",
            citacoes=cit,
        )
        return self._conferir(p, texto_final, entrada, texto_original, cit)

    def comunicar_fatura(
        self,
        persona: Persona | str,
        *,
        achados_motor: Sequence[Achado],
        explicacoes: Sequence[Achado],
    ) -> Mensagem:
        """Resultado da conferência da fatura: veredito do motor + explicações normativas."""
        p = Persona(persona)
        diverg = [a for a in achados_motor if _diverge(a)]
        absten = [a for a in achados_motor if a.abstencao]
        cit = _citacoes_unicas([c for e in explicacoes for c in e.citacoes])
        explic_por_item = {e.item: e for e in explicacoes}
        if p is Persona.CELINA:
            if diverg:
                linhas = [f"Encontramos {len(diverg)} ponto(s) da conta que não conferem:"]
                for a in diverg:
                    linhas.append(
                        f"- {a.item}: deveria ser {a.valor_esperado}, mas está {a.valor_cobrado}."
                    )
                linhas.append(ORIENTACAO)
            else:
                linhas = ["Nos itens que conseguimos conferir, a sua conta está certa."]
            if absten:
                linhas.append(
                    f"Não deu para conferir {len(absten)} item(ns) com os dados da conta."
                )
        elif p is Persona.RAFAEL:
            linhas = ["Conferência item a item:"]
            for a in achados_motor:
                status = "NÃO CONFERE" if _diverge(a) else ("SEM DADOS" if a.abstencao else "OK")
                extra = (
                    f" (calculado {a.valor_esperado}; na conta {a.valor_cobrado})"
                    if a.valor_esperado is not None and a.valor_cobrado is not None
                    else ""
                )
                linhas.append(f"- [{status}] {a.item}: {a.descricao}{extra}")
        else:
            linhas = ["Resultado da conferência determinística (nível A):"]
            for a in achados_motor:
                linhas.append(f"- {a.item}: {a.descricao}")
                e = explic_por_item.get(a.item)
                if e is not None and not e.abstencao:
                    linhas.append(
                        f"  Norma aplicável: {'; '.join(formatar_citacao(c) for c in e.citacoes)}"
                    )
            if diverg:
                linhas.append("")
                linhas.append("Minuta de pedido de esclarecimento (linguagem neutra):")
                linhas.append(
                    "Solicito esclarecimento sobre os itens abaixo da minha fatura, em que o valor "
                    "informado difere do calculado a partir dos próprios dados da fatura:"
                )
                for a in diverg:
                    linhas.append(
                        f"- {a.item}: calculado {a.valor_esperado}; informado {a.valor_cobrado}."
                    )
                if cit:
                    linhas.append(
                        "Peço que a resposta indique a regra aplicada, considerando: "
                        + "; ".join(_fonte_curta(c) for c in cit)
                        + "."
                    )
        texto_final = "\n".join(linhas)
        original = "\n".join(f"{a.item}: {a.descricao}" for a in achados_motor)
        valores = " ".join(
            f"{a.valor_esperado} {a.valor_cobrado} {a.descricao}" for a in achados_motor
        )
        entrada = _entrada_numeros(
            original,
            valores,
            *(e.descricao for e in explicacoes),
            str(len(diverg)),
            str(len(absten)),
            citacoes=cit,
        )
        return self._conferir(p, texto_final, entrada, original, cit)


def _diverge(a: Achado) -> bool:
    return (
        not a.abstencao
        and a.valor_esperado is not None
        and a.valor_cobrado is not None
        and a.valor_esperado != a.valor_cobrado
    )
