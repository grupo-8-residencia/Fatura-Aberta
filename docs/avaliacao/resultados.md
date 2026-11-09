# Resultados

!!! warning "Leia antes de citar estes números"
    A rodada da S3 mede **a recuperação** (RAG sem LLM gerador), com um embedder determinístico, sobre
    120 perguntas **ainda sem revisão humana**. O juiz LLM não foi calibrado e o B1 não foi executado.
    As perguntas foram escritas a partir do próprio texto dos dispositivos, então o recall@5 está
    provavelmente otimista. Os números abaixo são reais e reprodutíveis, mas não são o resultado final.

    **Status do golden set:** os hashes foram congelados (`checksums.sha256`) antes desta rodada, mas as 120 perguntas ainda não tiveram revisão humana. A regra de `dados/README.md` (conjuntos do experimento são congelados antes das rodadas) foi cumprida quanto ao hash, não quanto à revisão. Se a revisão alterar perguntas, será preciso refazer o congelamento e a rodada. Trate os resultados como **preliminares**.

## S2: Gate de Recall@5 da Norma Vigente (F2)

Medição oficial do Gate da Sprint S2 sobre 30 perguntas com versão-gabarito do golden set (`dados/golden-set/perguntas.jsonl`).
Intervalo de confiança de 95% por bootstrap (B = 10.000, semente 20261109). Fonte:
[`avaliacao/resultados/s2-recall-gate.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s2-recall-gate.json),
gerado por `uv run python avaliacao/medir_recall_s2.py`.

| Métrica de Gate | Meta da Sprint S2 | Resultado Obtido [IC 95%] | Status |
|---|---|---|---|
| **recall@5 da norma vigente (n = 30)** | ≥ 0,70 | **0,967 [0,900; 1,000]** (29 acertos em 30) | **APROVADO (GO)** |

## S3: B1, B2 e B3

Intervalos de confiança de 95% por bootstrap (B = 10.000, semente 20261109). Fonte:
[`avaliacao/resultados/s3-b2-b3.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-b2-b3.json),
gerado por `.venv/bin/python avaliacao/rodar_b2_b3.py`.

| Baseline | O que é | Acerto por item (n = 120) | recall@5 vigente (n = 103) | Abstenção correta (n = 17) | Citações de dispositivo fora de vigência |
|---|---|---|---|---|---|
| **B1** | LLM sem RAG | TODO: exige um LLM configurado | TODO | TODO | TODO |
| **B2** | RAG sem filtro de vigência | 0,850 [0,783; 0,908] | 0,981 [0,951; 1,000] | 0,059 [0,000; 0,176] | 25 em 11 itens |
| **B3** | RAG com filtro de vigência | 0,933 [0,883; 0,975] | 0,981 [0,951; 1,000] | 0,647 [0,412; 0,882] | 0 |

**B3 − B2 no acerto por item:** +0,083 (IC 95% [0,042; 0,133]). **McNemar pareado:** 10 itens em que o
B2 erra e o B3 acerta, 0 no sentido contrário; χ² com correção de Edwards = 8,1, p = 0,0044
(p exato binomial = 0,0020). A diferença é significativa a 5%, **mas esse p-valor só vale para este golden set, em que a vantagem do B3 vem dos 12 itens de vigência incluídos de propósito (ver abaixo). Não deve ser citado sem essa limitação.**

### O que o resultado mostra e o que não mostra

- **A vantagem do B3 vem inteira dos 12 itens de vigência** (data anterior à entrada em vigor da REN
  ANEEL 1.000/2021): o B2 se abstém corretamente em 1 deles, o B3 em 11. Nos 97 itens normativos e nos
  6 de lacuna, B2 e B3 são idênticos, porque a data de referência é atual. Essa vantagem existe **por
  construção do golden set**: ele inclui perguntas em que o filtro deveria fazer diferença.
- **Falha dos dois baselines:** nas 5 perguntas de CIP/COSIP que a Lei Distrital 7.888/2026 não
  responde (valor, alíquota, multa), ambos acertam 0 de 5. O sistema não se abstém porque encontra a
  própria lei, que trata do mesmo assunto, mas ela não traz a resposta. O limiar de abstenção (0,30)
  mede semelhança com o tema, não se o dispositivo responde à pergunta; precisa ser calibrado.
