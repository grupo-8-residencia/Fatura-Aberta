"""Checagens de nível B contra a tabela oficial ANEEL versionada (issue #34).

Todo achado de nível B inclui a fonte e a data de obtenção da tabela versionada
em ``dados/tarifas/``, usa linguagem estritamente descritiva ("diverge da tabela
oficial que conseguimos obter") e nunca emite juízo jurídico ("ilegal") nem
estima valores de restituição.
"""

import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl

from fa_contratos import Achado, Citacao, Fatura, ItemFatura, Nivel
from fa_contratos.base import ModeloBase

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[4]
PASTA_TARIFAS = RAIZ_REPOSITORIO / "dados" / "tarifas"
CAMINHO_PADRAO_PROVENIENCIA = PASTA_TARIFAS / "proveniencia.json"

_NAMESPACE_XLSX = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_DATA_BASE_EXCEL = date(1899, 12, 30)
_MIL = Decimal("1000")
_PRECISAO_TARIFA_KWH = Decimal("0.00001")
_CENTAVO = Decimal("0.01")

# VALORES_BANDEIRA_ANEEL_KWH (em R$/kWh, sem tributos):
# - Fonte normativa de referência: Resolução Homologatória ANEEL nº 3.316, de 26/03/2024
#   (vigência a partir de 01/04/2024: amarela = R$ 18,85/MWh, vermelha patamar 1 =
#   R$ 44,63/MWh e vermelha patamar 2 = R$ 78,77/MWh, convertidos para R$/kWh por /1000).
# - Classificação no projeto: PARÂMETRO DO PROJETO (a planilha exportada em
#   dados/tarifas/aneel_neoenergia_brasilia_b1_2026.xlsx não valida a tarifa de bandeira,
#   conforme dados/tarifas/README.md, e a REH 3.316/2024 segue como "A verificar" em
#   dados/normas/README.md; pode ser sobrescrito via ``referencia_bandeiras``).
VALORES_BANDEIRA_ANEEL_KWH: dict[str, Decimal] = {
    "verde": Decimal("0.00000"),
    "amarela": Decimal("0.01885"),
    "vermelha 1": Decimal("0.04463"),
    "vermelha patamar 1": Decimal("0.04463"),
    "vermelha 2": Decimal("0.07877"),
    "vermelha patamar 2": Decimal("0.07877"),
}

_TERMOS_IGNORADOS_CONSUMO = (
    "icms",
    "ilum",
    "cip",
    "cosip",
    "contribui",
    "multa",
    "juros",
    "correção",
    "correcao",
    "band",
    "80 kwh",
    "80kwh",
    "até 80",
    "ate 80",
    "acima de 80",
    "excedente",
    "faixa 01",
    "faixa 1",
    "faixa 02",
    "faixa 2",
    "tarifa social",
    "desconto social",
    "baixa renda",
)


def _para_kwh(valor_mwh: Decimal) -> Decimal:
    return (valor_mwh / _MIL).quantize(_PRECISAO_TARIFA_KWH, rounding=ROUND_HALF_UP)


