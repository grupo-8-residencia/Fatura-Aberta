"""Layouts de fatura mapeados na S1 (issue #9) e escolha entre eles.

O layout mudou em maio/2026. A escolha é feita pelo mês de referência, que é lido antes de
qualquer outro campo.

TODO: os rótulos abaixo são provisórios. Substituir pelos rótulos reais de cada layout quando
o mapa da #9 estiver registrado em `docs/frentes/f4.md`.
"""

import re
from dataclasses import dataclass
from datetime import date

CORTE_NOVO_LAYOUT = date(2026, 5, 1)


@dataclass(frozen=True)
class Layout:
    """Expressões que localizam cada campo do contrato `Fatura` no texto do PDF.

    Cada expressão tem um grupo de captura com o valor. Nenhuma captura dado pessoal.
    """

    nome: str
    distribuidora: re.Pattern[str]
    leitura_anterior: re.Pattern[str]
    leitura_atual: re.Pattern[str]
    consumo_kwh: re.Pattern[str]
    bandeira: re.Pattern[str]
    aliquota_icms: re.Pattern[str]
    total: re.Pattern[str]
    inicio_itens: re.Pattern[str]
    fim_itens: re.Pattern[str]


_NUM = r"(-?\d[\d.]*(?:,\d+)?)"


def _padrao(rotulo: str, valor: str = _NUM) -> re.Pattern[str]:
    return re.compile(rf"(?im)^\s*{rotulo}\s*:?\s*{valor}\s*$")


# O mês de referência é lido antes de escolher o layout, então o padrão é comum aos dois.
# TODO: confirmar com o mapa da #9.
MES_REFERENCIA = _padrao(r"(?:m[eê]s de )?refer[eê]ncia", r"(\d{2}/\d{4})")

# TODO: provisório até a #9. Os dois layouts partem dos mesmos rótulos.
_PROVISORIO = {
    "distribuidora": _padrao("distribuidora", r"(.+?)"),
    "leitura_anterior": _padrao("leitura anterior"),
    "leitura_atual": _padrao("leitura atual"),
    "consumo_kwh": _padrao(r"consumo(?: kwh)?"),
    "bandeira": _padrao("bandeira", r"(.+?)"),
    "aliquota_icms": _padrao(r"(?:al[ií]quota )?icms", r"([\d.,]+)\s*%"),
    "total": _padrao(r"total(?: a pagar)?", rf"(?:R\$\s*)?{_NUM}"),
    "inicio_itens": re.compile(r"(?im)^\s*itens da fatura\s*$"),
    "fim_itens": re.compile(r"(?im)^\s*total(?: a pagar)?\b"),
}

LAYOUT_ANTERIOR = Layout(nome="anterior-a-2026-05", **_PROVISORIO)
LAYOUT_POSTERIOR = Layout(nome="a-partir-de-2026-05", **_PROVISORIO)


def escolher_layout(mes_referencia: date) -> Layout:
    """Escolhe o layout pelo mês de referência da fatura."""
    return LAYOUT_POSTERIOR if mes_referencia >= CORTE_NOVO_LAYOUT else LAYOUT_ANTERIOR
