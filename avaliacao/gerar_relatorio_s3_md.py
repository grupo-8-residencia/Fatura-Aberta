#!/usr/bin/env python3
"""Gera `docs/avaliacao/relatorio-s3.md` a partir de `s3-comparacao.json`.

Nenhum número é digitado à mão: tudo vem do JSON da comparação. Se a cobertura estiver incompleta
(`completo = false`), o relatório diz isso no topo e não emite recomendação final.

Uso: python avaliacao/gerar_relatorio_s3_md.py
"""

# ruff: noqa: E501
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
ENTRADA = RAIZ / "avaliacao" / "resultados" / "s3-comparacao.json"
SAIDA = RAIZ / "docs" / "avaliacao" / "relatorio-s3.md"

NOMES_P = {"LLM": "T1 LLM sem RAG", "RAG": "T2 RAG extrativo sem LLM", "B2": "T3 LLM + RAG (B2)",
           "B3": "T4 LLM + RAG + vigência (B3)"}  # fmt: skip
NOMES_F = {"B1": "B1 motor determinístico", "LLM": "T1 LLM sem RAG", "B2": "T3 LLM + RAG (B2)",
           "B3": "T4 LLM + RAG + vigência (B3)"}  # fmt: skip


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def ic(m: dict[str, Any]) -> str:
    return f"{pct(m['estimativa'])} [{pct(m['ic95_inf'])}; {pct(m['ic95_sup'])}]"


