<!-- Responsável: Raissa · Par de revisão: Maria Eduarda · Issue S1-17 -->

### Requisitos Não Funcionais (Engenharia e Qualidade)

| ID | Requisito | Meta / como medir |
|---|---|---|
| **RNF-01** | Privacidade e LGPD: anonimizar nome, endereço, instalação e CPF antes de modelos; retenção zero. | RIPD aprovado (`S1-03`); arquivo descartado após análise. |
| **RNF-02** | Fatura real nunca entra no Git; benchmark público 100% sintético. | Pre-commit e CI bloqueiam PDFs/imagens reais. |
| **RNF-03** | Segurança contra injeção de prompt via documento/imagem (OWASP LLM). | Sucesso do ataque < 5% em 10 faturas maliciosas (S5). |
| **RNF-04** | Transparência: toda saída traz nível, fonte, vigência e trilha de agentes. | 100% dos itens com nível; 100% do nível B com fonte/data. |
| **RNF-05** | Reprodutibilidade: modelos, dados e prompts fixados; Docker e CI. | Benchmark reproduzível com semente fixa. |
| **RNF-06** | Desempenho: latência máxima de análise por fatura. | p95 ≤ 60 s (PDF) e ≤ 120 s (foto); medir na S2. |
| **RNF-07** | Disponibilidade e custo: demo estável e VLM local sem custo por consulta. | Disponibilidade ≥ 95% na demo/estudo; custo API = R$ 0. |
| **RNF-08** | Acessibilidade e linguagem simples (persona Dona Celina). | WCAG 2.1 AA nas telas principais; teste na S7. |
