#!/usr/bin/env python3
"""Rodada S4 (issue #37): B4 × B5 e ablação com e sem Auditor, sobre as 120 perguntas do golden set.

Definições (`docs/avaliacao/index.md`):
- B4: Analista Normativo sem Auditor (todas as afirmações propostas são emitidas).
- B5: Analista + Auditor com abstenção forçada (qualquer reprovação vira abstenção).

B4 e B5 partilham a MESMA saída do Analista: uma única chamada ao LLM por pergunta (temperatura 0,
semente 42), então a diferença entre os dois vem só do Auditor. O Auditor roda sem o juiz LLM, que
foi reprovado na calibração da S3 (κ 0,03): "afirmação sem suporte" aqui é a reprovação por uma
verificação determinística (citação ausente/inventada/divergente, fora de vigência, número ou
cobertura de palavras sem lastro, expressão proibida do RF-15).

Nenhum prompt ou limiar é ajustado nesta rodada: o prompt do Analista e o limiar 0,30 vêm da #36 e
da S3. Todas as 120 perguntas são, portanto, teste (o limiar 0,30 herda uma calibração da S3 feita
com dados do mesmo golden set; veja o relatório).

Uso (Ollama local, ADR-002; uma chamada por vez):
    FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s4.py --etapa analista --limite 5
    FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s4.py --etapa tudo   # retomável
    .venv/bin/python avaliacao/rodada_s4.py --etapa metricas                       # sem LLM
Sem `FA_LLM_PROVEDOR=ollama`, usa o cliente falso (só para testar a tubulação).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rodada_s3 as rs  # noqa: E402
from auditar_cobertura import ids_esperados  # noqa: E402
from estatistica import B_PADRAO, SEMENTE_PADRAO, bootstrap_ic_diferenca, mcnemar  # noqa: E402

from fa_agentes import (  # noqa: E402
    Afirmacao,
    AnalistaNormativo,
    Auditor,
    ClienteLLM,
    RelatorioAnalise,
    criar_cliente,
    metadados_rodada,
    verificar_linguagem,
)
from fa_agentes.analista import SISTEMA_ANALISTA  # noqa: E402
from fa_agentes.auditor import COBERTURA_MINIMA  # noqa: E402
from fa_agentes.llm import RespostaLLM  # noqa: E402
from fa_rag import DocumentoNormativo, IndiceHibrido  # noqa: E402
from fa_rag.sintese import LIMIAR_PADRAO  # noqa: E402

RESULTADOS = Path(__file__).resolve().parent / "resultados"
SAIDA = RESULTADOS / "s4-b4-b5.json"
GOLDEN = rs.GOLDEN
CACHE = rs.CACHE
ARMS = ("B4", "B5", "B5_estrutural")
ESTRATEGIA_ERRO = ("comunicacao", "timeout")


# --------------------------------------------------------------------------- cliente


class ClienteRobusto:
    """Embrulha um cliente: refaz só falha de comunicação ou timeout e guarda a última resposta.

    JSON inválido do modelo nunca é refeito (a resposta desfavorável continua valendo).
    """

    def __init__(self, base: ClienteLLM) -> None:
        self.base = base
        self.provedor = base.provedor
        self.modelo = base.modelo
        self.ultima: RespostaLLM | None = None
        self.tentativas = 0

    def versao(self) -> str:
        return self.base.versao()

    def gerar(
        self, *, sistema: str, prompt: str, esquema: Mapping[str, Any] | None = None
    ) -> RespostaLLM:
        self.ultima = None
        for tentativa in range(1 + rs.TENTATIVAS_EXTRAS):
            self.tentativas = tentativa + 1
            try:
                self.ultima = self.base.gerar(sistema=sistema, prompt=prompt, esquema=esquema)
                return self.ultima
            except Exception as erro:
                if (
                    rs.classificar_erro(erro) not in ESTRATEGIA_ERRO
                    or tentativa == rs.TENTATIVAS_EXTRAS
                ):
                    raise
                time.sleep(rs.PAUSA_NOVA_TENTATIVA_S)
        raise AssertionError("inalcançável")  # pragma: no cover


# --------------------------------------------------------------------------- Analista


def _json_valido(bruto: str) -> bool:
    try:
        d = json.loads(bruto)
    except ValueError:
        return False
    return isinstance(d, dict) and isinstance(d.get("afirmacoes"), list)


def registrar_analise(
    analista: AnalistaNormativo, cliente: ClienteRobusto, p: dict[str, Any]
) -> dict[str, Any]:
    """Uma pergunta no Analista; guarda o que é preciso para auditar de novo sem o LLM."""
    base: dict[str, Any] = {"id": p["id"], "tipo": p["tipo"]}
    cliente.ultima = None
    try:
        rel = analista.analisar(
            p["pergunta"], data_referencia=date.fromisoformat(p["data_referencia"])
        )
    except Exception as erro:  # a rodada segue e registra; na retomada, é refeito
        return base | {
            "valido": False,
            "erro_tipo": rs.classificar_erro(erro),
            "erro": f"{type(erro).__name__}: {erro}"[:300],
        }
    r = cliente.ultima
    chamou_llm = r is not None
    return base | {
        "valido": True,
        "chamou_llm": chamou_llm,
        "json_valido": _json_valido(rel.resposta_bruta) if chamou_llm else None,
        "dispositivos_ids": [d.id for d in rel.dispositivos],
        "afirmacoes": [
            {"texto": a.texto, "ids_fontes": list(a.ids_fontes)} for a in rel.afirmacoes
        ],
        "resposta_bruta": rel.resposta_bruta[:2000],
        "tentativas": cliente.tentativas if chamou_llm else 0,
        "duracao_s": r.duracao_s if r else 0.0,
        "tokens_saida": r.tokens_saida if r else 0,
        "do_cache": r.do_cache if r else False,
    }


def reconstruir(
    registro: dict[str, Any], docs: Mapping[str, DocumentoNormativo], p: dict[str, Any]
) -> RelatorioAnalise:
    """Refaz o ``RelatorioAnalise`` guardado (as citações vêm sempre do dispositivo recuperado)."""
    recuperados = {i: docs[i] for i in registro["dispositivos_ids"]}
    afirmacoes = tuple(
        Afirmacao(
            a["texto"],
            tuple(a["ids_fontes"]),
            tuple(recuperados[i].citacao for i in a["ids_fontes"] if i in recuperados),
        )
        for a in registro["afirmacoes"]
    )
    return RelatorioAnalise(
        p["pergunta"],
        date.fromisoformat(p["data_referencia"]),
        tuple(recuperados.values()),
        afirmacoes,
        registro.get("resposta_bruta", ""),
    )


# --------------------------------------------------------------------------- braços


def _artigo(doc_id: str) -> str:
    return doc_id.split("::")[0]


def _acertou(p: dict[str, Any], abstencao: bool, ids: Sequence[str]) -> bool:
    if p["abstencao_esperada"]:
        return abstencao
    return (not abstencao) and any(_artigo(i) in set(p["citacao_canonica"]) for i in ids)


def _problemas_por_afirmacao(
    rel: RelatorioAnalise, auditor: Auditor
) -> list[tuple[Afirmacao, list[str]]]:
    """Motivos de reprovação de cada afirmação, auditada sozinha (API pública do Auditor)."""
    saida = []
    for a in rel.afirmacoes:
        sub = RelatorioAnalise(
            rel.consulta, rel.data_referencia, rel.dispositivos, (a,), rel.resposta_bruta
        )
        saida.append((a, [str(x.motivo) for x in auditor.auditar(sub).problemas]))
    return saida


def avaliar_braco(
    nome: str, rel: RelatorioAnalise, p: dict[str, Any], medidor: Auditor
) -> dict[str, Any]:
    """Resultado de um braço para uma pergunta.

    ``medidor`` é o Auditor usado só para MEDIR afirmações sem suporte no que cada braço emitiu.
    """
    if nome == "B4":
        emitidas = rel.afirmacoes
        abst = not emitidas
    else:
        auditor = Auditor(None, cobertura_minima=0.0) if nome == "B5_estrutural" else medidor
        res = auditor.auditar(rel)
        abst = res.abstencao
        emitidas = res.afirmacoes_aprovadas
    ids = [i for a in emitidas for i in a.ids_fontes]
    emitido = RelatorioAnalise(rel.consulta, rel.data_referencia, rel.dispositivos, emitidas, "")
    motivos: Counter[str] = Counter()
    reprovadas = 0
    for _, ms in _problemas_por_afirmacao(emitido, medidor):
        if ms:
            reprovadas += 1
        motivos.update(set(ms))
    texto = " ".join(a.texto for a in emitidas)
    canon = set(p["citacao_canonica"])
    return {
        "id": p["id"],
        "tipo": p["tipo"],
        "abstencao": abst,
        "acerto": _acertou(p, abst, ids),
        "ids_citados": sorted(set(ids)),
        "n_afirmacoes": len(emitidas),
        "n_afirmacoes_sem_suporte": reprovadas,
        "emitiu_sem_suporte": (not abst) and reprovadas > 0,
        "motivos": dict(motivos),
        "citacao_inventada": motivos["citacao_inventada"] > 0,
        "fora_de_vigencia": motivos["fora_de_vigencia"] > 0,
        "linguagem": [x.termo for x in verificar_linguagem(texto)],
        "cita_canonico": any(_artigo(i) in canon for i in ids),
        "recuperou_canonico": any(_artigo(d.id) in canon for d in rel.dispositivos),
    }


def avaliar_tudo(
    registros: Sequence[dict[str, Any]],
    perguntas: Mapping[str, dict[str, Any]],
    docs: Mapping[str, DocumentoNormativo],
) -> dict[str, list[dict[str, Any]]]:
    """Aplica os braços às análises válidas, na ordem do golden set."""
    medidor = Auditor(None, cobertura_minima=COBERTURA_MINIMA)
    saida: dict[str, list[dict[str, Any]]] = {b: [] for b in ARMS}
    for reg in registros:
        if not reg.get("valido"):
            continue
        p = perguntas[reg["id"]]
        rel = reconstruir(reg, docs, p)
        for b in ARMS:
            saida[b].append(avaliar_braco(b, rel, p, medidor))
    return saida


# --------------------------------------------------------------------------- métricas


def bootstrap_reducao(
    b4: Sequence[bool], b5: Sequence[bool], *, b: int = B_PADRAO, semente: int = SEMENTE_PADRAO
) -> dict[str, float | None]:
    """Redução relativa (B4 − B5)/B4 da taxa de respostas com afirmação sem suporte, com IC."""
    n = len(b4)
    soma4 = sum(b4)
    if n == 0 or len(b5) != n:
        raise ValueError("amostras pareadas precisam ter o mesmo tamanho (> 0)")
    ponto = None if soma4 == 0 else (soma4 - sum(b5)) / soma4
    rng = random.Random(semente)
    reducoes: list[float] = []
    for _ in range(b):
        idx = [rng.randrange(n) for _ in range(n)]
        s4 = sum(b4[i] for i in idx)
        if s4:
            reducoes.append((s4 - sum(b5[i] for i in idx)) / s4)
    if not reducoes:
        return {"estimativa": ponto, "ic95_inf": None, "ic95_sup": None, "reamostras_validas": 0}
    reducoes.sort()
    k = len(reducoes)
    return {
        "estimativa": ponto,
        "ic95_inf": reducoes[max(0, int(0.025 * k))],
        "ic95_sup": reducoes[min(k - 1, int(0.975 * k))],
        "reamostras_validas": k,
    }


def _dif(a: Sequence[bool], b: Sequence[bool]) -> dict[str, float]:
    ic = bootstrap_ic_diferenca([float(x) for x in a], [float(x) for x in b])
    return {"estimativa": ic.estimativa, "ic95_inf": ic.inferior, "ic95_sup": ic.superior}


def resumo_braco(itens: Sequence[dict[str, Any]]) -> dict[str, Any]:
    n = len(itens)
    esperam = [i for i in itens if i["tipo"] in ("vigencia", "fora_do_corpus")]
    respondiveis = [i for i in itens if i["tipo"] not in ("vigencia", "fora_do_corpus")]
    return {
        "n": n,
        "acerto": rs._ic([i["acerto"] for i in itens]) if n else None,
        "acerto_por_tipo": {
            t: sum(i["acerto"] for i in itens if i["tipo"] == t)
            / sum(1 for i in itens if i["tipo"] == t)
            for t in sorted({i["tipo"] for i in itens})
        },
        "taxa_abstencao": sum(i["abstencao"] for i in itens) / max(n, 1),
        "abstencao_correta_nas_que_exigem": sum(i["abstencao"] for i in esperam)
        / max(len(esperam), 1),
        "abstencao_indevida_nas_respondiveis": sum(i["abstencao"] for i in respondiveis)
        / max(len(respondiveis), 1),
        "respostas_com_afirmacao_sem_suporte": rs._ic([i["emitiu_sem_suporte"] for i in itens])
        if n
        else None,
        "afirmacoes_emitidas": sum(i["n_afirmacoes"] for i in itens),
        "afirmacoes_sem_suporte": sum(i["n_afirmacoes_sem_suporte"] for i in itens),
        "perguntas_com_citacao_inventada": sum(i["citacao_inventada"] for i in itens),
        "perguntas_com_citacao_fora_de_vigencia": sum(i["fora_de_vigencia"] for i in itens),
        "violacoes_rf15": sum(1 for i in itens if i["linguagem"]),
        "motivos": dict(sorted(sum((Counter(i["motivos"]) for i in itens), Counter()).items())),
    }


def comparar(b4: Sequence[dict[str, Any]], b5: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Gate da S4: B5 × B4 em afirmações sem suporte (IC e redução) e em correção (McNemar)."""
    ss4 = [i["emitiu_sem_suporte"] for i in b4]
    ss5 = [i["emitiu_sem_suporte"] for i in b5]
    ac4 = [i["acerto"] for i in b4]
    ac5 = [i["acerto"] for i in b5]
    dif_ss = _dif(ss4, ss5)
    reducao = bootstrap_reducao(ss4, ss5)
    mc = mcnemar(ac4, ac5)
    dif_ac = _dif(ac4, ac5)
    nao_pior_sem_suporte = dif_ss["ic95_sup"] <= 0.0
    reducao_30 = reducao["estimativa"] is not None and reducao["estimativa"] >= 0.30
    perda_acerto_significativa = mc.significativo and mc.n10 > mc.n01
    return {
        "n_pares": len(b4),
        "sem_suporte_diferenca_B5_menos_B4": dif_ss,
        "sem_suporte_reducao_relativa": reducao,
        "sem_suporte_B5_nao_pior_que_B4": nao_pior_sem_suporte,
        "reducao_de_30pct_atingida": reducao_30,
        "acerto_diferenca_B5_menos_B4": dif_ac,
        "acerto_mcnemar_B4_vs_B5": {
            "n01_B4_erra_B5_acerta": mc.n01,
            "n10_B4_acerta_B5_erra": mc.n10,
            "chi2_edwards": mc.chi2,
            "p_valor": mc.p_valor,
            "p_exato": mc.p_exato,
            "significativo_5pct": mc.significativo,
        },
        "perda_de_acerto_significativa": perda_acerto_significativa,
        "gate_s4_aprovado": nao_pior_sem_suporte and reducao_30 and not perda_acerto_significativa,
        "ressalva": (
            "B5 emite apenas afirmações aprovadas pelas mesmas verificações usadas para medir "
            "'sem suporte'; por construção a taxa do B5 é zero. A redução mede quanto do que o B4 "
            "emitiria o Auditor barra, e o acerto mede o preço em abstenções. A medida não "
            "captura erro factual que passe nas verificações determinísticas (isso depende da "
            "anotação humana)."
        ),
    }


