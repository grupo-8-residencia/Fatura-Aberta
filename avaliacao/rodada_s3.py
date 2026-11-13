#!/usr/bin/env python3
"""Rodada S3 completa (issue #33): B1 (motor), B2 e B3 (LLM + RAG) e juiz, sobre o golden set.

Baselines, conforme `docs/avaliacao/index.md`:
- B1: motor determinístico puro (`fa_motor`), sem LLM.
- B2: LLM com RAG sem filtro de vigência.
- B3: LLM com RAG com filtro de vigência e com as saídas do motor no contexto.

Conjuntos: 200 faturas sintéticas (veredito por fatura) e 120 perguntas (artigo canônico citado ou
abstenção). Métricas com IC 95% (bootstrap, B = 10.000) e McNemar. O juiz (modelo de outra família)
roda nos 40 itens da calibração; as colunas humanas ficam vazias.

Uso (Ollama local, ADR-002):
    FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s3.py --etapa tudo
    .venv/bin/python avaliacao/rodada_s3.py --etapa b1            # só o motor, sem LLM
    FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s3.py --etapa faturas --limite 5
Sem `FA_LLM_PROVEDOR=ollama`, usa o cliente falso (só para testar a tubulação).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from auditar_cobertura import auditar, carregar, ids_esperados  # noqa: E402
from calibrar_juiz import escrever_csv, ler_csv  # noqa: E402
from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic, mcnemar  # noqa: E402

from fa_agentes import ClienteLLM, criar_cliente, metadados_rodada, verificar_linguagem  # noqa: E402
from fa_contratos import Achado, Fatura, ItemFatura  # noqa: E402
from fa_motor import analisar_nivel_a  # noqa: E402
from fa_rag import IndiceHibrido, carregar_corpus, responder  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
GOLDEN = RAIZ / "dados" / "golden-set"
SAIDA = Path(__file__).resolve().parent / "resultados" / "s3-rodada.json"
CACHE = Path(__file__).resolve().parent / "cache"
CSV_JUIZ = Path(__file__).resolve().parent / "anotacoes" / "juiz-40.csv"
TOP_K = 5
CONSULTA_FATURA = (
    "conferência da fatura de energia elétrica grupo B1: leituras, consumo, tarifa, bandeira "
    "tarifária, itens cobrados, total e impostos"
)

SISTEMA_FATURA = (
    "Você confere faturas de energia elétrica residencial (grupo B1) da Neoenergia Brasília. "
    "Use linguagem de evidência: descreva o que os números mostram. Nunca diga que algo é ilegal, "
    "nunca estime restituição ou ressarcimento e nunca oriente ação judicial. Confira com os dados "
    "da fatura e com os dispositivos fornecidos. Faça as contas no campo 'analise' (até 5 linhas) "
    "ANTES dos vereditos. Confira: (1) leitura atual menos leitura anterior contra o consumo "
    "informado; (2) quantidade vezes tarifa contra o valor de cada linha; (3) a soma das linhas "
    "contra o total; (4) a alíquota de ICMS informada. Em 'achados' liste SOMENTE os itens com "
    "divergência ('diverge_A') ou que você não consegue conferir ('abstem'), cada um com uma frase "
    "curta; se tudo confere, liste um único achado com item 'Fatura' e veredito 'confere'. Cite em "
    "'citacoes' apenas ids de dispositivos fornecidos que você realmente usou (pode ser "
    "vazio). Use 'diverge_A' só quando a divergência estiver nos próprios números da fatura."
)
SISTEMA_PERGUNTA = (
    "Você responde perguntas sobre a regulação de energia elétrica residencial (grupo B1, Distrito "
    "Federal) usando SOMENTE os dispositivos fornecidos. Cite os ids dos dispositivos que "
    "sustentam a resposta. Se os dispositivos não cobrirem a pergunta, ou não valerem na data da "
    "pergunta, use abstencao = true, deixe a resposta vazia e não cite nada. Use linguagem de "
    "evidência: nunca diga que algo é ilegal, nunca estime restituição ou ressarcimento e nunca "
    "oriente ação judicial. Raciocine em 'analise' (até 3 linhas) e responda em até 3 frases."
)

SISTEMA_PERGUNTA_PURO = (
    "Você responde perguntas sobre a regulação de energia elétrica residencial (grupo B1, "
    "Distrito Federal) a partir do que você sabe, SEM consultar documentos. Em 'citacoes' "
    "indique a norma e o dispositivo em que se apoia (por exemplo, 'REN ANEEL 1.000/2021, "
    "art. 323'). Se você não sabe ou não tem como confirmar, use abstencao = true, deixe a "
    "resposta vazia e não cite nada. Use linguagem de evidência: nunca diga que algo é ilegal, "
    "nunca estime restituição ou ressarcimento e nunca oriente ação judicial. Raciocine em "
    "'analise' (até 3 linhas) e responda em até 3 frases."
)
SISTEMA_FATURA_PURO = (
    SISTEMA_FATURA
    + " Não há dispositivos fornecidos nem resultados de motor: use só os números da fatura e "
    "deixe 'citacoes' vazio."
)
SISTEMA_JUIZ = (
    "Você é um auditor. Receba a evidência e a saída de um sistema. Decomponha a saída em "
    "proposições atômicas (normativas ou factuais) e classifique cada uma como suportada (está nos "
    "dispositivos ou nos dados da fatura fornecidos) ou sem suporte. Seja literal: o que não "
    "aparece na evidência é sem suporte."
)

ESQUEMA_FATURA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "analise": {"type": "string"},
        "achados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "veredito": {"type": "string", "enum": ["confere", "diverge_A", "abstem"]},
                    "descricao": {"type": "string"},
                    "citacoes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["item", "veredito", "descricao", "citacoes"],
            },
        },
    },
    "required": ["analise", "achados"],
}
ESQUEMA_PERGUNTA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "analise": {"type": "string"},
        "resposta": {"type": "string"},
        "abstencao": {"type": "boolean"},
        "citacoes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["analise", "resposta", "abstencao", "citacoes"],
}
ESQUEMA_JUIZ: dict[str, Any] = {
    "type": "object",
    "properties": {
        "proposicoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"texto": {"type": "string"}, "suportada": {"type": "boolean"}},
                "required": ["texto", "suportada"],
            },
        }
    },
    "required": ["proposicoes"],
}


# --------------------------------------------------------------------------- dados


def ler_jsonl(caminho: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in caminho.read_text(encoding="utf-8").splitlines() if x.strip()]


def converter_fatura(r: dict[str, Any]) -> Fatura:
    def dec(v: str | None) -> Decimal | None:
        return None if v is None else Decimal(v)

    return Fatura(
        distribuidora=r["distribuidora"],
        grupo_tarifario=r["grupo_tarifario"],
        mes_referencia=date.fromisoformat(r["mes_referencia"]),
        leitura_anterior=dec(r["leitura_anterior"]),
        leitura_atual=dec(r["leitura_atual"]),
        consumo_kwh=Decimal(r["consumo_kwh"]),
        bandeira=r["bandeira"],
        aliquota_icms=dec(r["aliquota_icms"]),
        itens=[
            ItemFatura(
                descricao=i["descricao"],
                quantidade=dec(i["quantidade"]),
                tarifa=dec(i["tarifa"]),
                valor=Decimal(i["valor"]),
            )
            for i in r["itens"]
        ],
        total=Decimal(r["total"]),
    )


def texto_fatura(r: dict[str, Any]) -> str:
    linhas = [
        f"Mês de referência: {r['mes_referencia'][:7]}",
        f"Leitura anterior: {r['leitura_anterior']} kWh",
        f"Leitura atual: {r['leitura_atual']} kWh",
        f"Consumo informado: {r['consumo_kwh']} kWh",
        f"Bandeira tarifária: {r['bandeira']}",
        f"Alíquota de ICMS informada: {r['aliquota_icms']}",
        "Itens:",
    ]
    for i in r["itens"]:
        q, t = i["quantidade"], i["tarifa"]
        detalhe = f"{q} x {t} = " if q is not None and t is not None else ""
        linhas.append(f"- {i['descricao']}: {detalhe}R$ {i['valor']}")
    linhas.append(f"Total informado: R$ {r['total']}")
    return "\n".join(linhas)


def contexto_rag(indice: IndiceHibrido, consulta: str, data: date, *, filtrar: bool) -> list[Any]:
    return list(
        indice.buscar(
            consulta, data_referencia=data, top_k=TOP_K, filtrar_vigencia=filtrar,
            um_por_dispositivo=True,
        )
    )  # fmt: skip


def texto_contexto(resultados: Sequence[Any]) -> str:
    blocos = []
    for r in resultados:
        c = r.documento.citacao
        fim = c.vigencia_fim.isoformat() if c.vigencia_fim else "em vigor"
        blocos.append(
            f"[{r.documento.id}] {c.ato}, {c.dispositivo} (vigência {c.vigencia_inicio} a {fim}):\n"
            f"{r.documento.texto}"
        )
    return "\n\n".join(blocos) if blocos else "(nenhum dispositivo recuperado)"


def _artigo(doc_id: str) -> str:
    return doc_id.split("::")[0]


# --------------------------------------------------------------------------- B1


def divergente(a: Achado) -> bool:
    return (
        not a.abstencao
        and a.valor_esperado is not None
        and a.valor_cobrado is not None
        and a.valor_esperado != a.valor_cobrado
    )


def veredito_motor(achados: Sequence[Achado]) -> str:
    return "diverge_A" if any(divergente(a) for a in achados) else "confere"


def rodar_b1(faturas: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    saida = []
    for r in faturas:
        achados = analisar_nivel_a(converter_fatura(r))
        v = veredito_motor(achados)
        saida.append(
            {
                "id": r["id"],
                "veredito": v,
                "acerto": v == r["gabarito_fatura"],
                "anomalia": r["anomalia_injetada"],
                "linguagem": [x.termo for a in achados for x in verificar_linguagem(a.descricao)],
            }
        )
    return saida


def resumo_motor(achados: Sequence[Achado]) -> str:
    linhas = []
    for a in achados:
        extra = ""
        if a.valor_esperado is not None and a.valor_cobrado is not None:
            extra = f" (esperado {a.valor_esperado}; cobrado {a.valor_cobrado})"
        marca = "ABSTENÇÃO" if a.abstencao else ("DIVERGE" if divergente(a) else "CONFERE")
        linhas.append(f"- {marca} | {a.item}: {a.descricao}{extra}")
    return "\n".join(linhas)


# --------------------------------------------------------------------------- LLM


TENTATIVAS_EXTRAS = 2  # só para falha de comunicação ou tempo esgotado, com os mesmos parâmetros
PAUSA_NOVA_TENTATIVA_S = 5.0


def classificar_erro(erro: BaseException) -> str:
    """Tipo da falha: comunicacao, timeout, modelo_indisponivel ou erro_cliente."""
    if isinstance(erro, TimeoutError):
        return "timeout"
    texto = str(erro).lower()
    if "timed out" in texto or "timeout" in texto:
        return "timeout"
    if isinstance(erro, RuntimeError) and "não está instalado" in str(erro):
        return "modelo_indisponivel"
    if isinstance(erro, OSError):  # URLError, ConnectionError e afins
        return "comunicacao"
    return "erro_cliente"


def _chamar(
    cliente: ClienteLLM, sistema: str, prompt: str, esquema: dict[str, Any]
) -> dict[str, Any]:
    """Uma chamada ao LLM. Falha de comunicação ou timeout é refeita até TENTATIVAS_EXTRAS vezes
    com os mesmos parâmetros; toda tentativa fica registrada. JSON inválido nunca é refeito: a
    resposta desfavorável continua contando como inválida."""
    t0 = time.perf_counter()
    falhas: list[dict[str, str]] = []
    r = None
    for tentativa in range(1 + TENTATIVAS_EXTRAS):
        try:
            r = cliente.gerar(sistema=sistema, prompt=prompt, esquema=esquema)
            break
        except Exception as erro:  # a rodada segue e registra
            tipo = classificar_erro(erro)
            falhas.append({"tipo": tipo, "mensagem": f"{type(erro).__name__}: {erro}"[:300]})
            if tipo not in ("comunicacao", "timeout") or tentativa == TENTATIVAS_EXTRAS:
                return {
                    "valido": False,
                    "erro": falhas[-1]["mensagem"],
                    "erro_tipo": tipo,
                    "tentativas": falhas,
                    "duracao_s": 0.0,
                }
            time.sleep(PAUSA_NOVA_TENTATIVA_S)
    assert r is not None
    base: dict[str, Any] = {
        "duracao_s": r.duracao_s or round(time.perf_counter() - t0, 3),
        "tokens_saida": r.tokens_saida,
        "do_cache": r.do_cache,
    }
    if falhas:
        base["tentativas"] = falhas  # tentativas anteriores que falharam antes de dar certo
    try:
        dados = r.json()
    except ValueError:
        return {**base, "valido": False, "erro": "JSON inválido", "erro_tipo": "json_invalido",
                "bruto": r.texto[:300]}  # fmt: skip
    if not isinstance(dados, dict):
        return {**base, "valido": False, "erro": "JSON não é objeto", "erro_tipo": "esquema",
                "bruto": r.texto[:300]}  # fmt: skip
    return {**base, "valido": True, "dados": dados}


def _limpa_id(c: object) -> str:
    return str(c).strip().strip("[]").strip()


def _paralelo(
    itens: Sequence[Any],
    fn: Callable[[Any], dict[str, Any]],
    n: int,
    progresso: Callable[[str], None],
    rotulo: str,
) -> list[dict[str, Any]]:
    """Executa ``fn`` sobre os itens com até ``n`` threads, mantendo a ordem de entrada."""
    trava, feitos = threading.Lock(), [0]

    def envolto(x: Any) -> dict[str, Any]:
        r = fn(x)
        with trava:
            feitos[0] += 1
            resultado = r.get("veredito", r.get("acerto"))
            progresso(f"{rotulo} {feitos[0]}/{len(itens)} {r['id']} -> {resultado}")
        return r

    if n <= 1:
        return [envolto(x) for x in itens]
    with ThreadPoolExecutor(max_workers=n) as ex:
        return list(ex.map(envolto, itens))


def rodar_llm_faturas(
    cliente: ClienteLLM, indice: IndiceHibrido, faturas: Sequence[dict[str, Any]], baseline: str,
    progresso: Callable[[str], None], paralelo: int = 1,
) -> list[dict[str, Any]]:  # fmt: skip
    def uma(r: dict[str, Any]) -> dict[str, Any]:
        data = date.fromisoformat(r["mes_referencia"])
        ctx = contexto_rag(indice, CONSULTA_FATURA, data, filtrar=baseline == "B3")
        prompt = f"FATURA\n{texto_fatura(r)}\n\nDISPOSITIVOS RECUPERADOS\n{texto_contexto(ctx)}\n"
        if baseline == "B3":
            motor = resumo_motor(analisar_nivel_a(converter_fatura(r)))
            prompt += f"\nRESULTADOS DO MOTOR DETERMINÍSTICO (fatos já verificados)\n{motor}\n"
        res = _chamar(cliente, SISTEMA_FATURA, prompt, ESQUEMA_FATURA)
        item: dict[str, Any] = {
            "id": r["id"], "baseline": baseline, "anomalia": r["anomalia_injetada"],
            "contexto_ids": [x.documento.id for x in ctx], **res,
        }  # fmt: skip
        if not res["valido"]:
            return item | {
                "veredito": "invalido", "acerto": False, "linguagem": [], "citacoes_inventadas": [],
            }  # fmt: skip
        achados = [a for a in res["dados"].get("achados", []) if isinstance(a, dict)]
        vereditos = [a.get("veredito") for a in achados]
        if "diverge_A" in vereditos:
            v = "diverge_A"
        elif vereditos and any(x == "confere" for x in vereditos):
            v = "confere"
        else:
            v = "abstem"
        textos = " ".join(str(a.get("descricao", "")) for a in achados)
        ids_ctx = {x.documento.id for x in ctx}
        citados = [_limpa_id(c) for a in achados for c in a.get("citacoes", [])]
        return item | {
            "veredito": v,
            "acerto": v == r["gabarito_fatura"],
            "linguagem": [x.termo for x in verificar_linguagem(textos)],
            "citacoes_inventadas": sorted({c for c in citados if c not in ids_ctx}),
        }

    return _paralelo(faturas, uma, paralelo, progresso, f"{baseline} fatura")


def rodar_llm_perguntas(
    cliente: ClienteLLM, indice: IndiceHibrido, perguntas: Sequence[dict[str, Any]], baseline: str,
    progresso: Callable[[str], None], paralelo: int = 1,
) -> list[dict[str, Any]]:  # fmt: skip
    def uma(p: dict[str, Any]) -> dict[str, Any]:
        data = date.fromisoformat(p["data_referencia"])
        ctx = contexto_rag(indice, p["pergunta"], data, filtrar=baseline == "B3")
        prompt = (
            f"DATA DE REFERÊNCIA: {p['data_referencia']}\nPERGUNTA: {p['pergunta']}\n\n"
            f"DISPOSITIVOS RECUPERADOS\n{texto_contexto(ctx)}\n"
        )
        res = _chamar(cliente, SISTEMA_PERGUNTA, prompt, ESQUEMA_PERGUNTA)
        por_id = {x.documento.id: x for x in ctx}
        item: dict[str, Any] = {
            "id": p["id"], "baseline": baseline, "tipo": p["tipo"],
            "contexto_ids": list(por_id), **res,
        }  # fmt: skip
        if not res["valido"]:
            return item | {
                "abstencao": None, "citacoes": [], "acerto": False, "citacoes_inventadas": [],
                "citacoes_fora_de_vigencia": [], "linguagem": [],
            }  # fmt: skip
        d = res["dados"]
        abst = bool(d.get("abstencao"))
        cit = [_limpa_id(c) for c in d.get("citacoes", [])]
        canon = set(p["citacao_canonica"])
        if p["abstencao_esperada"]:
            acerto = abst
        else:
            acerto = (not abst) and any(_artigo(c) in canon for c in cit)
        return item | {
            "abstencao": abst,
            "citacoes": cit,
            "acerto": acerto,
            "citacoes_inventadas": [c for c in cit if c not in por_id],
            "citacoes_fora_de_vigencia": [
                c for c in cit if c in por_id and not por_id[c].documento.vigente_em(data)
            ],
            "linguagem": [x.termo for x in verificar_linguagem(str(d.get("resposta", "")))],
        }

    return _paralelo(perguntas, uma, paralelo, progresso, f"{baseline} pergunta")


# --------------------------------------------------------------------------- testes extras

_CHAVES_ATO = {
    "ren1000": r"1\.?000|\bREN\b",
    "cdc": r"8\.?078|\bCDC\b|Defesa do Consumidor",
    "df7888": r"7\.?888",
}
_DOCS_CORPUS: dict[str, Any] = {}


def cita_dispositivo(texto: str, canonicos: set[str]) -> bool:
    """Diz se uma citação livre (ex.: 'REN 1.000/2021, art. 323') aponta para um artigo canônico."""
    if not _DOCS_CORPUS:
        _DOCS_CORPUS.update({d.id: d for d in carregar_corpus()})
    for cid in canonicos:
        doc = _DOCS_CORPUS.get(cid)
        if doc is None:
            continue
        num = re.search(r"art\.\s*(\d+)", str(doc.citacao.dispositivo))
        chave = _CHAVES_ATO.get(cid.split("-")[0])
        if (
            num
            and chave
            and re.search(rf"art(?:igo|\.)?\s*{num.group(1)}(?!\d)", texto, re.I)
            and re.search(chave, texto, re.I)
        ):
            return True
    return False


def rodar_llm_puro_perguntas(
    cliente: ClienteLLM, perguntas: Sequence[dict[str, Any]],
    progresso: Callable[[str], None], paralelo: int = 1,
) -> list[dict[str, Any]]:  # fmt: skip
    """Teste 1: LLM sem RAG. Cita de memória; o acerto exige apontar o artigo canônico."""

    def uma(p: dict[str, Any]) -> dict[str, Any]:
        prompt = f"DATA DE REFERÊNCIA: {p['data_referencia']}\nPERGUNTA: {p['pergunta']}\n"
        res = _chamar(cliente, SISTEMA_PERGUNTA_PURO, prompt, ESQUEMA_PERGUNTA)
        item: dict[str, Any] = {"id": p["id"], "baseline": "LLM", "tipo": p["tipo"], **res}
        vazio: dict[str, Any] = {
            "abstencao": None, "citacoes": [], "acerto": False, "citacoes_inventadas": [],
            "citacoes_fora_de_vigencia": [], "linguagem": [], "cita_algo_errado": False,
        }  # fmt: skip
        if not res["valido"]:
            return item | vazio
        d = res["dados"]
        abst = bool(d.get("abstencao"))
        cit = [str(c) for c in d.get("citacoes", [])]
        canon = set(p["citacao_canonica"])
        acertou_cit = any(cita_dispositivo(c, canon) for c in cit)
        acerto = abst if p["abstencao_esperada"] else ((not abst) and acertou_cit)
        return item | {
            "abstencao": abst,
            "citacoes": cit,
            "acerto": acerto,
            "citacoes_inventadas": [],
            "citacoes_fora_de_vigencia": [],
            "linguagem": [x.termo for x in verificar_linguagem(str(d.get("resposta", "")))],
            "cita_algo_errado": (not abst) and bool(cit) and not acertou_cit,
        }

    return _paralelo(perguntas, uma, paralelo, progresso, "LLM puro pergunta")


def rodar_llm_puro_faturas(
    cliente: ClienteLLM, faturas: Sequence[dict[str, Any]],
    progresso: Callable[[str], None], paralelo: int = 1,
) -> list[dict[str, Any]]:  # fmt: skip
    """Teste 1 nas faturas: LLM só com os números da fatura, sem RAG e sem motor."""

    def uma(r: dict[str, Any]) -> dict[str, Any]:
        res = _chamar(cliente, SISTEMA_FATURA_PURO, f"FATURA\n{texto_fatura(r)}\n", ESQUEMA_FATURA)
        item: dict[str, Any] = {
            "id": r["id"], "baseline": "LLM", "anomalia": r["anomalia_injetada"],
            "contexto_ids": [], **res,
        }  # fmt: skip
        if not res["valido"]:
            return item | {
                "veredito": "invalido", "acerto": False, "linguagem": [], "citacoes_inventadas": [],
            }  # fmt: skip
        achados = [a for a in res["dados"].get("achados", []) if isinstance(a, dict)]
        vereditos = [a.get("veredito") for a in achados]
        if "diverge_A" in vereditos:
            v = "diverge_A"
        elif any(x == "confere" for x in vereditos):
            v = "confere"
        else:
            v = "abstem"
        textos = " ".join(str(a.get("descricao", "")) for a in achados)
        return item | {
            "veredito": v,
            "acerto": v == r["gabarito_fatura"],
            "linguagem": [x.termo for x in verificar_linguagem(textos)],
            "citacoes_inventadas": [],
        }

    return _paralelo(faturas, uma, paralelo, progresso, "LLM puro fatura")


def rodar_rag_extrativo_perguntas(
    indice: IndiceHibrido, perguntas: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Teste 2: RAG sem LLM. Filtra a vigência, recupera e responde só com trechos literais."""
    saida = []
    for p in perguntas:
        data = date.fromisoformat(p["data_referencia"])
        t0 = time.perf_counter()
        top = indice.buscar(
            p["pergunta"], data_referencia=data, top_k=TOP_K, um_por_dispositivo=True
        )
        r = responder(top)
        citados = {_artigo(i) for i in r.ids_fontes}
        canon = set(p["citacao_canonica"])
        acerto = (
            r.abstencao
            if p["abstencao_esperada"]
            else ((not r.abstencao) and bool(citados & canon))
        )
        saida.append(
            {
                "id": p["id"], "baseline": "RAG", "tipo": p["tipo"], "valido": True,
                "abstencao": r.abstencao, "citacoes": list(r.ids_fontes), "acerto": acerto,
                "citacoes_inventadas": [], "citacoes_fora_de_vigencia": [],
                "linguagem": [x.termo for x in verificar_linguagem(r.texto)],
                "duracao_s": round(time.perf_counter() - t0, 4), "do_cache": False,
                "recuperou_canonico": bool({_artigo(x.documento.id) for x in top} & canon),
            }
        )  # fmt: skip
    return saida


