## 1. Cenário escolhido

<!-- Responsável: Natalia · Par de revisão: Talita · Issue S1-12 · Limite: até 200 palavras -->

O **Fatura Aberta** é uma plataforma aberta e auditável para verificação automatizada de faturas de energia elétrica residenciais (**Grupo B1**) da **Neoenergia Brasília** no Distrito Federal. O sistema recebe PDFs nativos ou fotos de faturas impressas e gera um cartão de decisão que confronta cada item com as normas vigentes e tabelas homologadas pela ANEEL, citando ato, dispositivo e vigência em três níveis de evidência:

!!! nivel-a "Nível A (Checagem Determinística)"
    Validação matemática direta com os dados impressos na própria fatura (leituras, consumo, somatório de itens e alíquota de ICMS). Único nível emitido automaticamente pelo motor de regras.

!!! nivel-b "Nível B (Confronto Tarifário Oficial)"
    Comparação com as tabelas homologadas pela ANEEL na data do processamento, informando fonte, data e versão de referência.

!!! nivel-c "Nível C (Análise Contextual e Assistida)"
    Indícios regulatórios não confirmáveis apenas pela fatura; gera minuta neutra de pedido de esclarecimento à distribuidora e orienta busca ao Procon-DF ou à Defensoria Pública.

**Estratégia e escopo:** Sistema de apoio à decisão sob deliberação final do usuário, com código aberto, rastreabilidade normativa, ADRs, matriz de riscos e avaliação estatística. Excluem-se do escopo inicial: água/saneamento (Caesb), alta tensão (Grupo A), geração distribuída (GD) e telecomunicações.
