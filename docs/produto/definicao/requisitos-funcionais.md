## 5. Requisitos funcionais e não funcionais

<!-- Responsável: Talita · Par de revisão: Pedro · Issue S1-16 · Limite: tabela com pelo menos 10 requisitos -->

### Requisitos Funcionais (Priorização MoSCoW — Must Have)

| ID | O sistema deve… | Nível | Sprint | Critério de aceite (resumo) |
|---|---|---|---|---|
| **RF-01/02** | Receber fatura em PDF digital e foto em formato válido (M) | Transv. | S2\* | Válido aceito; inválido rejeitado com aviso. |
| **RF-03** | Exibir campos extraídos para confirmação/ajuste antes do cálculo (M) | Transv. | S2\* | Ajuste do usuário é aplicado nas regras. |
| **RF-04/05/06** | Conferir leituras/consumo, somas/total e linhas (qtd × tarifa) (M) | A | S2 | Detecta erro injetado; zero alerta em fatura correta. |
| **RF-07** | Conferir ICMS com alíquota e base impressas na fatura (M) | A | S2 | Reproduz cálculo; ausência gera abstenção. |
| **RF-08** | Conferir parcela até 80 kWh conforme regra aplicável (M) | A | S2 | Cobre elegível, não elegível e erro injetado. |
| **RF-09/10/11** | Comparar TUSD, TE e bandeira com tabela ANEEL vigente, citando fonte/data (M) | B | S3 | Divergência traz valores e metadados da tabela. |
| **RF-12** | Citar ato, dispositivo e vigência nas análises de nível C (M) | C | S3\* | Exibe os três dados ou declara abstenção. |
| **RF-13** | Abster-se quando dados, fonte ou aplicabilidade forem insuficientes (M) | A/B/C | S2–S3\* | Sem conclusão categórica; informa o motivo. |
| **RF-14** | Exibir cartão de decisão com resultado, nível, justificativa e fontes (M) | A/B/C | S3\* | Distingue achado, conformidade e abstenção. |
| **RF-15** | Usar linguagem de evidência, sem juízo de ilicitude nem restituição (M) | A/B/C | S2–S3\* | Testes automáticos barram termos proibidos. |

*Fora da versão atual: água/telecomunicações, Grupo A, geração distribuída, envio automático de contestações, API com distribuidora e app nativo.*
