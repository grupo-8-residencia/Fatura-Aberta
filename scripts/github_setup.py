#!/usr/bin/env python3
"""Cria labels, milestones e issues no GitHub a partir de `planejamento/*.yaml`.

Uso:
    uv run python scripts/github_setup.py                # --dry-run (padrão): só mostra o plano
    uv run python scripts/github_setup.py --aplicar      # cria/atualiza de verdade
    uv run python scripts/github_setup.py --aplicar --projeto   # também o GitHub Project (v2)

Idempotente: rodar de novo não duplica nada.
- Label: criada; se cor ou descrição mudaram, atualizada.
- Milestone: casado pelo título; descrição e data atualizadas se mudaram.
- Issue: casada pelo marcador `<!-- fa-id: S1-01 -->` (ou, na falta dele, pelo título exato).
  Se já existe, o corpo NÃO é reescrito (para não apagar checklists marcados); só são
  acrescentados labels, assignees e milestone que estiverem faltando.

Requer o `gh` instalado e autenticado (`gh auth status`). O dry-run tenta ler o estado atual do
GitHub; se não conseguir (sem `gh`, sem login ou repositório inexistente), assume tudo vazio.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PLANEJAMENTO = RAIZ / "planejamento"
A_CONFIRMAR = "A_CONFIRMAR"
MARCADOR = "<!-- fa-id: {id} -->"


class ErroGh(RuntimeError):
    """Falha ao executar o `gh`."""


# --------------------------------------------------------------------------- modelos


@dataclass(frozen=True)
class Label:
    nome: str
    cor: str
    descricao: str


@dataclass(frozen=True)
class Milestone:
    titulo: str
    descricao: str
    vence_em: date


@dataclass(frozen=True)
class Issue:
    id: str
    titulo: str
    corpo: str
    labels: tuple[str, ...]
    milestone: str
    assignees: tuple[str, ...]
    frente: str
    sprint: str


@dataclass
class Plano:
    repositorio: str
    labels: list[Label] = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    projeto: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- leitura do plano


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    with caminho.open(encoding="utf-8") as arquivo:
        dados = yaml.safe_load(arquivo)
    if not isinstance(dados, dict):
        raise ValueError(f"{caminho} deve conter um mapa YAML")
    return dados


def sexta_da_sprint(inicio: date, numero: int) -> date:
    """Sexta-feira da sprint `numero` (1 = primeira), dado o início na segunda-feira."""
    return inicio + timedelta(days=7 * (numero - 1) + 4)


def corpo_da_issue(bruta: dict[str, Any], frente: dict[str, Any], responsaveis: list[str]) -> str:
    """Monta o corpo no mesmo formato de `.github/ISSUE_TEMPLATE/tarefa.yml`."""
    quem = ", ".join(responsaveis) if responsaveis else "—"
    tarefas = "\n".join(f"- [ ] {t}" for t in bruta["tarefas"])
    criterios = "\n".join(f"- [ ] {c}" for c in bruta["criterios"])
    contexto = str(bruta["contexto"]).strip()
    return (
        f"{MARCADOR.format(id=bruta['id'])}\n"
        f"**Sprint:** {bruta['sprint']} · **Frente:** {bruta['frente']} "
        f"({frente['funcao']}) · **Responsável:** {quem}\n\n"
        f"### Contexto\n\n{contexto}\n\n"
        f"### Tarefas\n\n{tarefas}\n\n"
        f"### Critérios de aceite\n\n{criterios}\n"
    )


def carregar_plano(pasta: Path = PLANEJAMENTO, repositorio: str | None = None) -> Plano:
    sprints = _ler_yaml(pasta / "sprints.yaml")
    backlog = _ler_yaml(pasta / "issues.yaml")

    inicio = sprints["inicio"]
    if not isinstance(inicio, date):
        raise ValueError("`inicio` em sprints.yaml deve ser uma data (AAAA-MM-DD)")
    if inicio.weekday() != 0:
        raise ValueError(f"`inicio` ({inicio}) não é uma segunda-feira")

    plano = Plano(
        repositorio=repositorio or sprints["repositorio"],
        projeto=backlog.get("projeto", {}),
    )

    # Labels: as de frente (uma cor por frente) e as fixas.
    for codigo, frente in backlog["frentes"].items():
        descricao = f"{frente['funcao']}"[:100]
        plano.labels.append(Label(f"frente:{codigo}", str(frente["cor"]), descricao))
    for rotulo in backlog["labels"]:
        plano.labels.append(Label(rotulo["nome"], str(rotulo["cor"]), rotulo["descricao"]))
    nomes_labels = {rotulo.nome for rotulo in plano.labels}

    # Milestones.
    titulos: dict[str, str] = {}
    for indice, sprint in enumerate(sprints["sprints"], start=1):
        titulo = f"{sprint['codigo']} — {sprint['titulo']}"
        titulos[sprint["codigo"]] = titulo
        descricao = f"Entregável: {sprint['entregavel']}\nGate: {sprint['gate']}"
        plano.milestones.append(Milestone(titulo, descricao, sexta_da_sprint(inicio, indice)))

    # Issues.
    equipe: dict[str, str] = backlog["equipe"]
    ids_vistos: set[str] = set()
    titulos_vistos: set[str] = set()
    for bruta in backlog["issues"]:
        if bruta["id"] in ids_vistos or bruta["titulo"] in titulos_vistos:
            raise ValueError(f"issue duplicada: {bruta['id']} / {bruta['titulo']}")
        ids_vistos.add(bruta["id"])
        titulos_vistos.add(bruta["titulo"])

        frente = backlog["frentes"][bruta["frente"]]
        responsaveis = bruta.get("responsaveis") or [frente["responsavel"]]
        assignees = tuple(login for nome in responsaveis if (login := equipe[nome]) != A_CONFIRMAR)
        labels = (f"frente:{bruta['frente']}", *bruta["labels"])
        desconhecidas = set(labels) - nomes_labels
        if desconhecidas:
            raise ValueError(f"{bruta['id']}: labels inexistentes: {sorted(desconhecidas)}")
        if bruta["sprint"] not in titulos:
            raise ValueError(f"{bruta['id']}: sprint inexistente: {bruta['sprint']}")

        plano.issues.append(
            Issue(
                id=bruta["id"],
                titulo=bruta["titulo"],
                corpo=corpo_da_issue(bruta, frente, responsaveis),
                labels=labels,
                milestone=titulos[bruta["sprint"]],
                assignees=assignees,
                frente=bruta["frente"],
                sprint=bruta["sprint"],
            )
        )
    return plano


# --------------------------------------------------------------------------- acesso ao GitHub


class GitHub(Protocol):
    """Operações de que o script precisa. `GhCli` implementa com o `gh`."""

    def listar_labels(self) -> dict[str, dict[str, str]]: ...
    def salvar_label(self, label: Label) -> None: ...
    def listar_milestones(self) -> dict[str, dict[str, Any]]: ...
    def criar_milestone(self, milestone: Milestone) -> None: ...
    def atualizar_milestone(self, numero: int, milestone: Milestone) -> None: ...
    def listar_issues(self) -> list[dict[str, Any]]: ...
    def criar_issue(self, issue: Issue) -> str: ...
    def editar_issue(
        self,
        numero: int,
        *,
        adicionar_labels: list[str],
        milestone: str | None,
        adicionar_assignees: list[str],
    ) -> None: ...


Executor = Callable[..., str]


def executar_gh(args: list[str], entrada: str | None = None) -> str:
    """Roda `gh` e devolve a saída padrão; levanta `ErroGh` em caso de falha."""
    try:
        resultado = subprocess.run(
            ["gh", *args], input=entrada, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as erro:
        raise ErroGh("`gh` não está instalado (brew install gh)") from erro
    if resultado.returncode != 0:
        raise ErroGh(f"gh {' '.join(args[:3])} falhou: {resultado.stderr.strip()}")
    return resultado.stdout


def _due_on(milestone: Milestone) -> str:
    # Meio-dia UTC evita que fusos de -12 a +11 mudem o dia exibido.
    return f"{milestone.vence_em.isoformat()}T12:00:00Z"


class GhCli:
    def __init__(self, repositorio: str, executor: Executor | None = None) -> None:
        self.repo = repositorio
        # Resolve `executar_gh` na hora da chamada (facilita trocar o executor nos testes).
        self.executor = executor or (lambda *args, **kwargs: executar_gh(*args, **kwargs))

    def listar_labels(self) -> dict[str, dict[str, str]]:
        saida = self.executor(
            ["label", "list", "--repo", self.repo, "--limit", "200",
             "--json", "name,color,description"]
        )  # fmt: skip
        return {item["name"]: item for item in json.loads(saida or "[]")}

    def salvar_label(self, label: Label) -> None:
        self.executor(
            ["label", "create", label.nome, "--repo", self.repo,
             "--color", label.cor, "--description", label.descricao, "--force"]
        )  # fmt: skip

    def listar_milestones(self) -> dict[str, dict[str, Any]]:
        saida = self.executor(
            ["api", "--paginate", "--slurp", f"repos/{self.repo}/milestones?state=all&per_page=100"]
        )
        paginas = json.loads(saida or "[]")
        return {item["title"]: item for pagina in paginas for item in pagina}

    def criar_milestone(self, milestone: Milestone) -> None:
        self.executor(
            ["api", "-X", "POST", f"repos/{self.repo}/milestones",
             "-f", f"title={milestone.titulo}", "-f", f"description={milestone.descricao}",
             "-f", f"due_on={_due_on(milestone)}"]
        )  # fmt: skip

    def atualizar_milestone(self, numero: int, milestone: Milestone) -> None:
        self.executor(
            ["api", "-X", "PATCH", f"repos/{self.repo}/milestones/{numero}",
             "-f", f"description={milestone.descricao}", "-f", f"due_on={_due_on(milestone)}"]
        )  # fmt: skip

    def listar_issues(self) -> list[dict[str, Any]]:
        saida = self.executor(
            ["issue", "list", "--repo", self.repo, "--state", "all", "--limit", "1000",
             "--json", "number,title,body,url,labels,milestone,assignees"]
        )  # fmt: skip
        return [
            {
                "number": item["number"],
                "title": item["title"],
                "body": item.get("body") or "",
                "url": item["url"],
                "labels": [rotulo["name"] for rotulo in item["labels"]],
                "milestone": (item.get("milestone") or {}).get("title"),
                "assignees": [pessoa["login"] for pessoa in item["assignees"]],
            }
            for item in json.loads(saida or "[]")
        ]

    def criar_issue(self, issue: Issue) -> str:
        args = ["issue", "create", "--repo", self.repo, "--title", issue.titulo,
                "--body-file", "-", "--milestone", issue.milestone]  # fmt: skip
        for rotulo in issue.labels:
            args += ["--label", rotulo]
        for login in issue.assignees:
            args += ["--assignee", login]
        return self.executor(args, entrada=issue.corpo).strip()

    def editar_issue(
        self,
        numero: int,
        *,
        adicionar_labels: list[str],
        milestone: str | None,
        adicionar_assignees: list[str],
    ) -> None:
        args = ["issue", "edit", str(numero), "--repo", self.repo]
        if adicionar_labels:
            args += ["--add-label", ",".join(adicionar_labels)]
        if milestone:
            args += ["--milestone", milestone]
        if adicionar_assignees:
            args += ["--add-assignee", ",".join(adicionar_assignees)]
        self.executor(args)


class GitHubVazio:
    """Estado vazio para o dry-run quando o GitHub não pode ser consultado."""

    def listar_labels(self) -> dict[str, dict[str, str]]:
        return {}

    def listar_milestones(self) -> dict[str, dict[str, Any]]:
        return {}

    def listar_issues(self) -> list[dict[str, Any]]:
        return []


# --------------------------------------------------------------------------- sincronização


@dataclass
class Resumo:
    criados: int = 0
    atualizados: int = 0
    inalterados: int = 0

    def somar(self, outro: Resumo) -> None:
        self.criados += outro.criados
        self.atualizados += outro.atualizados
        self.inalterados += outro.inalterados


Log = Callable[[str], None]


def sincronizar_labels(plano: Plano, gh: GitHub, aplicar: bool, log: Log) -> Resumo:
    resumo = Resumo()
    existentes = gh.listar_labels()
    for label in plano.labels:
        atual = existentes.get(label.nome)
        if atual is None:
            log(f"[criar]      label {label.nome}")
            resumo.criados += 1
        elif (atual.get("color", "").lower() != label.cor.lower()
              or (atual.get("description") or "") != label.descricao):  # fmt: skip
            log(f"[atualizar]  label {label.nome}")
            resumo.atualizados += 1
        else:
            resumo.inalterados += 1
            continue
        if aplicar:
            gh.salvar_label(label)
    return resumo


def sincronizar_milestones(plano: Plano, gh: GitHub, aplicar: bool, log: Log) -> Resumo:
    resumo = Resumo()
    existentes = gh.listar_milestones()
    for milestone in plano.milestones:
        atual = existentes.get(milestone.titulo)
        quando = milestone.vence_em.strftime("%d/%m/%Y")
        if atual is None:
            log(f"[criar]      milestone {milestone.titulo} (entrega {quando})")
            resumo.criados += 1
            if aplicar:
                gh.criar_milestone(milestone)
            continue
        data_atual = (atual.get("due_on") or "")[:10]
        if (atual.get("description") or "") != milestone.descricao or (
            data_atual != milestone.vence_em.isoformat()
        ):
            log(f"[atualizar]  milestone {milestone.titulo} (entrega {quando})")
            resumo.atualizados += 1
            if aplicar:
                gh.atualizar_milestone(int(atual["number"]), milestone)
        else:
            resumo.inalterados += 1
    return resumo


def _achar_existente(issue: Issue, existentes: list[dict[str, Any]]) -> dict[str, Any] | None:
    marcador = MARCADOR.format(id=issue.id)
    for item in existentes:
        if marcador in item["body"]:
            return item
    for item in existentes:
        if item["title"] == issue.titulo:
            return item
    return None


def sincronizar_issues(plano: Plano, gh: GitHub, aplicar: bool, log: Log) -> Resumo:
    resumo = Resumo()
    existentes = gh.listar_issues()
    for issue in plano.issues:
        atual = _achar_existente(issue, existentes)
        quem = ",".join(issue.assignees) or "sem assignee"
        if atual is None:
            log(f"[criar]      issue {issue.id} {issue.titulo} ({issue.milestone[:2]}, {quem})")
            resumo.criados += 1
            if aplicar:
                url = gh.criar_issue(issue)
                existentes.append(
                    {"number": 0, "title": issue.titulo, "body": issue.corpo, "url": url,
                     "labels": list(issue.labels), "milestone": issue.milestone,
                     "assignees": list(issue.assignees)}
                )  # fmt: skip
            continue
        faltam_labels = [rotulo for rotulo in issue.labels if rotulo not in atual["labels"]]
        faltam_pessoas = [login for login in issue.assignees if login not in atual["assignees"]]
        novo_milestone = issue.milestone if atual["milestone"] != issue.milestone else None
        if faltam_labels or faltam_pessoas or novo_milestone:
            log(f"[atualizar]  issue #{atual['number']} {issue.id} (só acrescenta o que falta)")
            resumo.atualizados += 1
            if aplicar:
                gh.editar_issue(
                    int(atual["number"]),
                    adicionar_labels=faltam_labels,
                    milestone=novo_milestone,
                    adicionar_assignees=faltam_pessoas,
                )
        else:
            resumo.inalterados += 1
    return resumo


# --------------------------------------------------------------------------- Project (v2)

_MUTACAO_OPCOES = """
mutation($campo: ID!, $opcoes: [ProjectV2SingleSelectFieldOptionInput!]!) {
  updateProjectV2Field(input: {fieldId: $campo, singleSelectOptions: $opcoes}) {
    projectV2Field { ... on ProjectV2SingleSelectField { id name options { id name } } }
  }
}
"""


def sincronizar_projeto(
    plano: Plano, executor: Executor, issues: list[dict[str, Any]], aplicar: bool, log: Log
) -> None:
    """Cria o GitHub Project "Fatura Aberta" com campos Status, Frente e Sprint.

    EXPERIMENTAL: depende do escopo `project` (`gh auth refresh -s project`) e ainda não foi
    exercitado contra o GitHub real; por isso só roda com --projeto e confirmação do time.
    """
    titulo = plano.projeto.get("titulo", "Fatura Aberta")
    status = list(plano.projeto.get("status", ["A fazer", "Em andamento", "Em revisão", "Feito"]))
    frentes = sorted({i.frente for i in plano.issues})
    sprints = sorted({i.sprint for i in plano.issues})
    dono = plano.repositorio.split("/")[0]
    log(f"[projeto]    '{titulo}' em {dono}: Status {status}, Frente {frentes}, Sprint {sprints}")
    log(f"[projeto]    adicionaria {len(plano.issues)} issues e preencheria Status/Frente/Sprint")
    if not aplicar:
        return

    projetos = json.loads(
        executor(["project", "list", "--owner", dono, "--format", "json", "--limit", "100"])
    )["projects"]
    projeto = next((p for p in projetos if p["title"] == titulo), None)
    if projeto is None:
        projeto = json.loads(
            executor(["project", "create", "--owner", dono, "--title", titulo, "--format", "json"])
        )
    numero = str(projeto["number"])

    def campos() -> dict[str, dict[str, Any]]:
        saida = executor(["project", "field-list", numero, "--owner", dono, "--format", "json"])
        return {c["name"]: c for c in json.loads(saida)["fields"]}

    por_nome = campos()
    opcoes_status = [{"name": n, "color": "GRAY", "description": ""} for n in status]
    nomes_atuais = [o["name"] for o in por_nome["Status"].get("options", [])]
    if nomes_atuais != status:
        variaveis = {"campo": por_nome["Status"]["id"], "opcoes": opcoes_status}
        corpo = {"query": _MUTACAO_OPCOES, "variables": variaveis}
        executor(["api", "graphql", "--input", "-"], entrada=json.dumps(corpo))
    for nome, valores in (("Frente", frentes), ("Sprint", sprints)):
        if nome not in por_nome:
            executor(
                ["project", "field-create", numero, "--owner", dono, "--name", nome,
                 "--data-type", "SINGLE_SELECT", "--single-select-options", ",".join(valores)]
            )  # fmt: skip
    por_nome = campos()

    def opcao(campo: str, nome: str) -> tuple[str, str]:
        achada = next(o for o in por_nome[campo]["options"] if o["name"] == nome)
        return por_nome[campo]["id"], achada["id"]

    por_titulo = {i["title"]: i for i in issues}
    for issue in plano.issues:
        existente = por_titulo.get(issue.titulo)
        if existente is None:
            log(f"[projeto]    pulando {issue.id}: issue ainda não existe no GitHub")
            continue
        item = json.loads(
            executor(["project", "item-add", numero, "--owner", dono,
                      "--url", existente["url"], "--format", "json"])
        )  # fmt: skip
        for campo, valor in (("Status", status[0]), ("Frente", issue.frente),
                             ("Sprint", issue.sprint)):  # fmt: skip
            id_campo, id_opcao = opcao(campo, valor)
            executor(
                ["project", "item-edit", "--id", item["id"], "--project-id", projeto["id"],
                 "--field-id", id_campo, "--single-select-option-id", id_opcao]
            )  # fmt: skip


# --------------------------------------------------------------------------- linha de comando


def sincronizar(plano: Plano, gh: GitHub, aplicar: bool, log: Log) -> dict[str, Resumo]:
    return {
        "labels": sincronizar_labels(plano, gh, aplicar, log),
        "milestones": sincronizar_milestones(plano, gh, aplicar, log),
        "issues": sincronizar_issues(plano, gh, aplicar, log),
    }


def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="só mostra o plano (padrão)")
    modo.add_argument("--aplicar", action="store_true", help="cria/atualiza no GitHub")
    parser.add_argument("--repo", help="OWNER/NOME; padrão: `repositorio` de sprints.yaml")
    parser.add_argument("--projeto", action="store_true", help="também cria o GitHub Project (v2)")
    parser.add_argument("--planejamento", type=Path, default=PLANEJAMENTO)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _montar_parser().parse_args(argv)
    aplicar = bool(args.aplicar)
    plano = carregar_plano(args.planejamento, args.repo)
    print(f"Repositório: {plano.repositorio}")
    print(f"Modo: {'APLICAR' if aplicar else 'DRY-RUN (nada será alterado)'}\n")

    gh: GitHub = GhCli(plano.repositorio)
    try:
        if aplicar:
            executar_gh(["auth", "status"])
        issues_atuais = gh.listar_issues()
    except ErroGh as erro:
        if aplicar:
            print(f"ERRO: {erro}", file=sys.stderr)
            return 1
        print(f"AVISO: não consegui ler o GitHub ({erro}); assumindo repositório vazio.\n")
        gh = GitHubVazio()  # type: ignore[assignment]
        issues_atuais = []

    try:
        resumo = sincronizar(plano, gh, aplicar, print)
        if args.projeto:
            if aplicar:
                issues_atuais = gh.listar_issues()
            sincronizar_projeto(plano, executar_gh, issues_atuais, aplicar, print)
    except ErroGh as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1

    print("\nResumo:")
    for nome, parte in resumo.items():
        print(
            f"  {nome:<11} criar={parte.criados:<3} atualizar={parte.atualizados:<3} "
            f"sem mudança={parte.inalterados}"
        )
    if not aplicar:
        print("\nNada foi alterado. Rode com --aplicar para executar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