# --------------------------------------------------------------------------- métricas


def _ic(valores: Sequence[bool]) -> dict[str, float]:
    ic = bootstrap_ic([float(v) for v in valores], b=B_PADRAO, semente=SEMENTE_PADRAO)
    return {"estimativa": ic.estimativa, "ic95_inf": ic.inferior, "ic95_sup": ic.superior}


def _mc(a: Sequence[bool], b: Sequence[bool]) -> dict[str, Any]:
    r = mcnemar(a, b)
    return {
        "n01_primeiro_erra_segundo_acerta": r.n01, "n10_primeiro_acerta_segundo_erra": r.n10,
        "chi2_edwards": r.chi2, "p_valor": r.p_valor, "p_exato": r.p_exato,
        "significativo_5pct": r.significativo,
    }  # fmt: skip


def metricas_faturas(res: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for b, itens in res.items():
        com = [i for i in itens if i["anomalia"]]
        sem = [i for i in itens if not i["anomalia"]]
        saida[b] = {
            "n": len(itens),
            "acerto_por_fatura": _ic([i["acerto"] for i in itens]),
            "deteccao_nas_faturas_com_anomalia": _ic([i["veredito"] == "diverge_A" for i in com])
            if com
            else None,
            "falso_alarme_nas_faturas_corretas": _ic([i["veredito"] == "diverge_A" for i in sem])
            if sem
            else None,
            "respostas_invalidas": sum(1 for i in itens if i.get("veredito") == "invalido"),
            "violacoes_rf15": sum(1 for i in itens if i.get("linguagem")),
            "citacoes_inventadas": sum(1 for i in itens if i.get("citacoes_inventadas")),
            "duracao_media_s": round(
                sum(i.get("duracao_s", 0.0) for i in itens) / max(len(itens), 1), 2
            ),
        }
        por_tipo: dict[str, list[bool]] = {}
        for i in com:
            por_tipo.setdefault(i["anomalia"], []).append(i["veredito"] == "diverge_A")
        saida[b]["deteccao_por_tipo"] = {k: sum(v) / len(v) for k, v in sorted(por_tipo.items())}
    pares = {b: [i["acerto"] for i in itens] for b, itens in res.items()}
    comparacoes: dict[str, Any] = {}
    for a, b in (("B2", "B3"), ("B1", "B3"), ("B1", "B2")):
        if a in pares and b in pares and len(pares[a]) == len(pares[b]):
            comparacoes[f"{b}_vs_{a}"] = _mc(pares[a], pares[b])
    saida["mcnemar"] = comparacoes
    return saida


def metricas_perguntas(res: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    saida: dict[str, Any] = {}
    for b, itens in res.items():
        saida[b] = {
            "n": len(itens),
            "acerto": _ic([i["acerto"] for i in itens]),
            "acerto_por_tipo": {
                t: sum(i["acerto"] for i in itens if i["tipo"] == t)
                / max(sum(1 for i in itens if i["tipo"] == t), 1)
                for t in sorted({i["tipo"] for i in itens})
            },
            "respostas_invalidas": sum(1 for i in itens if not i["valido"]),
            "violacoes_rf15": sum(1 for i in itens if i["linguagem"]),
            "citacoes_inventadas": sum(1 for i in itens if i["citacoes_inventadas"]),
            "itens_com_citacao_fora_de_vigencia": sum(
                1 for i in itens if i["citacoes_fora_de_vigencia"]
            ),
            "duracao_media_s": round(
                sum(i.get("duracao_s", 0.0) for i in itens) / max(len(itens), 1), 2
            ),
        }
    if "B2" in res and "B3" in res and len(res["B2"]) == len(res["B3"]):
        saida["mcnemar"] = {
            "B3_vs_B2": _mc([i["acerto"] for i in res["B2"]], [i["acerto"] for i in res["B3"]])
        }
    return saida


# --------------------------------------------------------------------------- juiz


def evidencia_item(
    item_id: str,
    faturas: dict[str, dict[str, Any]],
    perguntas: dict[str, dict[str, Any]],
    indice: IndiceHibrido,
    contexto_ids: Sequence[str],
) -> str:
    docs = {d.id: d for d in indice.documentos}
    trechos = "\n".join(f"[{c}] {docs[c].texto}" for c in contexto_ids if c in docs)
    if item_id in faturas:
        return f"FATURA\n{texto_fatura(faturas[item_id])}\n\nDISPOSITIVOS\n{trechos}"
    p = perguntas[item_id]
    return f"PERGUNTA: {p['pergunta']}\n\nDISPOSITIVOS\n{trechos}"


def texto_saida(item: dict[str, Any]) -> str:
    d = item.get("dados") or {}
    if "achados" in d:
        return "\n".join(
            f"[{a.get('veredito')}] {a.get('item')}: {a.get('descricao')}"
            for a in d["achados"] if isinstance(a, dict)
        )  # fmt: skip
    return str(d.get("resposta", "") or "(abstenção)")


def rodar_juiz(
    juiz: ClienteLLM, itens_csv: list[dict[str, str]], b3: dict[str, dict[str, Any]],
    faturas: dict[str, dict[str, Any]], perguntas: dict[str, dict[str, Any]],
    indice: IndiceHibrido, progresso: Callable[[str], None],
) -> list[dict[str, str]]:  # fmt: skip
    for n, linha in enumerate(itens_csv, 1):
        i = b3.get(linha["item_id"])
        if i is None or not i.get("valido"):
            linha["saida_do_sistema"] = "(sem saída válida do B3)"
            continue
        evid = evidencia_item(linha["item_id"], faturas, perguntas, indice, i["contexto_ids"])
        saida = texto_saida(i)
        linha["saida_do_sistema"], linha["evidencia"] = saida, evid
        r = _chamar(
            juiz, SISTEMA_JUIZ, f"EVIDÊNCIA\n{evid}\n\nSAÍDA DO SISTEMA\n{saida}\n", ESQUEMA_JUIZ
        )
        if r["valido"]:
            props = [p for p in r["dados"].get("proposicoes", []) if isinstance(p, dict)]
            linha["veredito_juiz"] = (
                "sem_suporte" if any(not p.get("suportada", False) for p in props) else "suportada"
            )
            linha["proposicoes_juiz"] = json.dumps(props, ensure_ascii=False)
        progresso(f"juiz {n}/{len(itens_csv)} {linha['item_id']} -> {linha.get('veredito_juiz')}")
    return itens_csv


# --------------------------------------------------------------------------- CLI


def _carregar_saida(caminho: Path) -> dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}


def _gravar(dados: dict[str, Any], caminho: Path) -> None:
    """Grava por arquivo temporário e troca atômica: uma interrupção não deixa JSON pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(caminho.name + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, caminho)


@contextmanager
def trava_de_rodada(caminho: Path) -> Iterator[None]:
    """Impede duas rodadas ao mesmo tempo no mesmo arquivo de saída (PID no arquivo de trava)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        try:
            pid = int(caminho.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, ProcessLookupError):
            caminho.unlink(missing_ok=True)  # trava velha de processo que não existe mais
        except PermissionError:
            raise RuntimeError(f"Já há uma rodada em andamento (trava {caminho})") from None
        else:
            raise RuntimeError(f"Já há uma rodada em andamento (PID {pid}, trava {caminho})")
    caminho.write_text(str(os.getpid()), encoding="utf-8")
    try:
        yield
    finally:
        caminho.unlink(missing_ok=True)


PRIVADO_JUIZ = RAIZ / ".local" / "juiz" / "veredito-juiz-40.json"
COLUNAS_DO_JUIZ = ("veredito_juiz", "proposicoes_juiz")


def separar_veredito_juiz(
    linhas: Sequence[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Tira o veredito e as proposições do juiz das linhas versionadas.

    Os avaliadores humanos não podem ver a opinião do juiz. As linhas devolvidas ficam sem essas
    colunas; o conteúdo vai para o arquivo privado, usado só na calibração depois que as 80
    decisões humanas estiverem travadas.
    """
    cegas, privado = [], {}
    for linha in linhas:
        privado[linha["item_id"]] = {c: linha.get(c, "") for c in COLUNAS_DO_JUIZ}
        cegas.append({**linha, **dict.fromkeys(COLUNAS_DO_JUIZ, "")})
    return cegas, privado


def gravar_privado_juiz(privado: dict[str, dict[str, str]], caminho: Path | None = None) -> None:
    caminho = caminho or PRIVADO_JUIZ
    existente = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    for item, v in privado.items():
        if v.get("veredito_juiz") or item not in existente:
            existente[item] = v  # não apaga um veredito já guardado com uma linha em branco
    _gravar(existente, caminho)


def cegar_arquivos(saida: Path) -> int:
    """Move o veredito do juiz do CSV e do JSON da rodada para o arquivo privado."""
    if CSV_JUIZ.exists():
        cegas, privado = separar_veredito_juiz(ler_csv(CSV_JUIZ))
        gravar_privado_juiz(privado)
        escrever_csv(CSV_JUIZ, cegas)
    dados = _carregar_saida(saida)
    if dados.get("juiz_calibracao"):
        dados["juiz_calibracao"], privado = separar_veredito_juiz(dados["juiz_calibracao"])
        gravar_privado_juiz(privado)
        _gravar(dados, saida)
    print(f"Veredito do juiz guardado em {PRIVADO_JUIZ} (fora do Git)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        "--etapa",
        choices=["b1", "faturas", "perguntas", "juiz", "tudo", "extra", "cegar", "completa"],
        default="tudo",
        help="completa = b1, B2/B3, LLM puro, RAG extrativo, juiz (cego) e auditoria de cobertura",
    )
    ap.add_argument("--limite", type=int, default=None, help="só os N primeiros itens (teste)")
    ap.add_argument("--saida", type=Path, default=SAIDA)
    ap.add_argument("--paralelo", type=int, default=3, help="chamadas simultâneas ao LLM")
    ap.add_argument(
        "--limite-faturas-llm",
        type=int,
        default=None,
        help="chamadas de LLM só nas N primeiras faturas e nas dos itens do juiz",
    )
    args = ap.parse_args(argv)
    saida = args.saida
    if args.etapa == "cegar":
        return cegar_arquivos(saida)
    with trava_de_rodada(saida.with_suffix(".lock")):
        return _executar(args)


def _executar(args: argparse.Namespace) -> int:
    saida: Path = args.saida
    completa = args.etapa == "completa"
    etapa = "tudo" if completa else args.etapa

    faturas = ler_jsonl(GOLDEN / "faturas_sinteticas.jsonl")[: args.limite]
    perguntas = ler_jsonl(GOLDEN / "perguntas.jsonl")[: args.limite]
    faturas_llm = faturas
    if args.limite_faturas_llm is not None:
        ids_juiz = {r["item_id"] for r in ler_csv(CSV_JUIZ)} if CSV_JUIZ.exists() else set()
        faturas_llm = faturas[: args.limite_faturas_llm] + [
            f for f in faturas[args.limite_faturas_llm :] if f["id"] in ids_juiz
        ]
    indice = IndiceHibrido.do_corpus()
    gerador = criar_cliente("gerador", cache_dir=CACHE)
    juiz = criar_cliente("juiz", cache_dir=CACHE)

    def say(msg: str) -> None:
        print(msg, flush=True)

    dados = _carregar_saida(saida)
    dados["cabecalho"] = metadados_rodada(
        {"gerador": gerador, "juiz": juiz}, checksums=GOLDEN / "checksums.sha256", raiz=RAIZ
    )
    dados["cabecalho"]["semente_llm"] = 42
    dados["cabecalho"]["semente_bootstrap"] = SEMENTE_PADRAO
    dados["cabecalho"]["limite"] = args.limite
    dados["cabecalho"]["faturas_llm"] = len(faturas_llm)

    if etapa in ("b1", "faturas", "tudo"):
        dados.setdefault("faturas", {})["B1"] = rodar_b1(faturas_llm)
        dados["b1_200_faturas"] = rodar_b1(faturas)
        n_ok = sum(i["acerto"] for i in dados["faturas"]["B1"])
        say(f"B1: {n_ok}/{len(faturas_llm)} faturas certas")
    if etapa in ("perguntas", "tudo"):
        dados.setdefault("perguntas", {})
        for b in ("B2", "B3"):
            dados["perguntas"][b] = rodar_llm_perguntas(
                gerador, indice, perguntas, b, say, args.paralelo
            )
            _gravar(dados, saida)
    if etapa in ("faturas", "tudo"):
        for b in ("B2", "B3"):
            dados["faturas"][b] = rodar_llm_faturas(
                gerador, indice, faturas_llm, b, say, args.paralelo
            )
            _gravar(dados, saida)
    if etapa == "extra" or completa:
        dados.setdefault("perguntas", {})
        dados.setdefault("faturas", {})
        dados["perguntas"]["RAG"] = rodar_rag_extrativo_perguntas(indice, perguntas)
        say(f"RAG extrativo: {sum(i['acerto'] for i in dados['perguntas']['RAG'])} acertos")
        dados["perguntas"]["LLM"] = rodar_llm_puro_perguntas(gerador, perguntas, say, args.paralelo)
        _gravar(dados, saida)
        dados["faturas"]["LLM"] = rodar_llm_puro_faturas(gerador, faturas_llm, say, args.paralelo)
        _gravar(dados, saida)
    if etapa in ("juiz", "tudo") and CSV_JUIZ.exists():
        linhas = ler_csv(CSV_JUIZ)
        b3 = {
            i["id"]: i
            for i in dados.get("faturas", {}).get("B3", [])
            + dados.get("perguntas", {}).get("B3", [])
        }
        linhas = rodar_juiz(
            juiz,
            linhas,
            b3,
            {r["id"]: r for r in faturas},
            {p["id"]: p for p in perguntas},
            indice,
            say,
        )
        linhas, privado = separar_veredito_juiz(linhas)
        if args.limite is None:
            escrever_csv(CSV_JUIZ, linhas)
            gravar_privado_juiz(privado)
        dados["juiz_calibracao"] = linhas
    if "faturas" in dados:
        dados["metricas_faturas"] = metricas_faturas(dados["faturas"])
    if "perguntas" in dados:
        dados["metricas_perguntas"] = metricas_perguntas(dados["perguntas"])
    if completa:
        resumo = auditar(carregar(saida, None), ids_esperados())
        dados["cobertura"] = resumo
        dados["completo"] = bool(resumo["completo"])
        say(
            "COBERTURA COMPLETA" if dados["completo"] else "COBERTURA INCOMPLETA (sem recomendação)"
        )
    _gravar(dados, saida)
    say(f"Gravado em {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
