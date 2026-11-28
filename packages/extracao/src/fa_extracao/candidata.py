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
import re
import unicodedata
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

_NUMERO = re.compile(r"^(?:R\$\s*)?-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+|\.\d+)?-?\s*%?$", re.I)
_MES_ANO = re.compile(r"^(\d{1,2})/(\d{4})$")
_GRUPO = re.compile(
    r"^([ab][1-4])(?:\s+(?:residencial|rural|comercial|demais\s+classes|poder\s+publico|iluminacao\s+publica))?$"
)
_NEOENERGIA = re.compile(
    r"^neoenergia(?:\s+distribuicao)?(?:\s+brasilia)?(?:\s+s\.?/?a\.?)?(?:\s*-?\s*df)?$"
)

_BANDEIRAS = {
    "verde": "Verde",
    "bandeira verde": "Verde",
    "amarela": "Amarela",
    "bandeira amarela": "Amarela",
    "vermelha": "Vermelha",
    "bandeira vermelha": "Vermelha",
    "vermelha 1": "Vermelha 1",
    "bandeira vermelha 1": "Vermelha 1",
    "vermelha patamar 1": "Vermelha Patamar 1",
    "vermelha p1": "Vermelha Patamar 1",
    "vermelha 2": "Vermelha 2",
    "bandeira vermelha 2": "Vermelha 2",
    "vermelha patamar 2": "Vermelha Patamar 2",
    "vermelha p2": "Vermelha Patamar 2",
    "escassez hidrica": "Escassez Hídrica",
    "bandeira escassez hidrica": "Escassez Hídrica",
}
_UNIDADES = {
    "kwh": "kWh",
    "kw": "kW",
    "dia": "dia",
    "dias": "dias",
    "un": "un",
    "mes": "mês",
    "mês": "mês",
    "%": "%",
    "r$": "R$",
}
_CONECTORES_ITEM = frozenset(
    {"de", "da", "do", "das", "dos", "e", "em", "com", "sem", "por", "para", "no", "na", "a", "o"}
)
_VOCABULARIO_ITEM = frozenset(
    {
        "energia",
        "ativa",
        "reativa",
        "consumo",
        "tusd",
        "te",
        "tarifa",
        "uso",
        "sistema",
        "distribuicao",
        "unitario",
        "unitaria",
        "comp",
        "bandeira",
        "band",
        "acres",
        "acrescimo",
        "adicional",
        "verde",
        "amarela",
        "vermelha",
        "patamar",
        "escassez",
        "hidrica",
        "custo",
        "disponibilidade",
        "taxa",
        "minima",
        "parcela",
        "faixa",
        "ate",
        "acima",
        "kwh",
        "kw",
        "dia",
        "dias",
        "mes",
        "meses",
        "b1",
        "residencial",
        "convencional",
        "ilum",
        "iluminacao",
        "pub",
        "publica",
        "distrital",
        "cip",
        "cosip",
        "contrib",
        "contribuicao",
        "servico",
        "icms",
        "pis",
        "cofins",
        "tributo",
        "tributos",
        "encargo",
        "encargos",
        "subvencao",
        "social",
        "baixa",
        "renda",
        "desconto",
        "credito",
        "debito",
        "ajuste",
        "devolucao",
        "compensacao",
        "dic",
        "fic",
        "dmic",
        "dicri",
        "dise",
        "juros",
        "multa",
        "ipca",
        "nf",
        "atualizacao",
        "correcao",
        "monetaria",
        "mora",
        "fatura",
        "faturamento",
        "diferenca",
        "saldo",
        "anterior",
        "posterior",
        "atual",
        "parcelamento",
        "religacao",
        "visita",
        "tecnica",
        "inspecao",
        "afericao",
        "medidor",
        "segunda",
        "via",
        "cobranca",
        "valor",
        "total",
        "outro",
        "item",
        "teste",
    }
)
_NUMERICOS = frozenset(
    {"leitura_anterior", "leitura_atual", "consumo_kwh", "aliquota_icms", "total"}
)
_NUMERICOS_ITEM = frozenset({"quantidade", "tarifa", "valor"})


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


