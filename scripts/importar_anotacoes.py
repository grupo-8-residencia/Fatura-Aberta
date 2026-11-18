#!/usr/bin/env python3
"""Importa as anotações humanas exportadas da página de anotação para os CSV do repositório.

O banco da página (Artifact) é só o meio de coleta. O repositório é a fonte versionada.
Este script lê
um JSON exportado do banco, valida tudo e grava nos formatos do kit (#118) e do juiz (#33).

Formato do JSON de entrada (`esquema_versao` 1): objeto com `exportado_em`, `versao_pagina`,
`hash_golden_set` e `entregas`, uma por pessoa:
    {"github": "...", "enviado_em": "...",
     "golden":  {"GS-Q008": {"concorda": "sim|não", "correcao": "", "comentario": ""}},
     "revisao": {"GS-Q001": {"concorda": "sim", "correcao": "", "comentario": ""}},
     "juiz":    {"JZ-001": {"veredito": "suportada|sem_suporte", "comentario": ""}}}

Regras:
- Por padrão só simula e imprime o relatório. A escrita exige `--aplicar`.
- Nada é gravado se houver qualquer erro (tudo ou nada). Antes de gravar, faz backup dos CSV.
- Nunca sobrescreve uma anotação já presente com valor diferente (conflito = erro).
- Reaplicar o mesmo JSON não muda nada (idempotente).
- Cada aplicação gera uma linha em `importacoes.jsonl` com o hash do JSON.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import io
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "dados" / "golden-set" / "anotacoes"
DISTRIBUICAO = PASTA / "distribuicao-revisao.json"
REVISAO = PASTA / "revisao-perguntas.csv"
JUIZ = RAIZ / "avaliacao" / "anotacoes" / "juiz-40.csv"
LOG = PASTA / "importacoes.jsonl"
PESSOAS = (
    "pedrohpsantos",
    "NatyEvelin",
    "RaissaOliveira19",
    "TalitaaNunes",
    "luizoryone",
    "mariadenis",
)
VEREDITOS = ("suportada", "sem_suporte")
ESQUEMA = 1


class ErroImportacao(Exception):
    """Entrada inválida ou conflito: nada é gravado."""


@dataclass
class Plano:
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    novos: dict[str, int] = field(default_factory=lambda: {"golden": 0, "revisao": 0, "juiz": 0})
    iguais: int = 0
    ausentes: dict[str, dict[str, int]] = field(default_factory=dict)
    arquivos: dict[Path, str] = field(default_factory=dict)


def _ler_csv(caminho: Path) -> tuple[list[str], list[dict[str, str]]]:
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        return list(leitor.fieldnames or []), list(leitor)


def _texto_csv(colunas: list[str], linhas: list[dict[str, str]]) -> str:
    saida = io.StringIO()
    w = csv.DictWriter(saida, fieldnames=colunas, lineterminator="\n")
    w.writeheader()
    w.writerows(linhas)
    return "﻿" + saida.getvalue()


def _norm_concorda(v: Any) -> str:
    s = str(v or "").strip().lower()
    return {"sim": "sim", "s": "sim", "não": "não", "nao": "não", "n": "não"}.get(s, "")


def _validar_resposta(
    fila: str, item_id: str, r: Any, plano: Plano, quem: str
) -> dict[str, str] | None:
    onde = f"{quem}/{fila}/{item_id}"
    if not isinstance(r, dict):
        plano.erros.append(f"{onde}: resposta não é um objeto")
        return None
    if fila == "juiz":
        v = str(r.get("veredito", "")).strip()
        if v not in VEREDITOS:
            plano.erros.append(f"{onde}: veredito '{v}' fora de {VEREDITOS}")
            return None
        return {"veredito": v, "comentario": str(r.get("comentario", "")).strip()}
    c = _norm_concorda(r.get("concorda"))
    if not c:
        plano.erros.append(f"{onde}: 'concorda' deve ser sim ou não")
        return None
    corr, com = str(r.get("correcao", "")).strip(), str(r.get("comentario", "")).strip()
    if c == "não" and not (corr and com):
        plano.erros.append(f"{onde}: 'não' exige correção e justificativa")
        return None
    return {"concorda": c, "correcao": corr if c == "não" else "", "comentario": com}


def _aplicar_campos(
    linha: dict[str, str], novos: dict[str, str], plano: Plano, onde: str, fila: str
) -> None:
    atuais = {k: linha.get(k, "") for k in novos}
    if any(atuais.values()):
        if atuais == novos:
            plano.iguais += 1
            return
        plano.erros.append(f"{onde}: já existe anotação diferente no CSV (não sobrescrevo)")
        return
    linha.update(novos)
    plano.novos[fila] += 1


def planejar(
    dados: dict[str, Any], pasta: Path = PASTA, revisao: Path = REVISAO, juiz: Path = JUIZ
) -> Plano:
    plano = Plano()
    if dados.get("esquema_versao") != ESQUEMA:
        plano.erros.append(
            f"esquema_versao deve ser {ESQUEMA}, veio {dados.get('esquema_versao')!r}"
        )
        return plano
    entregas = dados.get("entregas")
    if not isinstance(entregas, list) or not entregas:
        plano.erros.append("entregas ausente ou vazia")
        return plano
    vistos = [e.get("github") for e in entregas]
    for g in {x for x in vistos if vistos.count(x) > 1}:
        plano.erros.append(f"{g}: mais de uma entrega no export")
    for e in entregas:
        if e.get("github") not in PESSOAS:
            plano.erros.append(f"github desconhecido: {e.get('github')!r}")
    if plano.erros:
        return plano

    csvs_pessoa: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    blocos = json.loads((pasta / "distribuicao-revisao.json").read_text(encoding="utf-8"))["blocos"]
    rev_cols, rev_linhas = _ler_csv(revisao)
    rev_por_id = {x["id"]: x for x in rev_linhas}
    juiz_cols, juiz_linhas = _ler_csv(juiz) if juiz.exists() else ([], [])
    juiz_por_id = {x["item_id"]: x for x in juiz_linhas}

    for e in entregas:
        g = e["github"]
        if g not in csvs_pessoa:
            csvs_pessoa[g] = _ler_csv(pasta / f"{g}.csv")
        cols, linhas = csvs_pessoa[g]
        por_id = {x["id"]: x for x in linhas}
        recebidos: dict[str, set[str]] = {"golden": set(), "revisao": set(), "juiz": set()}

        for item_id, bruto in (e.get("golden") or {}).items():
            r = _validar_resposta("golden", item_id, bruto, plano, g)
            if item_id not in por_id:
                plano.erros.append(f"{g}/golden/{item_id}: item não pertence a este anotador")
            elif r:
                recebidos["golden"].add(item_id)
                _aplicar_campos(por_id[item_id], r, plano, f"{g}/golden/{item_id}", "golden")

        for item_id, bruto in (e.get("revisao") or {}).items():
            r = _validar_resposta("revisao", item_id, bruto, plano, g)
            if item_id not in blocos.get(g, []):
                plano.erros.append(f"{g}/revisao/{item_id}: pergunta fora do bloco deste revisor")
            elif r and item_id in rev_por_id:
                recebidos["revisao"].add(item_id)
                _aplicar_campos(rev_por_id[item_id], r, plano, f"{g}/revisao/{item_id}", "revisao")

        for item_id, bruto in (e.get("juiz") or {}).items():
            r = _validar_resposta("juiz", item_id, bruto, plano, g)
            linha = juiz_por_id.get(item_id)
            if linha is None:
                plano.erros.append(f"{g}/juiz/{item_id}: item inexistente em {juiz.name}")
                continue
            if g == linha.get("anotador_1"):
                coluna = "veredito_humano_1"
            elif g == linha.get("anotador_2"):
                coluna = "veredito_humano_2"
            else:
                plano.erros.append(f"{g}/juiz/{item_id}: item não atribuído a este avaliador")
                continue
            if r:
                recebidos["juiz"].add(item_id)
                _aplicar_campos(
                    linha, {coluna: r["veredito"]}, plano, f"{g}/juiz/{item_id}", "juiz"
                )

        esperado = {
            "golden": set(por_id),
            "revisao": set(blocos.get(g, [])),
            "juiz": {
                i for i, x in juiz_por_id.items() if g in (x.get("anotador_1"), x.get("anotador_2"))
            },
        }
        plano.ausentes[g] = {f: len(esperado[f] - recebidos[f]) for f in esperado}

    if plano.erros:
        return plano
    for g, (cols, linhas) in csvs_pessoa.items():
        plano.arquivos[pasta / f"{g}.csv"] = _texto_csv(cols, linhas)
    plano.arquivos[revisao] = _texto_csv(rev_cols, rev_linhas)
    if juiz_linhas:
        plano.arquivos[juiz] = _texto_csv(juiz_cols, juiz_linhas)
    return plano


def _escrever_atomico(caminho: Path, texto: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=caminho.parent, prefix=caminho.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(texto)
    os.replace(tmp, caminho)


def aplicar(
    plano: Plano,
    bruto: bytes,
    dados: dict[str, Any],
    log: Path = LOG,
    backup_em: Path | None = None,
) -> Path:
    if plano.erros:
        raise ErroImportacao("; ".join(plano.erros[:5]))
    carimbo = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pasta_backup = (backup_em or log.parent / ".backup") / carimbo
    pasta_backup.mkdir(parents=True, exist_ok=True)
    for caminho in plano.arquivos:
        if caminho.exists():
            shutil.copy2(caminho, pasta_backup / caminho.name)
    for caminho, texto in plano.arquivos.items():
        if not caminho.exists() or caminho.read_text(encoding="utf-8") != texto:
            _escrever_atomico(caminho, texto)
    entrada = {
        "em": datetime.now(UTC).isoformat(),
        "sha256_export": hashlib.sha256(bruto).hexdigest(),
        "exportado_em": dados.get("exportado_em"),
        "versao_pagina": dados.get("versao_pagina"),
        "hash_golden_set": dados.get("hash_golden_set"),
        "novos": plano.novos,
        "iguais": plano.iguais,
        "pessoas": sorted(e["github"] for e in dados["entregas"]),
    }
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return pasta_backup


def relatorio(plano: Plano) -> str:
    linhas = []
    for e in plano.erros:
        linhas.append(f"ERRO  {e}")
    for a in plano.avisos:
        linhas.append(f"AVISO {a}")
    linhas.append(f"novos: {plano.novos}  já iguais: {plano.iguais}")
    for g, f in sorted(plano.ausentes.items()):
        linhas.append(f"faltam {g}: golden {f['golden']}, revisão {f['revisao']}, juiz {f['juiz']}")
    return "\n".join(linhas)


def _chave(github: str, codigo: str) -> bytes:
    cod = "".join(c for c in codigo.upper() if c.isalnum())
    return hashlib.pbkdf2_hmac("sha256", cod.encode(), f"fa-anot:{github}".encode(), 100_000, 32)


def verificar_assinatura(entrega: dict[str, Any], codigos: dict[str, str]) -> dict[str, Any]:
    """Confere a assinatura de uma entrega v2 e devolve a entrega já aberta (formato v1)."""
    g = entrega.get("github")
    if g not in codigos:
        raise ErroImportacao(f"{g}: sem código no arquivo de códigos")
    esperado = hmac.new(_chave(g, codigos[g]), str(entrega.get("corpo", "")).encode(), "sha256")
    if not hmac.compare_digest(esperado.hexdigest(), str(entrega.get("assinatura", ""))):
        raise ErroImportacao(f"{g}: assinatura não confere (texto alterado ou código errado)")
    corpo: dict[str, Any] = json.loads(entrega["corpo"])
    if corpo.get("github") != g:
        raise ErroImportacao(f"{g}: o corpo assinado é de {corpo.get('github')!r}")
    return corpo


def juntar_exports(
    arquivos: list[dict[str, Any]],
    codigos: dict[str, str] | None = None,
    exigir_assinatura: bool = False,
) -> dict[str, Any]:
    """Aceita o export do banco e/ou arquivos individuais baixados ou colados pelas pessoas.

    Entrega v2 (`corpo` + `assinatura`) é verificada com o código pessoal. Entrega v1 não tem
    assinatura: com `exigir_assinatura` ela é recusada. Duas entregas da mesma pessoa viram erro
    no planejamento.
    """
    entregas: list[dict[str, Any]] = []
    base: dict[str, Any] = {"esquema_versao": ESQUEMA}
    for a in arquivos:
        if isinstance(a.get("entregas"), list):
            entregas.extend(a["entregas"])
            base.update({k: v for k, v in a.items() if k != "entregas"})
        elif a.get("esquema_versao") == 2 and "corpo" in a:
            if codigos is None:
                raise ErroImportacao("entrega assinada sem arquivo de códigos (--codigos)")
            entregas.append(verificar_assinatura(a, codigos))
        elif "github" in a:
            if exigir_assinatura:
                raise ErroImportacao(
                    f"{a['github']}: entrega sem assinatura (use --aceitar-sem-assinatura)"
                )
            entregas.append({k: v for k, v in a.items() if k != "esquema_versao"})
        else:
            raise ErroImportacao("arquivo sem `entregas`, `corpo` nem `github`")
    return {**base, "entregas": entregas}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument(
        "export", type=Path, nargs="+", help="JSON exportado do banco e/ou arquivos individuais"
    )
    ap.add_argument("--aplicar", action="store_true", help="grava os CSV (padrão: só simula)")
    ap.add_argument(
        "--codigos",
        type=Path,
        default=None,
        help="JSON {usuario: código} para verificar assinaturas",
    )
    ap.add_argument(
        "--aceitar-sem-assinatura", action="store_true", help="aceita entregas v1 sem assinatura"
    )
    args = ap.parse_args(argv)
    brutos = [e.read_bytes() for e in args.export]
    bruto = b"\n".join(brutos)
    try:
        codigos = json.loads(args.codigos.read_text(encoding="utf-8")) if args.codigos else None
        dados = juntar_exports(
            [json.loads(b) for b in brutos],
            codigos,
            exigir_assinatura=not args.aceitar_sem_assinatura,
        )
    except ErroImportacao as erro:
        print(f"ERRO  {erro}\nNada foi gravado.")
        return 1
    plano = planejar(dados)
    print(relatorio(plano))
    if plano.erros:
        print("Nada foi gravado.")
        return 1
    if not args.aplicar:
        print("Simulação: nada foi gravado. Use --aplicar para gravar.")
        return 0
    backup = aplicar(plano, bruto, dados)
    print(f"Gravado. Backup em {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
