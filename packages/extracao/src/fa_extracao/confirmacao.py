"""Confirmação dos campos pelo usuário.

Só `confirmar` transforma a candidata (texto lido da foto) em `Fatura`, e só quando o usuário
confirmou. `analisar_foto` junta o fluxo inteiro e chama a análise *depois* da confirmação:
sem confirmação, a análise nunca roda.
"""

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pydantic import ValidationError

from fa_contratos import Fatura, ItemFatura
from fa_extracao.candidata import CAMPOS, ExtratorDeFoto, FaturaCandidata, ItemCandidato
from fa_extracao.candidata import extrair_candidata as _extrair
from fa_extracao.erros import ErroExtracao

log = logging.getLogger(__name__)

# Sem estes campos não há o que conferir; o usuário precisa preenchê-los ou corrigi-los.
OBRIGATORIOS = ("distribuidora", "mes_referencia", "consumo_kwh", "total")

_NUMERO = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")
_MES_ANO = re.compile(r"^(\d{1,2})/(\d{4})$")


class ConfirmacaoPendente(ErroExtracao):
    """A análise não pode começar: falta a confirmação do usuário ou algum campo."""


@dataclass(frozen=True)
class Confirmacao:
    """Resposta do usuário diante dos campos lidos da foto."""

    confirmado: bool
    correcoes: Mapping[str, str] = field(default_factory=dict)
    itens: tuple[ItemCandidato, ...] | None = None


def campos_pendentes(candidata: FaturaCandidata) -> list[str]:
    """Campos obrigatórios que a leitura não trouxe e que o usuário precisa informar."""
    return [nome for nome in OBRIGATORIOS if not getattr(candidata, nome)]


def _numero(nome: str, texto: str) -> Decimal:
    """Número no formato brasileiro (`1.234,56`, `150`, `0,88-`). Ponto só como milhar."""
    limpo = re.sub(r"\s|R\$|%", "", texto)
    if limpo.endswith("-"):
        limpo = "-" + limpo[:-1]
    if not _NUMERO.match(limpo):
        # Não repete o valor: ele pode ter vindo de uma fatura.
        raise ErroExtracao(f"Número inválido no campo {nome}.")
    return Decimal(limpo.replace(".", "").replace(",", "."))


def _opcional(nome: str, texto: str | None) -> Decimal | None:
    return None if texto is None else _numero(nome, texto)


def _mes_referencia(texto: str) -> date:
    achado = _MES_ANO.match(texto.strip())
    if achado is None:
        raise ErroExtracao("Mês de referência fora do formato MM/AAAA.")
    try:
        return date(int(achado.group(2)), int(achado.group(1)), 1)
    except ValueError as erro:
        raise ErroExtracao("Mês de referência inválido.") from erro


def _item(item: ItemCandidato) -> ItemFatura:
    if not item.descricao or item.valor is None:
        raise ErroExtracao("Item da fatura incompleto: descrição e valor são obrigatórios.")
    return ItemFatura(
        descricao=item.descricao,
        quantidade=_opcional("quantidade", item.quantidade),
        unidade=item.unidade,
        tarifa=_opcional("tarifa", item.tarifa),
        valor=_numero("valor", item.valor),
    )


def confirmar(candidata: FaturaCandidata, confirmacao: Confirmacao) -> Fatura:
    """Aplica as correções do usuário e valida pelo contrato `Fatura`.

    Levanta `ConfirmacaoPendente` se o usuário não confirmou ou se faltar campo obrigatório.
    """
    if not confirmacao.confirmado:
        raise ConfirmacaoPendente("A análise só começa depois da confirmação do usuário.")
    desconhecidos = set(confirmacao.correcoes) - set(CAMPOS)
    if desconhecidos:
        raise ErroExtracao("Correção para campo desconhecido.")

    atualizacao: dict[str, object] = dict(confirmacao.correcoes)
    if confirmacao.itens is not None:
        atualizacao["itens"] = list(confirmacao.itens)
    final = candidata.model_copy(update=atualizacao)

    faltam = campos_pendentes(final)
    if faltam:
        raise ConfirmacaoPendente(f"Faltam campos para confirmar: {', '.join(faltam)}.")
    if "neoenergia" not in (final.distribuidora or "").lower():
        raise ErroExtracao("Distribuidora fora do escopo (Neoenergia Brasília).")
    if final.grupo_tarifario and final.grupo_tarifario.strip().upper() != "B1":
        raise ErroExtracao("Grupo tarifário fora do escopo (B1).")

    aliquota = _opcional("aliquota_icms", final.aliquota_icms)
    try:
        fatura = Fatura(
            distribuidora="Neoenergia Brasília",
            mes_referencia=_mes_referencia(final.mes_referencia or ""),
            leitura_anterior=_opcional("leitura_anterior", final.leitura_anterior),
            leitura_atual=_opcional("leitura_atual", final.leitura_atual),
            consumo_kwh=_numero("consumo_kwh", final.consumo_kwh or ""),
            bandeira=final.bandeira,
            aliquota_icms=None if aliquota is None else aliquota / 100,
            itens=[_item(i) for i in final.itens],
            total=_numero("total", final.total or ""),
        )
    except ValidationError as erro:
        # Não propaga `erro`: a mensagem do Pydantic repete o valor recebido.
        campos = sorted({str(e["loc"][0]) for e in erro.errors() if e["loc"]})
        raise ErroExtracao(f"Campos inválidos para o contrato: {', '.join(campos)}.") from None

    log.info("Fatura confirmada pelo usuário: itens=%d", len(fatura.itens))
    return fatura


def analisar_foto[T](
    imagem: bytes,
    *,
    extrator: ExtratorDeFoto,
    confirmador: Callable[[FaturaCandidata], Confirmacao],
    analisador: Callable[[Fatura], T],
) -> T:
    """Foto → candidata → confirmação do usuário → análise. A análise só roda depois."""
    candidata = _extrair(imagem, extrator)
    fatura = confirmar(candidata, confirmador(candidata))
    return analisador(fatura)