def _sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    ).lower()


def _texto(valor: object) -> str | None:
    if valor is None or isinstance(valor, Mapping | list | tuple | set):
        return None
    limpo = higienizar_texto_extraido(anonimizar(str(valor))).strip()
    return " ".join(limpo.split()) or None


def _numero(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo or not _NUMERO.fullmatch(limpo):
        return None
    return limpo


def _distribuidora(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo:
        return None
    if _NEOENERGIA.fullmatch(_sem_acentos(limpo)):
        return "Neoenergia Brasília"
    # Não preserva texto livre de outra distribuidora para evitar vazamento de PII sem rótulo.
    return "Outra distribuidora"


def _grupo_tarifario(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo:
        return None
    achado = _GRUPO.fullmatch(_sem_acentos(limpo))
    return achado.group(1).upper() if achado else None


def _mes_referencia(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo:
        return None
    achado = _MES_ANO.fullmatch(limpo)
    if not achado or not (1 <= int(achado.group(1)) <= 12):
        return None
    return f"{int(achado.group(1)):02d}/{achado.group(2)}"


def _bandeira(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo:
        return None
    return _BANDEIRAS.get(_sem_acentos(limpo))


def _unidade(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo:
        return None
    return _UNIDADES.get(limpo.lower())


def _token_item_permitido(token: str) -> bool:
    subtokens = [s for s in re.split(r"[-/]", _sem_acentos(token).strip(".,;:()[]")) if s]
    if not subtokens:
        return False
    return all(s in _VOCABULARIO_ITEM or s in _CONECTORES_ITEM or s.isdigit() for s in subtokens)


def _descricao_item(valor: object) -> str | None:
    limpo = _texto(valor)
    if not limpo:
        return None
    palavras = limpo.split()
    filtradas: list[str] = []
    for palavra in palavras:
        if _token_item_permitido(palavra):
            filtradas.append(palavra)
    while filtradas and _sem_acentos(filtradas[0]).strip(".,;:()[]") in _CONECTORES_ITEM:
        filtradas.pop(0)
    while filtradas and _sem_acentos(filtradas[-1]).strip(".,;:()[]") in _CONECTORES_ITEM:
        filtradas.pop()
    return " ".join(filtradas) or None


def _campo_fatura(nome: str, valor: object) -> str | None:
    if nome in _NUMERICOS:
        return _numero(valor)
    if nome == "distribuidora":
        return _distribuidora(valor)
    if nome == "grupo_tarifario":
        return _grupo_tarifario(valor)
    if nome == "mes_referencia":
        return _mes_referencia(valor)
    if nome == "bandeira":
        return _bandeira(valor)
    return None


def _campo_item(nome: str, valor: object) -> str | None:
    if nome in _NUMERICOS_ITEM:
        return _numero(valor)
    if nome == "unidade":
        return _unidade(valor)
    if nome == "descricao":
        return _descricao_item(valor)
    return None


def extrair_candidata(imagem: bytes, extrator: ExtratorDeFoto) -> FaturaCandidata:
    """Lê a foto com o extrator e devolve a candidata, que ainda precisa de confirmação."""
    try:
        bruto = extrator.extrair(imagem)
    except ErroExtracao:
        raise  # mensagens escritas por nós, sem trechos da fatura
    except Exception:
        # Não propaga a exceção: a mensagem do modelo pode repetir trechos da fatura.
        raise ErroExtracao("O modelo de visão não conseguiu ler a foto.") from None
    if not isinstance(bruto, Mapping):
        raise ErroExtracao("O modelo de visão devolveu um formato inesperado.")

    campos = {nome: _campo_fatura(nome, bruto.get(nome)) for nome in CAMPOS}
    itens_brutos = bruto.get("itens")
    itens = [
        ItemCandidato(**{nome: _campo_item(nome, item.get(nome)) for nome in CAMPOS_ITEM})
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
