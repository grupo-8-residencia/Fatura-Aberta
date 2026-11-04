## 7. Premissas

<!-- Responsável: Talita · Par de revisão: Pedro · Issue S1-19 · Limite: tabela com pelo menos 8 premissas -->

*Premissas de engenharia e estratégias de contingência associadas:*

| ID | Premissa | Como validar (prazo) | Se for falsa |
|---|---|---|---|
| **P-01** | Haverá acesso a ao menos 15 faturas com consentimento válido. | Contagem formal e gestão de consentimentos LGPD. | Reduzir validação real e ampliar dados sintéticos. |
| **P-02** | A tabela ANEEL de Neoenergia Brasília B1 pode ser obtida e versionada. | Verificação de integridade, vigência, URL oficial e hashes SHA-256. | Outra fonte oficial ou suspender o nível B. |
| **P-03** | Um modelo de visão roda localmente no hardware disponível. | Prova de conceito: tempo, memória, qualidade (início da S2). | Outra extração ou menos formatos. |
| **P-04** | As normas estarão em fonte oficial com ato, dispositivo e vigência identificáveis. | Amostra de normas e verificação de versões (antes do nível C). | Restringir nível C e abster-se. |
| **P-05** | PDFs e fotos terão campos suficientes para o nível A. | Medir completude por campo (S2). | Confirmação manual e abstenção. |
| **P-06** | Os contratos de dados representam valores, unidades, datas e campos ausentes sem ambiguidade. | Revisar o schema e testar casos (início da S2). | Ajustar contratos antes de integrar o motor. |
| **P-07** | As regras do nível A passam sem falso alarme nas faturas corretas. | Testes por checagem e erros injetados no CI (gate da S2). | Ajustar regras e tolerâncias. |
| **P-08** | É possível gerar faturas sintéticas e erros rotulados de forma reproduzível. | Semente fixa, ≥ 1 erro por checagem A (S2). | Revisar o gerador; limitar alegações. |
| **P-09** | Vigência e atributos da base tarifária selecionam a referência certa por fatura. | Testar seleção por data, modalidade e componente (antes do nível B). | Não emitir B nos casos ambíguos. |
| **P-10** | O fluxo de revisão por pares fecha o pacote de definição no prazo. | PR até 29/10 12h, revisão até 17h, entrega 30/10. | Sinalizar o risco e renegociar o prazo. |