def cobertura(registros: Sequence[dict[str, Any]], esperados: Sequence[str]) -> dict[str, Any]:
    """Cobertura por id (mesma lógica de `auditar_cobertura.py`: id válido e uma única vez)."""
    contagem = Counter(r["id"] for r in registros)
    validos = {r["id"] for r in registros if r.get("valido")}
    invalidos = sorted({r["id"] for r in registros} - validos)
    concluidos = [x for x in esperados if x in validos and contagem[x] == 1]
    pendentes = [x for x in esperados if x not in concluidos and x not in invalidos]
    return {
        "esperado": len(esperados),
        "concluidos": len(concluidos),
        "invalidos": invalidos,
        "duplicados": sorted(k for k, v in contagem.items() if v > 1),
        "pendentes": pendentes,
        "fora_do_conjunto": sorted(set(contagem) - set(esperados)),
        "completo": len(concluidos) + len(invalidos) == len(esperados) and not pendentes,
    }


def metricas(
    registros: Sequence[dict[str, Any]],
    perguntas: Mapping[str, dict[str, Any]],
    docs: Mapping[str, DocumentoNormativo],
    esperados: Sequence[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    bracos = avaliar_tudo(registros, perguntas, docs)
    validos = [r for r in registros if r.get("valido")]
    comp: dict[str, Any] = {
        "cobertura": cobertura(registros, esperados),
        "analista": {
            "perguntas_validas": len(validos),
            "chamadas_llm": sum(1 for r in validos if r["chamou_llm"]),
            "sem_dispositivo_acima_do_limiar": sum(1 for r in validos if not r["chamou_llm"]),
            "json_invalido": sum(1 for r in validos if r["json_valido"] is False),
            "duracao_media_s": round(
                sum(r["duracao_s"] for r in validos if r["chamou_llm"])
                / max(sum(1 for r in validos if r["chamou_llm"]), 1),
                2,
            ),
        },
        "bracos": {b: resumo_braco(v) for b, v in bracos.items()},
    }
    if bracos["B4"]:
        comp["B5_vs_B4"] = comparar(bracos["B4"], bracos["B5"])
        comp["B5_estrutural_vs_B4"] = comparar(bracos["B4"], bracos["B5_estrutural"])
    return bracos, comp


# --------------------------------------------------------------------------- CLI


def _sha256_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def caminho_comparacao(saida: Path) -> Path:
    return saida.with_name(saida.stem + "-comparacao.json")


def conferir_cabecalho(antigo: Mapping[str, Any], novo: Mapping[str, Any]) -> None:
    """A retomada só é válida com o mesmo modelo, digest, golden set e prompt do Analista."""
    for chave in ("sha256_checksums_golden_set", "sha256_prompt_analista", "limiar", "top_k"):
        if antigo.get(chave) != novo.get(chave):
            raise RuntimeError(
                f"Não retomo: {chave} mudou ({antigo.get(chave)} -> {novo.get(chave)})"
            )
    if antigo.get("modelos") != novo.get("modelos"):
        raise RuntimeError("Não retomo: modelo ou digest do gerador mudou")


def executar(args: argparse.Namespace, say: Callable[[str], None] = print) -> int:
    saida: Path = args.saida
    perguntas = rs.ler_jsonl(GOLDEN / "perguntas.jsonl")
    esperados = ids_esperados()["perguntas"]
    alvo = perguntas[: args.limite]
    indice = IndiceHibrido.do_corpus()
    docs = {d.id: d for d in indice.documentos}
    base = criar_cliente("gerador", cache_dir=CACHE)
    cliente = ClienteRobusto(base)

    dados = rs._carregar_saida(saida)
    cab = metadados_rodada(
        {"gerador": cliente}, checksums=GOLDEN / "checksums.sha256", raiz=rs.RAIZ
    )
    cab.update(
        {
            "semente_llm": 42,
            "semente_bootstrap": SEMENTE_PADRAO,
            "bootstrap_b": B_PADRAO,
            "limiar": LIMIAR_PADRAO,
            "top_k": 5,
            "cobertura_minima": COBERTURA_MINIMA,
            "juiz_llm": "não usado (reprovado na calibração da S3)",
            "sha256_prompt_analista": hashlib.sha256(SISTEMA_ANALISTA.encode()).hexdigest(),
            "conjunto": "120 perguntas (golden set congelado); faturas fora do escopo da S4",
        }
    )
    if dados.get("cabecalho"):
        conferir_cabecalho(dados["cabecalho"], cab)
    dados["cabecalho"] = {**cab, "limite": args.limite}
    por_id = {r["id"]: r for r in dados.get("registros", [])}

    if args.etapa in ("analista", "tudo"):
        analista = AnalistaNormativo(indice, cliente, limiar=LIMIAR_PADRAO)
        pendentes = [p for p in alvo if not por_id.get(p["id"], {}).get("valido")]
        say(f"Analista: {len(alvo) - len(pendentes)} já feitas, {len(pendentes)} a fazer")
        for n, p in enumerate(pendentes, 1):
            reg = registrar_analise(analista, cliente, p)
            por_id[p["id"]] = reg
            dados["registros"] = [por_id[x["id"]] for x in perguntas if x["id"] in por_id]
            rs._gravar(dados, saida)  # a cada pergunta: uma queda não perde trabalho
            say(
                f"B4/B5 {n}/{len(pendentes)} {p['id']} -> "
                f"{'ok' if reg['valido'] else reg['erro_tipo']} "
                f"afirmacoes={len(reg.get('afirmacoes', []))} {reg.get('duracao_s', 0)}s"
            )

    registros = [por_id[x["id"]] for x in perguntas if x["id"] in por_id]
    dados["registros"] = registros
    bracos, comp = metricas(registros, {p["id"]: p for p in perguntas}, docs, esperados)
    dados["bracos"] = bracos
    dados["parcial"] = not comp["cobertura"]["completo"]
    dados["metricas"] = comp
    rs._gravar(dados, saida)
    rs._gravar({"cabecalho": dados["cabecalho"], **comp}, caminho_comparacao(saida))
    cob = comp["cobertura"]
    say(
        f"Cobertura: {cob['concluidos']}/{cob['esperado']} perguntas "
        f"({'COMPLETA' if cob['completo'] else 'PARCIAL'}); gravado em {saida}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--etapa", choices=["analista", "metricas", "tudo"], default="tudo")
    ap.add_argument("--limite", type=int, default=None, help="só as N primeiras perguntas (teste)")
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args(argv)
    with rs.trava_de_rodada(args.saida.with_suffix(".lock")):
        return executar(args)


if __name__ == "__main__":
    raise SystemExit(main())
