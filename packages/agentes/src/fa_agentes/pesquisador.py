"""Pesquisador: ferramenta de busca com citação usada pelos outros agentes (S4-03, issue #38).

É o único agente que consulta o corpus normativo. Para uma consulta e uma data de referência,
devolve os dispositivos vigentes acima do limiar de abstenção, com a citação completa de cada um
(ato, dispositivo e vigência), e a resposta extrativa (trechos literais, sem LLM), que serve de
piso para o fluxo: se o rascunho do Analista for barrado pelo Auditor, é ela que o usuário recebe.

Quando não há dispositivo, o Pesquisador diz por quê: a norma existe no corpus mas não estava
vigente na data, ou o tema não está no corpus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fa_rag import DocumentoNormativo, IndiceHibrido
from fa_rag.sintese import LIMIAR_PADRAO, Resposta, responder


class MotivoAbstencao:
    """Por que o Pesquisador não entregou dispositivos (texto curto, para o rastro)."""

    NENHUM = ""
    FORA_DE_VIGENCIA = "há dispositivo sobre o tema no corpus, mas nenhum vigente na data"
    FORA_DO_CORPUS = "nenhum dispositivo do corpus cobre a consulta acima do limiar"


@dataclass(frozen=True, slots=True)
class Evidencias:
    """O que o Pesquisador entrega: dispositivos vigentes, scores e a resposta extrativa."""

    consulta: str
    data_referencia: date
    dispositivos: tuple[DocumentoNormativo, ...]
    scores: tuple[float, ...]
    resposta_extrativa: Resposta
    motivo_abstencao: str = MotivoAbstencao.NENHUM

    @property
    def abstencao(self) -> bool:
        return not self.dispositivos


class Pesquisador:
    """Busca híbrida com filtro de vigência e subgrupo, limiar de abstenção e citação completa."""

    def __init__(
        self,
        indice: IndiceHibrido,
        *,
        limiar: float = LIMIAR_PADRAO,
        top_k: int = 5,
        subgrupos: tuple[str, ...] = ("B1",),
    ) -> None:
        self.indice = indice
        self.limiar = limiar
        self.top_k = top_k
        self.subgrupos = subgrupos

    def buscar_com_citacao(self, consulta: str, *, data_referencia: date) -> Evidencias:
        """Dispositivos vigentes na data, acima do limiar, na ordem de relevância."""
        resultados = self.indice.buscar(
            consulta,
            data_referencia=data_referencia,
            subgrupos=self.subgrupos,
            top_k=self.top_k,
        )
        uteis = [r for r in resultados if r.score >= self.limiar]
        motivo = MotivoAbstencao.NENHUM
        if not uteis:
            sem_filtro = self.indice.buscar(
                consulta,
                data_referencia=data_referencia,
                subgrupos=self.subgrupos,
                top_k=self.top_k,
                filtrar_vigencia=False,
            )
            existe = any(r.score >= self.limiar for r in sem_filtro)
            motivo = MotivoAbstencao.FORA_DE_VIGENCIA if existe else MotivoAbstencao.FORA_DO_CORPUS
        return Evidencias(
            consulta=consulta,
            data_referencia=data_referencia,
            dispositivos=tuple(r.documento for r in uteis),
            scores=tuple(round(r.score, 4) for r in uteis),
            resposta_extrativa=responder(resultados, limiar=self.limiar),
            motivo_abstencao=motivo,
        )
