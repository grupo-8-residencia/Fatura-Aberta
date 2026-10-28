# Convenções

## Commits (Conventional Commits em português)

```text
tipo(escopo): descrição curta no imperativo
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`.
Escopos: `contratos`, `rag`, `motor`, `extracao`, `agentes`, `api`, `web`, `avaliacao`, `docs`, `infra`.

Exemplos:

```text
feat(motor): checagem do ICMS
fix(extracao): ignora linha em branco no layout novo
docs(conformidade): preenche RIPD
```

## Branches

`tipo/numero-da-issue-descricao`, por exemplo `feat/12-motor-icms`.

## Pull requests

- Pequenos e focados.
- Fecham a issue: `Closes #12`.
- Revisão do par da frente. Um code owner aprova.
- `packages/contratos/`: **2 aprovações**.

## Código

- Python 3.12, Pydantic v2, `ruff` (lint e formato), `mypy --strict` no repositório inteiro.
- Nomes de código podem ser em português; comentários, docs, issues e commits em português.

## Documentação

- Use os admonitions `nivel-a`, `nivel-b` e `nivel-c` ao falar de níveis de evidência:

```markdown
!!! nivel-a "Nível A"
    Texto.
```

- Onde faltar informação, escreva `TODO:` explícito.
