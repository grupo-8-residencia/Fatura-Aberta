"""Achado: resultado da checagem de um item, com nível de evidência."""

from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from fa_contratos.base import ModeloBase
from fa_contratos.citacao import Citacao
from fa_contratos.registro import RegistroAuditavel


class Nivel(StrEnum):
    """Nível de evidência (regra central do produto).

    - A: checagem determinística com dados da própria fatura; único nível emitido automaticamente.
    - B: divergência contra a tabela oficial ANEEL versionada (fonte e data sempre informadas).
    - C: indício não confirmável; vira pedido de esclarecimento à distribuidora.
    """

    A = "A"
    B = "B"
    C = "C"


class Categoria(StrEnum):
    """Resultado de um achado, nas cinco categorias da análise jurídico-regulatória (§12)."""

    COMPATIVEL = "compativel"
    DIVERGENCIA_IDENTIFICADA = "divergencia_identificada"
    VERIFICACAO_NECESSARIA = "verificacao_necessaria"
    DADOS_INSUFICIENTES = "dados_insuficientes"
    FORA_DO_ESCOPO = "fora_do_escopo"


def categoria_derivada(dados: dict[str, Any]) -> Categoria:
    """Categoria pelo que o achado traz, quando quem gerou não a informou.

    Abstenção vira ``dados_insuficientes``; valores iguais, ``compativel``; valores diferentes,
    ``divergencia_identificada``; sem valores para comparar, ``verificacao_necessaria``.
    """
    if dados.get("abstencao"):
        return Categoria.DADOS_INSUFICIENTES
    esperado, cobrado = dados.get("valor_esperado"), dados.get("valor_cobrado")
    if esperado is None or cobrado is None:
        return Categoria.VERIFICACAO_NECESSARIA
    if Decimal(str(esperado)) == Decimal(str(cobrado)):
        return Categoria.COMPATIVEL
    return Categoria.DIVERGENCIA_IDENTIFICADA


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
    categoria: Categoria | None = Field(
        default=None,
        description="Resultado do achado. Se ausente, é derivado (ver categoria_derivada).",
    )
    registro: RegistroAuditavel | None = Field(
        default=None, description="Regra, cálculo, data de consulta e limitações."
    )

    @model_validator(mode="before")
    @classmethod
    def _categoria_padrao(cls, dados: Any) -> Any:
        if isinstance(dados, dict) and dados.get("categoria") is None:
            return {**dados, "categoria": categoria_derivada(dados)}
        return dados

    @model_validator(mode="after")
    def _nivel_b_exige_citacao_oficial(self) -> Self:
        if self.nivel == Nivel.B and not self.abstencao and not self.citacoes:
            raise ValueError(
                "Achados de nível B sem abstenção exigem ao menos uma citação da tabela oficial"
            )
        return self
