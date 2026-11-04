## 1. Cenário escolhido

<!-- Responsável: Natalia · Par de revisão: Talita · Issue S1-12 · Limite: até 200 palavras -->

O **Fatura Aberta** é uma plataforma aberta, transparente e auditável desenvolvida para a verificação automatizada de faturas de energia elétrica de consumidores residenciais (**Grupo B1**) atendidos pela **Neoenergia Brasília** no Distrito Federal. O sistema processa documentos em formato digital (PDF nativo) ou capturas de imagem (fotografias de faturas impressas), gerando um painel estruturado de tomada de decisão. A ferramenta analisa a conformidade de cada item faturado em relação à regulamentação vigente e às tabelas tarifárias homologadas, acompanhada pela citação explícita do dispositivo legal, ato normativo e período de vigência aplicável. As análises são categorizadas por três níveis formais de evidência:

!!! nivel-a "Nível A (Checagem Determinística)"
    Validação matemática e lógica direta com base nos dados contidos na própria fatura (histórico de leitura, consumo medido, somatório de itens e alíquota de ICMS impressa). É o único nível emitido de forma automatizada pelo motor de regras.

!!! nivel-b "Nível B (Confronto Tarifário Oficial)"
    Identificação de divergências em relação às tabelas homologadas pela ANEEL. A resposta é contextualizada com base na base tarifária recuperada na data do processamento, indicando a fonte e a versão de referência.

!!! nivel-c "Nível C (Análise Contextual e Assistida)"
    Identificação de inconsistências regulatórias complexas não confirmadas automaticamente. Nesses casos, o sistema formula minuta padronizada para requerimento de esclarecimentos perante a distribuidora e orienta o encaminhamento aos órgãos de proteção ao consumidor (Procon-DF ou Defensoria Pública).

**Visão Arquitetural e Estratégia:** A solução atua estritamente como um sistema de apoio à decisão operacional, mantendo a deliberação final sob responsabilidade do usuário. A arquitetura cumpre integralmente as diretrizes de transparência técnica, rastreabilidade normativa, registro rigoroso de decisões de projeto via ADRs, matriz formal de riscos, avaliação estatística rigorosa e acoplamento exclusivo a fontes de dados oficiais.

**Delimitação de Escopo:** O escopo do produto é restrito ao segmento residencial Grupo B1 da Neoenergia Brasília. O diferencial técnico fundamenta-se na auditabilidade pontual (código aberto, rastreabilidade regulatória e publicação transparente de métricas de falso-positivo). Estão formalmente excluídos do escopo inicial: faturas de água e saneamento (Caesb), atendimento ao Grupo A de alta tensão, unidades com geração distribuída (GD) e serviços de telecomunicações.
