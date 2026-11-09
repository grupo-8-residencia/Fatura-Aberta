"""Gerador determinístico de faturas sintéticas e de erros injetados v0 (issue #29)."""

import json
import random
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import Field

from fa_contratos import Fatura, ItemFatura
from fa_contratos.base import ModeloBase

SEMENTE_PADRAO = 20261109
QUANTIDADE_PADRAO = 30
RAIZ_REPOSITORIO = Path(__file__).resolve().parents[4]
PASTA_SINTETICAS = RAIZ_REPOSITORIO / "dados" / "benchmark" / "sinteticas"
CAMINHO_PADRAO_SINTETICAS = PASTA_SINTETICAS / "faturas_v0.jsonl"

_CENTAVO = Decimal("0.01")
_TARIFA_TUSD = Decimal("0.45")
_TARIFA_TE = Decimal("0.38")
_TARIFA_FAIXA_01 = Decimal("0.28")
_TARIFA_FAIXA_02 = Decimal("0.83")
_ADICIONAIS_BANDEIRA: dict[str, Decimal] = {
    "verde": Decimal("0.00"),
    "amarela": Decimal("0.02"),
    "vermelha 1": Decimal("0.05"),
    "vermelha 2": Decimal("0.08"),
}
_ALIQUOTAS_B1 = (Decimal("0.12"), Decimal("0.20"), Decimal("0.25"))
_ILUMINACAO_PUBLICA = Decimal("12.00")


