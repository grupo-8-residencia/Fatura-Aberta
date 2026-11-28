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

import re
import time
import unicodedata
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from fa_agentes.analista import AnalistaNormativo, consulta_do_achado
from fa_agentes.auditor import Auditor, Problema, divergente
from fa_agentes.comunicador import Comunicador, Mensagem, Persona, texto_so_referencias
from fa_agentes.linguagem import verificar_linguagem
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
    motivos_auditor: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RespostaFaturaPergunta:
    """Resposta única para uma pergunta em texto sobre uma fatura confirmada."""

    pergunta: str
    resposta: Resposta
    origem: str
    achados_motor: tuple[Achado, ...]
    achados_relevantes: tuple[Achado, ...]
    campos_usados: dict[str, str]
    motivo_abstencao: str
    mensagem: Mensagem
    rastro: tuple[Passo, ...]

    @property
    def abstencao(self) -> bool:
        return self.resposta.abstencao


MOTIVO_DADOS_INSUFICIENTES = "dados_insuficientes"

# Palavras da pergunta -> item do motor a que se referem (comparação sem acento, minúscula).
_TEMAS_ITEM: dict[str, tuple[str, ...]] = {
    "Consumo medido": ("consumo", "leitura", "leituras", "medidor", "kwh"),
    "Total da fatura": ("total", "soma", "somam", "pagar", "valor"),
    "ICMS": ("icms", "imposto", "aliquota"),
    "Parcela até 80 kWh": ("80", "parcela", "isencao", "faixa"),
    "Linha": ("linha", "linhas", "item", "itens", "duplicada", "duplicado", "cobrada"),
}
_TEMAS_CONSUMO = frozenset(_TEMAS_ITEM["Consumo medido"]) - {"kwh"}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in base if not unicodedata.combining(c)).lower()


def _palavras(texto: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _sem_acento(texto)))


def _brl(valor: object) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _campos_da_fatura(fatura: Fatura) -> dict[str, str]:
    campos = {
        "mes_referencia": f"{fatura.mes_referencia:%m/%Y}",
        "consumo_kwh": f"{fatura.consumo_kwh:f}",
        "total": f"{fatura.total:f}",
    }
    if fatura.leitura_anterior is not None:
        campos["leitura_anterior"] = f"{fatura.leitura_anterior:f}"
    if fatura.leitura_atual is not None:
        campos["leitura_atual"] = f"{fatura.leitura_atual:f}"
    if fatura.bandeira:
        campos["bandeira"] = fatura.bandeira
    if fatura.aliquota_icms is not None:
        campos["aliquota_icms"] = f"{fatura.aliquota_icms:f}"
    return campos


