"""Síntese extrativa fundamentada: só diz o que está nos dispositivos recuperados."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fa_contratos import Citacao
from fa_rag.models import ResultadoBusca

TEXTO_ABSTENCAO = (
    "Não encontrei no corpus normativo um dispositivo vigente que cubra esta pergunta. "
    "O sistema não responde sem fonte; consulte a distribuidora ou a ANEEL."
)
# Limiar padrão mantido em 0.30 conforme recomendação de auditoria metodológica:
# a calibração estratificada (S3-07) apontou 0,25 no treino (calibração), mas no teste
# cego (n=60) e no out-of-sample o 0,30 obteve melhor equilíbrio e maior revocação de
# abstenção (F1 0,800 vs 0,714). O 0,25 não se validou fora da calibração.
LIMIAR_PADRAO = 0.30


@dataclass(frozen=True, slots=True)
class Resposta:
    texto: str
    citacoes: tuple[Citacao, ...]
    abstencao: bool
    ids_fontes: tuple[str, ...] = ()


def _trecho(texto: str, limite: int = 420) -> str:
    plano = " ".join(texto.split())
    return plano if len(plano) <= limite else plano[: limite - 1].rstrip() + "…"


def responder(
    resultados: Sequence[ResultadoBusca], *, limiar: float = LIMIAR_PADRAO, max_fontes: int = 3
) -> Resposta:
    """Monta a resposta com trechos literais acima do limiar; abaixo dele, abstém-se."""
    uteis = [r for r in resultados if r.score >= limiar][:max_fontes]
    if not uteis:
        return Resposta(TEXTO_ABSTENCAO, (), True)
    linhas = ["Dispositivos vigentes recuperados (trechos literais, sem interpretação):"]
    for r in uteis:
        c = r.documento.citacao
        linhas.append(f"- {c.ato}, {c.dispositivo}: “{_trecho(r.documento.texto)}”")
    linhas.append("Isto é o texto da norma; a aplicação ao seu caso depende dos dados da fatura.")
    return Resposta(
        "\n".join(linhas),
        tuple(r.documento.citacao for r in uteis),
        False,
        tuple(r.documento.id for r in uteis),
    )
