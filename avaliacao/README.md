# Avaliação (F5)

Harness dos baselines e das métricas. O protocolo está em [`docs/avaliacao/`](../docs/avaliacao/index.md).

| Arquivo | Para quê |
|---|---|
| `estatistica.py` | bootstrap (B = 10.000), McNemar com correção de Edwards e Kappa de Cohen, só com a biblioteca padrão |
| `rodar_b2_b3.py` | roda B2 (RAG sem filtro de vigência) e B3 (com filtro) nas 120 perguntas e grava `resultados/s3-b2-b3.json` |
| `calibrar_juiz.py` | calibra o juiz LLM contra 40 itens humanos (kappa ≥ 0,75); `--gerar-modelo` cria o CSV |
| `anotacoes/juiz-40.csv` | modelo com os 40 itens sorteados; **vazio até haver anotação humana real** |
| `resultados/` | saídas das rodadas, versionadas para auditoria |

Reproduzir: `.venv/bin/python avaliacao/rodar_b2_b3.py`. A saída é determinística (embedder por hashing,
semente fixa). TODO: B1 (LLM sem RAG) e o juiz exigem um LLM configurado.
