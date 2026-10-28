#!/usr/bin/env python3
"""Gera as páginas de frentes e de sprints em `docs/` a partir dos templates e do planejamento.

    uv run python scripts/gerar_paginas.py                  # só cria o que ainda não existe
    uv run python scripts/gerar_paginas.py --sobrescrever   # recria tudo (apaga edições!)

Por padrão NUNCA sobrescreve uma página existente: depois de gerada, ela é do time (é onde vão a
retrospectiva, a decisão do gate e os detalhes da frente).
"""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml
from github_setup import PLANEJAMENTO, RAIZ, carregar_plano, sexta_da_sprint

DOCS = RAIZ / "docs"
TEMPLATES = DOCS / "_templates"


def preencher(modelo: str, valores: dict[str, str]) -> str:
    for chave, valor in valores.items():
        modelo = modelo.replace("{{" + chave + "}}", valor)
    return modelo


def _lista(titulos: list[str]) -> str:
    return "\n".join(f"- [ ] {t}" for t in titulos) if titulos else "- TODO"


def pagina_sprint(
    modelo: str, sprint: dict[str, Any], numero: int, inicio: Any, issues: list[Any]
) -> str:
    sexta = sexta_da_sprint(inicio, numero)
    segunda = sexta - timedelta(days=4)
    por_frente: dict[str, list[str]] = {}
    for issue in issues:
        por_frente.setdefault(issue.frente, []).append(issue.titulo)
    blocos = [
        f"**{frente}**\n\n{_lista(titulos)}" for frente, titulos in sorted(por_frente.items())
    ]
    return preencher(
        modelo,
        {
            "codigo": sprint["codigo"],
            "titulo": sprint["titulo"],
            "periodo": f"{segunda:%d/%m/%Y} a {sexta:%d/%m/%Y}",
            "entregavel": sprint["entregavel"],
            "entrega": f"{sexta:%d/%m/%Y} (sexta-feira)",
            "gate": sprint["gate"],
            "entregaveis": "\n\n".join(blocos) if blocos else "TODO",
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sobrescrever", action="store_true")
    args = parser.parse_args()

    plano = carregar_plano()
    sprints = yaml.safe_load((PLANEJAMENTO / "sprints.yaml").read_text(encoding="utf-8"))
    backlog = yaml.safe_load((PLANEJAMENTO / "issues.yaml").read_text(encoding="utf-8"))
    inicio = sprints["inicio"]
    modelo_sprint = (TEMPLATES / "sprint.md").read_text(encoding="utf-8")
    modelo_frente = (TEMPLATES / "frente.md").read_text(encoding="utf-8")

    saidas: dict[Path, str] = {}
    for numero, sprint in enumerate(sprints["sprints"], start=1):
        deles = [i for i in plano.issues if i.sprint == sprint["codigo"]]
        saidas[DOCS / "sprints" / f"s{numero}.md"] = pagina_sprint(
            modelo_sprint, sprint, numero, inicio, deles
        )

    for codigo, frente in backlog["frentes"].items():
        if codigo == "transversal":
            continue
        github = backlog["equipe"][frente["responsavel"]]
        par = frente["par"]
        par_github = backlog["equipe"].get(par, "")
        deles = [i for i in plano.issues if i.frente == codigo]
        por_sprint: dict[str, list[str]] = {}
        for issue in deles:
            por_sprint.setdefault(issue.sprint, []).append(issue.titulo)
        backlog_md = "\n\n".join(f"**{s}**\n\n{_lista(t)}" for s, t in sorted(por_sprint.items()))
        saidas[DOCS / "frentes" / f"{codigo.lower()}.md"] = preencher(
            modelo_frente,
            {
                "codigo": codigo,
                "funcao": frente["funcao"],
                "responsavel": f"{frente['responsavel']} (`{github}`)",
                "par": f"{par} (`{par_github}`)",
                "pastas": ", ".join(f"`{p}/`" for p in frente["pastas"]) or "—",
                "escopo": frente["escopo"],
                "backlog": backlog_md or "- TODO",
            },
        )

    criadas = puladas = 0
    for caminho, conteudo in saidas.items():
        if caminho.exists() and not args.sobrescrever:
            puladas += 1
            continue
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
        criadas += 1
    print(f"Páginas criadas: {criadas}; já existiam (preservadas): {puladas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
