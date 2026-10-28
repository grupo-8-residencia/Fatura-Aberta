# Como rodar

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho)
- Git
- Docker (opcional, para `docker compose up`)

## Primeira vez

```bash
git clone https://github.com/grupo-8-residencia/Fatura-Aberta.git
cd Fatura-Aberta
uv sync
uv run pre-commit install
```

## Dia a dia

=== "Testes"

    ```bash
    uv run pytest
    ```

=== "Qualidade"

    ```bash
    uv run ruff check .
    uv run ruff format .
    uv run mypy
    uv run pre-commit run --all-files
    ```

=== "Documentação"

    ```bash
    uv run mkdocs serve          # http://127.0.0.1:8000
    uv run mkdocs build --strict
    ```

=== "API"

    ```bash
    docker compose -f infra/docker-compose.yml up --build
    # ou, sem Docker:
    uv run uvicorn fa_api.main:app --reload
    ```

## GitHub (planejamento)

```bash
uv run python scripts/github_setup.py             # dry-run
uv run python scripts/github_setup.py --aplicar   # cria labels, milestones e issues
```

Precisa do [GitHub CLI](https://cli.github.com/) autenticado (`gh auth login`).
