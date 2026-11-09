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

_NUMERO = r"\d[\d.]*,\d+-?"
# Linha de item: descrição, unidade opcional e só números depois (crédito termina em "-").
_LINHA_ITEM = re.compile(
    rf"(?im)^[ \t]*(?P<desc>[A-Za-zÀ-ÿ][^\n]*?)[ \t]+(?P<unid>kWh)?[ \t]*"
    rf"(?P<nums>(?:{_NUMERO}[ \t]*)+)$"
)
# Linhas que têm só números mas não são itens da fatura (tributos e totais).
_NAO_ITENS = {"pis", "cofins", "icms", "total", "total a pagar", "total da fatura"}


def _decimal(bruto: str) -> Decimal:
    """Converte número no formato brasileiro (1.234,56 ou 0,88-) em `Decimal`."""
    negativo = bruto.endswith("-")
    try:
        valor = Decimal(bruto.rstrip("-").replace(".", "").replace(",", "."))
    except InvalidOperation as erro:
        raise ErroExtracao("Número em formato inválido.") from erro
    return -valor if negativo else valor


def _mes_referencia(texto: str) -> date:
    achado = MES_REFERENCIA.search(texto)
    if achado is None:
        raise ErroExtracao("Mês de referência não encontrado.")
    try:
        return date(int(achado.group(2)), int(achado.group(1)), 1)
    except ValueError as erro:
        raise ErroExtracao("Mês de referência inválido.") from erro


def _obrigatorio(padrao: re.Pattern[str], nome: str, texto: str) -> str:
    achado = padrao.search(texto)
    if achado is None:
        raise ErroExtracao(f"Campo obrigatório não encontrado: {nome}.")
    return achado.group(1).strip()


def _itens(texto: str) -> list[ItemFatura]:
    itens = []
    for achado in _LINHA_ITEM.finditer(texto):
        descricao = " ".join(achado["desc"].split())
        if descricao.lower() in _NAO_ITENS:
            continue
        numeros = re.findall(_NUMERO, achado["nums"])
        if achado["unid"] and len(numeros) >= 3:
            quantidade, tarifa, valor = (_decimal(n) for n in numeros[:3])
            itens.append(
                ItemFatura(
                    descricao=descricao,
                    quantidade=quantidade,
                    unidade="kWh",
                    tarifa=tarifa,
                    valor=valor,
                )
            )
        elif not achado["unid"]:
            itens.append(ItemFatura(descricao=descricao, valor=_decimal(numeros[0])))
    return itens


def _bandeira(layout: Layout, texto: str) -> str | None:
    achado = layout.bandeira.search(texto) or layout.bandeira_item.search(texto)
    return achado.group(1).capitalize() if achado else None


def parse_texto(texto: str) -> Fatura:
    """Converte o texto de uma fatura em `Fatura`, lendo só os campos do contrato."""
    mes = _mes_referencia(texto)
    layout = escolher_layout(mes)

    if layout.distribuidora.search(texto) is None:
        raise ErroExtracao("Distribuidora fora do escopo (Neoenergia Brasília) ou não encontrada.")
    if _obrigatorio(layout.grupo, "grupo_tarifario", texto).upper() != "B1":
        raise ErroExtracao("Grupo tarifário fora do escopo (B1).")

    medidores = list(layout.medidor.finditer(texto))
    if not medidores:
        raise ErroExtracao("Campo obrigatório não encontrado: leituras do medidor.")
    aliquota = layout.aliquota_icms.search(texto)

    try:
        fatura = Fatura(
            distribuidora="Neoenergia Brasília",
            mes_referencia=mes,
            leitura_anterior=_decimal(medidores[0].group(1)),
            leitura_atual=_decimal(medidores[0].group(2)),
            consumo_kwh=sum((_decimal(m.group(4)) for m in medidores), start=Decimal(0)),
            bandeira=_bandeira(layout, texto),
            aliquota_icms=None if aliquota is None else _decimal(aliquota.group(1)) / 100,
            itens=_itens(texto),
            total=_decimal(_obrigatorio(layout.total, "total", texto)),
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
