#!/usr/bin/env python3
"""Avaliação fora da amostra (out-of-sample) do RAG em perguntas novas (Sprint S3).

Atende à solicitação de revisão da Issue #35 / PR #135:
Verifica a capacidade de generalização da normalização léxica e do limiar
de abstenção em 20 perguntas independentes e não vistas durante o desenvolvimento,
formuladas em linguagem cotidiana de consumidores.

Uso:
    python avaliacao/checar_perguntas_novas.py
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from estatistica import B_PADRAO, SEMENTE_PADRAO, Intervalo, bootstrap_ic, mcnemar

from fa_rag import IndiceHibrido, responder
from fa_rag.sintese import LIMIAR_PADRAO

SAIDA_PADRAO = (
    Path(__file__).resolve().parent / "resultados" / "s3-perguntas-novas-out-of-sample.json"
)

# 20 perguntas novas e independentes (não constam em dados/golden-set/perguntas.jsonl)
PERGUNTAS_NOVAS: tuple[dict[str, Any], ...] = (
    {
        "id": "NOV-Q01",
        "pergunta": "A concessionária pode cortar minha luz na sexta-feira à tarde?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-361"],
        "abstencao_esperada": False,
        "categoria": "corte_notificacao",
    },
    {
        "id": "NOV-Q02",
        "pergunta": "Quantos dias antes do corte a empresa precisa me avisar do débito?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-360"],
        "abstencao_esperada": False,
        "categoria": "corte_notificacao",
    },
    {
        "id": "NOV-Q03",
        "pergunta": "Se o relógio ficar trancado no quintal sem acesso, como é cobrado?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-281", "ren1000-art-285"],
        "abstencao_esperada": False,
        "categoria": "medicao_estimada",
    },
    {
        "id": "NOV-Q04",
        "pergunta": "Qual o prazo mínimo entre a entrega da fatura e o vencimento em residência?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-338"],
        "abstencao_esperada": False,
        "categoria": "tarifas_b1",
    },
    {
        "id": "NOV-Q05",
        "pergunta": "Se a conta cobrar o dobro do consumo real por erro no sistema, como recebo?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-323", "cdc-art-42"],
        "abstencao_esperada": False,
        "categoria": "devolucao_em_dobro",
    },
    {
        "id": "NOV-Q06",
        "pergunta": "Paguei o boleto da luz ontem no banco e hoje no aplicativo sem querer.",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-342"],
        "abstencao_esperada": False,
        "categoria": "cobranca_indevida",
    },
    {
        "id": "NOV-Q07",
        "pergunta": "Quantos porcento de multa a distribuidora pode cobrar por atraso na conta?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-343"],
        "abstencao_esperada": False,
        "categoria": "encargos_multas",
    },
    {
        "id": "NOV-Q08",
        "pergunta": "A empresa pode cobrar fatura retroativa por erro de medição de três anos?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-324"],
        "abstencao_esperada": False,
        "categoria": "cobranca_indevida",
    },
    {
        "id": "NOV-Q09",
        "pergunta": "A fatura precisa trazer o histórico de consumos mensais e código legível?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-327"],
        "abstencao_esperada": False,
        "categoria": "tarifas_b1",
    },
    {
        "id": "NOV-Q10",
        "pergunta": "Qual é o valor exato em reais da taxa de iluminação pública em Taguatinga?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": [],
        "abstencao_esperada": True,
        "categoria": "fora_do_corpus",
    },
    {
        "id": "NOV-Q11",
        "pergunta": "Qual a porcentagem da alíquota de ICMS sobre energia residencial no DF?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": [],
        "abstencao_esperada": True,
        "categoria": "fora_do_corpus",
    },
    {
        "id": "NOV-Q12",
        "pergunta": "Como funciona o financiamento bancário para placas solares residenciais?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": [],
        "abstencao_esperada": True,
        "categoria": "fora_do_corpus",
    },
    {
        "id": "NOV-Q13",
        "pergunta": "Qual a punição criminal no Código Penal para ligação clandestina de energia?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": [],
        "abstencao_esperada": True,
        "categoria": "fora_do_corpus",
    },
    {
        "id": "NOV-Q14",
        "pergunta": "Quem é o órgão competente para fixar a tarifa de ônibus no Distrito Federal?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": [],
        "abstencao_esperada": True,
        "categoria": "fora_do_corpus",
    },
    {
        "id": "NOV-Q15",
        "pergunta": "A leitura da luz pode ser feita com intervalo de apenas 15 dias entre contas?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-260"],
        "abstencao_esperada": False,
        "categoria": "medicao_estimada",
    },
    {
        "id": "NOV-Q16",
        "pergunta": "Em corte indevido de conta já paga, quais os direitos básicos do consumidor?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["cdc-art-6", "cdc-art-42"],
        "abstencao_esperada": False,
        "categoria": "cobranca_indevida",
    },
    {
        "id": "NOV-Q17",
        "pergunta": "A distribuidora pode exigir vantagem manifestamente excessiva ao consumidor?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["cdc-art-39"],
        "abstencao_esperada": False,
        "categoria": "cobranca_indevida",
    },
    {
        "id": "NOV-Q18",
        "pergunta": "Como solicitar revisão da taxa de iluminação pública cobrada na conta no DF?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["df7888-art-3", "df7888-art-4"],
        "abstencao_esperada": False,
        "categoria": "cip_cosip",
    },
    {
        "id": "NOV-Q19",
        "pergunta": "Quais os requisitos para ter direito à tarifa social de energia elétrica?",
        "data_referencia": "2026-11-09",
        "citacao_canonica": ["ren1000-art-290"],
        "abstencao_esperada": False,
        "categoria": "tarifas_b1",
    },
    {
        "id": "NOV-Q20",
        "pergunta": "Em maio de 2020, as regras da Resolução Normativa 1.000 já eram válidas?",
        "data_referencia": "2020-05-15",
        "citacao_canonica": ["ren1000-art-177"],
        "abstencao_esperada": True,
        "categoria": "vigencia",
    },
)


def _artigo(doc_id: str) -> str:
    return doc_id.split("::")[0]


def avaliar_perguntas_novas(
    limiar_teste: float = LIMIAR_PADRAO,
    limiar_comparacao: float = 0.30,
) -> dict[str, Any]:
    """Avalia o recuperador e a abstenção nas 20 perguntas novas."""
    indice = IndiceHibrido.do_corpus()

    com_norma = [p for p in PERGUNTAS_NOVAS if not p["abstencao_esperada"]]
    total_norma = len(com_norma)

    acertos_top1 = 0
    acertos_top5 = 0
    detalhes: list[dict[str, Any]] = []

    respostas_limiar_teste: list[bool] = []
    respostas_limiar_comp: list[bool] = []
    gabarito_abstencao: list[bool] = []

    for item in PERGUNTAS_NOVAS:
        dt = date.fromisoformat(item["data_referencia"])
        top = indice.buscar(
            item["pergunta"],
            data_referencia=dt,
            top_k=5,
            filtrar_vigencia=True,
            um_por_dispositivo=True,
        )
        canonicos = set(item["citacao_canonica"])

        recuperou_top1 = False
        recuperou_top5 = False
        if canonicos:
            if (
                top
                and _artigo(top[0].documento.id) in canonicos
                and top[0].documento.vigente_em(dt)
            ):
                recuperou_top1 = True
            recuperou_top5 = any(
                _artigo(r.documento.id) in canonicos and r.documento.vigente_em(dt) for r in top
            )
            if recuperou_top1:
                acertos_top1 += 1
            if recuperou_top5:
                acertos_top5 += 1

        resp_teste = responder(top, limiar=limiar_teste)
        resp_comp = responder(top, limiar=limiar_comparacao)

        absteve_teste = resp_teste.abstencao
        absteve_comp = resp_comp.abstencao
        espera_abstencao = bool(item["abstencao_esperada"])

        respostas_limiar_teste.append(absteve_teste)
        respostas_limiar_comp.append(absteve_comp)
        gabarito_abstencao.append(espera_abstencao)

        detalhes.append(
            {
                "id": item["id"],
                "pergunta": item["pergunta"],
                "categoria": item["categoria"],
                "data_referencia": item["data_referencia"],
                "canonicos": list(canonicos),
                "espera_abstencao": espera_abstencao,
                "recuperou_top1": recuperou_top1,
                "recuperou_top5": recuperou_top5,
                "top5": [
                    {
                        "id": r.documento.id,
                        "dispositivo": r.documento.citacao.dispositivo,
                        "score": round(r.score, 4),
                        "vigente": r.documento.vigente_em(dt),
                    }
                    for r in top
                ],
                "absteve_limiar_025": absteve_teste,
                "absteve_limiar_030": absteve_comp,
            }
        )

    hit1_ic: Intervalo = bootstrap_ic(
        [1.0 if d["recuperou_top1"] else 0.0 for d in detalhes if not d["espera_abstencao"]],
        b=B_PADRAO,
        semente=SEMENTE_PADRAO,
    )
    hit5_ic: Intervalo = bootstrap_ic(
        [1.0 if d["recuperou_top5"] else 0.0 for d in detalhes if not d["espera_abstencao"]],
        b=B_PADRAO,
        semente=SEMENTE_PADRAO,
    )

    def _calcular_confusao(predicoes: list[bool], gabarito: list[bool]) -> dict[str, Any]:
        vp = sum(1 for p, g in zip(predicoes, gabarito, strict=True) if p and g)
        fp = sum(1 for p, g in zip(predicoes, gabarito, strict=True) if p and not g)
        fn = sum(1 for p, g in zip(predicoes, gabarito, strict=True) if not p and g)
        vn = sum(1 for p, g in zip(predicoes, gabarito, strict=True) if not p and not g)
        prec = vp / (vp + fp) if (vp + fp) > 0 else 0.0
        rec = vp / (vp + fn) if (vp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        acuracia = (vp + vn) / len(gabarito) if gabarito else 0.0
        return {
            "vp": vp,
            "fp": fp,
            "fn": fn,
            "vn": vn,
            "precisao": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "acuracia": round(acuracia, 4),
        }

    conf_teste = _calcular_confusao(respostas_limiar_teste, gabarito_abstencao)
    conf_comp = _calcular_confusao(respostas_limiar_comp, gabarito_abstencao)

    acertos_teste = [
        p == g for p, g in zip(respostas_limiar_teste, gabarito_abstencao, strict=True)
    ]
    acertos_comp = [p == g for p, g in zip(respostas_limiar_comp, gabarito_abstencao, strict=True)]
    mc = mcnemar(acertos_comp, acertos_teste)

    return {
        "tipo_avaliacao": "fora_da_amostra (out-of-sample)",
        "descricao": (
            "Avaliação em 20 perguntas formuladas de forma independente em linguagem cotidiana, "
            "sem consulta prévia ao dicionário de normalização léxica."
        ),
        "n_total": len(PERGUNTAS_NOVAS),
        "n_com_norma": total_norma,
        "n_abstencao_esperada": sum(1 for p in PERGUNTAS_NOVAS if p["abstencao_esperada"]),
        "recuperacao_perguntas_com_norma": {
            "acertos_top1": acertos_top1,
            "acertos_top5": acertos_top5,
            "total": total_norma,
            "hit@1": {
                "estimativa": round(hit1_ic.estimativa, 4),
                "ic95_inferior": round(hit1_ic.inferior, 4),
                "ic95_superior": round(hit1_ic.superior, 4),
                "formatado": hit1_ic.formatar(3),
            },
            "hit@5": {
                "estimativa": round(hit5_ic.estimativa, 4),
                "ic95_inferior": round(hit5_ic.inferior, 4),
                "ic95_superior": round(hit5_ic.superior, 4),
                "formatado": hit5_ic.formatar(3),
            },
        },
        "abstencao_limiar_025": conf_teste,
        "abstencao_limiar_030": conf_comp,
        "comparacao_mcnemar_030_vs_025": {
            "n01": mc.n01,
            "n10": mc.n10,
            "chi2": round(mc.chi2, 4),
            "p_valor": round(mc.p_valor, 4),
            "p_exato": round(mc.p_exato, 4),
            "significativo_5pct": mc.significativo,
        },
        "detalhes": detalhes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="Caminho do arquivo JSON de saída.",
    )
    args = parser.parse_args()

    print("=" * 68)
    print("FATURA ABERTA - AVALIAÇÃO FORA DA AMOSTRA EM PERGUNTAS NOVAS (S3)")
    print("=" * 68)
    res = avaliar_perguntas_novas()

    rec = res["recuperacao_perguntas_com_norma"]
    print(f"Perguntas com norma esperada: {rec['total']}")
    print(f"Hit@1: {rec['acertos_top1']}/{rec['total']} ({rec['hit@1']['formatado']})")
    print(f"Hit@5: {rec['acertos_top5']}/{rec['total']} ({rec['hit@5']['formatado']})")

    abs25 = res["abstencao_limiar_025"]
    abs30 = res["abstencao_limiar_030"]
    print("\nAbstenção em 20 perguntas (6 abstenções esperadas):")
    p25, r25, f25 = abs25["precisao"], abs25["recall"], abs25["f1"]
    v25, f_p25, f_n25, vn25 = abs25["vp"], abs25["fp"], abs25["fn"], abs25["vn"]
    print(
        f"  Limiar 0,25: F1 = {f25} (P={p25}, R={r25}, VP={v25}, FP={f_p25}, FN={f_n25}, VN={vn25})"
    )
    p30, r30, f30 = abs30["precisao"], abs30["recall"], abs30["f1"]
    v30, f_p30, f_n30, vn30 = abs30["vp"], abs30["fp"], abs30["fn"], abs30["vn"]
    print(
        f"  Limiar 0,30: F1 = {f30} (P={p30}, R={r30}, VP={v30}, FP={f_p30}, FN={f_n30}, VN={vn30})"
    )

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultado salvo em: {args.saida}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
