# Como contribuir

## Fluxo de trabalho

1. Pegue uma **issue** do board (ou abra uma com o template `tarefa`, `experimento` ou `bug`).
2. Crie a branch no padrão `tipo/numero-da-issue-descricao`, por exemplo `feat/12-motor-icms`.
3. Faça commits pequenos no padrão [Conventional Commits em português](convencoes.md).
4. Abra um **PR pequeno** que fecha a issue (`Closes #12`).
5. O **par de revisão** da frente revisa. Um code owner precisa aprovar e o CI precisa estar verde.
6. Mudou `packages/contratos/`? Use a label `contrato`: exige **2 aprovações**.
7. Merge na `main`. Nunca há push direto na `main`.

## Antes do PR

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
uv run pre-commit run --all-files
```

## Regras de ouro

!!! warning "Privacidade"
    Nunca commite fatura real, segredo, token ou `.env`. Veja a [política de dados](../conformidade/politica-de-dados.md).

- Não invente dados de pesquisa, números ou normas. Use `TODO:`.
- Linguagem de evidência: nada de "ilegal" nem estimativa de restituição.

Veja também [convenções](convencoes.md) e [como rodar](como-rodar.md).
