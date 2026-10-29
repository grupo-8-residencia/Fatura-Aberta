# Requisitos Funcionais — Fatura Aberta

**Sprint de documentação:** S1  
**Responsável:** Talita  
**Revisor:** Pedro  
**Status:** Proposta para revisão

## Objetivo e níveis de evidência

O Fatura Aberta apoia a análise de faturas de energia elétrica com resultados rastreáveis, sem declarar automaticamente a ilegalidade de cobranças.

- **A:** checagens determinísticas com dados da própria fatura; único nível com emissão automática de achados.
- **B:** comparação com referências oficiais versionadas; resultado condicionado à fonte e à vigência.
- **C:** análise normativa contextual, sem conclusão automática definitiva.

**MoSCoW:** M = Must have; S = Should have; C = Could have; W = Won't have nesta versão. **Sprint:** previsão sujeita à confirmação do planejamento do grupo; `A definir` indica decisão pendente.

## Tabela de requisitos

| ID | Requisito (O sistema deve...) | MoSCoW | Evidência | Sprint | Critério de aceite verificável |
|---|---|---|---|---|---|
| RF-01 | O sistema deve receber faturas em PDF. | M | Transversal | S2* | PDF válido aceito; arquivo inválido rejeitado com mensagem. |
| RF-02 | O sistema deve receber fotografias de faturas em formato de imagem suportado. | M | Transversal | S2* | Imagem válida encaminhada à extração; formato incompatível rejeitado. |
| RF-03 | O sistema deve apresentar campos extraídos para confirmação ou correção antes das checagens. | M | Transversal | S2* | Correção confirmada pelo usuário é utilizada nas checagens. |
| RF-04 | O sistema deve conferir leituras anterior e atual e o consumo registrado, quando aplicável. | M | A | S2 | Testes identificam divergência conhecida e não alertam em caso correto. |
| RF-05 | O sistema deve conferir somas e total da fatura conforme tolerância de arredondamento documentada. | M | A | S2 | Casos corretos passam; erro superior à tolerância é detectado. |
| RF-06 | O sistema deve conferir valores das linhas de cobrança com quantidades e preços unitários. | M | A | S2 | Testes com linha correta e linha adulterada passam no CI. |
| RF-07 | O sistema deve conferir ICMS com alíquota e base impressas na fatura quando suficientes. | M | A | S2 | Cálculo reproduzido em caso elegível; falta de dados causa abstenção. |
| RF-08 | O sistema deve conferir a parcela até 80 kWh quando a regra aplicável estiver definida. | M | A | S2 | Testes cobrem caso elegível, não elegível e erro injetado, sem falso alarme nos corretos. |
| RF-09 | O sistema deve comparar TUSD e TE com tabela ANEEL da distribuidora, subgrupo, modalidade e vigência pertinentes. | M | B | S3 | Comparação reproduzível e divergência acompanhada de valores e referência. |
| RF-10 | O sistema deve comparar bandeira tarifária com fonte oficial pertinente ao período de referência. | M | B | S3 | Testes distinguem bandeira compatível, divergente e ausência de referência. |
| RF-11 | O sistema deve informar fonte, data de obtenção, versão e vigência da referência tarifária em achados de nível B. | M | B | S3 | Todo achado B inclui metadados da tabela consultada. |
| RF-12 | O sistema deve citar ato normativo, dispositivo e vigência nas análises de nível C. | M | C | A definir* | Análise C exibe os três dados ou explicita referência não confirmada. |
| RF-13 | O sistema deve abster-se quando dados, fonte ou aplicabilidade da regra forem insuficientes. | M | A/B/C | S2–S3* | Casos incompletos não geram conclusão categórica e informam motivo. |
| RF-14 | O sistema deve apresentar cartão de decisão com resultado, nível de evidência, justificativa e fontes. | M | A/B/C | S3* | Cartão distingue achado, ausência de divergência e abstenção. |
| RF-15 | O sistema deve usar linguagem de evidência, sem declarar cobrança “ilegal” ou estimar restituição. | M | A/B/C | S2–S3* | Testes verificam mensagens e ausência das expressões proibidas. |

\* **Pendente de confirmação** da sprint com o planejamento do grupo; não representa compromisso já aprovado.

## Regras de comunicação e qualidade

- O nível A pode emitir automaticamente apenas achados determinísticos sustentados pelos dados.
- O nível B deve informar que o valor **“diverge da tabela oficial que conseguimos obter”**, com fonte, data e vigência, sem tratar divergência como ilegalidade.
- O nível C deve apresentar a referência normativa e as limitações da interpretação, sem conclusão automática definitiva.
- Em todos os níveis, informação insuficiente deve resultar em abstenção explicada.
- O benchmark público deve usar faturas sintéticas, sem dados pessoais ou faturas reais.
- O gate de S2 exige **zero falso alarme nas faturas corretas do conjunto de teste**; cada checagem A deve ter testes unitários no CI.

## Pendências de validação com o grupo

Confirmar as sprints dos requisitos transversais e de nível C, os contratos de dados, tolerâncias de arredondamento, condições de aplicabilidade da parcela até 80 kWh e o esquema do cartão de decisão. Este documento integra o pacote de definição em `docs/produto/pacote-de-definicao.md` após revisão.
