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

## Contexto regulatório e mitigação de risco jurídico

- **Risco monitorado:** exercício ilegal da advocacia / linguagem juridicamente arriscada (a OAB autorizou ações contra empresas de IA em ago/2026, segundo a auditoria).
- **Mitigação:** adoção restrita de linguagem de evidência validada por testes automatizados (`RF-15`), validação jurídica consultiva com docente de Direito (S1–S3) e eventual remoção da minuta mantendo apenas a exposição dos fatos caso necessário.
