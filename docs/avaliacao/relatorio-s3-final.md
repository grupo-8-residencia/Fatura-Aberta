# Relatório S3: LLM × RAG no Fatura Aberta

!!! warning "Entrega da S3 (decisões do time em 16/11/2026)"
    Os números abaixo vêm da rodada completa de 13/11/2026 (`avaliacao/resultados/s3-rodada.json`),
    com o corpus congelado de 28 dispositivos e o limiar de abstenção 0,30.
    **O juiz LLM foi reprovado na calibração** (κ humano × juiz ≈ 0,03, abaixo de 0,75; veja os limites).
    Por isso a métrica de "afirmações sem suporte" **não entra** neste relatório como número confiável.

## Resumo

Comparamos quatro formas de responder a perguntas regulatórias de energia elétrica e de conferir faturas:
**T1** LLM sem RAG, **T2** RAG sem LLM (resposta extrativa), **T3** LLM + RAG sem filtro de vigência e
**T4** LLM + RAG com filtro de vigência (e, nas faturas, com as saídas do motor determinístico).

- **Perguntas (120):** o **T2 (RAG sem LLM) vence**, com acerto de **83,3%** [76,7%; 90,0%], nenhuma
  resposta inválida, nenhuma citação fora de vigência e latência de milissegundos. O LLM sem RAG acerta
  só **13,3%** [7,5%; 20,0%]. O melhor dos que usam LLM é o T4, com 78,3% [70,8%; 85,8%], mas com 16 respostas
  inválidas.
- **Faturas (200):** o **motor determinístico (B1) acerta 100%**, mas isso tem uma ressalva importante
  (seção de limites). Entre os testes com LLM, o T3 acerta 79,0% e o **T4 só 53,5%**, porque o modelo se
  abstém em 93 das 200 faturas, embora detecte 99% das anomalias.
- **Escolha para o produto (provisória):** RAG com filtro de vigência e resposta extrativa para as
  perguntas, e o motor determinístico para a conferência das faturas. O LLM entra, se entrar, só como
  redator sobre essa base, e isso ainda não foi testado.

## Contexto e objetivo

O Fatura Aberta confere, item por item, faturas de energia residencial (grupo B1) da Neoenergia Brasília e
cita a norma de cada resultado, com ato, dispositivo e vigência. A pergunta desta semana: o que muda, e por
que muda, quando respondemos com e sem LLM e com e sem RAG? O critério de pronto é fazer quatro testes
diferentes e escolher o melhor para o produto.

## Metodologia

Todos os testes rodam sobre o mesmo conjunto congelado, para que as diferenças venham do método.

| Item | Valor |
|---|---|
| Golden set | 120 perguntas (103 com norma esperada e 17 de abstenção) e 200 faturas sintéticas |
| Hash do golden set (SHA-256) | `87aae5275aad9c9f3a73ea4e33abe5dbea3cd6800431cf1ca094db32bd40f453` |
| Gerador | `gpt-oss:20b` (Ollama, versão `17052f91a42e`), temperatura 0, semente 42 |
| Juiz | `qwen3:14b` (Ollama, versão `bdbd181c33f2`) |
| Recuperação | busca híbrida (vetorial + léxica), embedder determinístico, corpus de 28 dispositivos conferidos, limiar de abstenção 0,30 |
| Intervalo de confiança | 95%, bootstrap não paramétrico, B = 10.000, semente 42 |
| Comparação entre testes | McNemar pareado, α = 0,05 |
| Commit da rodada | `165b229` |
| Privacidade | só dados sintéticos; nenhuma fatura real |

**Acerto** em pergunta: a resposta cita um artigo canônico vigente na data de referência, ou se abstém
quando a abstenção é esperada. **Acerto** em fatura: o veredito do item confere com o gabarito.
Respostas inválidas (JSON fora do esquema) contam como erro, nunca como acerto nem como item ausente.

**Regra de escolha**, declarada antes de ver os números: só concorre quem tem 0 respostas inválidas e 0
violações do RF-15 (linguagem de evidência); entre os que concorrem, vence o maior acerto, com desempate
(diferença menor que 1 ponto percentual) pela menor latência.

## Os quatro testes

