# Como contribuir

A versão completa, com exemplos, está em <https://grupo-8-residencia.github.io/Fatura-Aberta/contribuir/>. Este arquivo traz o essencial.

## Regras de ouro

1. **Fatura real, segredo, token e `.env` nunca entram no Git.** Use dados sintéticos ou anonimizados e o `.env.example`.
2. **Não invente** dados de pesquisa, números de resultado ou normas. Use `TODO:`.
3. **Linguagem de evidência:** nada de "ilegal" nem estimativa de restituição.
4. **Sem push direto na `main`.** Todo trabalho entra por PR.

## Commits

Conventional Commits, em português:

```text
tipo(escopo): descrição curta no imperativo
```

Exemplos: `feat(motor): checagem do ICMS`, `fix(extracao): trata layout novo`, `docs(conformidade): preenche RIPD`.

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`.

## Branches

`tipo/numero-da-issue-descricao`, por exemplo `feat/12-motor-icms`.

## Pull requests

- Pequenos, focados, e que fecham a issue: `Closes #12`.
- O **par de revisão** da frente revisa; um **code owner** precisa aprovar (ver `.github/CODEOWNERS` e a tabela em `docs/frentes/`).
- O CI precisa estar verde: lint, testes por pasta, gitleaks e, quando `docs/` muda, `mkdocs build --strict`.

### Mudanças em `packages/contratos/`

Os contratos são o idioma comum entre as frentes. Por isso:

- Use a label `contrato` na issue e no PR.
- **Exigem 2 aprovações.**
- Os revisores esperados são Pedro, Talita, Maria Eduarda e Luiz.

> **Por que está aqui?** A proteção de branch do GitHub aplica **um único número de aprovações para o repositório inteiro** (configuramos 1 aprovação de code owner). Não existe regra de aprovações por pasta. A segunda aprovação em `packages/contratos/` é portanto uma regra **de processo**, garantida por duas coisas: o `CODEOWNERS` pede revisão desses quatro responsáveis e **quem faz o merge confere que há 2 aprovações**. O PR template tem um item para isso.

## Antes de abrir o PR

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/contratos
uv run pytest
uv run pre-commit run --all-files
uv run mkdocs build --strict   # se mexeu em docs/
```

## Documentação

- Escrita em português do Brasil.
- Use os admonitions `nivel-a`, `nivel-b` e `nivel-c` ao falar dos níveis de evidência.
- Onde faltar informação, deixe um `TODO:` explícito.

## Planejamento

O backlog vive em `planejamento/issues.yaml` e as sprints em `planejamento/sprints.yaml`. O script `scripts/github_setup.py` (dry-run por padrão) cria labels, milestones e issues sem duplicar.
