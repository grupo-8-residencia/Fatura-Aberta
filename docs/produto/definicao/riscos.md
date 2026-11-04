## 6. Riscos

<!-- Responsável: Raissa · Par de revisão: Maria Eduarda · Issue S1-18 -->

*Matriz de riscos técnicos, regulatórios e operacionais (Probabilidade [P] / Impacto [I]: Alto [A], Médio [M], Baixo [B]):*

| Risco | Cat. | P / I | Mitigação e gatilho |
|---|---|---|---|
| **Sem diferencial observável frente aos concorrentes B2C (Conta Justa Energia, Conta de Luz Justa)** | Adoção | M / A | Benchmarking comparativo contínuo via ADR-001. Na ausência de diferencial: foco total no benchmark público. |
| **Poucas faturas reais (meta ≥ 15 com consentimento, ≥ 3 posteriores a maio/2026)** | Dados | A / A | Faturas sintéticas derivadas. Menos de 15 no dia 5 da S1 aciona o gatilho de pivot. |
| **Tarifa de referência provisória (ANEEL, 20/10/2026) gera falso alarme no nível B** | Técnico | M / A | Nível B sempre condicional, com data da tabela; tarifas versionadas por vigência. |
| **Layout da fatura mudou na migração de maio/2026; o parser quebra** | Técnico | M / M | Parser por versão de layout e VLM de reserva; testar faturas antes e depois de maio. |
| **Exercício ilegal da advocacia / linguagem juridicamente arriscada (a OAB autorizou ações contra empresas de IA em ago/2026, segundo a auditoria)** | Jurídico | M / A | Adoção restrita de linguagem de evidência; validação jurídica consultiva; eventual remoção da minuta mantendo apenas a exposição dos fatos. |
| **Vazamento de dados pessoais da fatura (LGPD)** | LGPD | B / A | Processamento local, mascaramento, retenção mínima, RIPD na S1, bloqueio de binários no Git. |
| **Falso alarme no nível A destrói a confiança** | Técnico | M / A | Gate da S2: zero falso alarme nas faturas corretas; qualquer ocorrência corrige a regra antes da S3. |
| **Injeção de prompt por documento enviado** | Segurança | M / M | Isolamento do conteúdo do documento; teste na S5; endurecer antes da S6 se ≥ 5%. |
| **Escopo excessivo e prazo (6 pessoas, cerca de 20 h/semana, estimativa de 840 h)** | Prazo | A / M | Gates Go/No-Go/Pivot semanais; água e itens extras fora do MVP; revisão em par. |
| **VLM local não roda no hardware disponível ou lê mal fotos** | Técnico | M / M | Prova de conceito no início da S2; abaixo de 90% nos campos-chave em 40 fotos, OCR + formulário de confirmação. |