| Teste | Componentes | Hipótese |
|---|---|---|
| T1. LLM sem RAG | O modelo responde sozinho | Responde com fluência, mas cita normas de memória |
| T2. RAG sem LLM | Recuperação com filtro de vigência e resposta com trechos literais dos dispositivos | É o piso rastreável: nunca inventa, mas não interpreta |
| T3. LLM + RAG sem filtro (B2) | Recuperação ingênua e geração pelo LLM | Melhora a leitura, mas cita dispositivos fora de vigência |
| T4. LLM + RAG com filtro e motor (B3) | Filtro de vigência, saídas do motor no contexto e geração pelo LLM | Une rastreabilidade e boa resposta |

## Resultados

### Perguntas (n = 120)

| Teste | Acerto [IC 95%] | Inválidas | Viol. RF-15 | Cit. fora de vigência | Latência média |
|---|---|---|---|---|---|
| T1 LLM sem RAG | 13,3% [7,5%; 20,0%] | 8 | 7 | 0 | 24,3 s |
| **T2 RAG sem LLM** | **83,3% [76,7%; 90,0%]** | **0** | **0** | **0** | **0,001 s** |
| T3 LLM + RAG (B2) | 74,2% [65,8%; 81,7%] | 11 | 4 | 11 | 24,4 s |
| T4 LLM + RAG + vigência (B3) | 78,3% [70,8%; 85,8%] | 16 | 5 | 0 | 22,7 s |

Acerto por tipo de pergunta:

| Teste | Normativa | Vigência | Lacuna | Fora do corpus |
|---|---|---|---|---|
| T1 | 8,2% | 25,0% | 33,3% | 60,0% |
| T2 | 88,7% | 91,7% | 50,0% | 0,0% |
| T3 | 88,7% | 8,3% | 33,3% | 0,0% |
| T4 | 88,7% | 50,0% | 33,3% | 0,0% |

McNemar pareado (p exato):

| Comparação | Só o 2º acerta | Só o 1º acerta | p | Diferença a 5% |
|---|---|---|---|---|
| T2 × T1 | 90 | 6 | 2,5e-20 | sim |
| T3 × T1 | 80 | 7 | 8,3e-17 | sim |
| T4 × T3 | 6 | 1 | 0,125 | não |
| T4 × T2 | 11 (T4) | 17 (T2) | 0,345 | não |
| T3 × T2 | 12 (T3) | 23 (T2) | 0,090 | não |

### Faturas (n = 200; T1 em 111)

| Teste | Acerto [IC 95%] | Detecção de anomalia | Falso alarme | Abstenções | Latência média |
|---|---|---|---|---|---|
| B1 motor (sem LLM) | 100% [100%; 100%] | 100% | 0% | 0 | 0 s |
| T1 LLM sem RAG (n = 111) | 73,9% [65,8%; 82,0%] | 56,3% | 2,1% | 0 | 37,5 s |
| T3 LLM + RAG (B2) | 79,0% [73,5%; 84,5%] | 67,0% | 9,7% | 0 | 55,0 s |
| T4 LLM + RAG + motor (B3) | 53,5% [46,5%; 60,0%] | **99,0%** | 0% | **93** | 67,3 s |

T4 contra T3 (McNemar): em 85 faturas o T3 acerta e o T4 erra, e em 34 ocorre o contrário (p = 3,3e-6).
O T4 contra o B1: 93 faturas em que o B1 acerta e o T4 erra, e nenhuma ao contrário.

## O que muda e por quê

1. **O RAG é o que faz o LLM acertar.** Sem RAG, o modelo acerta 13,3% e cita o artigo errado em 80 de 120
   perguntas. Com RAG o acerto sobe 61 pontos (T3) a 65 pontos (T4); a diferença é significativa.
2. **O filtro de vigência muda a norma citada.** O T3 cita 11 dispositivos fora de vigência e acerta 8,3%
   das perguntas de vigência; o T4 cita nenhum e acerta 50,0%. A diferença T4 × T3 no total não é
   significativa (p = 0,125), porque o efeito está concentrado nas 12 perguntas de vigência.
3. **O LLM não melhora o RAG nas perguntas.** O T2 (só recuperação) acerta mais que o T3 e o T4, embora
   a diferença não seja significativa (p = 0,09 e 0,34). Pela regra, o T2 ganha porque é o único sem
   respostas inválidas: o LLM erra o formato do JSON em 11 (T3) e 16 (T4) perguntas.
4. **O LLM faz o que o RAG extrativo não faz, em um só ponto.** Nas perguntas fora do corpus, o T1 se abstém
   em 60% dos casos, e o T2, T3 e T4 em 0%: a busca sempre encontra algo parecido. O limiar de abstenção
   (0,30) ainda é grosseiro, e é o ponto de melhoria mais claro do T2.
