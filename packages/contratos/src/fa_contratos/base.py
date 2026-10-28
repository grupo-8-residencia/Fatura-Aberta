"""Configuração comum dos modelos."""

from pydantic import BaseModel, ConfigDict


class ModeloBase(BaseModel):
    """Modelo imutável que rejeita campos desconhecidos.

    `extra="forbid"` faz com que um campo novo, ou um erro de digitação, quebre o contrato
    na hora em vez de passar despercebido entre frentes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
