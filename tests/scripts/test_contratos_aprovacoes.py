"""Testes do job `contratos-aprovacoes` definido em `.github/workflows/ci.yml`."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI_YML = RAIZ / ".github" / "workflows" / "ci.yml"


def _extrair_script_python() -> str:
    """Extrai o bloco `python - <<'PY' ... PY` do job `contratos-aprovacoes`."""
    dados = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    job = dados["jobs"]["contratos-aprovacoes"]
    comando = job["steps"][0]["run"]
    casamento = re.search(r"python - <<'PY'\n(.*?)\nPY", comando, flags=re.DOTALL)
    assert casamento is not None, "Bloco Python não encontrado em contratos-aprovacoes"
    return casamento.group(1)


def _executar_validacao(
    *,
    files: list[Any],
    reviews: list[Any],
    head_sha: str = "sha-atual-123",
    pr_author: str = "autor-pr",
) -> subprocess.CompletedProcess[str]:
    script = _extrair_script_python()
    env = {
        **os.environ,
        "PULL_JSON": json.dumps({"head": {"sha": head_sha}}),
        "FILES_JSON": json.dumps(files),
        "REVIEWS_JSON": json.dumps(reviews),
        "PR_AUTHOR": pr_author,
    }
    return subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _revisao(
    login: str,
    state: str = "APPROVED",
    commit_id: str = "sha-atual-123",
    submitted_at: str = "2026-11-04T12:00:00Z",
    user_type: str = "User",
    dismissed_at: str | None = None,
) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "user": {"login": login, "type": user_type},
        "state": state,
        "commit_id": commit_id,
        "submitted_at": submitted_at,
    }
    if dismissed_at is not None:
        dados["dismissed_at"] = dismissed_at
    return dados


def test_ausencia_de_alteracoes_contratuais_aprova() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/motor/src/fa_motor/__init__.py"}]],
        reviews=[[]],
    )
    assert resultado.returncode == 0
    assert "Nenhuma alteração em packages/contratos/." in resultado.stdout


def test_apenas_uma_aprovacao_falha() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/contratos/src/fa_contratos/fatura.py"}]],
        reviews=[[_revisao("revisor-1")]],
    )
    assert resultado.returncode == 1
    assert "Aprovações válidas encontradas: 1" in resultado.stdout
    assert "duas aprovações humanas distintas" in resultado.stdout


def test_duas_aprovacoes_validas_aprova() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/contratos/src/fa_contratos/fatura.py"}]],
        reviews=[[_revisao("revisor-1"), _revisao("revisor-2")]],
    )
    assert resultado.returncode == 0
    assert "Aprovações válidas encontradas: 2" in resultado.stdout
    assert "Duas aprovações válidas encontradas." in resultado.stdout


def test_aprovacao_do_proprio_autor_e_ignorada() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/contratos/src/fa_contratos/fatura.py"}]],
        reviews=[[_revisao("Autor-PR"), _revisao("revisor-1")]],
        pr_author="autor-pr",
    )
    assert resultado.returncode == 1
    assert "Aprovações válidas encontradas: 1" in resultado.stdout


def test_aprovacao_de_bots_e_ignorada() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/contratos/src/fa_contratos/fatura.py"}]],
        reviews=[
            [
                _revisao("revisor-1"),
                _revisao("dependabot[bot]", user_type="Bot"),
                _revisao("automacao[bot]", user_type="User"),
                _revisao("ci-bot", user_type="Bot"),
            ]
        ],
    )
    assert resultado.returncode == 1
    assert "Aprovações válidas encontradas: 1" in resultado.stdout


def test_aprovacao_em_commit_desatualizado_falha() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/contratos/src/fa_contratos/fatura.py"}]],
        reviews=[
            [
                _revisao("revisor-1", commit_id="sha-atual-123"),
                _revisao("revisor-2", commit_id="sha-antigo-000"),
            ]
        ],
        head_sha="sha-atual-123",
    )
    assert resultado.returncode == 1
    assert "Aprovações válidas encontradas: 1" in resultado.stdout


def test_revisao_mais_recente_alterando_aprovacao_anterior_falha() -> None:
    resultado = _executar_validacao(
        files=[[{"filename": "packages/contratos/src/fa_contratos/fatura.py"}]],
        reviews=[
            [
                _revisao("revisor-1", state="APPROVED", submitted_at="2026-11-04T12:00:00Z"),
                _revisao("revisor-2", state="APPROVED", submitted_at="2026-11-04T12:01:00Z"),
                _revisao(
                    "revisor-2",
                    state="CHANGES_REQUESTED",
                    submitted_at="2026-11-04T12:05:00Z",
                ),
            ]
        ],
    )
    assert resultado.returncode == 1
    assert "Aprovações válidas encontradas: 1" in resultado.stdout


def test_aprovacao_posteriormente_descartada_falha() -> None:
    resultado = _executar_validacao(
        files=[[{"previous_filename": "packages/contratos/src/fa_contratos/antigo.py"}]],
        reviews=[
            [
                _revisao("revisor-1"),
                _revisao("revisor-2", dismissed_at="2026-11-04T12:10:00Z"),
                _revisao("revisor-3", state="DISMISSED"),
            ]
        ],
    )
    assert resultado.returncode == 1
    assert "Aprovações válidas encontradas: 1" in resultado.stdout


def test_workflows_reduzem_o_json_antes_de_exportar() -> None:
    """PRs grandes estouravam o limite de argumento ("Argument list too long") ao exportar o
    JSON completo (com os diffs) como variável de ambiente."""
    for nome in ("ci.yml", "contratos-revisao.yml"):
        texto = (RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8")
        assert texto.count("| jq -c") == 3, nome
        assert "{filename, previous_filename}" in texto, nome


def test_validacao_aceita_payload_grande_reduzido() -> None:
    arquivos = [
        {"filename": f"docs/arquivo-{i}.md", "previous_filename": None} for i in range(1200)
    ]
    r = _executar_validacao(files=arquivos, reviews=[])
    assert r.returncode == 0