5. **Nas faturas, o motor determinístico vence.** Ele é exato, instantâneo e explicável. O LLM com RAG e
   motor no contexto (T4) detecta quase todas as anomalias (99%) e não dá falso alarme, mas se abstém em
   46% das faturas, o que derruba o acerto.

## Escolha para o produto (decidida pelo time em 16/11/2026)

- **Perguntas regulatórias:** T2, RAG com filtro de vigência e resposta extrativa, citando ato,
  dispositivo e vigência. Satisfaz os quatro critérios (sem citação fora de vigência, rastreável, sem
  afirmar sem fonte, latência desprezível). Ressalva: o ganho sobre o T3 e o T4 não é estatisticamente
  significativo, e a escolha vem da regra (0 inválidas).
- **Faturas:** motor determinístico (nível A) como base. O LLM só entra como redator de uma explicação sobre
  o resultado do motor, e isso **não foi testado**.
- **Hipótese para a S4 (primeira tarefa prática):** T2 + abstenção calibrada + motor nas faturas, com o LLM
  atuando só como redator sobre essa base. É uma hipótese, não um resultado.

### Decisões do time

| Decisão | Resultado |
|---|---|
| Corte do T1 nas faturas | Aceito: 111 faturas, declarado. O T1 é só linha de base; T2 e B1 definem a escolha |
| Corpus | Congelado em 28 dispositivos nesta rodada. O PR #139 (39 itens) entra na abertura da S4, com nova rodada de recuperação |
| Limiar de abstenção | 0,30, exatamente o que rodou. Na S4, calibrar para os casos fora do corpus e lacuna (PR #135) |
| Escolha do produto | T2 nas perguntas e B1 nas faturas; modelo híbrido como primeira tarefa da S4 |
| Juiz | Reprovado na calibração (κ ≈ 0,03); a métrica de afirmações sem suporte não é usada. Refinar o prompt do juiz na S4 |

## Limites e riscos (leia antes de citar os números)

1. **O 100% do motor é circular.** As 200 faturas sintéticas e seus gabaritos foram geradas com o mesmo
   conhecimento do motor (gerador de erros injetados). O B1 mede se ele acerta o que foi construído para
   ele acertar, não o desempenho em faturas reais.
2. **Golden set com revisão humana incompleta.** As 120 perguntas foram escritas a partir do texto dos
   próprios dispositivos, o que tende a inflar o recall. Em 16/11, 5 das 6 pessoas tinham concluído os 30
   itens (150 anotações, 0 divergências) e a revisão das 120 perguntas estava em 76. Verificação por
   amostragem dessas anotações: o recálculo independente das 200 faturas (consumo, energia, bandeira,
   total, ICMS e item duplicado) confirma os 200 gabaritos, e todas as citações canônicas existem no corpus.
   Ressalva: 72 das 90 anotações de faturas não têm comentário, então só as 18 com conta registrada
   mostram a conferência feita; "0 divergências" não deve ser lido como prova de revisão independente.
3. **Juiz LLM reprovado na calibração.** Em 39 dos 40 itens (o GS-Q114 ficou sem veredito válido do juiz,
   que travou duas vezes), o κ entre o juiz (`qwen3:14b`) e cada avaliador humano foi **0,029** (acurácia
   56,4%, IC 95% [41,0%; 71,8%]), muito abaixo do critério de 0,75. O juiz marcou `sem_suporte` em 17
   itens, contra 4 dos humanos: ele trata como "sem lastro" frases genéricas que repetem o que a norma exige
   da fatura. Pelo protocolo, o prompt do juiz deve ser refinado, ou a avaliação final passa a ser humana.
   **Recalibração (18/11/2026, `avaliacao/recalibrar_juiz.py`, resultado em `avaliacao/resultados/s3-recalibracao-juiz.json`).**
   Dividimos os 40 itens em desenvolvimento (20, onde se olharam os erros) e retida (20, só medida) e
   escrevemos um prompt v2 (conta aritmética refeita, abstenção suportada quando a evidência não traz o dado,
   proposições só da saída). O GS-Q114 passou a contar como erro do juiz, com timeout de 2 min. Resultado:

   | Prompt | κ nos 40 | κ retida | Acurácia retida [IC 95%] | `sem_suporte` (juiz/humano) |
   |---|---|---|---|---|
   | v1 (original) | 0,022 | −0,019 | 45% [25%; 65%] | 18 / 4 |
   | v2 | 0,125 | −0,136 | 75% [55%; 90%] | 5 / 4 |

   O v2 corrigiu o excesso de "sem suporte" (acurácia de 55% para 82,5% nos 40), mas o κ na metade retida
   segue negativo e **muito abaixo de 0,75**: com apenas 4 itens `sem_suporte` nos 40 (2 na retida), o κ é
   instável e quase qualquer erro o derruba. Conclusão: o juiz `qwen3:14b` **não está calibrado**, e a
   métrica de "afirmações sem suporte" continua fora dos números confiáveis; a avaliação final dessa
   dimensão deve ser humana ou usar um juiz maior, com mais itens `sem_suporte` anotados.
   Ressalva de proveniência: as 80 decisões humanas foram consolidadas e entregues pelo Pedro, não
   exportadas individualmente pela página, e os dois avaliadores concordam em todos os itens (κ humano ×
   humano = 1,000). Esse valor não deve ser citado como concordância independente.
4. **Cobertura desigual do T1 nas faturas.** O T1 rodou em 111 das 200 faturas (as 111 primeiras por id,
   corte declarado no cabeçalho da rodada, por custo de tempo). Por isso o T1 não é pareável com os outros
   nas faturas, e o IC dele é mais largo.
5. **Respostas inválidas.** Há 8 (T1), 11 (T3) e 16 (T4) perguntas com JSON fora do esquema. Elas contam como
   erro. Parte do desempenho baixo do LLM é de formato, não de conteúdo.
6. **Abstenção.** As 5 perguntas de CIP/COSIP que a lei distrital não responde dão 0 de 5 nos testes com
   recuperação: a busca acha a própria lei, que trata do mesmo tema.
7. **Embedder sem semântica.** O embedder padrão (hashing) só captura sobreposição de palavras.
8. **Gabarito disputado.** A pergunta GS-Q119 tem gabarito discutível (o filtro remove a REN, e o CDC art.
   42 vigorava em 2021).
9. **Corpus e recuperação.** A rodada usa o corpus de 28 dispositivos e a recuperação **anterior** ao PR
   #135, que entrou na `dev` em 16/11/2026 depois da rodada. Com a recuperação do #135, o T2 (RAG extrativo)
   passa de 100 para 113 acertos em 120 (94,2%), mas esse ganho é dentro da amostra (os ajustes usaram erros
   do próprio golden set) e **não foi refeito com LLM**. A ampliação do corpus (PRODIST e REH, PR #139)
   reduz o recall@5 de 0,981 para 0,971 e também não está nestes números.
10. **Um único gerador.** Só `gpt-oss:20b` foi usado. Não há evidência de que seja o melhor modelo; a escolha
    vem da ADR-002 (local e reproduzível).

## Pendências e decisões que dependem do time

| Item | Quem | Efeito nos números |
|---|---|---|
| Juiz: prompt v2 testado em 18/11 e ainda reprovado (κ retida −0,14). Próximo passo: juiz maior ou avaliação humana, com mais itens `sem_suporte` | Pedro | habilita "afirmações sem suporte" |
| Anotação do golden set (30 itens por pessoa, 0/30 hoje) | 6 pessoas | pode mudar gabaritos e exigir recongelar o conjunto |
| Medir modelos alternativos para o produto (ADR-003), na S4 | Pedro | muda a escolha do modelo, não a do método |
| Investigar as 16 respostas inválidas do T4 | Pedro | pode elevar o T4 acima do T2 |

## Reproduzir

```bash
FA_LLM_PROVEDOR=ollama .venv/bin/python avaliacao/rodada_s3.py --etapa completa --paralelo 2 \
    --limite-faturas-llm-puro 111
.venv/bin/python avaliacao/relatorio_s3.py
.venv/bin/python avaliacao/auditar_cobertura.py
```

## Links do projeto

- [Repositório](https://github.com/grupo-8-residencia/Fatura-Aberta)
- [Site de documentação](https://grupo-8-residencia.github.io/Fatura-Aberta/)
- [Protocolo de avaliação B1 a B5](index.md) e [resultados da recuperação](resultados.md)
- Pull requests: [#87](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/87) (RAG),
  [#107](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/107) (golden set e B2 × B3),
  [#117](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/117) (LLM local),
  [#134](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/134) (semente 42 e cobertura),
  [#136](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/136) (página de anotação),
  [#138](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/138) (rodada S3)
