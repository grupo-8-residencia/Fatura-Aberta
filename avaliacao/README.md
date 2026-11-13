# Avaliação (F5)

Harness dos baselines e das métricas. O protocolo está em [`docs/avaliacao/`](../docs/avaliacao/index.md).

| Arquivo | Para quê |
|---|---|
| `rodada_s3.py` | **rodada S3 completa**: B1 (motor), B2 e B3 (LLM + RAG) em 200 faturas e 120 perguntas, e o juiz nos 40 itens; grava `resultados/s3-rodada.json` |
| `calibrar_juiz.py` | calibra o juiz contra 40 itens anotados por 2 humanos (κ ≥ 0,75); `--gerar-modelo` cria o CSV |
| `anotacoes/juiz-40.csv` | os 40 itens: saída do sistema, evidência e veredito do juiz; **as colunas humanas ficam vazias até haver anotação real** |
| `estatistica.py` | bootstrap (B = 10.000), McNemar com correção de Edwards e Kappa de Cohen, só com a biblioteca padrão |
| `rodar_b2_b3.py` | mede só a **recuperação** (sem LLM) nas 120 perguntas e grava `resultados/s3-b2-b3.json` |
| `metricas_recuperacao.py` | recall@k, precisão@5, hit rate, MRR, nDCG@5, ablação de α, abstenção por limiar, fundamentação e latência |
| `resultados/` | saídas das rodadas, versionadas para auditoria |
| `cache/` | respostas do LLM em disco (não versionado); permite retomar uma rodada longa |

## Rodar com o LLM local (ADR-002)

```bash
# Ollama rodando, com gpt-oss:20b (gerador) e qwen3:14b (juiz) instalados
FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s3.py --etapa tudo --paralelo 3
```

- `--etapa b1` roda só o motor, sem LLM. `--limite N` roda só os N primeiros itens (teste).
- Sem `FA_LLM_PROVEDOR=ollama`, usa o cliente falso (só valida a tubulação, não produz resultado).
- Uma segunda execução usa o cache e não chama o modelo de novo para prompts iguais.
- Cada JSON de rodada traz no `cabecalho`: modelo e digest, temperatura 0, semente, SHA-256 do golden
  set, commit e data.

## Calibração do juiz (precisa de gente)

`anotacoes/juiz-40.csv` tem 40 itens, cada um com dois avaliadores humanos (`anotador_1` e
`anotador_2`). Cada pessoa abre o CSV, lê `saida_do_sistema` e `evidencia` e preenche **sozinha**
`veredito_humano_1` ou `veredito_humano_2` com `suportada` ou `sem_suporte`. Depois,
`python avaliacao/calibrar_juiz.py` calcula κ (humano 1 × juiz, humano 2 × juiz e humano 1 × humano 2).
Sem as três colunas preenchidas nos 40 itens, o script não produz número nenhum.
