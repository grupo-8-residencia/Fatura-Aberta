"""Testes do scripts/github_setup.py com um GitHub falso em memória (nada vai para a rede)."""

import json
from datetime import date
from typing import Any

import github_setup as gs
import pytest


class GitHubFalso:
    """Implementa a interface `GitHub` guardando o estado em dicionários."""

    def __init__(self) -> None:
        self.labels: dict[str, dict[str, str]] = {}
        self.milestones: dict[str, dict[str, Any]] = {}
        self.issues: list[dict[str, Any]] = []
        self.escritas = 0

    def listar_labels(self) -> dict[str, dict[str, str]]:
        return dict(self.labels)

    def salvar_label(self, label: gs.Label) -> None:
        self.escritas += 1
        self.labels[label.nome] = {
            "name": label.nome, "color": label.cor, "description": label.descricao,
        }  # fmt: skip

    def listar_milestones(self) -> dict[str, dict[str, Any]]:
        return dict(self.milestones)

    def criar_milestone(self, milestone: gs.Milestone) -> None:
        self.escritas += 1
        self.milestones[milestone.titulo] = {
            "number": len(self.milestones) + 1, "title": milestone.titulo,
            "description": milestone.descricao, "due_on": f"{milestone.vence_em}T12:00:00Z",
        }  # fmt: skip

    def atualizar_milestone(self, numero: int, milestone: gs.Milestone) -> None:
        self.escritas += 1
        self.milestones[milestone.titulo].update(
            description=milestone.descricao, due_on=f"{milestone.vence_em}T12:00:00Z"
        )

    def listar_issues(self) -> list[dict[str, Any]]:
        return [dict(i) for i in self.issues]

    def criar_issue(self, issue: gs.Issue) -> str:
        self.escritas += 1
        numero = len(self.issues) + 1
        self.issues.append(
            {"number": numero, "title": issue.titulo, "body": issue.corpo,
             "url": f"https://github.com/x/y/issues/{numero}", "labels": list(issue.labels),
             "milestone": issue.milestone, "assignees": list(issue.assignees)}
        )  # fmt: skip
        return str(self.issues[-1]["url"])

    def editar_issue(
        self,
        numero: int,
        *,
        adicionar_labels: list[str],
        milestone: str | None,
        adicionar_assignees: list[str],
    ) -> None:
        self.escritas += 1
        issue = next(i for i in self.issues if i["number"] == numero)
        issue["labels"] += adicionar_labels
        issue["assignees"] += adicionar_assignees
        if milestone:
            issue["milestone"] = milestone


@pytest.fixture(scope="module")
def plano() -> gs.Plano:
    return gs.carregar_plano()


def test_plano_tem_o_tamanho_esperado(plano: gs.Plano) -> None:
    assert len(plano.milestones) == 7
    assert len(plano.labels) == 19  # 7 de frente + 12 fixas
    assert len(plano.issues) == 51


def test_milestones_vencem_nas_sextas_a_partir_de_26_10_2026(plano: gs.Plano) -> None:
    datas = [m.vence_em for m in plano.milestones]
    assert datas[0] == date(2026, 10, 30)
    assert datas[-1] == date(2026, 12, 11)
    assert all(d.weekday() == 4 for d in datas)
    assert plano.milestones[0].titulo.startswith("S1 — ")


def test_toda_issue_tem_frente_milestone_e_criterios(plano: gs.Plano) -> None:
    titulos_milestones = {m.titulo for m in plano.milestones}
    for issue in plano.issues:
        assert issue.milestone in titulos_milestones
        assert any(rotulo.startswith("frente:") for rotulo in issue.labels)
        assert "### Critérios de aceite" in issue.corpo
        assert f"fa-id: {issue.id}" in issue.corpo


