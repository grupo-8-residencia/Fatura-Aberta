# Como contribuir

A versão completa, com exemplos, está em <https://grupo-8-residencia.github.io/Fatura-Aberta/contribuir/>. Este arquivo traz o essencial.

## Regras de ouro

1. **Fatura real, segredo, token e `.env` nunca entram no Git.** Use dados sintéticos ou anonimizados e o `.env.example`.
2. **Não invente** dados de pesquisa, números de resultado ou normas. Use `TODO:`.
3. **Linguagem de evidência:** nada de "ilegal" nem estimativa de restituição.
4. **Sem push direto na `main` nem na `dev`.** Todo trabalho entra por PR.

## Commits

Conventional Commits, em português:

```text
tipo(escopo): descrição curta no imperativo
```

Exemplos: `feat(motor): checagem do ICMS`, `fix(extracao): trata layout novo`, `docs(conformidade): preenche RIPD`.

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`.

## Fluxo de branches (gitflow)

O diagrama do fluxo está em <https://grupo-8-residencia.github.io/Fatura-Aberta/contribuir/>.

| Branch | Para quê | Sai de | Volta por PR para |
|---|---|---|---|
| `main` | Estável e publicado (o site de documentação sai daqui) | | só recebe `dev` ou `hotfix/*` |
| `dev` | Integração do trabalho da sprint. **Branch padrão do repositório** | | `main` (release) |
| `tipo/numero-da-issue-descricao` | Uma issue (ex.: `feat/12-motor-icms`) | `dev` | `dev` (squash) |
| `hotfix/numero-da-issue-descricao` | Correção urgente em algo já na `main` | `main` | `main` e depois `main` → `dev` |

- **Release:** no fim de cada sprint, depois do gate, um PR `dev` → `main` com o título `release: S2`, **merge commit** (sem squash) e, depois do merge, a tag `sprint-2`.
- **`Closes #12`** fecha a issue quando o PR entra na `dev`, porque ela é a branch padrão.
- **Nunca há push direto** em `main` nem em `dev`. O CI recusa PR para a `main` que não venha da `dev` ou de `hotfix/*`.

## Pull requests

- Pequenos, focados, e que fecham a issue: `Closes #12`.
- O **par de revisão** da frente revisa; um **code owner** precisa aprovar (ver `.github/CODEOWNERS` e a tabela em `docs/frentes/`).
- O CI precisa estar verde: lint, `mypy`, bloqueio de PDF e imagens, testes por pasta, gitleaks e, quando `docs/` muda, `mkdocs build --strict`.
- PR que altera `packages/contratos/` exige o status check `contratos-aprovacoes`, que verifica duas aprovações humanas distintas no commit `HEAD` atual.

### Mudanças em `packages/contratos/`

Os contratos são o idioma comum entre as frentes. Por isso:

- Use a label `contrato` na issue e no PR para classificação.
- **Exigem 2 aprovações humanas distintas no `HEAD` atual** (excluindo o autor do PR e contas de automação).
- Os revisores esperados são Pedro, Talita, Maria Eduarda e Luiz.

> **Como é garantido tecnicamente?** A proteção de branch do GitHub aplica 1 aprovação global de `CODEOWNERS`, e o status check independente `contratos-aprovacoes` consulta a API do GitHub a cada sincronização de PR ou evento de revisão (`pull_request_review`), garantindo que alterações em `packages/contratos/` só passem com ao menos 2 aprovações humanas distintas e vigentes no commit `HEAD` atual.

## Antes de abrir o PR

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
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
