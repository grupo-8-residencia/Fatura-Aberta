"""Motor determinístico de evidência nível A.

As regras abaixo só comparam valores presentes na própria fatura. Elas não
consultam tarifa externa nem emitem conclusão jurídica.
"""

from decimal import ROUND_HALF_UP, Decimal

from fa_contratos import Achado, Fatura, Nivel

__version__ = "0.1.0"
FRENTE = "F3"

CENTAVO = Decimal("0.01")
LIMITE_PARCELA_ATE_80_KWH = Decimal("80")
ALIQUOTA_ICMS_MAXIMA_B1 = Decimal("0.25")

_TERMOS_PARCELA_80 = (
    "80 kwh",
    "80kwh",
    "até 80",
    "ate 80",
    "faixa 01",
    "faixa 1",
    "1ª faixa",
    "primeira faixa",
    "tarifa social",
    "desconto social",
    "baixa renda",
)
_TERMOS_EXCEDENTE_80 = (
    "acima de 80",
    "excedente",
    "faixa 02",
    "faixa 2",
    "2ª faixa",
    "segunda faixa",
)
_TERMOS_NAO_TRIBUTAVEIS_ICMS = (
    "ilum",
    "cip",
    "cosip",
    "contribui",
    "multa",
    "juros",
    "correção",
    "correcao",
)


