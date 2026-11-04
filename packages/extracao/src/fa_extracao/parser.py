"""Parser de PDF de fatura para o contrato `Fatura`."""

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from fa_contratos import Fatura, ItemFatura
from fa_extracao.erros import ErroExtracao
from fa_extracao.layouts import MES_REFERENCIA, Layout, escolher_layout
from fa_extracao.pdf import extrair_texto

log = logging.getLogger(__name__)

_ITEM = re.compile(r"^\s*(.+?)\s+(-?[\d.]+,\d{2})\s*$")


def _decimal(bruto: str) -> Decimal:
    """Converte número no formato brasileiro (1.234,56) em `Decimal`."""
    try:
        return Decimal(bruto.replace(".", "").replace(",", "."))
    except InvalidOperation as erro:
        raise ErroExtracao("Número em formato inválido.") from erro


def _mes_referencia(texto: str) -> date:
    achado = MES_REFERENCIA.search(texto)
    if achado is None:
        raise ErroExtracao("Mês de referência não encontrado.")
    mes, ano = achado.group(1).split("/")
    try:
        return date(int(ano), int(mes), 1)
    except ValueError as erro:
        raise ErroExtracao("Mês de referência inválido.") from erro


def _campo(layout: Layout, nome: str, texto: str) -> str | None:
    achado = getattr(layout, nome).search(texto)
    return achado.group(1).strip() if achado else None


def _obrigatorio(layout: Layout, nome: str, texto: str) -> str:
    valor = _campo(layout, nome, texto)
    if valor is None:
        raise ErroExtracao(f"Campo obrigatório não encontrado: {nome}.")
    return valor


def _opcional_decimal(layout: Layout, nome: str, texto: str) -> Decimal | None:
    valor = _campo(layout, nome, texto)
    return None if valor is None else _decimal(valor)


def _itens(layout: Layout, texto: str) -> list[ItemFatura]:
    inicio = layout.inicio_itens.search(texto)
    if inicio is None:
        return []
    resto = texto[inicio.end() :]
    fim = layout.fim_itens.search(resto)
    bloco = resto[: fim.start()] if fim else resto
    itens = []
    for linha in bloco.splitlines():
        achado = _ITEM.match(linha)
        if achado:
            itens.append(ItemFatura(descricao=achado.group(1), valor=_decimal(achado.group(2))))
    return itens


def parse_texto(texto: str) -> Fatura:
    """Converte o texto de uma fatura em `Fatura`, lendo só os campos do contrato."""
    mes = _mes_referencia(texto)
    layout = escolher_layout(mes)

    aliquota = _opcional_decimal(layout, "aliquota_icms", texto)
    try:
        fatura = Fatura(
            distribuidora=_obrigatorio(layout, "distribuidora", texto),
            mes_referencia=mes,
            leitura_anterior=_opcional_decimal(layout, "leitura_anterior", texto),
            leitura_atual=_opcional_decimal(layout, "leitura_atual", texto),
            consumo_kwh=_decimal(_obrigatorio(layout, "consumo_kwh", texto)),
            bandeira=_campo(layout, "bandeira", texto),
            aliquota_icms=None if aliquota is None else aliquota / 100,
            itens=_itens(layout, texto),
            total=_decimal(_obrigatorio(layout, "total", texto)),
        )
    except ValidationError as erro:
        # Não propaga `erro`: a mensagem do Pydantic repete o valor recebido.
        campos = sorted({str(e["loc"][0]) for e in erro.errors() if e["loc"]})
        raise ErroExtracao(f"Campos inválidos para o contrato: {', '.join(campos)}.") from None

    log.info("Fatura extraída: layout=%s itens=%d", layout.nome, len(fatura.itens))
    return fatura


def parse_pdf(origem: Path | bytes) -> Fatura:
    """Extrai uma `Fatura` de um PDF. Dados pessoais nunca saem desta função."""
    return parse_texto(extrair_texto(origem))
