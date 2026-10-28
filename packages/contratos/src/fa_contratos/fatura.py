"""Fatura de energia elétrica residencial (grupo B1) já extraída e estruturada.

PRIVACIDADE: este contrato **não** tem campos para nome, endereço nem número da instalação.
Dados pessoais são descartados na extração (F4) e nunca trafegam entre as frentes.
"""

from datetime import date
from decimal import Decimal

from pydantic import Field

from fa_contratos.base import ModeloBase


class ItemFatura(ModeloBase):
    """Uma linha cobrada na fatura."""

    descricao: str = Field(min_length=1)
    quantidade: Decimal | None = None
    unidade: str | None = None
    tarifa: Decimal | None = None
    valor: Decimal


class Fatura(ModeloBase):
    """Dados mínimos de uma fatura para a checagem de nível A."""

    distribuidora: str = Field(min_length=1)
    grupo_tarifario: str = "B1"
    mes_referencia: date = Field(description="Primeiro dia do mês de referência.")
    leitura_anterior: Decimal | None = None
    leitura_atual: Decimal | None = None
    consumo_kwh: Decimal = Field(ge=0)
    bandeira: str | None = None
    aliquota_icms: Decimal | None = Field(
        default=None, ge=0, le=1, description="Alíquota impressa na fatura, em fração (0,20 = 20%)."
    )
    itens: list[ItemFatura] = Field(default_factory=list)
    total: Decimal
