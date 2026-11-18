"""Analista Normativo (B4/B5/T5): redige afirmações citadas sobre dispositivos vigentes.

O Analista só enxerga o que o Pesquisador (``IndiceHibrido``) devolve para a data de
referência (filtro de vigência) e acima do limiar de abstenção. O LLM redige as afirmações e
aponta os ``id`` dos dispositivos que as sustentam; a ``Citacao`` de cada afirmação é sempre
copiada do dispositivo recuperado, nunca escrita pelo modelo. Quem confere o lastro é o
Auditor (``auditor.py``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from fa_agentes.llm import ClienteLLM
from fa_agentes.pesquisador import Evidencias, Pesquisador
from fa_contratos import Achado, Citacao
from fa_rag import DocumentoNormativo, IndiceHibrido
from fa_rag.sintese import LIMIAR_PADRAO

SISTEMA_ANALISTA = (
    "Você é o Analista Normativo de um verificador aberto de faturas de energia (grupo B1). "
    "Responda SOMENTE com base nos dispositivos fornecidos; não use conhecimento externo. "
    "Cada afirmação deve ser curta, fiel ao texto do dispositivo e apontar em `fontes` os `id` "
    "dos dispositivos que a sustentam. Use linguagem de evidência: nunca qualifique uma cobrança "
    "como ilegal, não estime restituição e não oriente ação judicial. Se os dispositivos não "
    'cobrirem a pergunta, devolva {"afirmacoes": []}. Responda apenas em JSON.'
)

REGRA_MOTOR = (
    "O resultado do motor determinístico abaixo é definitivo: não refaça a conta, não mude o "
    "veredito e não escreva números que não estejam nele ou nos dispositivos. Explique qual "
    "regra dos dispositivos se aplica ao item."
)

ESQUEMA_ANALISTA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "afirmacoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string"},
                    "fontes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["texto", "fontes"],
            },
        }
    },
    "required": ["afirmacoes"],
}


@dataclass(frozen=True, slots=True)
class Afirmacao:
    """Uma afirmação do Analista, com as fontes que ele apontou e as citações resolvidas.

    ``ids_fontes`` é o que o modelo declarou; ``citacoes`` só contém as que existem entre os
    dispositivos recuperados. Se os dois não batem, o Auditor trata como citação inventada.
    """

    texto: str
    ids_fontes: tuple[str, ...]
    citacoes: tuple[Citacao, ...]


@dataclass(frozen=True, slots=True)
class RelatorioAnalise:
    """Saída do Analista: a consulta, os dispositivos recuperados e as afirmações propostas."""

    consulta: str
    data_referencia: date
    dispositivos: tuple[DocumentoNormativo, ...]
    afirmacoes: tuple[Afirmacao, ...]
    resposta_bruta: str = ""


def consulta_do_achado(achado: Achado) -> str:
    """Texto de busca para um achado do motor: o item e a sua descrição."""
    return f"{achado.item}. {achado.descricao}"


def _prompt(consulta: str, dispositivos: tuple[DocumentoNormativo, ...], data: date) -> str:
    blocos = []
    for d in dispositivos:
        c = d.citacao
        blocos.append(
            f"[id: {d.id}] {c.ato}, {c.dispositivo} "
            f"(vigente desde {c.vigencia_inicio.isoformat()})\n{' '.join(d.texto.split())}"
        )
    return (
        f"Data de referência: {data.isoformat()}\n"
        f"Pergunta ou achado: {consulta}\n\n"
        "Dispositivos vigentes recuperados:\n" + "\n\n".join(blocos)
    )


def _bloco_motor(achado: Achado) -> str:
    linhas = [REGRA_MOTOR, f"Item: {achado.item}", f"Resultado do motor: {achado.descricao}"]
    if achado.valor_esperado is not None:
        linhas.append(f"Valor calculado pelo motor: {achado.valor_esperado}")
    if achado.valor_cobrado is not None:
        linhas.append(f"Valor informado na fatura: {achado.valor_cobrado}")
    return "\n".join(linhas)


def _ler_afirmacoes(bruto: str, por_id: dict[str, DocumentoNormativo]) -> tuple[Afirmacao, ...]:
    try:
        dados = json.loads(bruto)
        itens = dados["afirmacoes"]
        if not isinstance(itens, list):
            return ()
    except (ValueError, KeyError, TypeError):
        return ()
    afirmacoes: list[Afirmacao] = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        texto = str(item.get("texto", "")).strip()
        fontes = item.get("fontes", [])
        if not texto:
            continue
        ids = tuple(str(f) for f in fontes) if isinstance(fontes, list) else ()
        citacoes = tuple(por_id[i].citacao for i in ids if i in por_id)
        afirmacoes.append(Afirmacao(texto, ids, citacoes))
    return tuple(afirmacoes)


class AnalistaNormativo:
    """Redator restrito: recebe as evidências do Pesquisador e pede ao LLM afirmações com fonte.

    ``analisar`` mantém o comportamento do B4/B5 (busca e redige numa chamada); ``redigir`` é o
    passo usado pelo Orquestrador, que entrega evidências já recuperadas e, no fluxo de fatura,
    o achado do motor que o Analista só pode explicar.
    """

    def __init__(
        self,
        indice: IndiceHibrido,
        cliente: ClienteLLM,
        *,
        limiar: float = LIMIAR_PADRAO,
        top_k: int = 5,
        subgrupos: tuple[str, ...] = ("B1",),
    ) -> None:
        self.indice = indice
        self.cliente = cliente
        self.limiar = limiar
        self.top_k = top_k
        self.subgrupos = subgrupos
        self.pesquisador = Pesquisador(indice, limiar=limiar, top_k=top_k, subgrupos=subgrupos)

    def analisar(
        self,
        pergunta: str | None = None,
        *,
        data_referencia: date,
        achado: Achado | None = None,
    ) -> RelatorioAnalise:
        """Analisa uma pergunta ou um achado do motor, para a data de referência da fatura."""
        if pergunta is None and achado is None:
            raise ValueError("informe uma pergunta ou um achado")
        consulta = pergunta if pergunta is not None else consulta_do_achado(achado)  # type: ignore[arg-type]
        evidencias = self.pesquisador.buscar_com_citacao(consulta, data_referencia=data_referencia)
        return self.redigir(evidencias)

    def redigir(self, evidencias: Evidencias, *, achado: Achado | None = None) -> RelatorioAnalise:
        """Redige afirmações citadas sobre as evidências; sem dispositivo, nem chama o LLM."""
        consulta, data, dispositivos = (
            evidencias.consulta,
            evidencias.data_referencia,
            evidencias.dispositivos,
        )
        if not dispositivos:
            # Sem dispositivo vigente acima do limiar não há o que redigir: nem chama o LLM.
            return RelatorioAnalise(consulta, data, (), ())
        prompt = _prompt(consulta, dispositivos, data)
        if achado is not None:
            prompt = f"{_bloco_motor(achado)}\n\n{prompt}"
        resposta = self.cliente.gerar(
            sistema=SISTEMA_ANALISTA, prompt=prompt, esquema=ESQUEMA_ANALISTA
        )
        por_id = {d.id: d for d in dispositivos}
        return RelatorioAnalise(
            consulta, data, dispositivos, _ler_afirmacoes(resposta.texto, por_id), resposta.texto
        )
