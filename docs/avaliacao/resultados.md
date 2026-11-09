# Resultados

!!! warning "Leia antes de citar estes números"
    A rodada da S3 mede **a recuperação** (RAG sem LLM gerador), com um embedder determinístico, sobre
    120 perguntas **ainda sem revisão humana**. O juiz LLM não foi calibrado e o B1 não foi executado.
    As perguntas foram escritas a partir do próprio texto dos dispositivos, então o recall@5 está
    provavelmente otimista. Os números abaixo são reais e reprodutíveis, mas não são o resultado final.

## S3: B1, B2 e B3

Intervalos de confiança de 95% por bootstrap (B = 10.000, semente 20261109). Fonte:
[`avaliacao/resultados/s3-b2-b3.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-b2-b3.json),
gerado por `.venv/bin/python avaliacao/rodar_b2_b3.py`.

| Baseline | O que é | Acerto por item (n = 120) | recall@5 vigente (n = 100) | Abstenção correta (n = 20) | Citações de dispositivo fora de vigência |
|---|---|---|---|---|---|
| **B1** | LLM sem RAG | TODO: exige um LLM configurado | TODO | TODO | TODO |
| **B2** | RAG sem filtro de vigência | 0,850 [0,783; 0,908] | 0,980 [0,950; 1,000] | 0,200 [0,050; 0,400] | 25 em 11 itens |
| **B3** | RAG com filtro de vigência | 0,933 [0,883; 0,975] | 0,980 [0,950; 1,000] | 0,700 [0,500; 0,900] | 0 |

**B3 − B2 no acerto por item:** +0,083 (IC 95% [0,042; 0,133]). **McNemar pareado:** 10 itens em que o
B2 erra e o B3 acerta, 0 no sentido contrário; χ² com correção de Edwards = 8,1, p = 0,0044
(p exato binomial = 0,0020). A diferença é significativa a 5%.

### O que o resultado mostra e o que não mostra

- **A vantagem do B3 vem inteira dos 12 itens de vigência** (data anterior à entrada em vigor da REN
  ANEEL 1.000/2021): o B2 se abstém corretamente em 1 deles, o B3 em 11. Nos 94 itens normativos e nos
  6 de lacuna, B2 e B3 são idênticos, porque a data de referência é atual. Essa vantagem existe **por
  construção do golden set**: ele inclui perguntas em que o filtro deveria fazer diferença.
- **Falha dos dois baselines:** nas 8 perguntas de CIP/COSIP (fora do corpus), ambos se abstêm em só 3.
  Nas outras 5 a síntese cita um dispositivo da REN ANEEL 1.000/2021 que não responde à pergunta. O
  limiar de abstenção (0,30) é grosseiro e precisa ser calibrado.
- **Item de vigência que o B3 erra (1 de 12, GS-Q119):** o filtro remove a REN, mas o CDC, art. 42,
  parágrafo único (devolução em dobro), vigorava em 2021 e é citado. A citação é defensável; o
  gabarito pediu abstenção porque a pergunta fala da resolução da ANEEL. Vale revisar esse item.
- **Dois itens normativos erram nos dois baselines** (92 de 94): o artigo canônico não ficou no top-5.

### Definição de acerto

- Pergunta com norma esperada: algum artigo canônico está no top-5 **e** estava vigente na
  `data_referencia`.
- Pergunta em que a abstenção é esperada: a síntese se abstém.

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
| recall@5 em 30 perguntas | S2 | RAG | recall@5 de 0,980 nas 100 perguntas com norma esperada do golden set (bootstrap acima). O conjunto de 30 perguntas do gate da S2 não existe separado. TODO: definir se o subconjunto de 30 é sorteado do golden set | [JSON](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s3-b2-b3.json) |
| LLM × RAG | S3 | B2, B3 | Tabela acima; B1 e juiz pendentes | acima |
| Agentes | S4 | B4, B5 | Aguardando execução da S4 | — |
| Campos-chave em 40 fotos | S5 | extração | Aguardando execução da S5 | — |
| Rodada final | S7 | B1–B5 | Aguardando execução da S7 | — |
