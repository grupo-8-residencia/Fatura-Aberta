# Critérios de aceite

Critérios de aceitação funcionais e não funcionais consolidados na [Especificação de Produto (PRD) e Arquitetura Técnica (RFC)](pacote-de-definicao.md).

## Critérios de aceitação do produto

- [ ] **Envio e validação de entrada (`RF-01/02`):** recebe fatura em PDF nativo e fotografia em formato suportado; aceita arquivos válidos e rejeita inválidos com mensagem clara.
- [ ] **Confirmação de campos (`RF-03`):** exibe os campos extraídos para confirmação ou correção antes das checagens; a correção do usuário é efetivamente utilizada nas checagens.
- [ ] **Checagens determinísticas de Nível A (`RF-04/05/06`, `RF-07`, `RF-08`):** confere leituras e consumo, somas e total, linhas (`quantidade × preço`), ICMS (com alíquota e base impressas) e parcela até 80 kWh; detecta divergência conhecida com **zero falso alarme** em faturas corretas e abstém-se na falta de dados.
- [ ] **Confronto tarifário oficial de Nível B (`RF-09/10/11`):** compara TUSD, TE e bandeira com a referência oficial vigente da ANEEL; toda divergência traz valores e metadados obrigatórios (fonte, data, versão e vigência).
- [ ] **Citação normativa de Nível C (`RF-12`):** exibe ato normativo, dispositivo e vigência, ou declara referência não confirmada.
- [ ] **Abstenção formal (`RF-13`):** abstém-se de conclusão categórica e informa o motivo quando dados, fonte ou aplicabilidade forem insuficientes.
- [ ] **Cartão de decisão (`RF-14`):** apresenta resultado, nível de evidência (`A`, `B` ou `C`), justificativa e fontes, distinguindo achado, ausência de divergência e abstenção (100% dos itens com nível).
- [ ] **Linguagem de evidência (`RF-15`):** não utiliza a expressão "ilegal" nem estima valores financeiros de restituição; testes automatizados barram expressões proibidas.

## Requisitos de engenharia e qualidade (RNFs)

| ID | Requisito | Meta e critério de verificação |
|---|---|---|
| **RNF-01** | Privacidade e LGPD | Mascarar dados pessoais (nome, endereço, nº da instalação) antes de qualquer modelo externo; processamento local quando possível; retenção zero (arquivo apagado ao fim da análise); RIPD aprovado (`S1-03`). |
| **RNF-02** | Proteção do repositório | Fatura real nunca entra no Git; benchmark público exclusivamente com faturas sintéticas; bloqueio em pre-commit e no CI. |
| **RNF-03** | Segurança contra injeção de prompt | Taxa de sucesso do ataque < 5% em 10 faturas maliciosas (OWASP Top 10 para LLM, hipótese H-G na S5). |
| **RNF-04** | Transparência e auditabilidade | 100% dos itens do cartão com nível; 100% dos achados B com fonte e data; trilha de agentes e trechos usados. |
| **RNF-05** | Reprodutibilidade | Versões de modelo, dados e prompts fixadas; Docker Compose; CI com testes; benchmark reproduzível com semente fixa. |
| **RNF-06** | Desempenho | Tempo máximo de análise por fatura: **p95 ≤ 60 s** para PDF digital e **p95 ≤ 120 s** para foto (medir na S2 e revisar). |
| **RNF-07** | Disponibilidade e custo | **≥ 95%** durante demonstração e estudo com usuários, com plano offline; custo de API por consulta = **R$ 0** (VLM local). |
| **RNF-08** | Acessibilidade e linguagem simples | Conformidade **WCAG 2.1 nível AA** nas telas principais e texto em linguagem simples (persona Dona Celina); teste de legibilidade com usuários na S7. |

## Dos gates das sprints

Veja a página de cada [sprint](../sprints/index.md) e as [métricas de sucesso](../avaliacao/metricas.md).
