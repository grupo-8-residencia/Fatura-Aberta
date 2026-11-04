## Riscos

<!-- Responsável: Raissa · Par de revisão: Maria Eduarda · Issue S1-18 -->

Probabilidade e impacto são estimativas qualitativas iniciais do time, a revisar nos gates. Um gatilho indica quando executar a mitigação, sem afirmar que o risco já ocorreu.

| Risco | Categoria | Probabilidade | Impacto | Mitigação | Dono | Gatilho |
|---|---|---|---|---|---|---|
| R-01: recuperação não encontra a norma vigente | Técnico | Média | Alto | Revisar corpus, vigência e busca; reavaliar antes de avançar. | F2 (Luiz) | `recall@5` abaixo de 0,70 nas 30 perguntas do gate da S2. |
| R-02: agentes geram afirmações sem suporte | Técnico | Média | Alto | Comparar B5 com B4 no protocolo de avaliação; se B5 não melhorar, usar B4 como produto e registrar o achado. | F5 (Pedro) | Gate da S4 não demonstra melhora de B5 sobre B4 nesse indicador. |
| R-03: extração de fotos falha nos campos-chave | Técnico | Alta | Alto | Usar OCR e formulário de confirmação antes da análise; manter o erro documentado. | F4 (Maria Eduarda) | Acerto inferior a 90% nas 40 fotos do gate da S5. |
| R-04: fatura real ou dado de consumidor vaza | Jurídico e LGPD | Média | Alto | Guardar faturas reais fora do Git, restringir acesso, bloquear binários e segredos no CI; em incidente, acionar o procedimento de resposta com F1. | F6 (Raissa) e F1 (Natalia) | Fatura real ou dado de consumidor aparece em commit, PR, log ou artefato público. |
| R-05: resultado ultrapassa a fronteira jurídica do produto | Jurídico e LGPD | Média | Alto | Revisar linguagem com F1; mostrar nível de evidência, fonte e vigência; transformar incerteza em pedido de esclarecimento. | F1 (Natalia) | Texto afirma conclusão jurídica categórica, omite suporte ou estima restituição. |
| R-06: amostra de faturas consentidas é insuficiente | Dados | Média | Alto | Priorizar coleta com termo de consentimento; usar dados sintéticos para desenvolvimento e declarar a limitação da avaliação. | F1 (Natalia) | Menos de 15 faturas reais consentidas ao final da S1. |
| R-07: norma ou tarifa usada está desatualizada | Dados | Média | Alto | Versionar fonte, data e vigência; suspender a comparação de nível B sem tabela verificável e apresentar pedido de esclarecimento quando necessário. | F2 (Luiz) e F3 (Talita) | Fonte oficial, versão ou vigência não pode ser confirmada para o período da fatura. |
| R-08: pacote de definição perde o prazo ou o limite | Prazo | Alta | Médio | Consolidar as seções por responsável, revisar pendências e submeter o gate com lacunas explícitas. | Tech Lead (Pedro) | Pacote de 3 a 5 páginas incompleto na entrega da S1. |
| R-09: pessoas não entendem o cartão de decisão | Adoção | Média | Médio | Testar linguagem e próximos passos com pessoas do público-alvo; ajustar a apresentação sem aumentar o alcance das conclusões. | F1 (Natalia) | Teste com usuários não permite identificar o nível de evidência ou o encaminhamento. **TODO: F1 define critério de usabilidade até a S5**. |
| R-10: proposta não demonstra diferencial frente a concorrentes | Adoção | Média | Alto | Aplicar o teste de cinco faturas previsto na ADR-001; se o gate de definição falhar, fazer o pivot com varredura de anterioridade. | F1 (Natalia) e Tech Lead (Pedro) | Teste de concorrentes não sustenta o recorte escolhido no gate da S1. |
