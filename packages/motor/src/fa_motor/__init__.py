"""Motor determinístico de evidência nível A.

As regras abaixo só comparam valores presentes na própria fatura. Elas não
consultam tarifa externa nem emitem conclusão jurídica.
"""

from decimal import Decimal

from fa_contratos import Achado, Fatura, Nivel

__version__ = "0.1.0"
FRENTE = "F3"


def analisar_nivel_a(fatura: Fatura) -> list[Achado]:
    """Produz achados reproduzíveis a partir de uma ``Fatura`` estruturada."""
    achados: list[Achado] = []
    if fatura.leitura_anterior is not None and fatura.leitura_atual is not None:
        consumo_calculado = fatura.leitura_atual - fatura.leitura_anterior
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


__all__ = ["FRENTE", "analisar_nivel_a"]
