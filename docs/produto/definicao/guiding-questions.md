## 9. Guiding questions

<!-- Responsável: Luiz · Par de revisão: Natalia · Issue S1-21 · Limite: de 8 a 12 perguntas -->

*Matriz de questões orientadoras e estratégias de validação técnica:*

| Tema | Pergunta | Como responder (sprint) |
|---|---|---|
| **Consumidor** | Como as pessoas conferem hoje a fatura e que decisão tomar quando estranham o valor? | Entrevistas e Lean Inception (S1) |
| **Consumidor** | Que informação e que linguagem fazem a pessoa entender o resultado e agir? | Teste com protótipo e estudo com usuários (S3, S7) |
| **Jurídico** | Onde termina a informação baseada em evidência e começa a consultoria jurídica? | Parecer de docente de Direito (S1) |
| **Jurídico** | Que frases do cartão são seguras para os níveis A, B e C? | Revisão do docente; testes de mensagem (S1–S3) |
| **Dados e normas** | Quais normas e tabelas formam o corpus, e como saber qual estava vigente na data da fatura? | Inventário do corpus e versionamento (S1–S2) |
| **Dados e normas** | Quanto uma tarifa provisória ou uma troca de layout afeta a confiabilidade do nível B? | Faturas antes e depois de maio/2026 (S2–S3) |
| **IA** | Quando recuperar a norma com RAG supera o modelo sozinho, sobretudo em normas recentes? | Experimento LLM × RAG, baselines B1–B5 (S3) |
| **IA** | Dois agentes (Analista e Auditor) reduzem afirmações sem suporte em relação a um pipeline mais simples? | Ablação B4 × B5 (S4) |
| **IA** | Em que condições a leitura de foto é confiável o bastante, e quando pedir confirmação ao usuário? | Medição por campo em 40 fotos (S5) |
| **Ética e privacidade** | Como proteger os dados pessoais da fatura e evitar que o documento manipule o sistema? | RIPD, mascaramento, teste de injeção (S1, S5) |
| **Avaliação** | Quais métricas e o tamanho da amostra bastam para sustentar as conclusões, com falsos alarmes publicados? | Protocolo de avaliação e benchmark (S1–S3) |
| **Avaliação** | O que o produto muda na decisão do usuário, em comparação com a fatura e um buscador? | Estudo com 8 a 12 usuários (S7) |
