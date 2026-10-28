"""Achado: resultado da checagem de um item, com nível de evidência."""

from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from fa_contratos.base import ModeloBase
from fa_contratos.citacao import Citacao


class Nivel(StrEnum):
    """Nível de evidência (regra central do produto).

    - A: checagem determinística com dados da própria fatura; único nível emitido automaticamente.
    - B: divergência contra a tabela oficial ANEEL versionada (fonte e data sempre informadas).
    - C: indício não confirmável; vira pedido de esclarecimento à distribuidora.
    """

    A = "A"
    B = "B"
    C = "C"


class Achado(ModeloBase):
    """Conclusão sobre um item da fatura. Linguagem de evidência, nunca "ilegal"."""

    item: str = Field(min_length=1)
    nivel: Nivel
    descricao: str = Field(min_length=1)
    valor_esperado: Decimal | None = None
    valor_cobrado: Decimal | None = None
    citacoes: list[Citacao] = Field(default_factory=list)
    abstencao: bool = Field(
        default=False, description="Verdadeiro quando o sistema se abstém de concluir."
    )
