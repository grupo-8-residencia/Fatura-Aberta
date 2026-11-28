# RIPD simplificado

**Projeto:** Fatura Aberta
**Responsável:** F1 — Produto, Pesquisa e Conformidade (Sprint 1)
**Par de revisão:** Talita
**Situação:** Aguardando revisão por pares da atualização de 25/11/2026.

> Este relatório apresenta os riscos relacionados ao tratamento de dados pessoais no Fatura Aberta e as medidas previstas para sua mitigação no âmbito do Challenge 2. Sua elaboração considera a arquitetura, a política de dados e as recomendações jurídico-regulatórias do projeto (`docs/conformidade/recomendacoes-juridico-regulatorias.md`). As questões que dependem de validação técnica ou jurídica permanecem identificadas. Este documento não substitui uma avaliação jurídica formal.

## 1. Descrição do tratamento

O Fatura Aberta é uma ferramenta desenvolvida para auxiliar consumidores residenciais na compreensão e conferência de suas contas de energia elétrica. O projeto trabalha inicialmente com faturas do grupo B1 da Neoenergia Brasília e busca identificar possíveis divergências nos valores cobrados, apresentar explicações acessíveis e orientar o consumidor sobre como solicitar esclarecimentos à distribuidora.

As faturas podem conter dados pessoais, como nome do titular, endereço, número da instalação e CPF, além de informações sobre leituras, consumo em kWh, bandeiras tarifárias, impostos, itens de cobrança e valor total.

O contrato estruturado `Fatura` não possui campos destinados à identificação pessoal do consumidor. A arquitetura prevê que apenas as informações necessárias à conferência sejam encaminhadas aos componentes responsáveis pela análise.

Os titulares envolvidos no tratamento são os consumidores que utilizam a ferramenta e os voluntários que disponibilizaram faturas reais para os testes.

A análise está organizada em três níveis de evidência:

- **Nível A:** verificar a coerência aritmética dos cálculos apresentados na fatura.
- **Nível B:** comparar as informações de cobrança com tarifas e referências oficiais da ANEEL.
- **Nível C:** quando não for possível confirmar uma cobrança ou houver atipicidade, orientar o consumidor sobre como solicitar esclarecimentos à distribuidora, utilizando linguagem baseada em evidências.

Durante a preparação dos testes, a frente F1 realizou a coleta de 15 faturas reais, identificadas pelos códigos F001 a F015. Os documentos foram disponibilizados voluntariamente e permanecem organizados em ambiente privado, fora do repositório público. A conferência da correspondência entre cada fatura e sua autorização deve permanecer registrada no controle interno da F1.

O formulário de consentimento registrou 22 respostas, enquanto a pesquisa com consumidores contabilizou 21 participantes. Esses quantitativos correspondem a instrumentos de coleta distintos e não representam necessariamente as mesmas pessoas.

Entre os 21 participantes da pesquisa, 17 informaram receber a conta de energia impressa e 12 relataram dificuldade para compreender como os valores são calculados. Esses resultados reforçam a necessidade de considerar diferentes formatos de entrada e apresentar explicações acessíveis sobre as cobranças.

As respostas aos formulários de pesquisa não substituem a autorização individual necessária para utilização das faturas reais recebidas para testes.

**Base legal (decisão de 18/11/2026):** consentimento do titular, conforme o art. 7º, inciso I, da Lei nº 13.709/2018 (LGPD), tanto para a cessão das faturas reais utilizadas na validação acadêmica quanto para a utilização da ferramenta pelo consumidor. Essa definição deverá ser submetida à avaliação jurídica prevista na issue #4, com previsão registrada até 27/11/2026.

**Controlador e operadores (decisão de 18/11/2026):** conforme definição preliminar da equipe, o controlador é a equipe acadêmica do projeto Fatura Aberta (UnB/FGA). Os serviços de armazenamento e hospedagem, incluindo Google Drive e Vercel, quando utilizados, deverão ter suas responsabilidades avaliadas de acordo com as respectivas atividades de tratamento. Nas avaliações das sprints S3 e S4, os modelos de linguagem foram executados localmente por meio do Ollama, conforme registrado na documentação do projeto.

A identificação formal dos agentes de tratamento e a adequação das bases legais permanecem sujeitas à validação jurídica.

## 2. Fluxo dos dados

O fluxo de tratamento previsto na arquitetura do Fatura Aberta compreende as seguintes etapas:

1. **Entrada:** o consumidor envia uma fatura em PDF ou imagem por meio da interface web, que encaminha a solicitação ao endpoint `POST /analisar`.

2. **Extração:** o componente `fa_extracao` identifica os campos necessários à conferência. A função `anonimizar()` é destinada à remoção ou ao mascaramento de identificadores pessoais, como nome, endereço, número da instalação, CPF, CNPJ e e-mail. Para imagens, a arquitetura prevê processamento local e higienização de instruções incorporadas ao documento. A conversão do resultado para o contrato `Fatura` ocorre após a confirmação do usuário, por meio de `confirmar()`.

