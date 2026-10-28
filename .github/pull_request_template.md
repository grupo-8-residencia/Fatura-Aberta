> Este PR aponta para a `dev` (gitflow). Só releases (`dev` → `main`) e hotfixes apontam para a `main`.

## O que muda

<!-- Uma ou duas frases. -->

Closes #

## Checklist

- [ ] PR pequeno e focado, branch no padrão `tipo/numero-da-issue-descricao`
- [ ] Commits em Conventional Commits, em português
- [ ] Testes novos ou atualizados; `uv run pytest` verde
- [ ] `uv run pre-commit run --all-files` verde
- [ ] Documentação atualizada (se mudou comportamento)
- [ ] **Nenhuma fatura real, segredo, token ou `.env` neste PR**
- [ ] Linguagem de evidência: nada de "ilegal" nem estimativa de restituição

### Só se mexe em `packages/contratos/`

- [ ] Issue com a label `contrato`
- [ ] **2 aprovações** (Pedro, Talita, Maria Eduarda ou Luiz)