def test_a_confirmar_nunca_vira_assignee(plano: gs.Plano) -> None:
    por_id = {i.id: i for i in plano.issues}
    assert por_id["S1-01"].assignees == ("NatyEvelin",)  # F1 = Natalia
    assert por_id["S1-04"].assignees == ("NatyEvelin", "pedrohpsantos")  # Natalia + Pedro
    assert por_id["S1-08"].assignees == ("TalitaaNunes",)
    assert gs.A_CONFIRMAR not in {a for i in plano.issues for a in i.assignees}


def test_issues_de_gate_tem_label_gate(plano: gs.Plano) -> None:
    com_gate = {i.id for i in plano.issues if "gate" in i.labels}
    assert {"S1-01", "S1-05", "S1-06", "S1-08", "S2-03", "S2-04", "S3-02", "S4-02"} <= com_gate
    assert {"S5-02", "S6-03", "S7-02", "S7-05", "S1-23"} <= com_gate


def test_dry_run_nao_escreve_nada(plano: gs.Plano) -> None:
    gh = GitHubFalso()
    linhas: list[str] = []
    resumo = gs.sincronizar(plano, gh, aplicar=False, log=linhas.append)
    assert gh.escritas == 0
    assert resumo["issues"].criados == 51
    assert any("issue S1-01" in linha for linha in linhas)


def test_aplicar_cria_e_segunda_rodada_nao_duplica(plano: gs.Plano) -> None:
    gh = GitHubFalso()
    gs.sincronizar(plano, gh, aplicar=True, log=lambda _: None)
    assert len(gh.labels) == 19
    assert len(gh.milestones) == 7
    assert len(gh.issues) == 51

    escritas_antes = gh.escritas
    resumo = gs.sincronizar(plano, gh, aplicar=True, log=lambda _: None)
    assert gh.escritas == escritas_antes
    assert all(r.criados == 0 and r.atualizados == 0 for r in resumo.values())
    assert len(gh.issues) == 51


def test_issue_existente_pelo_titulo_nao_duplica_e_corpo_nao_e_reescrito(
    plano: gs.Plano,
) -> None:
    gh = GitHubFalso()
    primeira = plano.issues[0]
    gh.issues.append(
        {"number": 7, "title": primeira.titulo, "body": "corpo editado à mão", "url": "u",
         "labels": [], "milestone": None, "assignees": []}
    )  # fmt: skip
    gs.sincronizar(plano, gh, aplicar=True, log=lambda _: None)
    assert len(gh.issues) == 51
    editada = next(i for i in gh.issues if i["number"] == 7)
    assert editada["body"] == "corpo editado à mão"
    assert set(primeira.labels) <= set(editada["labels"])
    assert editada["milestone"] == primeira.milestone


def test_label_com_cor_diferente_e_atualizada(plano: gs.Plano) -> None:
    gh = GitHubFalso()
    gs.sincronizar_labels(plano, gh, aplicar=True, log=lambda _: None)
    gh.labels["gate"]["color"] = "ffffff"
    resumo = gs.sincronizar_labels(plano, gh, aplicar=True, log=lambda _: None)
    assert resumo.atualizados == 1
    assert gh.labels["gate"]["color"] == "000000"


def test_inicio_que_nao_e_segunda_e_rejeitado(tmp_path: Any) -> None:
    for nome in ("sprints.yaml", "issues.yaml"):
        (tmp_path / nome).write_text((gs.PLANEJAMENTO / nome).read_text(encoding="utf-8"))
    texto = (tmp_path / "sprints.yaml").read_text(encoding="utf-8")
    (tmp_path / "sprints.yaml").write_text(texto.replace("2026-10-26", "2026-10-27"))
    with pytest.raises(ValueError, match="segunda-feira"):
        gs.carregar_plano(tmp_path)


# ---- GhCli: confere as linhas de comando sem executar o gh