3. **Análise:** os componentes `fa_motor` e `fa_rag` trabalham com as informações estruturadas no contrato `Fatura`. O motor realiza as verificações aritméticas e a busca normativa consulta as referências oficiais necessárias. Quando utilizado, o modelo de linguagem recebe os dados estruturados, conforme a decisão arquitetural ADR-002, que prevê execução local com Ollama.

4. **Saída:** o sistema apresenta um cartão de decisão com o nível de evidência, a descrição objetiva do resultado e as referências normativas utilizadas, incluindo informações sobre sua vigência quando aplicável.

5. **Armazenamento e descarte:** a arquitetura prevê processamento efêmero, sem armazenamento permanente do arquivo original pela API. O código contempla o cabeçalho `Cache-Control: no-store` e métricas operacionais em memória. A efetividade dessas medidas deverá ser confirmada mediante testes e revisão dos ambientes de execução, considerando arquivos temporários, buffers, registros auxiliares e serviços de infraestrutura.

6. **Faturas reais utilizadas nos testes:** as 15 faturas recebidas pela F1 estão armazenadas em uma subpasta exclusiva no Google Drive, fora do repositório GitHub, destinadas exclusivamente às atividades de teste abrangidas pelas autorizações concedidas.

### 2.1. Revisão das permissões de acesso

Durante a revisão realizada pela F1 em 25/11/2026, identificou-se que a pasta principal do projeto no Google Drive possuía configuração de acesso geral por link, representando risco potencial de acesso indevido aos documentos armazenados.

Conforme confirmação registrada pela F1 em 25/11/2026, a subpasta destinada às 15 faturas reais foi configurada em modo restrito, com compartilhamento público por link desativado e acesso concedido exclusivamente aos integrantes autorizados da equipe.

A relação de pessoas autorizadas e o registro da revisão das permissões deverão permanecer no controle privado da equipe, sem divulgação de dados pessoais ou links de acesso no repositório público.

A identificação desse risco não constitui, por si só, evidência de acesso indevido ou incidente de segurança.

### 2.2. Retenção e exclusão das faturas reais

As faturas reais serão utilizadas exclusivamente para as atividades de desenvolvimento e validação autorizadas.

Conforme decisão registrada em 18/11/2026, os documentos deverão ser excluídos ao término das atividades do Challenge 2, respeitando o prazo máximo de **18/12/2026**.

O procedimento deverá abranger:

- Exclusão das faturas armazenadas no Google Drive.
- Exclusão definitiva dos arquivos correspondentes da lixeira do Google Drive.
- Exclusão das cópias locais utilizadas pelos integrantes da equipe.
- Confirmação do descarte pelos integrantes que possuírem cópias.
- Registro da execução pela F1.
- Registro da conclusão na issue #3, sem exposição de dados pessoais, documentos originais ou informações de acesso.

A eventual necessidade de retenção dos registros de consentimento deverá ser avaliada separadamente, considerando sua finalidade e as obrigações legais aplicáveis.

No repositório público, a política de dados permite apenas documentos sintéticos ou efetivamente anonimizados.

## 3. Riscos e medidas

O tratamento de faturas reais exige cuidados específicos, considerando a possibilidade de identificação dos consumidores e a exposição de informações relacionadas ao consumo de energia elétrica.

| Risco identificado | Medida de proteção |
|---|---|
| Publicação acidental de faturas reais no GitHub | Proibição de publicação de documentos reais, mecanismos de bloqueio de arquivos binários, verificações no CI, análise de segredos com Gitleaks e revisão por pares. |
| Exposição de dados pessoais em logs | Previsão de registros limitados às informações necessárias ao diagnóstico e utilização de mecanismos de remoção ou mascaramento de identificadores. A efetividade deverá ser verificada nos ambientes de execução. |
| Envio de dados pessoais a serviços externos | Arquitetura que prevê execução local dos modelos de linguagem com Ollama, conforme ADR-002. A comunicação com serviços externos deverá ser avaliada durante a homologação. |
| Dados pessoais encaminhados ao motor de cálculo | Utilização do contrato estruturado `Fatura`, sem campos destinados à identificação pessoal, e extração limitada às informações necessárias à conferência. |
| Instruções maliciosas inseridas em imagens | Higienização do texto extraído e testes de segurança relacionados à injeção de prompt, conforme `docs/seguranca/injecao-por-imagem.md`. |
| Acesso indevido às faturas reais no Google Drive | Configuração restrita da subpasta das faturas, conforme revisão registrada pela F1 em 25/11/2026, com controle dos integrantes autorizados. |
| Utilização de fatura sem autorização correspondente | Conferência individual da correspondência entre os documentos e os respectivos consentimentos, com registro no controle privado da F1. |
| Permanência de cópias locais após os testes | Exclusão dos documentos no Drive e das cópias locais até 18/12/2026, com confirmação dos integrantes responsáveis e registro do descarte. |
| Orientação incorreta sobre cobranças ou direitos do consumidor | Utilização dos níveis de evidência A, B e C, referências oficiais e linguagem baseada em evidências, respeitando os limites estabelecidos em `docs/conformidade/fronteira-juridica.md` e no requisito RF-15. |

