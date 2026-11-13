# Roteiro da conversa com o docente de Direito

Material de apoio à issue `#4` (S1-04). Serve para conduzir uma conversa **informal** com um docente
de Direito e registrar o que ele disser. Nada aqui é parecer jurídico: tudo que depende da conversa
está marcado como `TODO:` e só pode ser preenchido por quem participar dela.

## 1. Objetivo

Validar, antes do MVP, a fronteira entre **informar** (conferir números e comparar com tabelas
públicas) e **aconselhar juridicamente** (atividade privativa da advocacia). A conversa deve sair com:

- a lista de frases permitidas e proibidas, validada ou ajustada, para cada nível de evidência;
- uma opinião sobre a minuta de pedido de esclarecimento (nível C);
- o texto do aviso de transparência que o produto deve exibir.

## 2. O produto em cinco linhas (para quem não é da área)

1. O Fatura Aberta lê a fatura de energia de uma residência (grupo B1, Neoenergia Brasília, DF).
2. Ele confere as contas da própria fatura (nível A) e compara tarifas com a tabela oficial da ANEEL
   que conseguimos obter (nível B).
3. Quando algo parece estranho e não dá para confirmar, ele diz isso e sugere pedir esclarecimento à
   distribuidora (nível C).
4. Toda conclusão traz a fonte, o dispositivo e a vigência da norma.
5. O produto **nunca** diz que uma cobrança é "ilegal", **nunca** calcula valor de restituição e
   **nunca** orienta ação judicial.

## 3. Pontos a validar

Os mesmos de [fronteira jurídica](fronteira-juridica.md):

1. **Natureza informacional (níveis A e B):** a conferência aritmética e a comparação com resoluções
   públicas da ANEEL, com fonte e data, são atividade informativa?
2. **Vedação à conclusão jurídica:** a proibição de "cobrança ilegal", de presumir má-fé e de
   quantificar repetição de indébito (CDC, art. 42, parágrafo único) é suficiente?
3. **Escopo do pedido de esclarecimento (nível C):** restringir a minuta a requerimento administrativo
   de esclarecimento e memória de cálculo, sem estrutura de peça judicial, afasta o risco de exercício
   ilegal da advocacia (Lei nº 8.906/1994, art. 1º, II)?
4. **Aviso de transparência:** basta informar que é uma ferramenta acadêmica e informativa e que não
   substitui a Defensoria Pública nem a advocacia?

## 4. Perguntas abertas para o docente

- A minuta de nível C pode ser considerada atividade privativa da advocacia? Em que ponto ela deixaria
  de ser um simples pedido de informação?
- O que muda se o usuário **editar** a minuta antes de enviá-la?
- Citar o artigo e a vigência de uma norma ao lado de um achado equivale a uma opinião jurídica?
- A frase "diverge da tabela oficial que conseguimos obter" é neutra o bastante?
- Há risco em encaminhar o usuário ao Procon-DF ou à Defensoria Pública?
- Quais cuidados adicionais com o uso de IA generativa (Recomendação nº 001/2024 do CFOAB) o produto
  deve ter?

## 5. Frases por nível de evidência

Preencher a última coluna **durante ou depois** da conversa, com `validada`, `ajustar` ou `remover`.

| Nível | Frase permitida proposta | Decisão do docente |
|---|---|---|
| A | "O produto entre consumo faturado (X kWh) e tarifa impressa (R$ Y/kWh) resulta em R$ Z, divergindo do valor cobrado na linha (R$ W)." | TODO: validada / ajustar / remover |
| A | "A soma aritmética dos itens listados na fatura difere do total geral impresso." | TODO: validada / ajustar / remover |
| A | "O consumo faturado não corresponde à diferença entre leitura atual e leitura anterior." | TODO: validada / ajustar / remover |
| B | "A tarifa unitária impressa diverge da tabela oficial da ANEEL vigente na data de referência que conseguimos obter (REH nº X, vigente de DD/MM/AAAA a DD/MM/AAAA)." | TODO: validada / ajustar / remover |
| B | "O valor adicional de bandeira tarifária difere do patamar publicado pela ANEEL para o mês de referência." | TODO: validada / ajustar / remover |
| C | "Há indício que não pode ser confirmado apenas com os dados impressos na fatura; recomenda-se solicitar memória de cálculo à distribuidora." | TODO: validada / ajustar / remover |
| C | "Não há evidência suficiente nas normas vigentes indexadas para concluir sobre este item (abstenção declarada)." | TODO: validada / ajustar / remover |

## 6. Expressões bloqueadas (RF-15)

O verificador de linguagem (`fa_agentes.linguagem`) rejeita as expressões abaixo. Perguntar ao docente
se a lista está completa ou se há termos a acrescentar ou retirar.

| Regra | Termos | Decisão do docente |
|---|---|---|
| Qualificação jurídica conclusiva | ilegal, ilegalidade, ilícito, crime, criminoso, fraude, roubo, extorsão | TODO |
| Reparação financeira | restituição, ressarcimento, repetição de indébito, danos morais, indenização, devolução em dobro | TODO |
| Aconselhamento processual | ação judicial, juizado especial, petição inicial, causa ganha, processar | TODO |

## 7. Ficha de registro (preencher depois da conversa, sem dados pessoais)

| Campo | Valor |
|---|---|
| Data da conversa | TODO |
| Quem do time participou | TODO |
| Docente informou que a conversa pode ser registrada | TODO: sim / não |
| Instituição e área do docente | TODO |
| Conclusões sobre os 4 pontos | TODO |
| Ajustes pedidos à lista de frases | TODO |
| Ajustes pedidos à lista de termos bloqueados | TODO |
| Texto aprovado do aviso de transparência | TODO |
| Próximos passos | TODO |

## 8. Perguntas complementares para revisão da equipe

- Se a ferramenta apresentar uma divergência incorreta, quais responsabilidades e medidas preventivas devemos considerar?
- Quais cuidados são necessários para proteger os dados pessoais presentes nas faturas, conforme a LGPD?
- Como devemos informar ao consumidor que uma norma ou tabela tarifária pode estar desatualizada?
- Como comunicar resultados inconclusivos sem transmitir a impressão de que a cobrança foi considerada correta?
- Termos como "cobrança indevida", "irregularidade" e "inconsistência" apresentam riscos jurídicos diferentes?

> Perguntas propostas pela F1, pendentes de revisão da equipe e avaliação dos profissionais de Direito.
Depois de preencher, atualize a seção "Diretrizes internas propostas para validação jurídica" de
[fronteira jurídica](fronteira-juridica.md) e feche a issue `#4` por PR com `Closes #4`.
