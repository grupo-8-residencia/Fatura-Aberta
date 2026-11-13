# RIPD simplificado

**Projeto:** Fatura Aberta  
**Responsável:** F1 — Produto, Pesquisa e Conformidade (Sprint 1)  
**Par de revisão:** Talita  
**Situação:** Revisado pelo par de revisão da F1 (pendências técnicas e jurídicas em acompanhamento)

> Este relatório apresenta os riscos relacionados ao tratamento de dados pessoais no Fatura Aberta e as medidas previstas para reduzi-los. As informações técnicas foram elaboradas com base na arquitetura e na documentação do projeto. As questões que dependem de definição jurídica ou de confirmação da implementação permanecem identificadas como pendências. Este documento não substitui uma avaliação jurídica.

## 1. Descrição do tratamento

O Fatura Aberta é uma ferramenta desenvolvida para auxiliar consumidores residenciais na compreensão e conferência de suas contas de energia elétrica. O projeto trabalha inicialmente com faturas do grupo B1 da Neoenergia Brasília e busca identificar possíveis divergências nos valores cobrados, apresentar explicações acessíveis e orientar o consumidor sobre como solicitar esclarecimentos à distribuidora.

As faturas podem conter dados pessoais, como nome do titular, endereço, número da instalação e, eventualmente, CPF, além de informações sobre leituras, consumo em kWh, bandeiras tarifárias, impostos, itens de cobrança e valor total.

O contrato estruturado `Fatura` não possui campos destinados à identificação pessoal do consumidor. A proposta é que apenas as informações necessárias à análise sejam encaminhadas aos componentes responsáveis pela conferência dos valores.

Os titulares envolvidos no tratamento são os consumidores que utilizam a ferramenta e os voluntários que disponibilizaram faturas reais para os testes.

A análise está organizada em três níveis:

- **Nível A:** verificar a coerência dos cálculos apresentados na fatura.
- **Nível B:** comparar as informações de cobrança com tarifas e referências oficiais da ANEEL.
- **Nível C:** quando não for possível confirmar uma cobrança, orientar o consumidor sobre como solicitar esclarecimentos à distribuidora, utilizando linguagem baseada em evidências.

Durante a preparação dos testes, a frente F1 realizou a coleta de 15 faturas reais, identificadas pelos códigos F001 a F015. Os documentos foram disponibilizados voluntariamente e seus respectivos termos de consentimento foram conferidos e vinculados individualmente, conforme a informação atualizada pela F1.

O formulário de consentimento recebeu 22 respostas, enquanto a pesquisa com consumidores contabilizou 21 participantes. A pesquisa foi utilizada para compreender dificuldades relacionadas à leitura das contas, à identificação de cobranças e à conferência de possíveis divergências. Essas respostas não substituem a autorização individual necessária para utilização das faturas reais.

**Base legal — TODO (F1):** confirmar com a Talita e, se possível, com o docente de Direito vinculado à atividade #4, quais hipóteses legais se aplicam ao funcionamento do produto e à utilização das faturas cedidas para testes. O consentimento, previsto no art. 7º, I, da Lei nº 13.709/2018, é uma hipótese a ser avaliada para os documentos disponibilizados voluntariamente.

**Controlador e operadores — TODO (F1):** definir formalmente quem exerce a função de controlador no contexto do projeto acadêmico e identificar eventuais operadores envolvidos no tratamento, considerando também os serviços utilizados na infraestrutura.

## 2. Fluxo dos dados

O fluxo de tratamento previsto na arquitetura do Fatura Aberta compreende as seguintes etapas:

1. **Entrada:** o consumidor envia uma fatura em PDF ou imagem por meio da interface web, que encaminha a solicitação ao endpoint `POST /analisar`.

2. **Extração:** o componente `fa_extracao` identifica os campos necessários à análise. A função `anonimizar()` é destinada à remoção ou ao mascaramento de identificadores pessoais, como nome, endereço, número da instalação, CPF, CNPJ e e-mail, em textos que precisem ser registrados. Para imagens, a arquitetura prevê um modelo de visão executado localmente, com higienização de instruções incorporadas ao documento. A conversão do resultado para o contrato `Fatura` ocorre após a confirmação do usuário, por meio de `confirmar()`.

3. **Análise:** os componentes `fa_motor` e `fa_rag` trabalham com as informações estruturadas no contrato `Fatura`. O motor realiza as verificações de cálculo e a busca normativa consulta as referências necessárias. Quando utilizado, o modelo de linguagem recebe os dados estruturados, conforme a decisão arquitetural ADR-002, que prevê execução local com Ollama.

4. **Saída:** o sistema apresenta um cartão de decisão com o nível da análise, a descrição do resultado e as referências utilizadas, incluindo informações sobre sua vigência quando aplicável.

5. **Armazenamento:** a arquitetura documentada prevê que a API não persista o arquivo original da fatura e que o resultado permaneça na sessão do usuário. Os registros de erro devem conter apenas informações necessárias ao diagnóstico, sem reproduzir o conteúdo do documento. Essas condições precisam ser confirmadas por meio de testes e revisão da implementação.

6. **Faturas reais utilizadas nos testes:** as 15 faturas recebidas pela F1 estão organizadas em uma pasta privada no Google Drive, fora do repositório GitHub. O controle da coleta registra os documentos recebidos, a conferência dos termos de consentimento e a vinculação individual das autorizações. O acesso à pasta está registrado como restrito, permanecendo necessária a confirmação das permissões e dos responsáveis autorizados.

Os arquivos reais são destinados exclusivamente aos testes abrangidos pelas autorizações concedidas. No repositório público, a política de dados permite apenas documentos sintéticos ou efetivamente anonimizados.

