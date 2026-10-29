# Premissas do Projeto — Fatura Aberta

**Sprint de documentação:** S1  
**Responsável:** Talita  
**Revisor:** Pedro  
**Status:** Hipóteses a validar; nenhuma é considerada comprovada

## Objetivo

Registrar hipóteses operacionais e técnicas que sustentam o planejamento do Fatura Aberta. Cada premissa deve ser validada antes de ser tratada como fato. Os prazos abaixo são **propostos** e dependem de confirmação com o grupo.

## Tabela de premissas

| ID | Premissa ainda não comprovada | Por que consideramos plausível | Como validar | Prazo proposto | Se for falsa, o que muda |
|---|---|---|---|---|---|
| P-01 | Será possível acessar ao menos 15 faturas com consentimento válido. | Há intenção de formar conjunto de avaliação. | Confirmar quantidade, consentimento, finalidade e condições de acesso, sem anexar faturas ao repositório. | Até o planejamento da S2 | Reduzir escopo de validação real e ampliar uso de dados sintéticos. |
| P-02 | A tabela tarifária ANEEL para Neoenergia Brasília B1 pode ser obtida e versionada. | Há portal oficial de bases tarifárias e exportação de dados. | Conferir arquivo exportado, filtros, TUSD/TE, vigência, URL, data e SHA-256; testar reprodução. | S1, antes do PR da issue #8 | Buscar outra publicação oficial ou suspender comparação B até obter referência confiável. |
| P-03 | Um modelo de visão poderá executar localmente no ambiente disponível. | Existem modelos e ferramentas locais de extração. | Rodar prova de conceito no hardware previsto, medir tempo, memória e qualidade de extração. | Início da S2 | Adotar alternativa de extração ou reduzir formatos e escopo. |
| P-04 | Normas aplicáveis estarão disponíveis em fontes oficiais com ato, dispositivo e vigência identificáveis. | Órgãos reguladores publicam atos e histórico normativo. | Montar amostra de normas, verificar acesso, versões, revogações e vigência. | Até desenho do nível C | Restringir análise C, citar lacunas e abster-se quando necessário. |
| P-05 | PDFs e fotografias conterão campos suficientes para as checagens do nível A. | Faturas normalmente exibem leituras, itens e totais. | Avaliar amostra consentida ou sintética e medir completude por campo. | S2, antes do gate A | Exigir confirmação manual e abster-se em regras com campos ausentes. |
| P-06 | Os contratos de dados permitirão representar valores, unidades, datas e campos ausentes sem ambiguidade. | Há separação prevista entre extração e motor de regras. | Revisar schema com frentes envolvidas e testar exemplos válidos, incompletos e contraditórios. | Início da S2 | Ajustar contratos antes de integrar o motor. |
| P-07 | As regras determinísticas do nível A podem ser testadas sem falsos alarmes no conjunto correto. | Operações aritméticas são verificáveis quando há dados suficientes. | Criar testes por checagem, casos corretos e erros injetados; executar CI. | Gate da S2 | Ajustar regras, tolerâncias e condições de abstenção antes da emissão automática. |
| P-08 | Será possível gerar faturas sintéticas representativas e erros rotulados de forma reproduzível. | A geração programática permite controle dos valores e da semente. | Gerar amostra com semente fixa, rotular ao menos um erro por checagem A e reproduzir saídas no CI. | S2 | Revisar gerador e limitar alegações de desempenho. |
| P-09 | A vigência e os atributos tarifários disponíveis permitirão selecionar a referência correta para cada fatura. | A base tarifária inclui dimensões como distribuidora e subgrupo. | Testar seleção por data, modalidade, classe/subclasse e componentes TUSD/TE. | Antes da implementação B na S3 | Não emitir comparação B nos casos ambíguos; aprimorar metadados. |
| P-10 | O processo de revisão por pares e integração no pacote de definição ocorrerá no prazo. | O fluxo de PR e revisão está previsto no planejamento. | Abrir PR, solicitar revisão de Pedro e verificar aprovação/merge. | PR até 29/10 12h; revisão prevista até 17h; entrega 30/10 | Sinalizar risco de prazo e negociar ajuste com responsáveis pela consolidação. |

## Política de validação

A validação deve registrar **resultado, responsável, data e evidência** (link de issue, PR, teste, relatório ou fonte oficial), sem publicar dados pessoais. Premissas não validadas permanecem como hipóteses; evidência contrária deve atualizar o plano e os requisitos relacionados.

## Relação com os requisitos

- P-01, P-05 e P-06 afetam entrada, confirmação de campos e checagens A.
- P-02 e P-09 afetam checagens B e a rastreabilidade da tabela ANEEL.
- P-04 afeta análises C e citação normativa.
- P-07 e P-08 afetam o gate e o benchmark da S2.
- P-10 afeta a consolidação do pacote de definição da S1.

**Observação:** a obtenção de um arquivo tarifário e o cálculo do hash não comprovam, por si, que todas as tarifas, modalidades e vigências necessárias estão presentes ou que o processo de download é reproduzível. Esses pontos exigem validação específica.