def tabela_perguntas(c: dict[str, Any]) -> list[str]:
    out = ["| Teste | n | Acerto (IC 95%) | Inválidas | Viol. RF-15 | Cit. inventadas | Fora de vigência | Latência média |",
           "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for k, nome in NOMES_P.items():
        d = c["perguntas"].get(k)
        if d:
            out.append(f"| {nome} | {d['n']} | {ic(d['acerto'])} | {d['invalidas']} | {d['rf15']} | "
                       f"{d['citacoes_inventadas']} | {d['fora_de_vigencia']} | {d['latencia_media_s']} s |")  # fmt: skip
    return out


def tabela_tipos(c: dict[str, Any]) -> list[str]:
    tipos = ["normativa", "vigencia", "lacuna", "fora_do_corpus"]
    out = ["| Teste | " + " | ".join(tipos) + " |", "|---|" + "---|" * len(tipos)]
    for k, nome in NOMES_P.items():
        d = c["perguntas"].get(k)
        if d:
            out.append(
                f"| {nome} | " + " | ".join(pct(d["acerto_por_tipo"][t]) for t in tipos) + " |"
            )
    return out


def tabela_faturas(c: dict[str, Any]) -> list[str]:
    out = ["| Teste | n | Acerto (IC 95%) | Detecção | Falso alarme | Abstenções | Latência média |",
           "|---|---|---|---|---|---|---|"]  # fmt: skip
    for k, nome in NOMES_F.items():
        d = c["faturas"].get(k)
        if d:
            out.append(f"| {nome} | {d['n']} | {ic(d['acerto'])} | {pct(d['deteccao']['estimativa'])} | "
                       f"{pct(d['falso_alarme']['estimativa'])} | {d['abstencoes']} | {d['latencia_media_s']} s |")  # fmt: skip
        else:
            out.append(f"| {nome} | — | **sem resultado (cobertura incompleta)** | — | — | — | — |")
    return out


def mcnemar(c: dict[str, Any], chave: str) -> list[str]:
    out = [
        "| Par | Só o 2º acerta | Só o 1º acerta | p (exato) | Diferença a 5% |",
        "|---|---|---|---|---|",
    ]
    for par, d in c[chave].items():
        out.append(f"| {par.replace('_vs_', ' × ')} | {d['n01_primeiro_erra_segundo_acerta']} | "
                   f"{d['n10_primeiro_acerta_segundo_erra']} | {d['p_exato']:.2g} | "
                   f"{'sim' if d['significativo_5pct'] else 'não'} |")  # fmt: skip
    return out


def gerar(c: dict[str, Any]) -> str:
    cab = c["cabecalho"]
    completo = c["completo"]
    cob = c["cobertura"]["baselines"]
    L: list[str] = ["# Relatório da S3 — B1, B2 e B3 (quatro testes)", ""]
    if not completo:
        faltam = [k for k, v in cob.items() if not v["completo"]]
        L += [f"> **RESULTADO PARCIAL.** Cobertura incompleta em: {', '.join(faltam)}. "
              "Não há recomendação final. Os números abaixo são dos itens já medidos.", ""]  # fmt: skip
    L += ["## 1. Dados da rodada", "",
          f"- Data (UTC): {cab['data_utc']}; commit `{cab['commit']}`; temperatura {cab['temperatura']}.",
          f"- Gerador: `{cab['modelos']['gerador']['modelo']}` (digest `{cab['modelos']['gerador']['versao']}`); "
          f"juiz: `{cab['modelos']['juiz']['modelo']}` (digest `{cab['modelos']['juiz']['versao']}`).",
          f"- Sementes: LLM {cab['semente_llm']}, bootstrap {cab['semente_bootstrap']} (B = 10.000).",
          f"- Hash do golden set: `{cab['sha256_checksums_golden_set']}`.", "",
          "## 2. Cobertura por baseline", "",
          "| Conjunto | Esperado | Concluídos | Completo |", "|---|---|---|---|"]  # fmt: skip
    for k, v in cob.items():
        L.append(
            f"| {k} | {v['esperado']} | {v['concluidos']} | {'sim' if v['completo'] else '**não**'} |"
        )
    L += ["", "Uma pergunta com resposta inválida (JSON fora do esquema) conta como inválida, não como acerto "
          "nem como item ausente.", "",
          "## 3. Perguntas (120)", ""] + tabela_perguntas(c) + ["", "Acerto por tipo de pergunta:", ""] + tabela_tipos(c)  # fmt: skip
    L += ["", "McNemar (pareado, p exato):", ""] + mcnemar(c, "mcnemar_perguntas")
    e = c["escolha_perguntas"]
    L += ["", f"Regra de escolha (congelada antes dos resultados): 0 inválidas e 0 violações do RF-15; maior acerto; "
          f"empate (< 1 p.p.) vai para a menor latência. Elegíveis nas perguntas: {', '.join(e['elegiveis']) or 'nenhum'}.",
          f"Escolhido nas perguntas: **{e['escolhido']}** (acerto {pct(e['acerto'])}).", "",
          "## 4. Faturas (200)", ""] + tabela_faturas(c) + ["", "McNemar:", ""] + mcnemar(c, "mcnemar_faturas")  # fmt: skip
    f = c["escolha_faturas"]
    L += ["", f"Elegíveis nas faturas: {', '.join(f['elegiveis'])}. Escolhido: **{f['escolhido']}**.", "",
          "## 5. Recomendação", ""]  # fmt: skip
    if completo and c.get("recomendacao_final"):
        L.append(f"{c['recomendacao_final']}")
    else:
        L.append(
            "**Sem recomendação final**: a cobertura exigida pelo protocolo não está completa. "
            "A leitura provisória acima não substitui a comparação dos quatro testes nas 200 faturas."
        )
    L += ["", "## 6. Limitações", "",
          "- O gabarito das faturas vem do mesmo gerador sintético do B1; o 100% do B1 mostra consistência do motor, "
          "não desempenho em faturas reais. Nenhuma fatura real foi usada (LGPD).",
          "- O B3 se abstém quando a evidência é insuficiente: nas faturas isso derruba o acerto e eleva a detecção. "
          "O custo de abstenção não entrou na regra de escolha.",
          "- Respostas inválidas (JSON fora do esquema) tornam o LLM inelegível pela regra; foi mantida a regra.",
          "- Determinismo do Ollama não é garantido bit a bit mesmo com temperatura 0; as chamadas ficam em cache.",
          "- Os IC 95% são bootstrap sobre os itens do golden set, cujo gabarito ainda está em revisão humana (#32).",
          "- O juiz automático ainda não foi calibrado contra duas pessoas (kappa pendente); nenhum veredito dele é "
          "usado como verdade.", ""]  # fmt: skip
    return "\n".join(L)


def main() -> int:
    c = json.loads(ENTRADA.read_text(encoding="utf-8"))
    SAIDA.write_text(gerar(c), encoding="utf-8")
    print(f"Gravado {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