def _moeda(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


class TipoErroNivelA(StrEnum):
    """Tipos de erros rotulados correspondentes às 5 checagens do nível A."""

    LEITURAS = "leituras_divergem_do_consumo"
    SOMAS = "soma_diverge_do_total"
    LINHAS = "linha_produto_incorreto"
    ICMS = "icms_diverge_da_aliquota"
    PARCELA_80 = "parcela_ate_80_kwh_incorreta"


TIPOS_ERRO_NIVEL_A: tuple[TipoErroNivelA, ...] = tuple(TipoErroNivelA)


class RegistroSintetico(ModeloBase):
    """Registro rotulado de fatura sintética para o benchmark público."""

    id: str = Field(min_length=1)
    semente: int
    erro_injetado: TipoErroNivelA | None = None
    item_esperado_divergente: str | None = None
    fatura: Fatura


def gerar_fatura_sintetica_valida(rng: random.Random, *, com_parcela_80: bool = False) -> Fatura:
    """Gera uma ``Fatura`` 100% sintética e aritmeticamente consistente no nível A."""
    mes = date(2026, rng.randint(1, 10), 1)
    consumo = Decimal(rng.randint(90, 320) if com_parcela_80 else rng.randint(50, 360))
    leitura_anterior = Decimal(rng.randint(1000, 50000))
    leitura_atual = leitura_anterior + consumo
    bandeira = rng.choice(tuple(_ADICIONAIS_BANDEIRA))
    aliquota_icms = rng.choice(_ALIQUOTAS_B1)

    itens: list[ItemFatura] = []
    if com_parcela_80:
        qtd_faixa_1 = min(consumo, Decimal("80"))
        qtd_faixa_2 = max(consumo - Decimal("80"), Decimal("0"))
        itens.append(
            ItemFatura(
                descricao="Parcela até 80 kWh (faixa 01)",
                quantidade=qtd_faixa_1,
                unidade="kWh",
                tarifa=_TARIFA_FAIXA_01,
                valor=_moeda(qtd_faixa_1 * _TARIFA_FAIXA_01),
            )
        )
        if qtd_faixa_2 > Decimal("0"):
            itens.append(
                ItemFatura(
                    descricao="Consumo excedente (faixa 02)",
                    quantidade=qtd_faixa_2,
                    unidade="kWh",
                    tarifa=_TARIFA_FAIXA_02,
                    valor=_moeda(qtd_faixa_2 * _TARIFA_FAIXA_02),
                )
            )
    else:
        itens.extend(
            [
                ItemFatura(
                    descricao="Consumo-TUSD",
                    quantidade=consumo,
                    unidade="kWh",
                    tarifa=_TARIFA_TUSD,
                    valor=_moeda(consumo * _TARIFA_TUSD),
                ),
                ItemFatura(
                    descricao="Consumo-TE",
                    quantidade=consumo,
                    unidade="kWh",
                    tarifa=_TARIFA_TE,
                    valor=_moeda(consumo * _TARIFA_TE),
                ),
            ]
        )

    tarifa_bandeira = _ADICIONAIS_BANDEIRA[bandeira]
    itens.append(
        ItemFatura(
            descricao=f"Acrés. Band. {bandeira.upper()}",
            quantidade=consumo,
            unidade="kWh",
            tarifa=tarifa_bandeira,
            valor=_moeda(consumo * tarifa_bandeira),
        )
    )

    base_icms = sum((item.valor for item in itens), start=Decimal("0"))
    valor_icms = _moeda(base_icms * aliquota_icms)
    itens.append(
        ItemFatura(
            descricao="Ilum. Púb. Distrital",
            valor=_ILUMINACAO_PUBLICA,
        )
    )
    itens.append(
        ItemFatura(
            descricao="ICMS",
            quantidade=base_icms,
            tarifa=aliquota_icms,
            valor=valor_icms,
        )
    )

    total = sum((item.valor for item in itens), start=Decimal("0"))
    return Fatura(
        distribuidora="Neoenergia Brasília",
        grupo_tarifario="B1",
        mes_referencia=mes,
        leitura_anterior=leitura_anterior,
        leitura_atual=leitura_atual,
        consumo_kwh=consumo,
        bandeira=bandeira,
        aliquota_icms=aliquota_icms,
        itens=itens,
        total=total,
    )


def injetar_erro_nivel_a(
    fatura: Fatura, tipo_erro: TipoErroNivelA, rng: random.Random
) -> tuple[Fatura, str]:
    """Injeta um erro rotulado específico em uma ``Fatura`` válida."""
    dados = fatura.model_dump()
    desvio_kwh = Decimal(rng.randint(12, 45))
    desvio_moeda = _moeda(Decimal(rng.randint(600, 2500)) / Decimal("100"))

    if tipo_erro is TipoErroNivelA.LEITURAS:
        assert fatura.leitura_atual is not None
        dados["leitura_atual"] = fatura.leitura_atual + desvio_kwh
        return Fatura.model_validate(dados), "Consumo medido"

    if tipo_erro is TipoErroNivelA.SOMAS:
        dados["total"] = _moeda(fatura.total + desvio_moeda)
        return Fatura.model_validate(dados), "Total da fatura"

    if tipo_erro is TipoErroNivelA.LINHAS:
        itens_copia = [dict(item) for item in dados["itens"]]
        itens_copia[0]["valor"] = _moeda(Decimal(str(itens_copia[0]["valor"])) + desvio_moeda)
        dados["itens"] = itens_copia
        dados["total"] = sum((Decimal(str(i["valor"])) for i in itens_copia), start=Decimal("0"))
        return Fatura.model_validate(dados), f"Linha: {itens_copia[0]['descricao']}"

    if tipo_erro is TipoErroNivelA.ICMS:
        itens_copia = [dict(item) for item in dados["itens"]]
        for item in itens_copia:
            if str(item["descricao"]).strip().upper() == "ICMS":
                item["valor"] = _moeda(Decimal(str(item["valor"])) + desvio_moeda)
                break
        dados["itens"] = itens_copia
        dados["total"] = sum((Decimal(str(i["valor"])) for i in itens_copia), start=Decimal("0"))
        return Fatura.model_validate(dados), "ICMS"

    if tipo_erro is TipoErroNivelA.PARCELA_80:
        base_fatura = (
            fatura
            if any("80 kWh" in i.descricao for i in fatura.itens)
            else gerar_fatura_sintetica_valida(rng, com_parcela_80=True)
        )
        dados_80 = base_fatura.model_dump()
        itens_80 = [dict(item) for item in dados_80["itens"]]
        qtd_invalida = Decimal("95")
        tarifa_0 = Decimal(str(itens_80[0]["tarifa"]))
        itens_80[0]["quantidade"] = qtd_invalida
        itens_80[0]["valor"] = _moeda(qtd_invalida * tarifa_0)
        # Reequilibra o ICMS e o total para isolar o erro na parcela até 80 kWh.
        base_tributavel = sum(
            (
                Decimal(str(i["valor"]))
                for i in itens_80
                if str(i["descricao"]).strip().upper() != "ICMS"
                and "ilum" not in str(i["descricao"]).lower()
            ),
            start=Decimal("0"),
        )
        aliquota = Decimal(str(dados_80["aliquota_icms"]))
        for item in itens_80:
            if str(item["descricao"]).strip().upper() == "ICMS":
                item["quantidade"] = base_tributavel
                item["valor"] = _moeda(base_tributavel * aliquota)
                break
        dados_80["itens"] = itens_80
        dados_80["total"] = sum((Decimal(str(i["valor"])) for i in itens_80), start=Decimal("0"))
        return Fatura.model_validate(dados_80), "Parcela até 80 kWh"

    raise ValueError(f"Tipo de erro desconhecido: {tipo_erro}")  # pragma: no cover


def gerar_conjunto_sintetico_v0(
    semente: int = SEMENTE_PADRAO, quantidade: int = QUANTIDADE_PADRAO
) -> list[RegistroSintetico]:
    """Gera o conjunto de faturas sintéticas (válidas e com erros rotulados) a partir de semente."""
    if quantidade < len(TIPOS_ERRO_NIVEL_A) * 2:
        raise ValueError(
            f"A quantidade deve ser de pelo menos {len(TIPOS_ERRO_NIVEL_A) * 2} faturas."
        )

    rng = random.Random(semente)
    registros: list[RegistroSintetico] = []
    metade_validas = quantidade // 2

    for indice in range(1, quantidade + 1):
        com_parcela_80 = indice % 2 == 0
        fatura_valida = gerar_fatura_sintetica_valida(rng, com_parcela_80=com_parcela_80)
        if indice <= metade_validas:
            registros.append(
                RegistroSintetico(
                    id=f"FA-SINT-{indice:03d}",
                    semente=semente,
                    erro_injetado=None,
                    item_esperado_divergente=None,
                    fatura=fatura_valida,
                )
            )
        else:
            indice_erro = (indice - metade_validas - 1) % len(TIPOS_ERRO_NIVEL_A)
            tipo_erro = TIPOS_ERRO_NIVEL_A[indice_erro]
            fatura_com_erro, item_divergente = injetar_erro_nivel_a(fatura_valida, tipo_erro, rng)
            registros.append(
                RegistroSintetico(
                    id=f"FA-SINT-{indice:03d}",
                    semente=semente,
                    erro_injetado=tipo_erro,
                    item_esperado_divergente=item_divergente,
                    fatura=fatura_com_erro,
                )
            )

    return registros


def gravar_conjunto_sintetico_v0(
    destino: Path = CAMINHO_PADRAO_SINTETICAS,
    semente: int = SEMENTE_PADRAO,
    quantidade: int = QUANTIDADE_PADRAO,
) -> Path:
    """Grava o conjunto sintético rotulado em JSONL em ``dados/benchmark/sinteticas/``."""
    registros = gerar_conjunto_sintetico_v0(semente=semente, quantidade=quantidade)
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        json.dumps(r.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) for r in registros
    ]
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return destino


__all__ = [
    "CAMINHO_PADRAO_SINTETICAS",
    "PASTA_SINTETICAS",
    "QUANTIDADE_PADRAO",
    "RegistroSintetico",
    "SEMENTE_PADRAO",
    "TIPOS_ERRO_NIVEL_A",
    "TipoErroNivelA",
    "gerar_conjunto_sintetico_v0",
    "gerar_fatura_sintetica_valida",
    "gravar_conjunto_sintetico_v0",
    "injetar_erro_nivel_a",
]
