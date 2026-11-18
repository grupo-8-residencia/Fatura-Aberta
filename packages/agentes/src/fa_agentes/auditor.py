"""Auditor (B5): confere cada afirmação do Analista e força a abstenção quando falta suporte.

Regras (todas determinísticas; o juiz LLM é opcional e só pode rejeitar, nunca aprovar sozinho):

1. a afirmação tem citação, e todo ``id`` citado é um dispositivo realmente recuperado;
2. a citação copiada é a do dispositivo e o dispositivo estava vigente na data de referência;
3. o texto tem lastro nos dispositivos citados (palavras de conteúdo e números);
4. nenhuma expressão proibida pelo RF-15.

Política estrita: se qualquer afirmação reprovar, a resposta final vira abstenção.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from fa_agentes.analista import Afirmacao, RelatorioAnalise
from fa_agentes.linguagem import verificar_linguagem
from fa_agentes.llm import ClienteLLM
from fa_contratos import Achado, Citacao, Nivel
from fa_rag import DocumentoNormativo
from fa_rag.sintese import TEXTO_ABSTENCAO, Resposta
from fa_rag.texto import tokenizar

COBERTURA_MINIMA = 0.6

SISTEMA_JUIZ = (
    "Você audita afirmações sobre normas de energia. Dada uma afirmação e os dispositivos "
    "citados, responda se o texto dos dispositivos sustenta a afirmação sem acrescentar nada. "
    'Responda apenas em JSON: {"suportada": true|false}.'
)
ESQUEMA_JUIZ: dict[str, Any] = {
    "type": "object",
    "properties": {"suportada": {"type": "boolean"}},
    "required": ["suportada"],
}


class Motivo(StrEnum):
    SEM_CITACAO = "sem_citacao"
    CITACAO_INVENTADA = "citacao_inventada"
    CITACAO_DIVERGENTE = "citacao_divergente"
    FORA_DE_VIGENCIA = "fora_de_vigencia"
    SEM_SUPORTE = "sem_suporte"
    LINGUAGEM_PROIBIDA = "linguagem_proibida"
    JUIZ_REJEITOU = "juiz_rejeitou"


@dataclass(frozen=True, slots=True)
class Problema:
    afirmacao: str
    motivo: Motivo
    detalhe: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoAuditoria:
    """Resposta final (``fa_rag.sintese.Resposta``) mais o porquê de cada reprovação."""

    resposta: Resposta
    problemas: tuple[Problema, ...]
    afirmacoes_aprovadas: tuple[Afirmacao, ...]

    @property
    def abstencao(self) -> bool:
        return self.resposta.abstencao


def _numeros(texto: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", texto))


def _cobertura(afirmacao: str, fontes: str) -> float:
    """Fração das palavras de conteúdo da afirmação que aparece nos dispositivos citados."""
    alvo = set(tokenizar(afirmacao))
    if not alvo:
        return 0.0
    return len(alvo & set(tokenizar(fontes))) / len(alvo)


def _formatar_citacao(c: Citacao) -> str:
    fim = f" a {c.vigencia_fim.isoformat()}" if c.vigencia_fim else ""
    return f"{c.ato}, {c.dispositivo} (vigência: {c.vigencia_inicio.isoformat()}{fim})"


class Auditor:
    """Confere as afirmações do Analista contra os dispositivos recuperados."""

    def __init__(
        self,
        juiz: ClienteLLM | None = None,
        *,
        cobertura_minima: float = COBERTURA_MINIMA,
    ) -> None:
        self.juiz = juiz
        self.cobertura_minima = cobertura_minima

    def _conferir(
        self,
        a: Afirmacao,
        contexto: dict[str, DocumentoNormativo],
        data: date,
    ) -> list[Problema]:
        if not a.ids_fontes:
            return [Problema(a.texto, Motivo.SEM_CITACAO)]
        problemas: list[Problema] = []
        desconhecidas = [i for i in a.ids_fontes if i not in contexto]
        if desconhecidas:
            problemas.append(
                Problema(a.texto, Motivo.CITACAO_INVENTADA, ", ".join(sorted(desconhecidas)))
            )
        docs = [contexto[i] for i in a.ids_fontes if i in contexto]
        for d in docs:
            if not d.citacao.vigente_em(data):
                problemas.append(
                    Problema(a.texto, Motivo.FORA_DE_VIGENCIA, _formatar_citacao(d.citacao))
                )
            if d.citacao not in a.citacoes:
                problemas.append(Problema(a.texto, Motivo.CITACAO_DIVERGENTE, d.id))
        for v in verificar_linguagem(a.texto):
            problemas.append(Problema(a.texto, Motivo.LINGUAGEM_PROIBIDA, v.termo))
        if docs:
            fontes = " ".join(f"{d.titulo} {d.texto}" for d in docs)
            if _numeros(a.texto) - _numeros(fontes) or (
                _cobertura(a.texto, fontes) < self.cobertura_minima
            ):
                problemas.append(Problema(a.texto, Motivo.SEM_SUPORTE))
            elif not problemas and self.juiz is not None and not self._juiz_aprova(a, docs):
                problemas.append(Problema(a.texto, Motivo.JUIZ_REJEITOU))
        return problemas

    def _juiz_aprova(self, a: Afirmacao, docs: list[DocumentoNormativo]) -> bool:
        assert self.juiz is not None
        citados = "\n\n".join(f"[{d.id}] {' '.join(d.texto.split())}" for d in docs)
        resposta = self.juiz.gerar(
            sistema=SISTEMA_JUIZ,
            prompt=f"Afirmação: {a.texto}\n\nDispositivos citados:\n{citados}",
            esquema=ESQUEMA_JUIZ,
        )
        try:
            return bool(json.loads(resposta.texto)["suportada"] is True)
        except (ValueError, KeyError, TypeError):
            return False  # juiz ilegível não aprova

    def auditar(self, relatorio: RelatorioAnalise) -> ResultadoAuditoria:
        """Aprova só o que tem suporte; qualquer reprovação ou ausência de afirmação abstém."""
        contexto = {d.id: d for d in relatorio.dispositivos}
        problemas: list[Problema] = []
        aprovadas: list[Afirmacao] = []
        for a in relatorio.afirmacoes:
            achados = self._conferir(a, contexto, relatorio.data_referencia)
            if achados:
                problemas.extend(achados)
            else:
                aprovadas.append(a)
        if problemas or not aprovadas:
            return ResultadoAuditoria(Resposta(TEXTO_ABSTENCAO, (), True), tuple(problemas), ())
        citacoes: list[Citacao] = []
        ids: list[str] = []
        linhas = ["Afirmações conferidas com os dispositivos vigentes na data de referência:"]
        for a in aprovadas:
            refs = "; ".join(_formatar_citacao(c) for c in a.citacoes)
            linhas.append(f"- {a.texto} ({refs})")
            for c in a.citacoes:
                if c not in citacoes:
                    citacoes.append(c)
            ids.extend(i for i in a.ids_fontes if i not in ids)
        linhas.append(
            "Isto é o texto da norma; a aplicação ao seu caso depende dos dados da fatura."
        )
        resposta = Resposta("\n".join(linhas), tuple(citacoes), False, tuple(ids))
        return ResultadoAuditoria(resposta, (), tuple(aprovadas))


def para_achado(item: str, resultado: ResultadoAuditoria) -> Achado:
    """Converte a resposta auditada em ``Achado``: abstenção vira nível C; senão, nível B."""
    r = resultado.resposta
    if r.abstencao:
        return Achado(item=item, nivel=Nivel.C, descricao=r.texto, abstencao=True)
    return Achado(item=item, nivel=Nivel.B, descricao=r.texto, citacoes=list(r.citacoes))
