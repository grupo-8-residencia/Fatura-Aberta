## 7. Premissas

<!-- Responsável: Talita · Par de revisão: Pedro · Issue S1-19 · Limite: tabela com pelo menos 8 premissas -->

*Premissas de engenharia e estratégias de contingência associadas:*

| ID | Premissa | Validação (prazo) | Contingência se falsa |
|---|---|---|---|
| **P-01** | Acesso a ≥ 15 faturas com consentimento LGPD. | Contagem formal (S1). | Ampliar faturas sintéticas derivadas. |
| **P-02** | Tabela ANEEL Neoenergia B1 obtida e versionada. | URL, vigência e SHA-256 (S1). | Outra fonte oficial ou suspender nível B. |
| **P-03** | Modelo de visão roda no hardware local. | PoC de tempo/memória (S2). | OCR + confirmação manual. |
| **P-04** | Normas oficiais têm ato, dispositivo e vigência. | Amostra do corpus (S1–S2). | Restringir nível C e abster-se. |
| **P-05** | PDFs e fotos trazem campos para o nível A. | Completude por campo (S2). | Confirmação do usuário e abstenção. |
| **P-06** | Contratos tipam valores, datas e opcionais sem ambiguidade. | Testes de schema (início S2). | Ajustar contratos antes do motor. |
| **P-07** | Regras do nível A têm zero falso alarme nas corretas. | Testes com erros no CI (S2). | Ajustar regras e tolerâncias. |
| **P-08** | Gerador sintético cria erros rotulados reproduzíveis. | Semente fixa, ≥ 1 erro/regra (S2). | Revisar gerador; limitar escopo. |
| **P-09** | Vigência seleciona a referência tarifária certa. | Testes por data/modalidade (S2). | Abster-se no nível B se ambíguo. |
| **P-10** | Revisão em par fecha o pacote no prazo. | PR 29/10, entrega 30/10 (S1). | Sinalizar risco e ajustar escopo. |
