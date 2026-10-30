## Requisitos não funcionais

<!-- Responsável: Raissa · Par de revisão: Maria Eduarda · Issue S1-17 -->

As metas ainda não fixadas pelos gates são decisões pendentes, indicadas com responsável e prazo. A medição usa somente dados sintéticos ou anonimizados no repositório.

| ID | Requisito | Métrica e forma de verificação | Meta |
|---|---|---|---|
| RNF-01 | Privacidade e LGPD | Faturas reais, dados de consumidores ou entrevistados e segredos encontrados no Git, nos artefatos de CI e nos logs da aplicação; revisão por PR e varredura automatizada. | **Zero** faturas reais, dados de consumidores ou entrevistados e segredos no Git; **zero** desses dados em logs. Local de guarda e prazo de retenção das faturas reais: **TODO: F1 e F6 definem até a S2**. |
| RNF-02 | Segurança do repositório | Proporção de PRs submetidos ao bloqueio de binários, à varredura de segredos e à revisão obrigatória. | **100%** dos PRs passam por essas verificações antes do merge; `main` e `dev` protegidas por PR, aprovação de code owner e CI verde. |
| RNF-03 | Desempenho da análise | Tempo entre o envio de uma fatura sintética e a resposta da API, medido em cenários ponta a ponta. | **TODO: F6 e F5 definem o tempo máximo e o tamanho de entrada até a S2**; medir novamente antes do gate da S6. |
| RNF-04 | Disponibilidade | Proporção de verificações de saúde bem-sucedidas no ambiente publicado, em janela de observação documentada. | **TODO: F6 define percentual e janela até a S5**; aplicação acessível por URL pública no gate da S6. |
| RNF-05 | Acessibilidade | Etapas essenciais de envio, confirmação e leitura do cartão executáveis por teclado; problemas registrados em revisão manual. | **100%** das etapas essenciais executáveis por teclado. **TODO: F1 e F6 definem demais critérios e método de auditoria até a S5**. |
| RNF-06 | Transparência e auditabilidade | Proporção de itens do cartão com nível de evidência, descrição e, quando houver citação, ato, dispositivo e vigência; nível B também informa fonte e data da tabela. | **100%** dos itens com nível A, B ou C visível; **100%** das citações emitidas com vigência; nenhuma afirmação categórica de irregularidade nem estimativa de restituição. |
| RNF-07 | Reprodutibilidade | Execução do ambiente fixado por `uv.lock`, testes e build da documentação no CI; fontes e datas registradas para tabelas e corpus. | **100%** dos PRs com CI verde antes do merge; resultados de avaliação acompanhados de versão dos dados e configuração. |
| RNF-08 | Custo e execução local do modelo de visão | Memória, tempo de processamento e custo de infraestrutura por análise em equipamento definido, medidos com imagens sintéticas. | **TODO: F4 e F6 definem equipamento, limite de custo e meta de tempo até a S5**; se a extração de foto não atingir o gate de **90% de acerto em 40 fotos**, usar OCR e formulário de confirmação. |