def test_ghcli_monta_comandos_esperados(plano: gs.Plano) -> None:
    chamadas: list[tuple[list[str], str | None]] = []

    def executor(args: list[str], entrada: str | None = None) -> str:
        chamadas.append((args, entrada))
        return "https://github.com/o/r/issues/9\n"

    gh = gs.GhCli("o/r", executor)
    issue = next(i for i in plano.issues if i.id == "S1-08")
    assert gh.criar_issue(issue).endswith("/issues/9")
    args, corpo = chamadas[-1]
    assert args[:4] == ["issue", "create", "--repo", "o/r"]
    assert "--body-file" in args and args[args.index("--body-file") + 1] == "-"
    assert args[args.index("--assignee") + 1] == "TalitaaNunes"
    assert corpo == issue.corpo

    gh.salvar_label(gs.Label("gate", "000000", "x"))
    assert chamadas[-1][0][:3] == ["label", "create", "gate"]
    assert "--force" in chamadas[-1][0]

    gh.editar_issue(3, adicionar_labels=["a", "b"], milestone="S1 — x", adicionar_assignees=[])
    assert chamadas[-1][0] == [
        "issue", "edit", "3", "--repo", "o/r", "--add-label", "a,b", "--milestone", "S1 — x",
    ]  # fmt: skip


