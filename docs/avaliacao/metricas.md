# Métricas

Métricas estruturadas de avaliação científica, produto e entrega definidas na [Especificação de Produto (PRD) e Arquitetura Técnica (RFC)](../produto/pacote-de-definicao.md):

| Grupo | Métrica | Meta | Método e sprint |
|---|---|---|---|
| **Científica** | **recall@5 da norma vigente** | ≥ 0,70 | 30 perguntas com versão-gabarito; gate da S2. |
| **Científica** | **Falsos alarmes no nível A** | 0 nas faturas corretas | Benchmark com erros injetados e CI; gate da S2, relatório final. |
| **Científica** | **Afirmações sem suporte (B5 com Auditor × B4)** | Redução ≥ 30% sem perda de correção; senão B4 vira o produto | Comparação nas rodadas da S4 com anotação de falhas. |
| **Científica** | **Correção por item da fatura e diferença LLM × RAG** | Diferença significativa (McNemar, p < 0,05). Item correto = veredito (confere, diverge ou abstém) igual ao gabarito | Golden set (S3); juiz LLM calibrado contra 40 itens humanos; IC de 95% por bootstrap. |
| **Científica** | **Acerto nos campos-chave de foto** | ≥ 90% em 40 fotos; senão OCR + formulário | Exact match por campo; gate da S5. |
| **Científica** | **Sucesso de injeção de prompt** | < 5% em 10 faturas maliciosas | Teste na S5. |
| **Produto e usuário** | **Decisão correta do usuário vs. gabarito de especialista** | Maior que o grupo de controle (fatura + buscador), sem aumento do tempo de decisão (hipótese de produto do estudo) | Estudo com 8 a 12 usuários na S7. |
| **Produto e usuário** | **Conclusão de tarefa e compreensão do cartão** | ≥ 80% concluem a tarefa e entendem o cartão | Teste de usabilidade e legibilidade (S7). |
| **Entrega** | **Itens do cartão com nível e achados B com fonte e data** | 100% | Testes automatizados; critérios de aceitação do produto. |
| **Entrega** | **Gates Go/No-Go/Pivot cumpridos por sprint** | Todos registrados no site de documentação | Auditoria e acompanhamento semanal de qualidade. |
