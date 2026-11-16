# ADR-002 — LLM local (Ollama) para o experimento

| | |
|---|---|
| **Status** | aceita para o experimento da S3 (decisão do Pedro em 09/11/2026; usada na rodada de 13/11/2026; a confirmação formal do time segue pendente) |
| **Data** | 2026-11-09 |
| **Decisores** | Pedro (Tech Lead, F5), com revisão da Raissa |

## Contexto

O experimento B1–B5 exige um LLM para os baselines B2 e B3, para os agentes (B4 e B5) e para o juiz.
O protocolo pede temperatura 0 e a versão do modelo gravada no cabeçalho de cada rodada
([protocolo](../../avaliacao/index.md)). Restrições: nenhuma credencial no repositório, CI sem rede e
sem chave, dados do experimento sintéticos, e a máquina de desenvolvimento é um Mac com 24 GB.

## Decisão

Usar modelos locais pelo **Ollama**, sem chave de API:

| Papel | Modelo | Por quê |
|---|---|---|
| Gerador (B2, B3, agentes) | `gpt-oss:20b` | maior modelo local disponível; aceita saída estruturada |
| Juiz | `qwen3:14b` | família diferente do gerador, para reduzir viés de autoavaliação |

A **versão** do modelo é o *digest* que o Ollama informa (12 primeiros caracteres), gravado no cabeçalho
de cada rodada junto com temperatura 0, semente 42 e o SHA-256 do golden set. O código está em
`packages/agentes/src/fa_agentes/llm.py` e usa só a biblioteca padrão.

O provedor é escolhido por variáveis de ambiente (`FA_LLM_PROVEDOR`, `FA_LLM_MODELO`,
`FA_LLM_JUIZ_MODELO`, `FA_LLM_URL`); o padrão é o **cliente falso**, determinístico, que o CI usa.

## Alternativas consideradas

- **API de um provedor remoto:** modelos mais fortes e rápidos, mas exigem chave, custo por chamada e
  envio de texto a terceiros. Fica possível pelo mesmo contrato `ClienteLLM`, sem mudar os baselines.
- **Só a infraestrutura, sem escolher modelo:** não destrava a S3.

## Consequências

- **Positivas:** sem custo, sem credencial, sem rede, reprodutível (`temperatura = 0`, semente fixa,
  digest registrado) e sem dado saindo da máquina.
- **Negativas ou riscos:**
  - Modelos locais são mais fracos e mais lentos (cerca de 12 a 15 s por chamada na M4). Em teste de
    fumaça, os dois modelos erraram uma subtração simples quando o veredito vinha antes da justificativa;
    por isso os prompts pedem a análise antes do veredito.
  - Reprodutibilidade depende de hardware e versão do Ollama; o cabeçalho registra o digest, mas não o
    hardware. Resultados com outro modelo não são comparáveis.
  - O determinismo do Ollama com `temperatura = 0` e semente fixa é bom, não garantido bit a bit.
- **O que muda no código, nos dados ou nos prazos:** `fa_agentes.llm` (cliente, cache e metadados),
  `fa_agentes.linguagem` (verificador RF-15), variáveis no `.env.example` e a rodada S3
  (`avaliacao/rodar_rodada_s3.py`). O cache de respostas fica em `avaliacao/cache/`, fora do Git.

## Evidência da S3 (13/11/2026)

- A rodada completa usou `gpt-oss:20b` (digest `17052f91a42e`) como gerador e `qwen3:14b` (digest
  `bdbd181c33f2`) como juiz, com temperatura 0 e semente 42; modelo, digest, semente e SHA-256 do golden
  set estão no `cabecalho` de `avaliacao/resultados/s3-rodada.json`.
- Comando único e reproduzível: `FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s3.py --etapa completa
  --paralelo 2 --limite-faturas-llm-puro 111`; retoma pelo cache em disco.
- O CI roda sem chave nem rede, com o cliente falso (padrão); um teste garante que o código não contém
  `API_KEY` nem `Bearer`.
- **Limite:** esta ADR não afirma que esses sejam os melhores modelos, apenas que cabem na máquina, são
  locais e reprodutíveis. A escolha do modelo do produto é da [ADR-003](adr-003-modelo-produto.md).
