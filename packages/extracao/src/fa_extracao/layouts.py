"""Layout da fatura da Neoenergia Brasília (B1), com os rótulos vistos em faturas reais.

Os padrões abaixo foram conferidos em um PDF real com texto (2ª via, 08/2026). As demais faturas
da amostra são fotos e dependem da leitura por imagem (#40). Pontos do layout que o parser trata:

- o valor vem *abaixo* do rótulo (`REF:MÊS/ANO` e depois `08/2026`);
- no topo, "LEITURA ANTERIOR/ATUAL" são datas; as leituras do medidor estão na tabela do rodapé,
  numa ou mais linhas "Energia Ativa";
- crédito aparece com o sinal no fim (`0,88-`);
- a classificação ("B1 RESIDENCIAL") e a distribuidora identificam se a fatura está no escopo.

TODO: sem amostra anterior a maio/2026, não dá para dizer se o layout mudou. Quando houver, criar
um segundo `Layout` e usar `escolher_layout`.
"""

import re
from dataclasses import dataclass
from datetime import date

CORTE_NOVO_LAYOUT = date(2026, 5, 1)

_NUM = r"[\d.]+,\d+"

# O mês de referência é lido antes de escolher o layout, então o padrão é comum.
MES_REFERENCIA = re.compile(r"(?i)REF:?\s*M[ÊE]S\s*/\s*ANO\s*(\d{1,2})/(\d{4})")


@dataclass(frozen=True)
class Layout:
    """Expressões que localizam cada campo do contrato `Fatura`. Nenhuma captura dado pessoal."""

    nome: str
    distribuidora: re.Pattern[str]
    grupo: re.Pattern[str]
    medidor: re.Pattern[str]
    bandeira: re.Pattern[str]
    bandeira_item: re.Pattern[str]
    aliquota_icms: re.Pattern[str]
    total: re.Pattern[str]


LAYOUT_NEOENERGIA_B1 = Layout(
    nome="neoenergia-b1",
    distribuidora=re.compile(r"(?i)(NEOENERGIA\s+DISTRIBUI[ÇC][ÃA]O\s+BRAS[ÍI]LIA)"),
    grupo=re.compile(r"(?i)CLASSIFICA[ÇC][ÃA]O:\s*(B\d)\b"),
    # Grupos: leitura anterior, leitura atual, constante do medidor, consumo (kWh).
    medidor=re.compile(
        rf"(?im)^[ \t]*\d+[ \t]+Energia[ \t]+Ativa\b[^\n\d]*?({_NUM})[ \t]+({_NUM})"
        rf"[ \t]+(\d+(?:,\d+)?)[ \t]+({_NUM})[ \t]*$"
    ),
    bandeira=re.compile(r"(?i)bandeira\s+em\s+vigor\s+[ée]\s+a\s+(\w+)"),
    bandeira_item=re.compile(r"(?i)Acr[ée]s\.?\s*Band\.?\s*(\w+)"),
    # Linha da tabela de tributos: "ICMS  <base>  <alíquota %>  <valor>".
    aliquota_icms=re.compile(rf"(?m)^[ \t]*ICMS[ \t]+{_NUM}[ \t]+(\d+,\d+)[ \t]+{_NUM}[ \t]*$"),
    total=re.compile(rf"(?i)TOTAL\s+A\s+PAGAR\s*R?\$?\s*({_NUM})"),
)


def escolher_layout(mes_referencia: date) -> Layout:
    """Layout para o mês de referência. Hoje só há um (sem amostra anterior a maio/2026)."""
    return LAYOUT_NEOENERGIA_B1