def _arredondar_moeda(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _eh_item_icms(descricao: str) -> bool:
    texto = descricao.strip().lower()
    return texto == "icms" or texto.startswith("icms ") or " icms" in texto


def _eh_item_isento_icms(descricao: str) -> bool:
    texto = descricao.strip().lower()
    return any(termo in texto for termo in _TERMOS_NAO_TRIBUTAVEIS_ICMS)


def _eh_item_excedente_80(descricao: str) -> bool:
    texto = descricao.strip().lower()
    return any(termo in texto for termo in _TERMOS_EXCEDENTE_80)


def _eh_item_parcela_80(descricao: str) -> bool:
    texto = descricao.strip().lower()
    if _eh_item_excedente_80(texto):
        return False
    return any(termo in texto for termo in _TERMOS_PARCELA_80)


def checar_linhas(fatura: Fatura) -> list[Achado]:
    """Confere o produto ``quantidade × tarifa`` em cada linha e identifica duplicidades."""
    achados: list[Achado] = []
    vistos: set[tuple[str, Decimal | None, Decimal | None, Decimal]] = set()

    for item in fatura.itens:
        chave = (item.descricao.strip().lower(), item.quantidade, item.tarifa, item.valor)
        if chave in vistos:
            achados.append(
                Achado(
                    item=f"Linha duplicada: {item.descricao}",
                    nivel=Nivel.A,
                    descricao=(
                        f"A linha '{item.descricao}' aparece duplicada com o mesmo valor na fatura."
                    ),
                    valor_esperado=Decimal("0.00"),
                    valor_cobrado=item.valor,
                )
            )
            continue
        vistos.add(chave)

        if _eh_item_icms(item.descricao):
            continue

        if item.quantidade is not None and item.tarifa is not None:
            if item.quantidade < 0:
                achados.append(
                    Achado(
                        item=f"Linha: {item.descricao}",
                        nivel=Nivel.A,
                        descricao=(
                            f"A linha '{item.descricao}' apresenta quantidade negativa; "
                            "a conferência foi interrompida."
                        ),
                        abstencao=True,
                    )
                )
                continue

            calculado = _arredondar_moeda(item.quantidade * item.tarifa)
            cobrado = _arredondar_moeda(item.valor)
            confere = calculado == cobrado
            esperado = item.valor if confere else calculado
            achados.append(
                Achado(
                    item=f"Linha: {item.descricao}",
                    nivel=Nivel.A,
                    descricao=(
                        f"O valor da linha '{item.descricao}' confere com o produto "
                        "entre quantidade e tarifa."
                        if confere
                        else f"O valor da linha '{item.descricao}' não confere com o produto "
                        "entre quantidade e tarifa."
                    ),
                    valor_esperado=esperado,
                    valor_cobrado=item.valor,
                )
            )
        elif (item.quantidade is None) != (item.tarifa is None) and not _eh_item_parcela_80(
            item.descricao
        ):
            achados.append(
                Achado(
                    item=f"Linha: {item.descricao}",
                    nivel=Nivel.A,
                    descricao=(
                        f"A linha '{item.descricao}' não informa simultaneamente quantidade "
                        "e tarifa para conferência do valor."
                    ),
                    abstencao=True,
                )
            )

    return achados


def checar_icms(fatura: Fatura) -> list[Achado]:
    """Confere o cálculo do ICMS com a alíquota impressa na fatura."""
    itens_icms = [item for item in fatura.itens if _eh_item_icms(item.descricao)]

    if itens_icms:
        item_icms = itens_icms[0]
        if fatura.aliquota_icms is not None:
            aliquota: Decimal | None = fatura.aliquota_icms
        elif item_icms.tarifa is not None:
            aliquota = (
                item_icms.tarifa / Decimal("100")
                if item_icms.tarifa > Decimal("1")
                else item_icms.tarifa
            )
        else:
            aliquota = None

        if aliquota is None:
            return [
                Achado(
                    item="ICMS",
                    nivel=Nivel.A,
                    descricao=(
                        "A alíquota de ICMS não foi informada na fatura; "
                        "a conferência do tributo foi interrompida."
                    ),
                    abstencao=True,
                )
            ]

        if item_icms.quantidade is not None:
            base_icms: Decimal | None = item_icms.quantidade
        else:
            tributaveis = [
                item
                for item in fatura.itens
                if not _eh_item_icms(item.descricao)
                and not _eh_item_isento_icms(item.descricao)
                and item.valor > Decimal("0")
            ]
            base_icms = (
                sum((item.valor for item in tributaveis), start=Decimal("0"))
                if tributaveis
                else None
            )

        if base_icms is None or base_icms <= Decimal("0"):
            return [
                Achado(
                    item="ICMS",
                    nivel=Nivel.A,
                    descricao=(
                        "A base de cálculo do ICMS não está disponível na fatura para conferência."
                    ),
                    abstencao=True,
                )
            ]

        calculado = _arredondar_moeda(base_icms * aliquota)
        cobrado = _arredondar_moeda(item_icms.valor)
        confere = calculado == cobrado
        esperado = item_icms.valor if confere else calculado
        return [
            Achado(
                item="ICMS",
                nivel=Nivel.A,
                descricao=(
                    "O valor de ICMS confere com a aplicação da alíquota impressa "
                    "sobre a base de cálculo."
                    if confere
                    else "O valor de ICMS não confere com a aplicação da alíquota impressa "
                    "sobre a base de cálculo."
                ),
                valor_esperado=esperado,
                valor_cobrado=item_icms.valor,
            )
        ]

    if fatura.aliquota_icms is not None:
        if fatura.aliquota_icms > ALIQUOTA_ICMS_MAXIMA_B1:
            return [
                Achado(
                    item="ICMS",
                    nivel=Nivel.A,
                    descricao=(
                        "A alíquota de ICMS impressa na fatura não confere com a faixa "
                        "residencial aplicável ao subgrupo B1."
                    ),
                    valor_esperado=ALIQUOTA_ICMS_MAXIMA_B1,
                    valor_cobrado=fatura.aliquota_icms,
                )
            ]
        return [
            Achado(
                item="ICMS",
                nivel=Nivel.A,
                descricao=(
                    "A alíquota de ICMS foi informada, mas a base de cálculo e o valor "
                    "cobrado do tributo não constam separadamente na fatura."
                ),
                abstencao=True,
            )
        ]

    return []


def checar_parcela_ate_80_kwh(fatura: Fatura) -> list[Achado]:
    """Confere a parcela de consumo até 80 kWh conforme elegibilidade e limite da faixa."""
    itens_parcela = [item for item in fatura.itens if _eh_item_parcela_80(item.descricao)]
    itens_excedente = [item for item in fatura.itens if _eh_item_excedente_80(item.descricao)]

    if not itens_parcela and not itens_excedente:
        return []

    elegivel_b1 = fatura.grupo_tarifario.strip().upper() == "B1"
    if not elegivel_b1:
        item_ref = itens_parcela[0] if itens_parcela else itens_excedente[0]
        cobrado = item_ref.quantidade if item_ref.quantidade is not None else item_ref.valor
        return [
            Achado(
                item="Parcela até 80 kWh",
                nivel=Nivel.A,
                descricao=(
                    "A parcela até 80 kWh é aplicável apenas ao subgrupo residencial B1; "
                    "a fatura informa grupo tarifário não elegível."
                ),
                valor_esperado=Decimal("0"),
                valor_cobrado=cobrado,
            )
        ]

    if not itens_parcela:
        return [
            Achado(
                item="Parcela até 80 kWh",
                nivel=Nivel.A,
                descricao=(
                    "A fatura apresenta faixa excedente sem discriminar a parcela até 80 kWh."
                ),
                abstencao=True,
            )
        ]

    for item in itens_parcela:
        if item.quantidade is None:
            return [
                Achado(
                    item="Parcela até 80 kWh",
                    nivel=Nivel.A,
                    descricao=(
                        "A linha da parcela até 80 kWh não informa a quantidade em kWh "
                        "para conferência."
                    ),
                    abstencao=True,
                )
            ]

    esperado_parcela = min(fatura.consumo_kwh, LIMITE_PARCELA_ATE_80_KWH)
    for item in itens_parcela:
        assert item.quantidade is not None
        if item.quantidade != esperado_parcela:
            return [
                Achado(
                    item="Parcela até 80 kWh",
                    nivel=Nivel.A,
                    descricao=(
                        "A quantidade faturada na parcela até 80 kWh não confere com o "
                        "limite de até 80 kWh do consumo medido."
                    ),
                    valor_esperado=esperado_parcela,
                    valor_cobrado=item.quantidade,
                )
            ]

    if itens_excedente:
        esperado_excedente = max(fatura.consumo_kwh - LIMITE_PARCELA_ATE_80_KWH, Decimal("0"))
        for item_exc in itens_excedente:
            if item_exc.quantidade is None:
                return [
                    Achado(
                        item="Parcela até 80 kWh",
                        nivel=Nivel.A,
                        descricao=(
                            "A linha da faixa excedente a 80 kWh não informa a quantidade em kWh."
                        ),
                        abstencao=True,
                    )
                ]
            if item_exc.quantidade != esperado_excedente:
                return [
                    Achado(
                        item="Parcela até 80 kWh",
                        nivel=Nivel.A,
                        descricao=(
                            "A soma entre a parcela até 80 kWh e a faixa excedente não "
                            "confere com o consumo informado."
                        ),
                        valor_esperado=fatura.consumo_kwh,
                        valor_cobrado=esperado_parcela + item_exc.quantidade,
                    )
                ]

    quantidade_confirmada = itens_parcela[0].quantidade
    assert quantidade_confirmada is not None
    return [
        Achado(
            item="Parcela até 80 kWh",
            nivel=Nivel.A,
            descricao=(
                "A quantidade faturada na parcela até 80 kWh confere com o limite "
                "aplicável ao consumo informado."
            ),
            valor_esperado=quantidade_confirmada,
            valor_cobrado=quantidade_confirmada,
        )
    ]


def analisar_nivel_a(fatura: Fatura) -> list[Achado]:
    """Produz achados reproduzíveis a partir de uma ``Fatura`` estruturada."""
    achados: list[Achado] = []
    if fatura.leitura_anterior is not None and fatura.leitura_atual is not None:
        consumo_calculado = fatura.leitura_atual - fatura.leitura_anterior
        if consumo_calculado < 0:
            achados.append(
                Achado(
                    item="Consumo medido",
                    nivel=Nivel.A,
                    descricao=(
                        "As leituras estão em ordem decrescente; a conferência de consumo "
                        "foi interrompida para evitar uma conclusão incorreta."
                    ),
                    abstencao=True,
                )
            )
        else:
            achados.append(
                Achado(
                    item="Consumo medido",
                    nivel=Nivel.A,
                    descricao=(
                        "A diferença entre as leituras confere com o consumo informado."
                        if consumo_calculado == fatura.consumo_kwh
                        else "A diferença entre as leituras não confere com o consumo informado."
                    ),
                    valor_esperado=consumo_calculado,
                    valor_cobrado=fatura.consumo_kwh,
                )
            )
    if fatura.itens:
        soma_itens = sum((item.valor for item in fatura.itens), start=Decimal("0"))
        achados.append(
            Achado(
                item="Total da fatura",
                nivel=Nivel.A,
                descricao=(
                    "A soma das linhas confere com o total informado."
                    if soma_itens == fatura.total
                    else "A soma das linhas não confere com o total informado."
                ),
                valor_esperado=soma_itens,
                valor_cobrado=fatura.total,
            )
        )
        achados.extend(checar_linhas(fatura))
    achados.extend(checar_icms(fatura))
    achados.extend(checar_parcela_ate_80_kwh(fatura))
    if not achados:
        achados.append(
            Achado(
                item="Dados disponíveis",
                nivel=Nivel.A,
                descricao=(
                    "Não há leituras ou itens suficientes para uma conferência determinística."
                ),
                abstencao=True,
            )
        )
    return achados


__all__ = [
    "FRENTE",
    "analisar_nivel_a",
    "checar_icms",
    "checar_linhas",
    "checar_parcela_ate_80_kwh",
]