As medidas descritas representam controles previstos ou identificados na documentação e no código do projeto. Sua implementação e eficácia deverão ser verificadas pela equipe responsável, especialmente quanto aos arquivos temporários, registros de execução e comunicação com serviços externos.

## 4. Direitos dos titulares

Os consumidores e voluntários envolvidos no projeto deverão receber informações claras sobre as finalidades do tratamento, as condições de utilização dos documentos e os canais disponíveis para exercício dos direitos previstos na LGPD.

Esses direitos incluem confirmação da existência de tratamento, acesso e correção de dados, eliminação nas hipóteses previstas em lei e revogação do consentimento, quando aplicável.

**Canal dos titulares:** `faturaaberta@gmail.com`.

Conforme decisão registrada em 18/11/2026, a equipe estabelece prazo de resposta de até **5 dias úteis**, observados os prazos e as condições legais aplicáveis a cada solicitação.

### 4.1. Aviso de privacidade aos usuários da ferramenta

O texto a seguir foi elaborado pela F1 para apresentação aos consumidores antes do envio de suas faturas. Sua disponibilização na interface e o mecanismo de manifestação do consentimento deverão ser confirmados pela equipe responsável pela implementação.

> **Aviso de Privacidade — Fatura Aberta**
>
> **Finalidade:** o Fatura Aberta é uma ferramenta acadêmica e informativa destinada a auxiliar consumidores residenciais na compreensão e conferência de suas contas de energia elétrica. Os resultados não substituem a análise da distribuidora ou uma avaliação técnica ou jurídica especializada.
>
> **Dados tratados:** as faturas enviadas podem conter informações pessoais, como nome, endereço, CPF e número da instalação. A ferramenta foi projetada para utilizar apenas as informações necessárias à conferência, como consumo, tarifas, tributos, períodos de faturamento e valores cobrados.
>
> **Base legal:** a utilização da ferramenta está prevista mediante consentimento do usuário, conforme definição preliminar do projeto.
>
> **Armazenamento e retenção:** a aplicação foi projetada para processar os documentos sem armazenamento permanente da fatura original. Os mecanismos de descarte e a eventual existência de arquivos temporários estão sujeitos à validação técnica.
>
> **Compartilhamento:** a arquitetura prevê execução local dos modelos de linguagem, sem encaminhamento intencional das faturas a provedores externos de IA. Os serviços de infraestrutura necessários ao funcionamento da aplicação deverão observar as condições de proteção de dados estabelecidas pelo projeto.
>
> **Direitos dos titulares:** o usuário poderá solicitar informações sobre o tratamento de seus dados, exercer os direitos previstos na LGPD e revogar seu consentimento, observadas as condições legais aplicáveis.
>
> **Canal de atendimento:** dúvidas e solicitações relacionadas à privacidade poderão ser encaminhadas ao e-mail `faturaaberta@gmail.com`, com prazo de resposta de até 5 dias úteis.

### 4.2. Atendimento aos voluntários da coleta

Os voluntários que disponibilizaram faturas reais para os testes poderão solicitar informações sobre o tratamento de seus dados, revogar o consentimento ou requerer a eliminação dos documentos, observadas as condições legais aplicáveis.

As solicitações deverão ser encaminhadas ao e-mail `faturaaberta@gmail.com` e acompanhadas pela frente F1.

Quando aplicável, a exclusão deverá abranger o documento armazenado no Google Drive e as eventuais cópias locais utilizadas pela equipe.

A conferência das autorizações, o atendimento das solicitações e os registros de exclusão deverão ser mantidos em ambiente privado, sem exposição de informações pessoais no GitHub.

## 5. Revisão

Este RIPD foi atualizado considerando a documentação técnica do Fatura Aberta, a política de dados, as recomendações jurídico-regulatórias e as atividades realizadas pela frente F1.

A revisão anterior, realizada em 13/11/2026, e as decisões registradas em 18/11/2026 foram consideradas nesta atualização.

Em 25/11/2026, foram incorporadas as seguintes atualizações:

- Registro da revisão das permissões de compartilhamento da subpasta das faturas reais no Google Drive.
- Identificação do canal oficial de atendimento aos titulares.
- Elaboração do aviso de privacidade destinado aos usuários da ferramenta.
- Consolidação do procedimento e do prazo de exclusão das faturas reais e das cópias locais.
- Distinção entre os controles documentados e as medidas que dependem de validação técnica ou jurídica.

Permanecem em acompanhamento a validação jurídica das bases legais e dos agentes de tratamento, a confirmação da efetividade dos mecanismos técnicos de proteção, a implementação do aviso de privacidade na interface e a comprovação futura do descarte das faturas reais.

**Responsável:** F1 — Produto, Pesquisa e Conformidade
**Par de revisão:** Talita
**Data da revisão anterior:** 13/11/2026
**Data da atualização:** 25/11/2026
**Situação:** Aguardando revisão por pares da atualização.

Este documento apresenta uma avaliação preliminar dos riscos relacionados à proteção de dados pessoais e não constitui parecer jurídico.