def _arredondar_moeda(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


class ProvenienciaTarifas(ModeloBase):
    """Metadados de proveniência da tabela ANEEL versionada em ``dados/tarifas/``."""

    fonte: str = Field(min_length=1)
    url: HttpUrl
    data_download: date
    arquivo: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    formato: str = Field(min_length=1)
    filtros: str = Field(min_length=1)
    observacoes: str = Field(default="")


class LinhaTarifaAneel(ModeloBase):
    """Linha normalizada da tabela ANEEL versionada (convertida para R$/kWh)."""

    sigla: str = Field(min_length=1)
    resolucao: str = Field(min_length=1)
    vigencia_inicio: date
    vigencia_fim: date
    base_tarifaria: str = Field(min_length=1)
    subgrupo: str = Field(min_length=1)
    modalidade: str = Field(min_length=1)
    classe: str = Field(min_length=1)
    subclasse: str = Field(min_length=1)
    detalhe: str = Field(min_length=1)
    unidade_origem: str = Field(min_length=1)
    tusd_mwh: Decimal
    te_mwh: Decimal
    tusd_kwh: Decimal
    te_kwh: Decimal
    tusd_mais_te_kwh: Decimal


class TabelaTarifasVersionada(ModeloBase):
    """Conjunto de linhas tarifárias carregadas com sua proveniência."""

    proveniencia: ProvenienciaTarifas
    linhas: tuple[LinhaTarifaAneel, ...]


def _converter_data_excel(serial_texto: str) -> date:
    return _DATA_BASE_EXCEL + timedelta(days=int(serial_texto))


def _ler_linhas_xlsx(caminho_xlsx: Path) -> list[LinhaTarifaAneel]:
    with zipfile.ZipFile(caminho_xlsx) as arquivo_zip:
        xml_bytes = arquivo_zip.read("xl/worksheets/sheet1.xml")
    raiz = ET.fromstring(xml_bytes)
    linhas_xml = raiz.findall(".//main:sheetData/main:row", _NAMESPACE_XLSX)

    cabecalho: list[str] = []
    resultado: list[LinhaTarifaAneel] = []

    for indice, linha_xml in enumerate(linhas_xml):
        valores: list[str] = []
        for celula in linha_xml.findall("main:c", _NAMESPACE_XLSX):
            tipo = celula.attrib.get("t")
            if tipo == "inlineStr":
                no_texto = celula.find(".//main:t", _NAMESPACE_XLSX)
                valores.append(no_texto.text if no_texto is not None and no_texto.text else "")
            else:
                no_valor = celula.find("main:v", _NAMESPACE_XLSX)
                valores.append(no_valor.text if no_valor is not None and no_valor.text else "")

        if indice == 0:
            cabecalho = valores
            continue

        if not cabecalho or len(valores) != len(cabecalho):
            continue

        mapa = dict(zip(cabecalho, valores, strict=True))
        tusd_mwh = Decimal(mapa["TUSD"])
        te_mwh = Decimal(mapa["TE"])
        tusd_kwh = _para_kwh(tusd_mwh)
        te_kwh = _para_kwh(te_mwh)
        resultado.append(
            LinhaTarifaAneel(
                sigla=mapa["Sigla"],
                resolucao=mapa["Resolução ANEEL"],
                vigencia_inicio=_converter_data_excel(mapa["Início Vigência"]),
                vigencia_fim=_converter_data_excel(mapa["Fim Vigência"]),
                base_tarifaria=mapa["Base Tarifária"],
                subgrupo=mapa["Subgrupo"],
                modalidade=mapa["Modalidade"],
                classe=mapa["Classe"],
                subclasse=mapa["Subclasse"],
                detalhe=mapa["Detalhe"],
                unidade_origem=mapa["Unidade"],
                tusd_mwh=tusd_mwh,
                te_mwh=te_mwh,
                tusd_kwh=tusd_kwh,
                te_kwh=te_kwh,
                tusd_mais_te_kwh=tusd_kwh + te_kwh,
            )
        )

    return resultado


@lru_cache(maxsize=4)
def carregar_tabela_tarifas_versionada(
    caminho_proveniencia: Path = CAMINHO_PADRAO_PROVENIENCIA,
) -> TabelaTarifasVersionada:
    """Carrega ``proveniencia.json`` e a planilha ``.xlsx`` validando o hash SHA-256."""
    dados_prov = json.loads(caminho_proveniencia.read_text(encoding="utf-8"))
    proveniencia = ProvenienciaTarifas.model_validate(dados_prov)
    caminho_xlsx = caminho_proveniencia.parent / proveniencia.arquivo
    hash_calculado = hashlib.sha256(caminho_xlsx.read_bytes()).hexdigest()
    if hash_calculado.lower() != proveniencia.sha256.lower():
        raise ValueError(
            f"Integridade da tabela ANEEL falhou: SHA-256 esperado {proveniencia.sha256}, "
            f"obtido {hash_calculado}."
        )
    linhas = _ler_linhas_xlsx(caminho_xlsx)
    return TabelaTarifasVersionada(proveniencia=proveniencia, linhas=tuple(linhas))


def obter_tarifa_aplicacao_b1(
    mes_referencia: date,
    *,
    subclasse: str = "Residencial",
    detalhe: str = "Não se aplica",
    tabela: TabelaTarifasVersionada | None = None,
) -> LinhaTarifaAneel | None:
    """Retorna a linha de ``Tarifa de Aplicação`` B1 vigente na data de referência."""
    tabela_uso = tabela or carregar_tabela_tarifas_versionada()
    for linha in tabela_uso.linhas:
        if (
            linha.base_tarifaria == "Tarifa de Aplicação"
            and linha.subgrupo.upper() == "B1"
            and linha.modalidade == "Convencional"
            and linha.classe == "Residencial"
            and linha.subclasse.lower() == subclasse.lower()
            and linha.detalhe.lower() == detalhe.lower()
            and linha.vigencia_inicio <= mes_referencia <= linha.vigencia_fim
        ):
            return linha
    return None


def _resumo_fonte_data(proveniencia: ProvenienciaTarifas, resolucao: str | None = None) -> str:
    data_iso = proveniencia.data_download.isoformat()
    if resolucao:
        return f"fonte: {proveniencia.fonte} ({resolucao}), data da tabela: {data_iso}"
    return f"fonte: {proveniencia.fonte}, data da tabela: {data_iso}"


def construir_citacao_tabela(linha: LinhaTarifaAneel, proveniencia: ProvenienciaTarifas) -> Citacao:
    """Constrói a ``Citacao`` normativa exata para uma linha da tabela ANEEL."""
    return Citacao(
        ato=(
            f"{linha.resolucao} — {proveniencia.fonte} "
            f"(data da tabela: {proveniencia.data_download.isoformat()})"
        ),
        dispositivo=(
            f"{linha.sigla}, Subgrupo {linha.subgrupo}, {linha.classe}/{linha.subclasse}, "
            f"{linha.base_tarifaria} ({linha.detalhe})"
        ),
        vigencia_inicio=linha.vigencia_inicio,
        vigencia_fim=linha.vigencia_fim,
        url=proveniencia.url,
    )


def construir_citacao_proveniencia(proveniencia: ProvenienciaTarifas) -> Citacao:
    """Constrói uma ``Citacao`` geral da tabela versionada quando não há linha específica."""
    return Citacao(
        ato=(f"{proveniencia.fonte} (data da tabela: {proveniencia.data_download.isoformat()})"),
        dispositivo=proveniencia.filtros,
        vigencia_inicio=date(2026, 1, 1),
        vigencia_fim=None,
        url=proveniencia.url,
    )


def _distribuidora_compativel(distribuidora: str) -> bool:
    texto = distribuidora.strip().lower()
    return "neoenergia" in texto and ("bras" in texto or "df" in texto)


def _classificar_itens_energia(
    itens: list[ItemFatura],
) -> tuple[list[ItemFatura], list[ItemFatura], list[ItemFatura]]:
    itens_tusd: list[ItemFatura] = []
    itens_te: list[ItemFatura] = []
    itens_combinados: list[ItemFatura] = []

    for item in itens:
        if item.tarifa is None:
            continue
        desc = item.descricao.strip().lower()
        if any(termo in desc for termo in _TERMOS_IGNORADOS_CONSUMO):
            continue
        tem_tusd = "tusd" in desc
        tem_te = (
            desc == "te"
            or desc.endswith("-te")
            or desc.endswith(" te")
            or "tarifa de energia" in desc
            or "consumo te" in desc
        )
        if tem_tusd and not tem_te:
            itens_tusd.append(item)
        elif tem_te and not tem_tusd:
            itens_te.append(item)
        else:
            itens_combinados.append(item)

    return itens_tusd, itens_te, itens_combinados


def checar_tusd_te(
    fatura: Fatura,
    *,
    tabela: TabelaTarifasVersionada | None = None,
    subclasse: str = "Residencial",
) -> list[Achado]:
    """Compara a tarifa TUSD+TE impressa na fatura contra a tabela ANEEL versionada."""
    tabela_uso = tabela or carregar_tabela_tarifas_versionada()
    prov = tabela_uso.proveniencia
    meta_padrao = _resumo_fonte_data(prov)

    if not _distribuidora_compativel(fatura.distribuidora) or (
        fatura.grupo_tarifario.strip().upper() != "B1"
    ):
        return [
            Achado(
                item="Tarifa TUSD+TE",
                nivel=Nivel.B,
                descricao=(
                    "A tabela oficial versionada contempla apenas Neoenergia Brasília no "
                    f"subgrupo B1; a conferência tarifária foi interrompida ({meta_padrao})."
                ),
                citacoes=[construir_citacao_proveniencia(prov)],
                abstencao=True,
            )
        ]

    linha = obter_tarifa_aplicacao_b1(fatura.mes_referencia, subclasse=subclasse, tabela=tabela_uso)
    if linha is None:
        return [
            Achado(
                item="Tarifa TUSD+TE",
                nivel=Nivel.B,
                descricao=(
                    f"O mês de referência {fatura.mes_referencia.isoformat()} está fora do "
                    "período de vigência coberto pela tabela ANEEL versionada; a conferência "
                    f"foi interrompida ({meta_padrao})."
                ),
                citacoes=[construir_citacao_proveniencia(prov)],
                abstencao=True,
            )
        ]

    citacao = construir_citacao_tabela(linha, prov)
    meta_linha = _resumo_fonte_data(prov, linha.resolucao)
    itens_tusd, itens_te, itens_combinados = _classificar_itens_energia(fatura.itens)

    if itens_tusd and itens_te:
        assert itens_tusd[0].tarifa is not None and itens_te[0].tarifa is not None
        tarifa_cobrada = itens_tusd[0].tarifa + itens_te[0].tarifa
        tarifa_esperada = linha.tusd_mais_te_kwh
    elif itens_combinados:
        assert itens_combinados[0].tarifa is not None
        tarifa_cobrada = itens_combinados[0].tarifa
        tarifa_esperada = linha.tusd_mais_te_kwh
    elif itens_tusd:
        assert itens_tusd[0].tarifa is not None
        tarifa_cobrada = itens_tusd[0].tarifa
        tarifa_esperada = linha.tusd_kwh
    elif itens_te:
        assert itens_te[0].tarifa is not None
        tarifa_cobrada = itens_te[0].tarifa
        tarifa_esperada = linha.te_kwh
    else:
        return [
            Achado(
                item="Tarifa TUSD+TE",
                nivel=Nivel.B,
                descricao=(
                    "A fatura não discrimina tarifa unitária de consumo (TUSD/TE) para "
                    f"comparação contra a tabela oficial ({meta_linha})."
                ),
                citacoes=[citacao],
                abstencao=True,
            )
        ]

    confere = tarifa_cobrada == tarifa_esperada
    esperado_achado = tarifa_cobrada if confere else tarifa_esperada
    descricao = (
        f"A tarifa TUSD+TE impressa na fatura (R$ {tarifa_cobrada}/kWh) confere com a "
        f"Tarifa de Aplicação sem tributos da tabela oficial (R$ {tarifa_esperada}/kWh — "
        f"{meta_linha})."
        if confere
        else f"A tarifa TUSD+TE impressa na fatura (R$ {tarifa_cobrada}/kWh) diverge da "
        f"tabela oficial que conseguimos obter (R$ {tarifa_esperada}/kWh na Tarifa de "
        f"Aplicação sem tributos — {meta_linha})."
    )
    return [
        Achado(
            item="Tarifa TUSD+TE",
            nivel=Nivel.B,
            descricao=descricao,
            valor_esperado=esperado_achado,
            valor_cobrado=tarifa_cobrada,
            citacoes=[citacao],
        )
    ]


def _normalizar_nome_bandeira(bandeira: str) -> str:
    texto = bandeira.strip().lower()
    for prefixo in ("bandeira ", "acrés. band. ", "acres. band. ", "adicional bandeira "):
        if texto.startswith(prefixo):
            texto = texto[len(prefixo) :].strip()
    return texto


def _itens_bandeira(itens: list[ItemFatura]) -> list[ItemFatura]:
    return [item for item in itens if "band" in item.descricao.strip().lower()]


def checar_bandeira(
    fatura: Fatura,
    *,
    tabela: TabelaTarifasVersionada | None = None,
    referencia_bandeiras: Mapping[str, Decimal] | None = None,
) -> list[Achado]:
    """Confere a bandeira tarifária e seu adicional contra a referência oficial ANEEL."""
    tabela_uso = tabela or carregar_tabela_tarifas_versionada()
    prov = tabela_uso.proveniencia
    linha = obter_tarifa_aplicacao_b1(fatura.mes_referencia, tabela=tabela_uso)
    citacao = (
        construir_citacao_tabela(linha, prov)
        if linha is not None
        else construir_citacao_proveniencia(prov)
    )
    meta = _resumo_fonte_data(prov, linha.resolucao if linha is not None else None)
    mapa_bandeiras = (
        dict(referencia_bandeiras)
        if referencia_bandeiras is not None
        else VALORES_BANDEIRA_ANEEL_KWH
    )

    itens_band = _itens_bandeira(fatura.itens)
    bandeira_fatura = (
        _normalizar_nome_bandeira(fatura.bandeira) if fatura.bandeira is not None else None
    )

    if bandeira_fatura is None and not itens_band:
        return [
            Achado(
                item="Bandeira tarifária",
                nivel=Nivel.B,
                descricao=(
                    "A fatura não informa a bandeira tarifária nem apresenta linha de "
                    f"adicional de bandeira para conferência ({meta})."
                ),
                citacoes=[citacao],
                abstencao=True,
            )
        ]

    if bandeira_fatura is not None and bandeira_fatura not in mapa_bandeiras:
        return [
            Achado(
                item="Bandeira tarifária",
                nivel=Nivel.B,
                descricao=(
                    f"A bandeira tarifária informada ('{fatura.bandeira}') não consta na "
                    f"referência oficial utilizada para conferência ({meta})."
                ),
                citacoes=[citacao],
                abstencao=True,
            )
        ]

    # Se a fatura não informa o campo bandeira no cabeçalho, tenta inferir da linha.
    if bandeira_fatura is None and itens_band:
        desc_item = itens_band[0].descricao.strip().lower()
        for chave in mapa_bandeiras:
            if chave in desc_item:
                bandeira_fatura = chave
                break
        if bandeira_fatura is None:
            return [
                Achado(
                    item="Bandeira tarifária",
                    nivel=Nivel.B,
                    descricao=(
                        "A linha de bandeira tarifária não identifica o patamar aplicável "
                        f"para comparação com a referência oficial ({meta})."
                    ),
                    citacoes=[citacao],
                    abstencao=True,
                )
            ]

    assert bandeira_fatura is not None
    adicional_esperado = mapa_bandeiras[bandeira_fatura]

    if not itens_band:
        if bandeira_fatura == "verde":
            return [
                Achado(
                    item="Bandeira tarifária",
                    nivel=Nivel.B,
                    descricao=(
                        "A bandeira tarifária verde não possui cobrança adicional na fatura, "
                        f"em conformidade com a referência oficial ({meta})."
                    ),
                    valor_esperado=Decimal("0.00"),
                    valor_cobrado=Decimal("0.00"),
                    citacoes=[citacao],
                )
            ]
        return [
            Achado(
                item="Bandeira tarifária",
                nivel=Nivel.B,
                descricao=(
                    f"A fatura indica bandeira '{fatura.bandeira}', mas não discrimina linha "
                    "própria do adicional de bandeira nem a tabela exportada permite isolar "
                    f"o valor cobrado ({meta})."
                ),
                citacoes=[citacao],
                abstencao=True,
            )
        ]

    item_band = itens_band[0]
    if item_band.tarifa is not None:
        cobrado = item_band.tarifa
        esperado = adicional_esperado
        # Bandeira verde: 0.00 == 0.00000 em Decimal, preserva escala do item quando confere.
        confere = cobrado == esperado
        esperado_achado = cobrado if confere else esperado
        descricao = (
            f"O adicional da bandeira '{bandeira_fatura}' impresso na fatura "
            f"(R$ {cobrado}/kWh) confere com a tabela oficial ({meta})."
            if confere
            else f"O adicional da bandeira '{bandeira_fatura}' impresso na fatura "
            f"(R$ {cobrado}/kWh) diverge da tabela oficial que conseguimos obter "
            f"(R$ {esperado}/kWh sem tributos — {meta})."
        )
        return [
            Achado(
                item="Bandeira tarifária",
                nivel=Nivel.B,
                descricao=descricao,
                valor_esperado=esperado_achado,
                valor_cobrado=cobrado,
                citacoes=[citacao],
            )
        ]

    quantidade_ref = (
        item_band.quantidade if item_band.quantidade is not None else fatura.consumo_kwh
    )
    if quantidade_ref <= Decimal("0") and bandeira_fatura != "verde":
        return [
            Achado(
                item="Bandeira tarifária",
                nivel=Nivel.B,
                descricao=(
                    "A linha de bandeira tarifária não informa tarifa unitária nem consumo "
                    f"positivo para conferência ({meta})."
                ),
                citacoes=[citacao],
                abstencao=True,
            )
        ]

    valor_esperado_moeda = _arredondar_moeda(quantidade_ref * adicional_esperado)
    valor_cobrado_moeda = _arredondar_moeda(item_band.valor)
    confere = valor_cobrado_moeda == valor_esperado_moeda
    esperado_achado = item_band.valor if confere else valor_esperado_moeda
    descricao = (
        f"O valor cobrado de bandeira '{bandeira_fatura}' (R$ {item_band.valor}) confere "
        f"com a referência oficial ({meta})."
        if confere
        else f"O valor cobrado de bandeira '{bandeira_fatura}' (R$ {item_band.valor}) "
        f"diverge da tabela oficial que conseguimos obter (R$ {valor_esperado_moeda} "
        f"sem tributos — {meta})."
    )
    return [
        Achado(
            item="Bandeira tarifária",
            nivel=Nivel.B,
            descricao=descricao,
            valor_esperado=esperado_achado,
            valor_cobrado=item_band.valor,
            citacoes=[citacao],
        )
    ]


def analisar_nivel_b(
    fatura: Fatura,
    *,
    tabela: TabelaTarifasVersionada | None = None,
    referencia_bandeiras: Mapping[str, Decimal] | None = None,
) -> list[Achado]:
    """Executa as checagens de nível B (TUSD+TE e bandeira tarifária) com fonte e data."""
    tabela_uso = tabela or carregar_tabela_tarifas_versionada()
    achados: list[Achado] = []
    achados.extend(checar_tusd_te(fatura, tabela=tabela_uso))
    achados.extend(
        checar_bandeira(fatura, tabela=tabela_uso, referencia_bandeiras=referencia_bandeiras)
    )
    return achados


__all__ = [
    "CAMINHO_PADRAO_PROVENIENCIA",
    "LinhaTarifaAneel",
    "PASTA_TARIFAS",
    "ProvenienciaTarifas",
    "TabelaTarifasVersionada",
    "VALORES_BANDEIRA_ANEEL_KWH",
    "analisar_nivel_b",
    "carregar_tabela_tarifas_versionada",
    "checar_bandeira",
    "checar_tusd_te",
    "construir_citacao_proveniencia",
    "construir_citacao_tabela",
    "obter_tarifa_aplicacao_b1",
]
