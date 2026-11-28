"""Registro auditável e categoria dos achados do motor (#169).

Cada achado recebe a regra que o gerou, a conta feita e as limitações. Achados de nível B trazem
também a data em que a tabela oficial foi obtida. A categoria segue as cinco classes da análise
jurídico-regulatória (§12): o padrão vem dos valores (ver ``fa_contratos.categoria_derivada``), e
só dois casos são marcados explicitamente: leituras × consumo (A2), que pede verificação pelo
parecer enquanto não há dados de multiplicador ou medição, e o escopo fora do B1 da Neoenergia.
"""

from datetime import date

from fa_contratos import Achado, Categoria, RegistroAuditavel

_REGRAS_NIVEL_A: tuple[tuple[str, str], ...] = (
    ("Linha duplicada:", "A: linha repetida na fatura"),
    ("Linha:", "A3: quantidade x tarifa contra o valor da linha"),
    ("ICMS", "A: alíquota de ICMS impressa aplicada à base"),
    ("Parcela até 80 kWh", "A: parcela de até 80 kWh (regra tarifária do B1)"),
    ("Consumo medido", "A2: diferença entre as leituras contra o consumo informado"),
    ("Total da fatura", "A1: soma das linhas contra o total informado"),
    ("Dados disponíveis", "A: dados insuficientes para a conferência"),
)
_LIMITACOES_NIVEL_A = ["Checagem feita só com os valores impressos na fatura informada"]
_LIMITACOES_NIVEL_B = [
    "Tarifa provisória da REH 3.614/2026 segue na tabela",
    "Sem rateio de bandeira por ciclo de consumo",
    "Valor de bandeira não validado pela tabela oficial",
]


def _calculo(achado: Achado) -> str | None:
    if achado.valor_esperado is None or achado.valor_cobrado is None:
        return None
    return f"calculado = {achado.valor_esperado}; informado = {achado.valor_cobrado}"


def _regra_nivel_a(item: str) -> str:
    for prefixo, regra in _REGRAS_NIVEL_A:
        if item.startswith(prefixo):
            return regra
    return "A: checagem determinística"


def _divergente(achado: Achado) -> bool:
    return (
        not achado.abstencao
        and achado.valor_esperado is not None
        and achado.valor_cobrado is not None
        and achado.valor_esperado != achado.valor_cobrado
    )


def anotar_nivel_a(achados: list[Achado]) -> list[Achado]:
    anotados: list[Achado] = []
    for achado in achados:
        atualizacao: dict[str, object] = {
            "registro": RegistroAuditavel(
                regra_aplicada=_regra_nivel_a(achado.item),
                calculo=_calculo(achado),
                limitacoes=list(_LIMITACOES_NIVEL_A),
            )
        }
        if achado.item == "Consumo medido" and _divergente(achado):
            atualizacao["categoria"] = Categoria.VERIFICACAO_NECESSARIA
        anotados.append(achado.model_copy(update=atualizacao))
    return anotados


def anotar_nivel_b(achados: list[Achado], *, data_tabela: date) -> list[Achado]:
    anotados: list[Achado] = []
    for achado in achados:
        if achado.item == "Tarifa TUSD+TE":
            regra = "B1: TUSD+TE contra a Tarifa de Aplicação da tabela ANEEL"
        else:
            regra = "B: bandeira tarifária (conferência não realizada nesta versão)"
        anotados.append(
            achado.model_copy(
                update={
                    "registro": RegistroAuditavel(
                        regra_aplicada=regra,
                        calculo=_calculo(achado),
                        data_consulta=data_tabela,
                        limitacoes=list(_LIMITACOES_NIVEL_B),
                    )
                }
            )
        )
    return anotados
