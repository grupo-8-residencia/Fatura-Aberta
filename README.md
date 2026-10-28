# Fatura Aberta

Verificador **aberto e auditável** de faturas de energia elétrica residencial (grupo B1) da Neoenergia Brasília (DF). O usuário envia a fatura (PDF ou foto) e recebe um cartão de decisão que mostra, item por item, se a cobrança confere com as regras e tarifas vigentes, com a citação exata da norma (ato, artigo ou inciso, vigência).

📖 **Documentação:** <https://grupo-8-residencia.github.io/Fatura-Aberta/>

## Níveis de evidência

| Nível | O que é | Emitido |
|---|---|---|
| **A** | Checagem determinística com dados da própria fatura (leituras, somas, linhas, ICMS com a alíquota impressa, parcela até 80 kWh) | Automaticamente |
| **B** | Divergência contra a tabela oficial ANEEL versionada. Sai sempre como "diverge da tabela oficial que conseguimos obter", com fonte e data | Com fonte e data da tabela |
| **C** | Indício que não dá para confirmar; vira pedido de esclarecimento à distribuidora | Como pedido de esclarecimento |

Nenhum nível diz "ilegal" nem estima restituição. O encaminhamento é para o Procon-DF ou a Defensoria.

## Como rodar

Requisitos: [uv](https://docs.astral.sh/uv/) e, opcionalmente, Docker.

```bash
uv sync                      # instala o workspace (Python 3.12)
uv run pytest                # testes
uv run pre-commit install    # ativa os hooks (ruff, gitleaks, bloqueio de binários)
uv run mkdocs serve          # documentação em http://127.0.0.1:8000/Fatura-Aberta/
docker compose up --build    # API em http://localhost:8000/saude
```

## Estrutura

```text
packages/   contratos, rag, motor, extracao, agentes
apps/       api (FastAPI), web (Next.js, esqueleto)
avaliacao/  harness B1 a B5
dados/      sintéticos e anonimizados apenas
docs/       site MkDocs Material
infra/      Dockerfile e docker-compose
planejamento/  sprints.yaml e issues.yaml (fonte da verdade do backlog)
scripts/    automação (GitHub, geração de páginas, hooks)
```

## Privacidade

> **Fatura real nunca entra no Git.** Ela contém nome, endereço e número da instalação. No repositório só entram faturas sintéticas ou anonimizadas.

Um hook de pre-commit bloqueia PDF e imagens fora de `docs/assets/` e de `dados/benchmark/sinteticas/` (o CI repete a checagem em todo PR), e o gitleaks procura segredos em todo commit e PR. Nunca commite `.env`: use o `.env.example`.

## Contribuir

Leia o [CONTRIBUTING.md](CONTRIBUTING.md). Em resumo: branch `tipo/numero-da-issue-descricao`, Conventional Commits em português, PR pequeno que fecha a issue, revisão do par da frente.

## Licença

TODO: decisão do time (prevista no checklist final da Sprint 7).