def _relevantes(pergunta: str, achados: Sequence[Achado]) -> list[Achado]:
    """Achados que tratam do assunto da pergunta; sem casamento, os que divergem ou se abstêm."""
    palavras = _palavras(pergunta)
    alvo = {item for item, termos in _TEMAS_ITEM.items() if palavras & set(termos)}
    achou = [a for a in achados if any(a.item.startswith(t) for t in alvo)]
    if achou:
        return achou
    pendentes = [a for a in achados if divergente(a) or a.abstencao]
    return pendentes or list(achados)


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
        extr = ev.resposta_extrativa
        # O trecho extrativo é texto literal da norma entre aspas, com a citação: exceção do RF-15.
        proibidas = sorted(
            {v.termo for v in verificar_linguagem(extr.texto, permitir_citacao_literal=True)}
        )
        if proibidas:
            # O trecho literal da norma traz termo vedado pelo RF-15 (ex.: "devolução em dobro"):
            # entrega só a referência aos dispositivos, sem transcrever o trecho.
            extr = Resposta(
                texto_so_referencias(extr.citacoes), extr.citacoes, False, extr.ids_fontes
            )
            nota = (
                f"usa a referência do Pesquisador sem transcrever (RF-15: {', '.join(proibidas)})"
            )
        else:
            nota = "usa a resposta extrativa do Pesquisador"
        rastro.passos.append(Passo("Orquestrador", "fallback", nota, 0.0))
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
        candidatos = [a for a in achados if divergente(a) or a.abstencao]
        alvo = candidatos[:max_itens]
        if len(candidatos) > max_itens:
            sem = ", ".join(a.item for a in candidatos[max_itens:])
            rastro.passos.append(
                Passo("Orquestrador", "limite", f"sem explicação (limite {max_itens}): {sem}", 0.0)
            )
        explicacoes: list[Achado] = []
        origens: dict[str, str] = {}
        motivos: dict[str, tuple[str, ...]] = {}
        for a in alvo:
            resposta, origem, _, problemas, ev = self._resolver(
                consulta_do_achado(a), fatura.mes_referencia, rastro, achado=a
            )
            origens[a.item] = origem
            motivos[a.item] = tuple(sorted({p.motivo.value for p in problemas}))
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
                        nivel=Nivel.C,  # análise normativa citada; B é a tabela da ANEEL
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
            veredito, achados, tuple(explicacoes), origens, msg, tuple(rastro.passos), motivos
        )

    def responder_sobre_fatura(
        self,
        pergunta: str,
        fatura: Fatura,
        *,
        achados_motor: Sequence[Achado] | None = None,
        persona: Persona | str = Persona.MARCIA,
    ) -> RespostaFaturaPergunta:
        """Uma só análise: campos confirmados da fatura + achados do motor + pergunta em texto.

        O motor decide os fatos; a norma citada vem do fluxo Pesquisador → Analista → Auditor; e
        se faltar dado para sustentar a resposta, o sistema se abstém dizendo o que falta.
        """
        persona = Persona(persona)
        rastro = Rastro()
        if achados_motor is None:
            if self.motor is None:
                raise ValueError("Orquestrador sem motor: informe motor= ou achados_motor=")
            with rastro.passo("Motor", "analisar_nivel_a") as d:
                achados_motor = self.motor(fatura)
                d.append(f"{len(achados_motor)} achado(s)")
        else:
            rastro.passos.append(
                Passo("Motor", "analisar_nivel_a", f"{len(achados_motor)} achado(s)", 0.0)
            )
        achados = tuple(achados_motor)
        veredito = "diverge_A" if any(divergente(a) for a in achados) else "confere"
        rastro.passos.append(Passo("Motor", "veredito", veredito, 0.0))
        campos = _campos_da_fatura(fatura)
        relevantes = _relevantes(pergunta, achados)
        rastro.passos.append(
            Passo("Orquestrador", "selecionar", ", ".join(a.item for a in relevantes), 0.0)
        )

        faltam: list[str] = []
        if _palavras(pergunta) & _TEMAS_CONSUMO:
            faltam = [
                nome
                for nome in ("leitura_anterior", "leitura_atual")
                if getattr(fatura, nome) is None
            ]
        sem_dados = bool(faltam) or all(a.abstencao for a in relevantes)
        if sem_dados:
            detalhes = [f"{a.item}: {a.descricao}" for a in relevantes if a.abstencao]
            if faltam:
                detalhes.insert(0, f"campos ausentes na fatura confirmada: {', '.join(faltam)}")
            texto = (
                "Dados insuficientes para responder com segurança. "
                + " ".join(detalhes)
                + " Confirme ou complete esses campos e envie a pergunta de novo."
            )
            rastro.passos.append(
                Passo("Orquestrador", "abstencao", MOTIVO_DADOS_INSUFICIENTES, 0.0)
            )
            resp = Resposta(texto, (), True)
            msg = Mensagem(persona, texto, (), adaptada=False, motivo=MOTIVO_DADOS_INSUFICIENTES)
            return RespostaFaturaPergunta(
                pergunta, resp, Origem.ABSTENCAO, achados, tuple(relevantes), campos,
                MOTIVO_DADOS_INSUFICIENTES, msg, tuple(rastro.passos),
            )  # fmt: skip

        principal = next((a for a in relevantes if divergente(a)), relevantes[0])
        norma, origem, _, _, ev = self._resolver(
            f"{pergunta}. {consulta_do_achado(principal)}",
            fatura.mes_referencia,
            rastro,
            achado=principal,
        )
        eco = (
            pergunta
            if not verificar_linguagem(pergunta)
            else "[omitida: contém termo fora da linguagem permitida]"
        )
        linhas = [
            f"Pergunta recebida: “{eco}”",
            "Dados da fatura confirmada: "
            f"mês {campos['mes_referencia']}, consumo {campos['consumo_kwh']} kWh, "
            f"total R$ {_brl(fatura.total)}.",
            "Conferência do motor determinístico:",
        ]
        for a in relevantes:
            extra = ""
            if a.valor_esperado is not None and a.valor_cobrado is not None:
                extra = f" (calculado: {a.valor_esperado:f}; informado: {a.valor_cobrado:f})"
            linhas.append(f"- {a.item}: {a.descricao}{extra}")
        abstem_norma = norma.abstencao
        if abstem_norma:
            linhas.append(
                "Fundamentação normativa: sem dispositivo vigente no corpus para este ponto "
                f"({ev.motivo_abstencao}); cabe pedido de esclarecimento à distribuidora."
            )
        else:
            linhas.append(f"Fundamentação normativa:\n{norma.texto}")
        texto = "\n".join(linhas)
        resp = Resposta(texto, norma.citacoes, False, norma.ids_fontes)
        with rastro.passo("Comunicador", f"compor para {persona.value}") as d:
            msg = Mensagem(persona, texto, tuple(norma.citacoes), adaptada=False, motivo="")
            d.append("resposta combinada: fatura confirmada + motor + norma")
        return RespostaFaturaPergunta(
            pergunta, resp, origem, achados, tuple(relevantes), campos,
            ev.motivo_abstencao if abstem_norma else "", msg, tuple(rastro.passos),
        )  # fmt: skip
