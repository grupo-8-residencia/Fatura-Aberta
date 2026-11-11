# Resultados

!!! warning "Leia antes de citar estes números"
    A rodada da S3 mede **a recuperação** (RAG sem LLM gerador), com um embedder determinístico, sobre
    120 perguntas **ainda sem revisão humana**. O juiz LLM não foi calibrado e o B1 não foi executado.
    As perguntas foram escritas a partir do próprio texto dos dispositivos, então o recall@5 está
    provavelmente otimista. Os números abaixo são reais e reprodutíveis, mas não são o resultado final.

    **Status do golden set:** os hashes foram congelados (`checksums.sha256`) antes desta rodada, mas as 120 perguntas ainda não tiveram revisão humana. A regra de `dados/README.md` (conjuntos do experimento são congelados antes das rodadas) foi cumprida quanto ao hash, não quanto à revisão. Se a revisão alterar perguntas, será preciso refazer o congelamento e a rodada. Trate os resultados como **preliminares**.

## S2: Gate de falso alarme do motor de nível A (F3)

Medição do critério "nenhum falso alarme de nível A nas faturas corretas", em dois conjuntos sintéticos, gerada por `uv run python avaliacao/medir_falso_alarme_s2.py` (resultado em
[`avaliacao/resultados/s2-falso-alarme.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s2-falso-alarme.json)).

| Conjunto | Faturas corretas | Falsos alarmes | Erros injetados detectados |
|---|---|---|---|
| Benchmark v0 (gerador da F3) | 15 | 0 | 15 de 15 |
| Golden set (200 faturas) | 103 | 0 | 97 de 97 |
| **Total** | **118** | **0** | **112 de 112** |

**Gate: aprovado.** Ressalva: os tipos de erro injetados são os que o próprio motor checa, então a detecção é alta por construção. O que o gate mede é a ausência de falso alarme, em faturas sintéticas.

## S2: Gate de Recall@5 da Norma Vigente (F2)

Medição oficial do Gate da Sprint S2 sobre 30 perguntas com versão-gabarito, **amostra estratificada por categoria** (proporcional ao tamanho de cada uma, com ao menos 1 por categoria, semente de amostragem 20261109) do golden set (`dados/golden-set/perguntas.jsonl`). Os 30 ids ficam gravados no JSON.
Intervalo de confiança de 95% por bootstrap (B = 10.000, semente 42). Fonte:
[`avaliacao/resultados/s2-recall-gate.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s2-recall-gate.json),
gerado por `uv run python avaliacao/medir_recall_s2.py`.

| Métrica de Gate | Meta da Sprint S2 | Resultado Obtido [IC 95%] | Status |
|---|---|---|---|
| **recall@5 da norma vigente (n = 30)** | ≥ 0,70 | **1,000 [1,000; 1,000]** (30 acertos em 30) | **APROVADO (GO)** |

Composição da amostra: devolução em dobro 7, tarifas B1 5, medição estimada 5, corte e notificação 5, encargos e multas 4, bandeiras 2 e CIP/COSIP 2.

!!! warning "Como ler este 100%"
    O IC de [1,000; 1,000] não significa que o RAG não erra: com 30 acertos em 30 o bootstrap não tem variação para reamostrar. As perguntas foram escritas a partir do texto dos próprios dispositivos e ainda não tiveram revisão humana, então o recall tende a ser otimista. No conjunto completo (103 perguntas com norma esperada), após os ajustes da S3, o `hit@5` é 1,000 [1,000; 1,000] e o `recall@5` é 0,995 [0,985; 1,000].

## S3: B1, B2 e B3

Intervalos de confiança de 95% por bootstrap (B = 10.000, semente 42). Fonte:
[`avaliacao/resultados/s3-b2-b3.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-b2-b3.json),
gerado por `uv run python avaliacao/rodar_b2_b3.py`.

| Baseline | O que é | Acerto por item (n = 120) | recall@5 vigente (n = 103) | Abstenção correta (n = 17) | Citações de dispositivo fora de vigência |
|---|---|---|---|---|---|
| **B1** | motor determinístico (sem LLM), só nas faturas | não se aplica às perguntas | não se aplica | não se aplica | não se aplica |
| **B2** | RAG sem filtro de vigência | 0,875 [0,817; 0,933] | 1,000 [1,000; 1,000] | 0,118 [0,000; 0,294] | 29 em 12 itens |
| **B3** | RAG com filtro de vigência | 0,958 [0,917; 0,992] | 1,000 [1,000; 1,000] | 0,706 [0,471; 0,882] | 0 |

**B3 − B2 no acerto por item:** +0,083 (IC 95% [0,042; 0,133]). **McNemar pareado:** 10 itens em que o
B2 erra e o B3 acerta, 0 no sentido contrário; χ² com correção de Edwards = 8,1, p = 0,0044
(p exato binomial = 0,0020). A diferença é significativa a 5%, **mas esse p-valor só vale para este golden set, em que a vantagem do B3 vem dos 12 itens de vigência incluídos de propósito (ver abaixo). Não deve ser citado sem essa limitação.**

### O que o resultado mostra e o que não mostra

- **A vantagem do B3 vem inteira dos 12 itens de vigência** (data anterior à entrada em vigor da REN
  ANEEL 1.000/2021): o B2 se abstém corretamente em 2 deles, o B3 em 10. Nos 97 itens normativos e nos
  6 de lacuna, B2 e B3 são idênticos, porque a data de referência é atual. Essa vantagem existe **por
  construção do golden set**: ele inclui perguntas em que o filtro deveria fazer diferença.
- **Erros remanescentes de abstenção (5 de 17 no B3 ajustado):** após a normalização léxica de termos
  leigos, a remoção da tag imprecisa `"CIP"` em `ren1000-art-343` (cujo § 2º não foi transcrito), o
  escopo negativo declarado (`nao_cobre`) em `df7888-*` e a calibração sem vazamento para o limiar
  `0,25`, o `recall@5` vigente subiu para 103 de 103 (0 falhas normativas) e as recusas falsas em
  perguntas respondíveis caíram de 9 para 0. Seguem sem abstenção 3 itens `fora_do_corpus` de CIP/COSIP
  e os 2 itens de vigência de 2021 (`GS-Q119` e `GS-Q120`), em que o CDC, art. 42, parágrafo único
  (vigente desde 1991), ultrapassa o limiar por tratar de repetição de indébito.
- **Zero itens normativos perdidos após os ajustes da S3:** as duas falhas normativas anteriores
  (`GS-Q026` e `GS-Q054`, termos leigos como "medidor lido no grupo B" e "paguei duas vezes") passaram
  a ser recuperadas no top-5 com `hit@5` = 1,000.

### Classificação dos erros da S3 e comparação com a S2 (S3-04)

| Classe de erro na linha de base (B3 S3 anterior) | Exemplos | Causa raiz | Ajuste aplicado | Situação pós-ajuste |
|---|---|---|---|---|
| **Vocabulário leigo fora do léxico jurídico** | `GS-Q026` ("medidor", "lido", "grupo B") e `GS-Q054` ("paguei duas vezes") | Prefixação `token[:5]` e stopwords não mapeavam flexões/expressões populares para `medição`, `leitura`, `duplicidade` e `grupob` | Normalização de expressões (`_FRASES`), sinônimos canônicos (`_SINONIMOS`) e limpeza de stopwords em `fa_rag.texto` | **2 → 0** (`hit@5 = 1,000`) |
| **Metadado impreciso em dispositivo** | `GS-Q072` e `GS-Q073` caindo em `ren1000-art-343` | Tag `"CIP"` presente no JSON mesmo sem o § 2º transcrito no texto | Remoção da tag `"CIP"` em `ren1000-art-343` e verificação de entidades em `IndiceHibrido.buscar` | **2 → 0** (ambas passaram a se abster) |
| **Mesmo assunto sem resposta na norma** | Perguntas de valor, alíquota e encargos da CIP batendo em `df7888-*` | Lei Distrital 7.888/2026 garante revisão e transparência, mas não fixa alíquota, valor ou multa | Campo declarativo `nao_cobre` em `df7888-*` + atenuação declarativa em `vector_store.py` | Parcial (**3** itens `fora_do_corpus` seguem sem abstenção no limiar 0,25) |
| **Intersecção temporal com CDC vigente em 2021** | `GS-Q119` e `GS-Q120` (data `2021-06-01`) | Filtro remove a REN 1.000/2021, mas `cdc-art-42-pu` vigorava em 2021 e trata de devolução em dobro | Mantido transparente sem regra ad hoc de IDs; exige refinamento do enunciado no golden set se a intenção for exclusiva da REN | **2** itens de vigência citando CDC vigente em 2021 |

Comparação consolidada da recuperação entre o gate da **Sprint S2**, a **linha de base da Sprint S3** e o **RAG ajustado da Sprint S3** (mesma semente `20261109` e mesmo conjunto congelado de 120 perguntas):

| Rodada / Etapa | Gate 30 perguntas (`s2-recall-gate.json`) | `hit@5` vigente (n = 103) | `recall@5` (n = 103) | `MRR` (n = 103) | Acerto global B3 (n = 120) | Falsas recusas (FP na abstenção) |
|---|---|---|---|---|---|---|
| **S2 (gate inicial)** | 30/30 (`1,000 [1,000; 1,000]`) | — | — | — | — | — |
| **S3 (linha de base anterior)** | 30/30 (`1,000 [1,000; 1,000]`) | 0,981 [0,951; 1,000] | 0,976 [0,942; 1,000] | 0,885 [0,836; 0,929] | 0,933 [0,883; 0,975] | 9 (limiar 0,30) |
| **S3 (após ajustes + calibração `0,25`)** | **30/30 (`1,000 [1,000; 1,000]`)** | **1,000 [1,000; 1,000]** | **0,995 [0,985; 1,000]** | **0,929 [0,892; 0,961]** | **0,958 [0,917; 0,992]** | **0 (limiar 0,25)** |

### Definição de acerto

- Pergunta com norma esperada: algum artigo canônico está no top-5 **e** estava vigente na
  `data_referencia`.
- Pergunta em que a abstenção é esperada: a síntese se abstém.

## Métricas ampliadas de recuperação e fundamentação (S3)

Mesmo golden set, B3 (com filtro de vigência), nível de artigo (um chunk por artigo). IC 95% por
bootstrap (B = 10.000). Fonte:
[`s3-metricas-recuperacao.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-metricas-recuperacao.json),
gerado por `.venv/bin/python avaliacao/metricas_recuperacao.py`.

### Ranking (103 perguntas com norma esperada)

| Métrica | Valor [IC 95%] |
|---|---|
| hit@1 | 0,864 [0,796; 0,922] |
| hit@3 | 1,000 [1,000; 1,000] |
| hit@5 | 1,000 [1,000; 1,000] |
| recall@1 | 0,835 [0,762; 0,898] |
| recall@3 | 0,985 [0,966; 1,000] |
| recall@5 | 0,995 [0,985; 1,000] |
| recall@10 | 1,000 [1,000; 1,000] |
| precisão@5 | 0,212 [0,204; 0,221] |
| MRR | 0,929 [0,892; 0,961] |
| nDCG@5 | 0,942 [0,915; 0,966] |

`hit@k` conta se algum artigo esperado aparece no top-k (é a métrica do gate, 1,000); `recall@k` é a
fração dos artigos esperados cobertos (0,995 em top-5). A precisão@5 é baixa por construção: a maioria
das perguntas tem um só artigo esperado entre 5 posições, então o teto é perto de 0,2.

### Ablação do peso α (vetorial × léxico)

| α | recall@5 | MRR |
|---|---|---|
| 0,00 (só léxico) | 0,995 | 0,874 |
| 0,25 | 1,000 | 0,917 |
| **0,50 (padrão)** | **0,995** | **0,929** |
| 0,75 | 0,995 | 0,941 |
| 1,00 (só vetorial) | 0,976 | 0,877 |

A combinação híbrida mantém o maior equilíbrio entre cobertura (`recall@5` = 0,995 em α = 0,50 e 1,000 em
α = 0,25) e ranqueamento no topo (`MRR` = 0,929–0,941 contra 0,874 no léxico puro e 0,877 no vetorial
puro). Como o embedder é lexical, o ganho de misturar vem de pesos complementares entre cobertura por
IDF e n-gramas de caracteres.

### Abstenção (120 perguntas; 17 esperam abstenção)

Positivo = abster-se.

| Limiar | Precisão | Recall | F1 |
|---|---|---|---|
| 0,20 | 1,00 | 0,71 | 0,83 |
| **0,25 (calibrado)** | **1,00** | **0,71** | **0,83** |
| 0,30 (anterior) | 0,93 | 0,76 | 0,84 |
| 0,35 | 0,65 | 0,76 | 0,70 |
| 0,40 | 0,41 | 0,82 | 0,55 |
| 0,50 | 0,29 | 1,00 | 0,45 |

### Calibração sem vazamento (split estratificado 60/60, S3-07)

Para evitar viés otimista de escolher o limiar sobre as mesmas 120 perguntas, o script
`avaliacao/calibrar_abstencao.py` divide o golden set em metades disjuntas e estratificadas por
`(tipo, categoria)` (`semente = 20261109`), seleciona o limiar **exclusivamente no split de
calibração (n = 60)** e avalia uma única vez no **split cego de teste (n = 60)**. Fonte:
[`avaliacao/resultados/s3-calibracao-abstencao.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-calibracao-abstencao.json).

| Split | Limiar | Precisão [IC 95%] | Recall [IC 95%] | F1 [IC 95%] | Acurácia [IC 95%] | Matriz (VP / FP / FN / VN) |
|---|---|---|---|---|---|---|
| **Calibração (n = 60)** | **0,25** (selecionado) | 1,000 [1,000; 1,000] | 0,875 [0,600; 1,000] | 0,933 [0,750; 1,000] | 0,983 [0,950; 1,000] | 7 / 0 / 1 / 52 |
| **Teste cego (n = 60)** | **0,25** (congelado) | **1,000 [1,000; 1,000]** | **0,556 [0,200; 0,889]** | **0,714 [0,333; 0,941]** | **0,933 [0,867; 0,983]** | **5 / 0 / 4 / 51** |
| **Teste cego (ablativo)** | 0,30 (anterior) | 1,000 | 0,667 | 0,800 | 0,950 | 6 / 0 / 3 / 51 |

No split cego de teste (`n = 60`), o limiar calibrado mantém **precisão de abstenção 1,000 (0 recusas
falsas em perguntas respondíveis)**, `recall@5` de 0,990 [0,971; 1,000] e `MRR` de 0,905 [0,843; 0,958]
nos 51 itens com norma esperada. Entre os 9 itens de abstenção do split de teste, 4 ainda não atingem o
corte (`FN = 4`, 3 `fora_do_corpus` de tema compartilhado com a lei distrital e 1 de vigência com CDC
aplicável em 2021). A diferença pareada entre `0,25` e `0,30` no split de teste não é estatisticamente
significativa (McNemar `p_exato = 1,0`).

### Fundamentação (108 respostas não abstidas)

| Métrica | Valor [IC 95%] |
|---|---|
| Citações vigentes na data da pergunta | 1,000 [1,000; 1,000] |
| Resposta cita o artigo esperado (entre as que têm norma esperada) | 0,990 [0,971; 1,000] |
| Trechos da resposta idênticos ao texto recuperado | 1,000 [1,000; 1,000] |

A síntese é extrativa, então a literalidade de 100% é garantida pelo desenho, não uma conquista. Não
medimos afirmações sem suporte de um LLM gerador (o B4 e o B5 da S4).

### Latência

Média de 0,9 ms e p95 de 0,9 ms por consulta (índice em memória, 62 chunks, CPU local). Um modelo
semântico externo mudaria esse número.

## Calibração do juiz LLM

| Item | Meta | Situação |
|---|---|---|
| Itens com anotação humana | 40 | TODO: modelo gerado em `avaliacao/anotacoes/juiz-40.csv`, sem anotações |
| Kappa de Cohen juiz × humano | ≥ 0,75 | TODO: aguarda anotação humana e rodada do juiz |
| Acurácia juiz × humano | reportar com IC 95% | TODO |

`.venv/bin/python avaliacao/calibrar_juiz.py` só calcula quando os 40 itens estiverem preenchidos e
não produz número nenhum antes disso.

## Demais rodadas

| Rodada | Sprint | Baselines | Resultado | Link |
|---|---|---|---|---|
| recall@5 em 30 perguntas | S2 | RAG | recall@5 de 1,000 [1,000; 1,000] (30 de 30) na amostra estratificada e 0,995 [0,985; 1,000] nas 103 perguntas com norma | [JSON](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s2-recall-gate.json) |
| LLM × RAG | S3 | B2, B3 | Tabela acima; B1 e juiz pendentes | acima |
| Calibração de abstenção (60/60) | S3 | B3 | Limiar `0,25` calibrado sem vazamento; F1 = 0,714 [0,333; 0,941] e precisão = 1,000 no split cego | [JSON](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-calibracao-abstencao.json) |
| Agentes | S4 | B4, B5 | Aguardando execução da S4 | — |
| Campos-chave em 40 fotos | S5 | extração | Aguardando execução da S5 | — |
| Rodada final | S7 | B1–B5 | Aguardando execução da S7 | — |
