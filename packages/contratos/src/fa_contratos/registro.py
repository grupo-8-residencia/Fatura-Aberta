"""Registro auditável de um achado: a regra aplicada, o cálculo e as limitações (#169).

Fonte e vigência ficam nas `citacoes` do achado; aqui, o que a conta usou e o que não cobre.
"""

from datetime import date

from pydantic import Field

from fa_contratos.base import ModeloBase


class RegistroAuditavel(ModeloBase):
    """O que permite refazer e questionar o achado."""

    regra_aplicada: str = Field(min_length=1, description="Regra interna que gerou o achado.")
    calculo: str | None = Field(default=None, description="Conta feita, com os valores usados.")
    data_consulta: date | None = Field(
        default=None, description="Data em que a fonte externa foi consultada (nível B)."
    )
    limitacoes: list[str] = Field(
        default_factory=list, description="O que o achado não cobre; vazio se nada."
    )
