"""Citação de uma norma, por dispositivo, com data de vigência."""

from datetime import date
from typing import Self

from pydantic import Field, HttpUrl, model_validator

from fa_contratos.base import ModeloBase


class Citacao(ModeloBase):
    """Referência exata a um dispositivo normativo.

    `vigencia_fim` vazio significa que o dispositivo segue em vigor.
    """

    ato: str = Field(min_length=1, description="Ato normativo, por exemplo uma resolução ou lei.")
    dispositivo: str = Field(min_length=1, description="Artigo, inciso ou parágrafo citado.")
    vigencia_inicio: date
    vigencia_fim: date | None = None
    url: HttpUrl

    @model_validator(mode="after")
    def _vigencia_coerente(self) -> Self:
        if self.vigencia_fim is not None and self.vigencia_fim < self.vigencia_inicio:
            raise ValueError("vigencia_fim não pode ser anterior a vigencia_inicio")
        return self

    def vigente_em(self, dia: date) -> bool:
        """Diz se o dispositivo estava em vigor no dia informado (limites inclusivos)."""
        if dia < self.vigencia_inicio:
            return False
        return self.vigencia_fim is None or dia <= self.vigencia_fim
