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

## Lista de frases permitidas e proibidas por nível de evidência

A tabela abaixo consolida o vocabulário validado para emissão nos cartões de decisão (`Achado.descricao`) e o conjunto de expressões bloqueadas por regra determinística (`RF-15`) e pelo agente Auditor (`B5`).

| Nível | Frases permitidas (padrão de evidência) | Expressões proibidas (bloqueadas em código) |
|---|---|---|
| **A (Checagem Determinística)** | *"O produto entre consumo faturado (X kWh) e tarifa impressa (R$ Y/kWh) resulta em R$ Z, divergindo do valor cobrado na linha (R$ W)."*<br>*"A soma aritmética dos itens listados na fatura difere do total geral impresso."*<br>*"O consumo faturado não corresponde à diferença entre leitura atual e leitura anterior."* | *"Cobrança ilegal"*, *"cobrança abusiva comprovada"*, *"fraude na medição"*, *"crime contra o consumidor"*, *"direito líquido e certo à devolução em dobro"*. |
| **B (Confronto Tarifário Oficial)** | *"A tarifa unitária impressa diverge da tabela oficial da ANEEL vigente na data de referência que conseguimos obter (REH nº X, vigente de DD/MM/AAAA a DD/MM/AAAA)."*<br>*"O valor adicional de bandeira tarifária difere do patamar publicado pela ANEEL para o mês de referência."* | *"A distribuidora descumpriu ilegalmente a tarifa"*, *"você tem direito a R$ X de restituição retroativa"*, *"processar a concessionária"*. |
| **C (Análise Contextual e Assistida)** | *"Há indício que não pode ser confirmado apenas com os dados impressos na fatura; recomenda-se solicitar memória de cálculo à distribuidora."*<br>*"Não há evidência suficiente nas normas vigentes indexadas para concluir sobre este item (abstenção declarada)."* | *"Exija indenização por danos morais"*, *"petição inicial"*, *"configura ato ilícito civil"*, qualquer cálculo de repetição de indébito ou ressarcimento. |

### Regras léxicas de bloqueio (`RF-15`)

O verificador de saída rejeita qualquer resposta que contenha:

1. Qualificação jurídica conclusiva: `ilegal`, `ilegalidade`, `ilícito`, `crime`, ` criminos`, `fraude`, `roubo`, `extorsão`.
2. Promessa ou cálculo de reparação financeira: `restituição em dobro`, `repetição de indébito`, `danos morais`, `indenização de R$`, `valor a ser ressarcido`.
3. Aconselhamento processual privativo da advocacia: `ação judicial`, `juizado especial cível`, `petição inicial`, `causa ganha`.

## Registro do parecer informal sobre a fronteira jurídica (`S1-04`)

- **Responsáveis pela condução e registro:** Natália (`F1 — Domínio, Regulatório e Conformidade`) e Pedro (`F5 — Agentes, Avaliação e Ciência`).
- **Escopo da consulta:** Delimitação entre sistema informativo de transparência tarifária e atividade privativa de consultoria/assessoria jurídica (Lei nº 8.906/1994, art. 1º, II), considerando o monitoramento da OAB sobre ferramentas automatizadas de IA (ago/2026).
- **Síntese das diretrizes consolidadas no parecer:**
  1. **Natureza informacional (Níveis A e B):** A conferência aritmética dos valores impressos na fatura e a comparação objetiva com resoluções homologatórias públicas da ANEEL constituem exercício de transparência ativa e educação para o consumo, desde que acompanhadas da fonte oficial, data de vigência e linguagem estritamente descritiva.
  2. **Vedação à subsunção jurídica conclusiva:** O sistema não deve emitir juízo de ilicitude (`"cobrança ilegal"`), presumir má-fé nem quantificar valores de repetição de indébito (art. 42, parágrafo único, do CDC), pois a aferição de engano justificável e de responsabilidade civil depende de análise jurídica individualizada.
  3. **Escopo administrativo do pedido de esclarecimento (Nível C):** A minuta gerada para achados de Nível C deve restringir-se a um requerimento administrativo de esclarecimento e memória de cálculo (previsto na REN ANEEL nº 1.000/2021) destinado ao atendimento da distribuidora ou aos órgãos públicos de defesa do consumidor (Procon-DF e Defensoria Pública do DF), jamais assumindo formato de peça processual.
  4. **Aviso de transparência obrigatório:** Todas as telas de resultado e documentos exportados devem informar de forma visível que o Fatura Aberta é uma ferramenta acadêmica e informativa de apoio à leitura da conta de luz, não substituindo o atendimento da Defensoria Pública ou de profissional da advocacia.

## Contexto regulatório e mitigação de risco jurídico

- **Risco monitorado:** exercício ilegal da advocacia / linguagem juridicamente arriscada (a OAB autorizou ações contra empresas de IA em ago/2026, segundo a auditoria).
- **Mitigação:** adoção restrita de linguagem de evidência validada por testes automatizados (`RF-15`), diretrizes de fronteira jurídica consolidadas em `S1-04` (com revisão contínua até a `S3`) e eventual remoção da minuta mantendo apenas a exposição dos fatos caso necessário.