Ao término do Challenge, as faturas reais deverão ser excluídas conforme o procedimento definido pela equipe. A exclusão também deverá abranger as cópias locais realizadas pelos integrantes durante os testes, com registro da execução.

**TODO (F1):** definir a data limite de exclusão, confirmar a relação de pessoas com acesso à pasta privada e estabelecer como será comprovada a exclusão dos documentos e das cópias locais.

## 3. Riscos e medidas

O tratamento de faturas reais exige cuidados porque os documentos podem conter informações que identificam diretamente os consumidores. Os riscos identificados e as medidas previstas pelo projeto são apresentados a seguir.

| Risco identificado | Medida de proteção |
|---|---|
| Publicação de faturas reais no GitHub | A política de dados proíbe documentos reais no repositório. O projeto prevê bloqueios de PDF e imagens por hooks de pre-commit e verificações no CI, além de análise de segredos com Gitleaks e revisão por pares. |
| Exposição de dados pessoais em logs | A arquitetura prevê registro limitado ao tipo de erro e utilização de `anonimizar()` para remover ou mascarar identificadores antes de qualquer registro necessário. |
| Envio de dados pessoais a serviços externos | A arquitetura prevê processamento local de imagens e execução local do modelo de linguagem com Ollama, conforme ADR-002. Os documentos públicos de benchmark devem utilizar dados sintéticos. |
| Dados pessoais encaminhados pelo analisador | O contrato `Fatura` não possui campos destinados à identificação pessoal e o componente de extração utiliza uma lista definida de informações necessárias à análise. |
| Instruções maliciosas inseridas em imagens | Estão previstas a higienização do texto extraído e verificações específicas de injeção de prompt, conforme `docs/seguranca/injecao-por-imagem.md`. |
| Acesso indevido às faturas reais | Os documentos foram organizados em pasta privada no Google Drive, com acesso registrado como restrito. A relação de pessoas autorizadas e as permissões precisam ser confirmadas. |
| Utilização de fatura sem autorização correspondente | A F1 informou a conclusão da conferência e da vinculação individual dos termos às 15 faturas. Essa situação deverá permanecer documentada no controle da coleta. |
| Permanência de cópias locais após os testes | Está prevista a exclusão dos arquivos ao término do Challenge, incluindo cópias locais. Ainda é necessário definir prazo, responsáveis e registro da exclusão. |
| Orientação incorreta sobre cobranças ou direitos do consumidor | O produto utiliza níveis de análise A, B e C, referências oficiais e linguagem baseada em evidências, respeitando os limites definidos em `docs/conformidade/fronteira-juridica.md` e os requisitos relacionados à comunicação dos resultados, incluindo RF-15. |

As medidas técnicas descritas representam os controles documentados para o projeto. Sua implementação e eficácia deverão ser verificadas pela equipe responsável, especialmente quanto ao tratamento de arquivos temporários, aos registros de execução e à comunicação com serviços externos.

## 4. Direitos dos titulares

Os consumidores que utilizarem o Fatura Aberta deverão receber informações claras sobre a finalidade do tratamento e sobre as condições de utilização de suas faturas.

A arquitetura prevê que o documento original não seja armazenado permanentemente pela API após o processamento. Entretanto, essa condição ainda precisa ser confirmada tecnicamente antes de ser apresentada como garantia ao usuário, considerando também possíveis arquivos temporários e registros auxiliares.

Os voluntários que disponibilizaram faturas para testes poderão exercer os direitos previstos na Lei Geral de Proteção de Dados Pessoais, observadas as condições aplicáveis a cada solicitação.

Esses direitos incluem obter informações sobre o tratamento, solicitar acesso ou correção de dados, requerer eliminação nas hipóteses previstas em lei e revogar o consentimento quando essa for a base legal utilizada.

A F1 realizou a conferência e a vinculação dos termos às 15 faturas recebidas, o que permite identificar, no controle privado, qual autorização corresponde a cada documento sem divulgar informações pessoais no repositório.

Ainda será necessário formalizar o canal de atendimento aos titulares, identificar os responsáveis pelas solicitações e estabelecer os procedimentos e prazos aplicáveis.

**TODO (F1):** definir o canal de contato dos titulares, o procedimento de atendimento e as informações de privacidade que serão apresentadas aos usuários da ferramenta.

## 5. Revisão

Este RIPD foi atualizado considerando a documentação técnica do Fatura Aberta, a política de dados do projeto e as atividades realizadas pela frente F1 durante a preparação dos testes.

A coleta das 15 faturas reais foi concluída, com os respectivos termos de consentimento conferidos e vinculados individualmente, conforme informado pela F1. Os documentos permanecem organizados em ambiente privado, separado do repositório público.

A pesquisa com consumidores reuniu 21 respostas. Desse total, 17 participantes informaram receber a conta impressa e 12 apontaram dificuldade para compreender como os valores são calculados. Esses resultados reforçam a necessidade de considerar diferentes formatos de entrada, especialmente fotografias e documentos digitalizados, e de apresentar explicações claras sobre as cobranças.

Apesar das medidas já documentadas, permanecem pendentes a validação das bases legais, a identificação formal dos agentes de tratamento, a confirmação técnica dos mecanismos de proteção, a revisão das permissões de acesso à pasta privada e a definição dos procedimentos de atendimento aos titulares e de exclusão dos documentos.

O relatório deverá ser atualizado conforme essas definições forem concluídas e as medidas previstas forem verificadas.

**Responsável:** F1 — Produto, Pesquisa e Conformidade  
**Revisora:** Talita  
**Data da revisão:** 13/11/2026  
**Situação:** Revisado pelo par da F1; aguardando validações técnicas e jurídicas pendentes.

Este documento apresenta uma avaliação preliminar dos riscos de proteção de dados e não constitui parecer jurídico.
