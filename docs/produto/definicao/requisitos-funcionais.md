## 5. Requisitos funcionais e não funcionais

<!-- Responsável: Talita · Par de revisão: Pedro · Issue S1-16 · Limite: tabela com pelo menos 10 requisitos -->

### Requisitos Funcionais (Priorização MoSCoW — Must Have)

| ID | O sistema deve… | Nível | Sprint | Critério de aceite (resumo) |
|---|---|---|---|---|
| **RF-01/02** | Receber fatura em PDF e fotografia em formato suportado (M) | Transv. | S2\* | Válido aceito; inválido rejeitado com mensagem. |
| **RF-03** | Mostrar os campos extraídos para confirmação ou correção antes das checagens (M) | Transv. | S2\* | A correção do usuário é usada nas checagens. |
| **RF-04/05/06** | Conferir leituras e consumo, somas e total, e linhas (quantidade × preço) (M) | A | S2 | Detecta divergência conhecida; sem alerta em caso correto. |
| **RF-07** | Conferir ICMS com alíquota e base impressas na fatura (M) | A | S2 | Reproduz o cálculo; falta de dados gera abstenção. |
| **RF-08** | Conferir a parcela até 80 kWh quando a regra estiver definida (M) | A | S2 | Cobre elegível, não elegível e erro injetado. |
| **RF-09/10/11** | Comparar TUSD, TE e bandeira com a referência oficial vigente e informar fonte, data, versão e vigência (M) | B | S3 | Divergência traz valores e referência; todo achado B tem metadados. |
| **RF-12** | Citar ato, dispositivo e vigência nas análises de nível C (M) | C | S3\* | Exibe os três dados ou declara referência não confirmada. |
| **RF-13** | Abster-se quando dados, fonte ou aplicabilidade forem insuficientes (M) | A/B/C | S2–S3\* | Sem conclusão categórica; informa o motivo. |
| **RF-14** | Apresentar cartão de decisão com resultado, nível, justificativa e fontes (M) | A/B/C | S3\* | Distingue achado, ausência de divergência e abstenção. |
| **RF-15** | Usar linguagem de evidência, sem “ilegal” nem estimativa de restituição (M) | A/B/C | S2–S3\* | Testes automáticos barram as expressões proibidas. |

### Recortes da Versão Atual

*Nota de Escopo Funcional: Permanecem excluídos da versão atual o processamento de serviços de água/telecomunicações, alta tensão (Grupo A), geração distribuída, envio automatizado de contestações, integração via API com a distribuidora e aplicativos móveis nativos.*
