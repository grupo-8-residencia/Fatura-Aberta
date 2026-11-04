## 8. Métricas de sucesso

<!-- Responsável: Pedro · Par de revisão: Raissa · Issue S1-20 · Limite: tabela com pelo menos 8 métricas -->

| Grupo | Métrica e definição operacional | Meta | Método e sprint |
|---|---|---|---|
| **Científica** | **recall@5 vigente:** dispositivo em vigor na data da fatura no top-5. | ≥ 0,70 | 30 perguntas (gate S2) e 120 no golden set (S3); IC 95% bootstrap. |
| **Científica** | **Falsos alarmes nível A:** alerta determinístico em fatura correta. | 0 nas corretas | Benchmark sintético no CI; gate S2 e S7. |
| **Científica** | **Afirmações sem suporte (B5 × B4):** proposições sem lastro normativo/fatura. | Redução ≥ 30% sem perder correção | Ablação B4 × B5 com anotação e IC 95%; gate S4. |
| **Científica** | **Correção por item (LLM × RAG):** veredito igual ao gabarito. | Diferença B3 × B2 (McNemar, p < 0,05) | Golden set (S3); juiz calibrado em 40 itens ($\kappa \ge 0,75$); IC 95%. |
| **Científica** | **Campos-chave em foto:** campos obrigatórios extraídos sem erro. | ≥ 90% em 40 fotos | Exact match por campo; gate S5. |
| **Científica** | **Sucesso de prompt injection:** faturas que burlam o veredito/RF-15. | < 5% em 10 faturas | Bateria adversarial na S5. |
| **Produto e usuário** | **Decisão correta vs. especialista:** acerto na ação escolhida. | Maior que controle, sem aumentar tempo | Estudo com 8 a 12 usuários (S7). |
| **Produto e usuário** | **Conclusão e compreensão:** conclui fluxo e entende níveis A/B/C. | ≥ 80% dos usuários | Teste de usabilidade e legibilidade (S7). |
| **Entrega** | **Cobertura de nível e fonte:** nível em todo item e fonte/data no B. | 100% dos itens | Testes automatizados no CI (S2–S7). |
| **Entrega** | **Gates Go/No-Go/Pivot:** decisão registrada a cada sprint. | 100% publicados | Auditoria semanal na documentação (S1–S7). |
