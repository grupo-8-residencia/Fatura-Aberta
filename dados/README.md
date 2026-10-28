# Dados

**Só entram aqui dados sintéticos ou anonimizados.** Fatura real nunca entra no Git: tem nome, endereço e número da instalação.

| Pasta | Conteúdo | Frente |
|---|---|---|
| `normas/` | Texto e inventário das normas (públicas) | F2 |
| `tarifas/` | Tabelas tarifárias da ANEEL, versionadas com fonte, data e hash | F3 |
| `benchmark/` | Benchmark público com erros injetados | F5 |
| `benchmark/sinteticas/` | Faturas sintéticas (única pasta de dados onde PDF e imagens são permitidos) | F3, F5 |
| `golden-set/` | Perguntas e faturas congeladas do experimento | F5 |

## Regras

1. Nada de fatura real, foto real, nota bruta de entrevista ou termo de consentimento.
2. Arquivos `*.pdf`, `*.jpg`, `*.jpeg`, `*.png` e `*.heic` só em `benchmark/sinteticas/` (e `docs/assets/` para a documentação). O hook de pre-commit bloqueia o resto.
3. Todo conjunto de dados traz origem, data e hash. Conjuntos do experimento são congelados antes das rodadas.
4. Dúvida se algo é pessoal? Não commite e pergunte ao Tech Lead.

Veja a [política de dados](https://grupo-8-residencia.github.io/Fatura-Aberta/conformidade/politica-de-dados/).