- **Item de vigência que o B3 erra (1 de 12, GS-Q119):** o filtro remove a REN, mas o CDC, art. 42,
  parágrafo único (devolução em dobro), vigorava em 2021 e é citado. A citação é defensável; o
  gabarito pediu abstenção porque a pergunta fala da resolução da ANEEL. Vale revisar esse item.
- **Dois itens normativos erram nos dois baselines** (95 de 97): o artigo canônico não ficou no top-5.

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
| hit@1 | 0,806 [0,728; 0,874] |
| hit@3 | 0,961 [0,922; 0,990] |
| hit@5 | 0,981 [0,951; 1,000] |
| recall@1 | 0,777 [0,699; 0,850] |
| recall@3 | 0,947 [0,903; 0,981] |
| recall@5 | 0,976 [0,942; 1,000] |
| recall@10 | 0,995 [0,985; 1,000] |
| precisão@5 | 0,208 [0,198; 0,219] |
| MRR | 0,885 [0,836; 0,929] |
| nDCG@5 | 0,903 [0,860; 0,940] |

`hit@k` conta se algum artigo esperado aparece no top-k (é a métrica do gate, 0,981); `recall@k` é a
fração dos artigos esperados cobertos. A precisão@5 é baixa por construção: a maioria das perguntas
tem um só artigo esperado entre 5 posições, então o teto é perto de 0,2.

### Ablação do peso α (vetorial × léxico)

| α | recall@5 | MRR |
|---|---|---|
| 0,00 (só léxico) | 0,961 | 0,836 |
| 0,25 | 0,976 | 0,876 |
| **0,50 (padrão)** | **0,976** | **0,885** |
| 0,75 | 0,966 | 0,890 |
| 1,00 (só vetorial) | 0,932 | 0,818 |

A combinação supera cada parte isolada no recall@5. O MRR é um pouco maior em α = 0,75, diferença
pequena e sem teste de significância. Como o embedder é lexical, o "vetorial" aqui não traz semântica
nova; o ganho de misturar vem de pesos diferentes sobre as mesmas palavras.

### Abstenção (120 perguntas; 17 esperam abstenção)

Positivo = abster-se.

| Limiar | Precisão | Recall | F1 |
|---|---|---|---|
| 0,20 | 0,91 | 0,59 | 0,71 |
| 0,25 | 0,69 | 0,65 | 0,67 |
| **0,30 (atual)** | **0,55** | **0,65** | **0,59** |
| 0,35 | 0,40 | 0,71 | 0,51 |
| 0,40 | 0,31 | 0,76 | 0,44 |
| 0,50 | 0,22 | 0,94 | 0,36 |

No limiar atual a síntese se abstém em 11 das 17 perguntas certas e em mais 9 que tinham resposta. Um
limiar menor (0,20) dá melhor F1 (0,71), mas **escolhido sobre estes mesmos dados**, então o número
está otimista. Para usar, é preciso calibrar num subconjunto e medir em outro. TODO.

### Fundamentação (100 respostas não abstidas)

| Métrica | Valor [IC 95%] |
|---|---|
| Citações vigentes na data da pergunta | 1,000 [1,000; 1,000] |
| Resposta cita o artigo esperado (entre as que têm norma esperada) | 0,947 [0,894; 0,989] |
| Trechos da resposta idênticos ao texto recuperado | 1,000 [1,000; 1,000] |

A síntese é extrativa, então a literalidade de 100% é garantida pelo desenho, não uma conquista. Não
medimos afirmações sem suporte de um LLM gerador (o B4 e o B5 da S4).

### Latência

Média de 0,7 ms e p95 de 0,8 ms por consulta (índice em memória, 62 chunks, CPU local). Um modelo
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
| recall@5 em 30 perguntas | S2 | RAG | recall@5 de 0,981 nas 103 perguntas com norma esperada do golden set (bootstrap acima). O conjunto de 30 perguntas do gate da S2 não existe separado. TODO: definir se o subconjunto de 30 é sorteado do golden set | [JSON](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-b2-b3.json) |
| LLM × RAG | S3 | B2, B3 | Tabela acima; B1 e juiz pendentes | acima |
| Agentes | S4 | B4, B5 | Aguardando execução da S4 | — |
| Campos-chave em 40 fotos | S5 | extração | Aguardando execução da S5 | — |
| Rodada final | S7 | B1–B5 | Aguardando execução da S7 | — |
