"""Fatura candidata: o que o modelo de visão leu da foto, ainda não confirmado pelo usuário.

O texto lido de imagem é dado não confiável. Por isso a candidata:

- guarda só os campos da lista abaixo; qualquer outro campo que o modelo devolva (por exemplo,
  `nome` ou `endereco`) é descartado antes de existir em memória como modelo;
- guarda tudo como texto, sem converter: a conversão em `Fatura` só acontece depois da
  confirmação do usuário (ver `fa_extracao.confirmacao`);
- passa cada texto pela anonimização e pela higienização de instruções de controle.

O extrator (modelo de visão local) é plugável. A foto nunca é gravada em disco.
"""

import logging
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import Field

from fa_contratos.base import ModeloBase
from fa_extracao.anonimizacao import anonimizar
from fa_extracao.erros import ErroExtracao
from fa_extracao.higienizacao import higienizar_texto_extraido

log = logging.getLogger(__name__)

CAMPOS = (
    "distribuidora",
    "grupo_tarifario",
    "mes_referencia",
    "leitura_anterior",
    "leitura_atual",
    "consumo_kwh",
    "bandeira",
    "aliquota_icms",
    "total",
)
CAMPOS_ITEM = ("descricao", "quantidade", "unidade", "tarifa", "valor")


class ItemCandidato(ModeloBase):
    """Uma linha lida da fatura, em texto."""

    descricao: str | None = None
    quantidade: str | None = None
    unidade: str | None = None
    tarifa: str | None = None
    valor: str | None = None


class FaturaCandidata(ModeloBase):
    """Campos lidos da foto, em texto e ainda sem validação do contrato `Fatura`."""

    distribuidora: str | None = None
    grupo_tarifario: str | None = None
    mes_referencia: str | None = None
    leitura_anterior: str | None = None
    leitura_atual: str | None = None
    consumo_kwh: str | None = None
    bandeira: str | None = None
    aliquota_icms: str | None = None
    total: str | None = None
    itens: list[ItemCandidato] = Field(default_factory=list)


class ExtratorDeFoto(Protocol):
    """Modelo de visão local. Devolve o JSON lido da foto, sem nenhuma garantia de formato."""

    def extrair(self, imagem: bytes) -> Mapping[str, Any]: ...


def _texto(valor: object) -> str | None:
    if valor is None or isinstance(valor, Mapping | list | tuple | set):
        return None
    limpo = higienizar_texto_extraido(anonimizar(str(valor))).strip()
    return limpo or None


def extrair_candidata(imagem: bytes, extrator: ExtratorDeFoto) -> FaturaCandidata:
    """Lê a foto com o extrator e devolve a candidata, que ainda precisa de confirmação."""
    try:
        bruto = extrator.extrair(imagem)
    except Exception:
        # Não propaga a exceção: a mensagem do modelo pode repetir trechos da fatura.
        raise ErroExtracao("O modelo de visão não conseguiu ler a foto.") from None
    if not isinstance(bruto, Mapping):
        raise ErroExtracao("O modelo de visão devolveu um formato inesperado.")

    campos = {nome: _texto(bruto.get(nome)) for nome in CAMPOS}
    itens_brutos = bruto.get("itens")
    itens = [
        ItemCandidato(**{nome: _texto(item.get(nome)) for nome in CAMPOS_ITEM})
        for item in (itens_brutos if isinstance(itens_brutos, list) else [])
        if isinstance(item, Mapping)
    ]
    candidata = FaturaCandidata(**campos, itens=itens)
    log.info(
        "Candidata extraída: campos_lidos=%d itens=%d",
        sum(valor is not None for valor in campos.values()),
        len(itens),
    )
    return candidata
