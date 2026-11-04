<!-- Responsável: Raissa · Par de revisão: Maria Eduarda · Issue S1-17 -->

### Requisitos Não Funcionais (Engenharia e Qualidade)

| ID | Requisito | Meta / como medir |
|---|---|---|
| **RNF-01** | Privacidade e LGPD: mascarar dados pessoais (nome, endereço, nº da instalação) antes de qualquer modelo externo; processamento local quando possível; retenção mínima. | Auditoria de dados enviados; RIPD aprovado (issue S1-03). Retenção zero: o arquivo é apagado ao fim da análise. |
| **RNF-02** | Fatura real nunca entra no Git; benchmark público só com faturas sintéticas. | Hook de pré-commit bloqueia PDF/imagem; verificação no CI (já implementado). |
| **RNF-03** | Segurança contra injeção de prompt via documento ou imagem (OWASP Top 10 para LLM). | Taxa de sucesso do ataque < 5% em 10 faturas maliciosas (hipótese H-G, S5). |
| **RNF-04** | Transparência e auditabilidade: toda saída tem nível, fonte, data/vigência e trilha (agentes, trechos usados). | 100% dos itens do cartão com nível; 100% dos achados B com fonte e data. |
| **RNF-05** | Reprodutibilidade: versões de modelo, dados e prompts fixadas; Docker Compose; CI com testes. | Execução limpa a partir do repositório; resultados do benchmark reproduzíveis com semente fixa. |
| **RNF-06** | Desempenho: tempo máximo de análise por fatura. | p95 ≤ 60 s para PDF digital e ≤ 120 s para foto; medir na S2 e revisar. |
| **RNF-07** | Disponibilidade e custo: demonstração estável, com plano offline; VLM local sem custo de API por consulta. | ≥ 95% durante demonstração e estudo com usuários; custo de API por consulta = R$ 0 (VLM local). |
| **RNF-08** | Acessibilidade e linguagem simples (persona Dona Celina). | WCAG 2.1 nível AA nas telas principais e texto em linguagem simples; teste de legibilidade com usuários na S7. |
