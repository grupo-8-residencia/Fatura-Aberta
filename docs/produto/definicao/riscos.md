## 6. Riscos

<!-- Responsável: Raissa · Par de revisão: Maria Eduarda · Issue S1-18 -->

*Matriz de riscos técnicos, regulatórios e operacionais (Probabilidade [P] / Impacto [I]: Alto [A], Médio [M], Baixo [B]):*

| Risco | Cat. | P / I | Mitigação e gatilho |
|---|---|---|---|
| **Sem diferencial frente a concorrentes B2C (Conta Justa, Conta de Luz Justa)** | Adoção | M / A | Teste em ADR-001; sem diferencial, pivot para benchmark público. |
| **Poucas faturas reais (< 15 consentidas ou < 3 pós-maio/2026)** | Dados | A / A | Faturas sintéticas derivadas; < 15 no dia 5 da S1 aciona pivot. |
| **Tarifa provisória (ANEEL, 20/10/2026) gera falso alarme no nível B** | Técnico | M / A | Nível B condicional com data e versão da tabela por vigência. |
| **Mudança de layout na migração de maio/2026 quebra o parser** | Técnico | M / M | Parser por versão de layout e VLM de reserva; testes pré/pós-maio. |
| **Ultrapassar fronteira de consultoria jurídica (monitoramento OAB ago/2026)** | Jurídico | M / A | Linguagem de evidência (`RF-15`), parecer `S1-04`, remoção de minuta se preciso. |
| **Vazamento de dados pessoais da fatura (LGPD)** | LGPD | B / A | Anonimização local, retenção zero, RIPD na S1 e bloqueio no Git. |
| **Falso alarme no nível A destrói a confiança do usuário** | Técnico | M / A | Gate S2 exige zero falso alarme nas corretas; correção imediata. |
| **Injeção de prompt via PDF ou foto enviada** | Segurança | M / M | Isolamento de entrada; bateria na S5; endurecer se ≥ 5%. |
| **Escopo excessivo para 6 pessoas (~20 h/sem, 840 h totais)** | Prazo | A / M | Gates semanais; água e extras fora do MVP; revisão em par. |
| **VLM local lento ou impreciso em fotos de faturas** | Técnico | M / M | PoC na S2; se < 90% em 40 fotos (S5), usar OCR + confirmação. |
