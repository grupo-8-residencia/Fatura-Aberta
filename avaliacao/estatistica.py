"""Estatística da avaliação (S3): bootstrap, McNemar e Kappa de Cohen, só com a biblioteca padrão.

Fórmulas conforme docs/avaliacao/metricas.md.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

B_PADRAO = 10_000
SEMENTE_PADRAO = 20261109


@dataclass(frozen=True, slots=True)
class Intervalo:
    estimativa: float
    inferior: float
    superior: float

    def formatar(self, casas: int = 3) -> str:
        return f"{self.estimativa:.{casas}f} [{self.inferior:.{casas}f}; {self.superior:.{casas}f}]"


@dataclass(frozen=True, slots=True)
class ResultadoMcNemar:
    n01: int  # primeiro erra e segundo acerta
    n10: int  # primeiro acerta e segundo erra
    chi2: float  # com correção de continuidade de Edwards
    p_valor: float  # qui-quadrado com 1 grau de liberdade
    p_exato: float  # binomial bicaudal, mais confiável com poucos discordantes

    @property
    def significativo(self) -> bool:
        return self.p_valor < 0.05


def media(valores: Sequence[float]) -> float:
    if not valores:
        raise ValueError("amostra vazia")
    return sum(valores) / len(valores)


def bootstrap_ic(
    valores: Sequence[float],
    *,
    b: int = B_PADRAO,
    semente: int = SEMENTE_PADRAO,
    nivel: float = 0.95,
) -> Intervalo:
    """IC percentil da média por bootstrap, com B reamostras com reposição."""
    if not valores:
        raise ValueError("amostra vazia")
    rng = random.Random(semente)
    n = len(valores)
    medias = sorted(sum(valores[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    cauda = (1 - nivel) / 2
    inferior = medias[max(0, math.floor(cauda * b))]
    superior = medias[min(b - 1, math.ceil((1 - cauda) * b) - 1)]
    return Intervalo(media(valores), inferior, superior)


def bootstrap_ic_diferenca(
    a: Sequence[float],
    b_: Sequence[float],
    *,
    b: int = B_PADRAO,
    semente: int = SEMENTE_PADRAO,
    nivel: float = 0.95,
) -> Intervalo:
    """IC bootstrap pareado da diferença média (b_ − a): reamostra os índices dos pares."""
    if len(a) != len(b_) or not a:
        raise ValueError("amostras pareadas precisam ter o mesmo tamanho (> 0)")
    dif = [y - x for x, y in zip(a, b_, strict=True)]
    return bootstrap_ic(dif, b=b, semente=semente, nivel=nivel)


def mcnemar(a: Sequence[bool], b: Sequence[bool]) -> ResultadoMcNemar:
    """Teste de McNemar pareado. ``a`` e ``b`` dizem se cada baseline acertou cada item."""
    if len(a) != len(b):
        raise ValueError("amostras pareadas precisam ter o mesmo tamanho")
    n01 = sum(1 for x, y in zip(a, b, strict=True) if not x and y)
    n10 = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    n = n01 + n10
    if n == 0:
        return ResultadoMcNemar(n01, n10, 0.0, 1.0, 1.0)
    chi2 = (abs(n01 - n10) - 1) ** 2 / n
    p_valor = math.erfc(math.sqrt(chi2 / 2))  # cauda superior do qui-quadrado com 1 g.l.
    menor = min(n01, n10)
    cauda = sum(math.comb(n, k) for k in range(menor + 1)) / 2**n
    return ResultadoMcNemar(n01, n10, chi2, p_valor, min(1.0, 2 * cauda))


def acuracia(a: Sequence[object], b: Sequence[object]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("listas precisam ter o mesmo tamanho (> 0)")
    return sum(1 for x, y in zip(a, b, strict=True) if x == y) / len(a)


def kappa_cohen(a: Sequence[str], b: Sequence[str]) -> float:
    """Kappa de Cohen entre dois avaliadores com rótulos categóricos."""
    if len(a) != len(b) or not a:
        raise ValueError("listas precisam ter o mesmo tamanho (> 0)")
    n = len(a)
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[r] * cb[r] for r in set(ca) | set(cb)) / (n * n)
    if math.isclose(pe, 1.0):
        return 1.0 if math.isclose(po, 1.0) else 0.0
    return (po - pe) / (1 - pe)