def test_main_dry_run_sem_gh_nao_quebra(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def sem_gh(args: list[str], entrada: str | None = None) -> str:
        raise gs.ErroGh("`gh` não está instalado")

    monkeypatch.setattr(gs, "executar_gh", sem_gh)
    assert gs.main([]) == 0
    saida = capsys.readouterr().out
    assert "DRY-RUN" in saida
    assert "AVISO" in saida
    assert "criar=51" in saida


def test_main_aplicar_sem_gh_falha_com_erro(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def sem_gh(args: list[str], entrada: str | None = None) -> str:
        raise gs.ErroGh("`gh` não está instalado")

    monkeypatch.setattr(gs, "executar_gh", sem_gh)
    assert gs.main(["--aplicar"]) == 1
    assert "ERRO" in capsys.readouterr().err


def test_issues_do_pacote_de_definicao(plano: gs.Plano) -> None:
    pacote = [i for i in plano.issues if i.id in {f"S1-{n}" for n in range(12, 25)}]
    assert len(pacote) == 13
    assert all(i.sprint == "S1" and i.frente == "transversal" for i in pacote)
    # Cada seção tem dono.
    por_id = {i.id: i for i in pacote}
    assert por_id["S1-12"].assignees == ("NatyEvelin",)  # Natalia
    assert por_id["S1-21"].assignees == ("luizoryone",)  # Luiz
    assert por_id["S1-14"].assignees == ("mariadenis",)
    assert por_id["S1-16"].assignees == ("TalitaaNunes",)
    assert por_id["S1-17"].assignees == ("RaissaOliveira19",)
    assert por_id["S1-20"].assignees == ("pedrohpsantos",)


def test_issue_sem_usuario_confirmado_fica_sem_assignee(tmp_path: Any) -> None:
    for nome in ("sprints.yaml", "issues.yaml"):
        (tmp_path / nome).write_text((gs.PLANEJAMENTO / nome).read_text(encoding="utf-8"))
    texto = (tmp_path / "issues.yaml").read_text(encoding="utf-8")
    (tmp_path / "issues.yaml").write_text(
        texto.replace("Natalia: NatyEvelin", "Natalia: A_CONFIRMAR")
    )
    plano = gs.carregar_plano(tmp_path)
    por_id = {i.id: i for i in plano.issues}
    assert por_id["S1-01"].assignees == ()
    assert por_id["S1-04"].assignees == ("pedrohpsantos",)


# ---- Project (v2): quadro e roadmap


class ProjetoFalso:
    """Executor do `gh project` em memória; guarda as chamadas e simula as respostas."""

    def __init__(self, itens_existentes: list[dict[str, Any]] | None = None) -> None:
        self.chamadas: list[list[str]] = []
        self.campos: dict[str, dict[str, Any]] = {
            "Status": {"id": "F-status", "name": "Status", "options": [{"id": "o", "name": "Todo"}]}
        }
        self.itens = itens_existentes or []

    def __call__(self, args: list[str], entrada: str | None = None) -> str:
        self.chamadas.append(args)
        if args[:2] == ["project", "list"]:
            return '{"projects": []}'
        if args[:2] == ["project", "create"]:
            return '{"number": 7, "id": "P1"}'
        if args[:2] == ["project", "field-create"]:
            nome = args[args.index("--name") + 1]
            opcoes = []
            if "--single-select-options" in args:
                valores = args[args.index("--single-select-options") + 1].split(",")
                opcoes = [{"id": f"{nome}-{v}", "name": v} for v in valores]
            self.campos[nome] = {"id": f"F-{nome}", "name": nome, "options": opcoes}
            return "{}"
        if args[:2] == ["project", "field-list"]:
            return json.dumps({"fields": list(self.campos.values())})
        if args[:2] == ["api", "graphql"]:
            corpo = json.loads(entrada or "{}")
            opcoes = corpo["variables"]["opcoes"]
            self.campos["Status"]["options"] = [
                {"id": f"S-{o['name']}", "name": o["name"]} for o in opcoes
            ]
            return "{}"
        if args[:2] == ["project", "item-list"]:
            return json.dumps({"items": self.itens})
        if args[:2] == ["project", "item-add"]:
            return json.dumps({"id": f"I{len(self.chamadas)}"})
        return "{}"

    def comandos(self, *inicio: str) -> list[list[str]]:
        return [c for c in self.chamadas if c[: len(inicio)] == list(inicio)]


def _issues_do_github(plano: gs.Plano) -> list[dict[str, Any]]:
    return [{"title": i.titulo, "url": f"https://github.com/x/y/issues/{n}"}
            for n, i in enumerate(plano.issues, start=1)]  # fmt: skip


def test_projeto_dry_run_nao_chama_o_gh(plano: gs.Plano) -> None:
    falso = ProjetoFalso()
    gs.sincronizar_projeto(plano, falso, [], aplicar=False, log=lambda _: None)
    assert falso.chamadas == []


def test_projeto_cria_campos_itens_e_datas(plano: gs.Plano) -> None:
    falso = ProjetoFalso()
    gs.sincronizar_projeto(plano, falso, _issues_do_github(plano), aplicar=True, log=lambda _: None)
    criados = {c[c.index("--name") + 1] for c in falso.comandos("project", "field-create")}
    assert criados == {"Frente", "Sprint", "Início", "Entrega"}
    assert falso.comandos("project", "link")[0][-2:] == ["--repo", "Fatura-Aberta"]
    assert len(falso.comandos("project", "item-add")) == 51
    assert len(falso.comandos("project", "item-edit")) == 51 * 5
    datas = {
        c[c.index("--date") + 1] for c in falso.comandos("project", "item-edit") if "--date" in c
    }
    assert {"2026-10-26", "2026-10-30", "2026-12-07", "2026-12-11"} <= datas
    assert [o["name"] for o in falso.campos["Status"]["options"]] == [
        "A fazer", "Em andamento", "Em revisão", "Feito",
    ]  # fmt: skip


def test_projeto_segunda_rodada_nao_reseta_status(plano: gs.Plano) -> None:
    issues = _issues_do_github(plano)
    existentes = [
        {"id": f"X{n}", "status": "Em andamento", "content": {"url": i["url"]}}
        for n, i in enumerate(issues, start=1)
    ]
    falso = ProjetoFalso(existentes)
    gs.sincronizar_projeto(plano, falso, issues, aplicar=True, log=lambda _: None)
    assert falso.comandos("project", "item-add") == []
    # Sem o Status: Frente, Sprint, Início e Entrega = 4 edições por item.
    assert len(falso.comandos("project", "item-edit")) == 51 * 4
