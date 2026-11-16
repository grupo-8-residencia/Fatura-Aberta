"""Analista Normativo (B4/B5): recupera dispositivos vigentes e redige afirmações citadas.

O Analista só enxerga o que o ``IndiceHibrido`` devolve para a data de referência (filtro de
vigência) e acima do limiar de abstenção. O LLM redige as afirmações e aponta os ``id`` dos
dispositivos que as sustentam; a ``Citacao`` de cada afirmação é sempre copiada do dispositivo
recuperado, nunca escrita pelo modelo. Quem confere o lastro é o Auditor (``auditor.py``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from fa_agentes.llm import ClienteLLM
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
    """Recupera dispositivos vigentes e pede ao LLM afirmações com fonte."""

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
        resultados = self.indice.buscar(
            consulta,
            data_referencia=data_referencia,
            subgrupos=self.subgrupos,
            top_k=self.top_k,
        )
        dispositivos = tuple(r.documento for r in resultados if r.score >= self.limiar)
        if not dispositivos:
            # Sem dispositivo vigente acima do limiar não há o que redigir: nem chama o LLM.
            return RelatorioAnalise(consulta, data_referencia, (), ())
        resposta = self.cliente.gerar(
            sistema=SISTEMA_ANALISTA,
            prompt=_prompt(consulta, dispositivos, data_referencia),
            esquema=ESQUEMA_ANALISTA,
        )
        por_id = {d.id: d for d in dispositivos}
        return RelatorioAnalise(
            consulta,
            data_referencia,
            dispositivos,
            _ler_afirmacoes(resposta.texto, por_id),
            resposta.texto,
        )
