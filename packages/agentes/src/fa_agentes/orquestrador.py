"""Orquestrador do sistema multiagentes (S4): Pesquisador → Analista → Auditor → Comunicador.

Duas tarefas:

- ``responder_pergunta``: pergunta regulatória com data de referência;
- ``analisar_fatura``: o motor determinístico decide o veredito de cada item; para os itens que
  divergem ou ficam sem dados, os agentes buscam e explicam a norma aplicável.

Política T5 ("LLM como redator restrito"): a decisão nunca é do LLM. O Pesquisador decide se há
evidência; o motor decide o veredito; o Analista só redige; o Auditor aprova ou barra. Se o
Auditor barrar o rascunho, o usuário recebe a resposta extrativa do Pesquisador (trechos
literais), em vez de abstenção, e o rastro registra o porquê. Assim o fluxo nunca responde menos
do que o RAG extrativo (T2), que foi o vencedor da S3.

Cada passo vira um ``Passo`` no ``rastro``: é o registro da colaboração entre os agentes, usado
na demonstração, na API e na documentação.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from fa_agentes.analista import AnalistaNormativo, consulta_do_achado
from fa_agentes.auditor import Auditor, Problema, divergente
from fa_agentes.comunicador import Comunicador, Mensagem, Persona
from fa_agentes.llm import ClienteLLM
from fa_agentes.pesquisador import Evidencias, Pesquisador
from fa_contratos import Achado, Citacao, Fatura, Nivel
from fa_rag import IndiceHibrido
from fa_rag.sintese import LIMIAR_PADRAO, Resposta

Motor = Callable[[Fatura], list[Achado]]


class Origem:
    """De onde veio a resposta entregue ao usuário."""

    ANALISTA_AUDITADO = "analista_auditado"
    PESQUISADOR_EXTRATIVO = "pesquisador_extrativo"
    ABSTENCAO = "abstencao"


@dataclass(frozen=True, slots=True)
class Passo:
    agente: str
    acao: str
    detalhe: str
    duracao_s: float


@dataclass(slots=True)
class Rastro:
    passos: list[Passo] = field(default_factory=list)

    @contextmanager
    def passo(self, agente: str, acao: str) -> Iterator[list[str]]:
        """Mede o passo; o chamador preenche o detalhe na lista recebida."""
        detalhe: list[str] = []
        inicio = time.perf_counter()
        try:
            yield detalhe
        finally:
            self.passos.append(
                Passo(agente, acao, "; ".join(detalhe), round(time.perf_counter() - inicio, 4))
            )


@dataclass(frozen=True, slots=True)
class RespostaPergunta:
    pergunta: str
    data_referencia: date
    resposta: Resposta
    origem: str
    afirmacoes: tuple[tuple[str, tuple[Citacao, ...]], ...]
    problemas: tuple[Problema, ...]
    motivo_abstencao: str
    mensagem: Mensagem
    rastro: tuple[Passo, ...]

    @property
    def abstencao(self) -> bool:
        return self.resposta.abstencao


@dataclass(frozen=True, slots=True)
class ResultadoFatura:
    veredito: str
    achados_motor: tuple[Achado, ...]
    explicacoes: tuple[Achado, ...]
    origens: dict[str, str]
    mensagem: Mensagem
    rastro: tuple[Passo, ...]


def _afirmacoes_extrativas(r: Resposta) -> tuple[tuple[str, tuple[Citacao, ...]], ...]:
    """Cada linha "- ato, dispositivo: “trecho”" da resposta extrativa vira uma afirmação."""
    saida: list[tuple[str, tuple[Citacao, ...]]] = []
    linhas = [x for x in r.texto.splitlines() if x.startswith("- ")]
    for linha, c in zip(linhas, r.citacoes, strict=False):
        trecho = linha.split(": ", 1)[1] if ": " in linha else linha[2:]
        saida.append((trecho.strip(), (c,)))
    return tuple(saida)


class Orquestrador:
    """Coordena os quatro agentes; o motor determinístico entra como dependência injetada."""

    def __init__(
        self,
        indice: IndiceHibrido,
        gerador: ClienteLLM,
        *,
        juiz: ClienteLLM | None = None,
        motor: Motor | None = None,
        limiar: float = LIMIAR_PADRAO,
        top_k: int = 5,
    ) -> None:
        self.pesquisador = Pesquisador(indice, limiar=limiar, top_k=top_k)
        self.analista = AnalistaNormativo(indice, gerador, limiar=limiar, top_k=top_k)
        self.auditor = Auditor(juiz)
        self.comunicador = Comunicador()
        self.motor = motor

    # ------------------------------------------------------------------ núcleo

    def _resolver(
        self,
        consulta: str,
        data_referencia: date,
        rastro: Rastro,
        achado: Achado | None = None,
    ) -> tuple[
        Resposta, str, tuple[tuple[str, tuple[Citacao, ...]], ...], tuple[Problema, ...], Evidencias
    ]:
        with rastro.passo("Pesquisador", "buscar_com_citacao") as d:
            ev = self.pesquisador.buscar_com_citacao(consulta, data_referencia=data_referencia)
            d.append(f"{len(ev.dispositivos)} dispositivo(s) vigente(s)")
            if ev.dispositivos:
                d.append(
                    ", ".join(
                        f"{x.id} ({s})" for x, s in zip(ev.dispositivos, ev.scores, strict=True)
                    )
                )
            else:
                d.append(f"abstenção: {ev.motivo_abstencao}")
        if ev.abstencao:
            return ev.resposta_extrativa, Origem.ABSTENCAO, (), (), ev
        with rastro.passo("Analista", "redigir") as d:
            relatorio = self.analista.redigir(ev, achado=achado)
            d.append(f"{len(relatorio.afirmacoes)} afirmação(ões) proposta(s)")
        with rastro.passo("Auditor", "auditar") as d:
            auditoria = self.auditor.auditar(relatorio, achado=achado)
            if auditoria.abstencao:
                motivos = sorted({p.motivo.value for p in auditoria.problemas}) or ["sem afirmação"]
                d.append(f"barrou o rascunho: {', '.join(motivos)}")
            else:
                d.append(f"aprovou {len(auditoria.afirmacoes_aprovadas)} afirmação(ões)")
        if not auditoria.abstencao:
            afirm = tuple((a.texto, a.citacoes) for a in auditoria.afirmacoes_aprovadas)
            return auditoria.resposta, Origem.ANALISTA_AUDITADO, afirm, auditoria.problemas, ev
        rastro.passos.append(
            Passo("Orquestrador", "fallback", "usa a resposta extrativa do Pesquisador", 0.0)
        )
        extr = ev.resposta_extrativa
        return (
            extr,
            Origem.PESQUISADOR_EXTRATIVO,
            _afirmacoes_extrativas(extr),
            auditoria.problemas,
            ev,
        )

    # ------------------------------------------------------------------ tarefas

    def responder_pergunta(
        self, pergunta: str, *, data_referencia: date, persona: Persona | str = Persona.MARCIA
    ) -> RespostaPergunta:
        rastro = Rastro()
        resposta, origem, afirm, problemas, ev = self._resolver(pergunta, data_referencia, rastro)
        with rastro.passo("Comunicador", f"adaptar para {Persona(persona).value}") as d:
            msg = self.comunicador.comunicar_resposta(
                persona,
                pergunta=pergunta,
                afirmacoes=afirm,
                texto_original=resposta.texto,
                abstencao=resposta.abstencao,
                motivo_abstencao=ev.motivo_abstencao,
                data_referencia=data_referencia,
            )
            d.append("adaptada" if msg.adaptada else f"sem adaptação ({msg.motivo})")
        return RespostaPergunta(
            pergunta, data_referencia, resposta, origem, afirm, problemas,
            ev.motivo_abstencao, msg, tuple(rastro.passos),
        )  # fmt: skip

    def analisar_fatura(
        self,
        fatura: Fatura,
        *,
        persona: Persona | str = Persona.MARCIA,
        max_itens: int = 3,
        achados_motor: Sequence[Achado] | None = None,
    ) -> ResultadoFatura:
        """Motor decide; agentes explicam até ``max_itens`` itens divergentes ou sem dados."""
        rastro = Rastro()
        if achados_motor is None:
            if self.motor is None:
                raise ValueError("Orquestrador sem motor: informe motor= ou achados_motor=")
            with rastro.passo("Motor", "analisar_nivel_a") as d:
                achados_motor = self.motor(fatura)
                d.append(f"{len(achados_motor)} achado(s)")
        achados = tuple(achados_motor)
        veredito = "diverge_A" if any(divergente(a) for a in achados) else "confere"
        rastro.passos.append(Passo("Motor", "veredito", veredito, 0.0))
        alvo = [a for a in achados if divergente(a) or a.abstencao][:max_itens]
        explicacoes: list[Achado] = []
        origens: dict[str, str] = {}
        for a in alvo:
            resposta, origem, _, _, ev = self._resolver(
                consulta_do_achado(a), fatura.mes_referencia, rastro, achado=a
            )
            origens[a.item] = origem
            if resposta.abstencao:
                explicacoes.append(
                    Achado(
                        item=a.item,
                        nivel=Nivel.C,
                        descricao=(
                            "Sem dispositivo vigente no corpus que trate deste item "
                            f"({ev.motivo_abstencao}); cabe pedido de esclarecimento."
                        ),
                        abstencao=True,
                    )
                )
            else:
                explicacoes.append(
                    Achado(
                        item=a.item,
                        nivel=Nivel.B,
                        descricao=resposta.texto,
                        citacoes=list(resposta.citacoes),
                    )
                )
        with rastro.passo("Comunicador", f"adaptar para {Persona(persona).value}") as d:
            msg = self.comunicador.comunicar_fatura(
                persona, achados_motor=achados, explicacoes=explicacoes
            )
            d.append("adaptada" if msg.adaptada else f"sem adaptação ({msg.motivo})")
        return ResultadoFatura(
            veredito, achados, tuple(explicacoes), origens, msg, tuple(rastro.passos)
        )
