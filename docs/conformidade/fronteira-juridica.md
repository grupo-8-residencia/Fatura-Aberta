# Fronteira jurídica

O Fatura Aberta atua estritamente como um **sistema de apoio à decisão operacional**, mantendo a deliberação final sob responsabilidade do usuário. Apresenta **evidência técnica e regulatória**, não consultoria nem parecer jurídico.

## O que o produto faz

- Analisa a conformidade de cada item faturado em relação à regulamentação vigente e às tabelas tarifárias homologadas pela ANEEL.
- Indica o nível formal de evidência (`A`, `B` ou `C`) de cada item do cartão de decisão, acompanhado da citação explícita do dispositivo legal, ato normativo e período de vigência aplicável.
- Formula minuta padronizada e neutra para requerimento de esclarecimentos perante a distribuidora nos casos de inconsistências não confirmadas automaticamente (Nível C).
- Orienta o encaminhamento aos órgãos de proteção ao consumidor (Procon-DF ou Defensoria Pública do DF).

## Fronteiras Técnicas do Projeto (Non-Goals)

Estão expressamente fora do escopo da plataforma:

- Atestar a ilegalidade jurídica de cobranças (nunca declarar cobrança "ilegal").
- Calcular montantes financeiros de restituição ou ressarcimento.
- Oferecer pareceres advocatícios ou estratégias jurídicas.
- Peticionar automaticamente perante concessionárias ou órgãos reguladores.
- Processar faturas de unidades que não pertençam ao enquadramento residencial Grupo B1 da Neoenergia Brasília.

## Diretrizes de linguagem por nível de evidência

| Nível | Diretriz de comunicação |
|---|---|
| **A (Checagem Determinística)** | Validação matemática e lógica direta com base nos dados impressos na própria fatura. Único nível emitido de forma automatizada pelo motor de regras; testes automatizados barram expressões proibidas (`RF-15`). |
| **B (Confronto Tarifário Oficial)** | Sempre condicional à base tarifária recuperada na data do processamento ("diverge da tabela oficial que conseguimos obter"), indicando explicitamente fonte, data e versão de referência. |
| **C (Análise Contextual e Assistida)** | Exposição neutra dos fatos com citação de ato, dispositivo e vigência (ou declaração de abstenção quando insuficiente), acompanhada de minuta de pedido de esclarecimento. |

## Lista proposta de frases permitidas e proibidas por nível de evidência

A tabela abaixo consolida o vocabulário proposto internamente para emissão nos cartões de decisão (`Achado.descricao`) e o conjunto de expressões que serão bloqueadas por regra determinística (`RF-15`, prevista para S2–S3) e pelo agente Auditor (`B5`).

| Nível | Frases permitidas (padrão de evidência) | Expressões proibidas (serão bloqueadas por RF-15) |
|---|---|---|
| **A (Checagem Determinística)** | *"O produto entre consumo faturado (X kWh) e tarifa impressa (R$ Y/kWh) resulta em R$ Z, divergindo do valor cobrado na linha (R$ W)."*<br>*"A soma aritmética dos itens listados na fatura difere do total geral impresso."*<br>*"O consumo faturado não corresponde à diferença entre leitura atual e leitura anterior."* | *"Cobrança ilegal"*, *"cobrança abusiva comprovada"*, *"fraude na medição"*, *"crime contra o consumidor"*, *"direito líquido e certo à devolução em dobro"*. |
| **B (Confronto Tarifário Oficial)** | *"A tarifa unitária impressa diverge da tabela oficial da ANEEL vigente na data de referência que conseguimos obter (REH nº X, vigente de DD/MM/AAAA a DD/MM/AAAA)."*<br>*"O valor adicional de bandeira tarifária difere do patamar publicado pela ANEEL para o mês de referência."* | *"A distribuidora descumpriu ilegalmente a tarifa"*, *"você tem direito a R$ X de restituição retroativa"*, *"processar a concessionária"*. |
| **C (Análise Contextual e Assistida)** | *"Há indício que não pode ser confirmado apenas com os dados impressos na fatura; recomenda-se solicitar memória de cálculo à distribuidora."*<br>*"Não há evidência suficiente nas normas vigentes indexadas para concluir sobre este item (abstenção declarada)."* | *"Exija indenização por danos morais"*, *"petição inicial"*, *"configura ato ilícito civil"*, qualquer cálculo de repetição de indébito ou ressarcimento. |

### Regras léxicas propostas para bloqueio (`RF-15`)

O verificador de saída (`RF-15`, a ser implementado nas Sprints 2 e 3) deverá rejeitar qualquer resposta que contenha:

1. Qualificação jurídica conclusiva: `ilegal`, `ilegalidade`, `ilícito`, `crime`, `criminoso`, `criminosa`, `fraude`, `roubo`, `extorsão`.
2. Promessa ou cálculo de reparação financeira: `restituição em dobro`, `repetição de indébito`, `danos morais`, `indenização de R$`, `valor a ser ressarcido`.
3. Aconselhamento processual privativo da advocacia: `ação judicial`, `juizado especial cível`, `petição inicial`, `causa ganha`.

## Diretrizes internas propostas para validação jurídica (`S1-04`)

- **Status:** Diretrizes internas **propostas** pelas frentes `F1` e `F5`, **pendentes de validação em conversa com docente de Direito** (issue `#4` / `S1-04`).
- **Escopo da consulta a realizar:** Delimitação entre sistema informativo de transparência tarifária e atividade privativa de consultoria e assessoria jurídica (Lei nº 8.906/1994 — Estatuto da Advocacia e a OAB, art. 1º, II).
- **Pontos submetidos à validação:**
  1. **Natureza informacional (Níveis A e B):** Conferência aritmética dos valores impressos na fatura e comparação objetiva com resoluções homologatórias públicas da ANEEL, acompanhadas da fonte oficial, data de vigência e linguagem descritiva.
  2. **Vedação à subsunção jurídica conclusiva:** Proibição de emitir juízo de ilicitude (`"cobrança ilegal"`), presumir má-fé ou quantificar valores de repetição de indébito (art. 42, parágrafo único, do CDC).
  3. **Escopo administrativo do pedido de esclarecimento (Nível C):** Restrição da minuta de Nível C a requerimento administrativo de esclarecimento e memória de cálculo (REN ANEEL nº 1.000/2021) perante a distribuidora ou órgãos públicos de defesa do consumidor (Procon-DF e Defensoria Pública do DF), sem estrutura de peça judicial.
  4. **Aviso de transparência obrigatório:** Exibição visível de que o Fatura Aberta é uma ferramenta acadêmica e informativa de apoio à leitura da conta de luz, não substituindo o atendimento da Defensoria Pública ou de profissional da advocacia.

## Contexto regulatório e mitigação de risco jurídico

- **Risco monitorado:** exercício ilegal da advocacia / linguagem juridicamente arriscada (conforme mapeado na Matriz de Riscos da Seção 6 do Documento de Definição do projeto e nas diretrizes do CFOAB — Recomendação nº 001/2024 sobre uso de IA generativa e fiscalização de ferramentas automatizadas de orientação jurídica).
- **Mitigação:** adoção restrita de linguagem de evidência que será validada por testes automatizados (`RF-15`), validação jurídica consultiva pendente com docente de Direito (`S1-04`) e eventual remoção da minuta mantendo apenas a exposição dos fatos caso necessário.
