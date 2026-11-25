# RIPD simplificado

**Projeto:** Fatura Aberta  
**Responsável:** F1 — Produto, Pesquisa e Conformidade (Sprint 1)  
**Par de revisão:** Talita  
**Situação:** Aguardando revisão por pares

> Este relatório apresenta os riscos relacionados ao tratamento de dados pessoais no Fatura Aberta e as medidas previstas e implementadas para mitigá-los no âmbito do Challenge 2. As informações técnicas foram elaboradas com base na arquitetura do sistema, na política de dados e nas diretrizes consolidadas nas Recomendações Jurídico-Regulatórias da Frente F1 (`docs/conformidade/recomendacoes-juridico-regulatorias.md`). Este documento não substitui uma avaliação jurídica formal.

## 1. Descrição do tratamento

O Fatura Aberta é uma ferramenta desenvolvida para auxiliar consumidores residenciais na compreensão e conferência de suas contas de energia elétrica. O projeto trabalha inicialmente com faturas do grupo B1 da Neoenergia Brasília e busca identificar possíveis divergências nos valores cobrados, apresentar explicações acessíveis e orientar o consumidor sobre como solicitar esclarecimentos à distribuidora.

As faturas de energia elétrica podem conter dados pessoais, como nome do titular, endereço, número da instalação e, eventualmente, CPF, além de informações sobre leituras, consumo em kWh, bandeiras tarifárias, impostos, itens de cobrança e valor total.

O contrato estruturado `Fatura` não possui campos destinados à identificação pessoal do consumidor. Apenas as informações técnicas e tarifárias necessárias à conferência são processadas pelos componentes de cálculo e busca normativa.

Os titulares envolvidos no tratamento são:
1. Os **consumidores residenciais** que utilizam a ferramenta para conferência de suas próprias faturas;
2. Os **voluntários** que disponibilizaram faturas reais para apoiar o desenvolvimento e os testes do sistema.

A análise está organizada em três níveis de evidência:
- **Nível A:** verificar a coerência aritmética dos cálculos apresentados na fatura.
- **Nível B:** comparar as informações de cobrança com tarifas e referências oficiais da ANEEL.
- **Nível C:** quando não for possível confirmar uma cobrança ou houver atipicidade, orientar o consumidor sobre como solicitar esclarecimentos à distribuidora, utilizando linguagem baseada em evidências.

Durante a preparação dos testes, a frente F1 realizou a coleta de 15 faturas reais, identificadas pelos códigos F001 a F015. Os documentos foram disponibilizados voluntariamente e seus respectivos termos de consentimento foram conferidos e vinculados individualmente no controle privado da F1, fora do repositório público.

O formulário de consentimento registrou 22 respostas, enquanto a pesquisa com consumidores contabilizou 21 participantes. Esses quantitativos correspondem a instrumentos de coleta distintos e não representam necessariamente as mesmas pessoas. Entre os 21 participantes da pesquisa, 17 informaram receber a conta de energia impressa e 12 relataram dificuldade para compreender como os valores são calculados. As respostas aos formulários de pesquisa não substituem a autorização individual necessária para utilização das 15 faturas reais recebidas para testes.

**Base legal:**
- **Faturas reais de teste (voluntários):** O tratamento fundamenta-se no **consentimento específico dos titulares** (art. 7º, inciso I, da Lei nº 13.709/2018 — LGPD), coletado mediante termo de autorização livre, informado e inequívoco, com finalidade restrita à validação dos módulos de extração e testes funcionais do projeto.
- **Utilização da ferramenta pelos consumidores:** O tratamento fundamenta-se no **consentimento do usuário** (art. 7º, inciso I, da LGPD) e na **execução de procedimentos preliminares a pedido do titular** (art. 7º, inciso V, da LGPD), formalizado pela adesão prévia e expressa ao Aviso de Privacidade antes do envio do arquivo para a execução efêmera da conferência.

**Controlador e operadores:**
- **Controlador:** O projeto acadêmico **Fatura Aberta** atua como **controlador independente** (art. 5º, VI, da LGPD), definindo as finalidades informativas e os meios essenciais do serviço de conferência, conforme estabelecido nas diretrizes de conformidade do projeto.
- **Operadores:** Na arquitetura do MVP, os módulos implementados suportam exclusivamente execução local para modelos de linguagem (Ollama, conforme ADR-002 e `packages/agentes/src/fa_agentes/llm.py`) e componentes locais de visão/extração, sem suporte nem transmissão a provedores externos de IA para treinamento. Serviços de infraestrutura e hospedagem atuam estritamente como suporte técnico de conectividade.

## 2. Fluxo dos dados

O fluxo de tratamento estabelecido na arquitetura do Fatura Aberta compreende as seguintes etapas:

1. **Entrada:** o consumidor envia uma fatura em PDF ou imagem por meio da interface web, que encaminha a solicitação ao endpoint `POST /analisar`.
2. **Extração:** o componente `fa_extracao` identifica os campos necessários à conferência. A função `anonimizar()` remove ou mascara identificadores pessoais (nome, endereço, instalação, CPF, CNPJ e e-mail) de textos processados. No caso de imagens, o modelo de visão executa localmente, com higienização de instruções maliciosas incorporadas ao documento. A conversão do resultado provisório para o contrato `Fatura` ocorre após a confirmação do usuário (`confirmar()`).
3. **Análise:** os componentes `fa_motor` e `fa_rag` trabalham exclusivamente com as grandezas numéricas e tarifárias estruturadas no contrato `Fatura`. O motor realiza as verificações aritméticas e a busca normativa consulta os atos regulatórios oficiais homologados. O modelo de linguagem, quando acionado, opera localmente e recebe apenas os dados técnicos estruturados.
4. **Saída:** a interface apresenta o cartão de decisão ao consumidor, contendo o nível de evidência (A, B ou C), a descrição objetiva e a citação normativa com vigência conferida.
5. **Armazenamento e descarte:** o código da API implementa **processamento efêmero em memória**, com resposta marcada como `Cache-Control: no-store` e métricas operacionais restritas a contadores de requisições e tempo de resposta. A arquitetura prevê que o arquivo original não seja persistido em banco de dados ou disco. *Nota de conformidade:* A garantia prática de inexistência de resíduos depende da validação contínua do ciclo de vida de arquivos temporários em runtime e do comportamento de buffers nos servidores de aplicação e balanceadores. Os logs de monitoramento registram apenas códigos de diagnóstico técnico e tipos de erro.
6. **Faturas reais utilizadas nos testes:** as 15 faturas recebidas (F001 a F015) estão armazenadas em uma subpasta exclusiva no Google Drive, dentro da pasta "Projeto IA / Fatura Aberta", fora do repositório Git. Durante a revisão de conformidade realizada em 25/11/2026 pela Frente F1, identificou-se que a pasta principal estava com acesso geral por link ("Qualquer pessoa com o link pode ver"), embora restrito na prática aos integrantes da equipe. Para mitigar o risco de acesso indevido decorrente da herança de permissões, a responsável da F1 (Natália Evelin) reconfigurou e confirmou em **25/11/2026** o acesso da subpasta das 15 faturas como estritamente **Restrito**, com compartilhamento público por link desativado e acesso concedido exclusivamente às contas dos integrantes autorizados da equipe técnica para testes de extração e OCR. Todos os arquivos de faturas reais armazenados no Google Drive e eventuais cópias locais utilizadas para testes serão definitivamente excluídos ao término formal das atividades do Challenge 2, mediante confirmação de descarte pelos integrantes da equipe que possuírem cópias.

## 3. Riscos e medidas

O tratamento de faturas reais e o fluxo de dados na ferramenta envolvem riscos que são mitigados pelas seguintes medidas técnicas e organizacionais:

| Risco | Medida de mitigação |
|---|---|
| Inclusão acidental de fatura real no Git | Bloqueio automático de PDFs e imagens via hook de pre-commit e verificação repetida no CI; execução contínua do gitleaks; e revisão obrigatória por pares em todo PR. |
| Presença de dados pessoais em logs do sistema | A API foi desenhada para registrar apenas tipos de erro e contadores em memória; a rotina `anonimizar()` higieniza textos antes de registros auxiliares. A ausência de vazamentos em logs em produção requer auditoria nos ambientes de deploy. |
| Envio de dados pessoais a serviços externos | O código-fonte restringe os provedores de modelo a `ollama` (local) e cliente simulado de teste, sem integração configurada para APIs públicas externas. Os benchmarks públicos utilizam apenas faturas sintéticas. |
| Dados pessoais encaminhados ao motor de cálculo | O contrato `Fatura` não possui campos de identificação pessoal e o extrator opera com uma lista restrita de campos necessários à conferência. |
| Instruções maliciosas inseridas em imagens (injeção de prompt) | Higienização do texto extraído e testes preventivos de injeção documentados em `docs/seguranca/injecao-por-imagem.md`. |
| Acesso indevido às faturas reais no Google Drive | As faturas estão em subpasta dedicada fora do Git. A revisão de 25/11/2026 identificou o risco de herança pelo link geral da pasta pai ("Qualquer pessoa com o link pode ver"). Em 25/11/2026, a responsável da F1 confirmou a remediação da subpasta para modo restrito, com link público desativado e acesso restrito exclusivamente aos integrantes autorizados da equipe. |
| Utilização de fatura sem autorização correspondente | A F1 realizou a conferência e a vinculação individual dos termos de consentimento a cada uma das faturas F001 a F015 no controle privado da coleta. |
| Permanência de cópias locais após os testes | Regra formal de descarte obrigatório de todas as faturas reais no Drive e cópias locais utilizadas para testes ao término formal das atividades do Challenge 2, com confirmação obrigatória de descarte pelos integrantes que possuírem cópias. |
| Orientação incorreta ou promessa jurídica indevida | Adoção estrita dos níveis de evidência A, B e C, linguagem moderada baseada em fatos objetivos, respeito à fronteira jurídica (`docs/conformidade/fronteira-juridica.md`) e verificador de conformidade textual RF-15. |

As medidas técnicas descritas representam controles identificados no código e nas políticas do projeto. A efetividade plena das salvaguardas que dependem de infraestrutura de execução (como limpeza de buffers de sistema operacional, arquivos temporários de upload e logs de proxies) deve ser acompanhada e validada nas etapas de homologação e deploy.

## 4. Direitos dos titulares

### 4.1. Informações de Privacidade e Transparência aos Usuários da Ferramenta

Para assegurar a transparência ativa exigida pelo art. 9º da LGPD, a interface web do Fatura Aberta apresenta ao usuário, antes do envio de qualquer documento, as seguintes informações de privacidade:

> **Aviso de Privacidade — Fatura Aberta**
>
> - **Finalidade:** O Fatura Aberta realiza a conferência técnica e matemática de faturas de energia elétrica residencial (Grupo B1, Neoenergia Brasília), indicando a coerência dos cálculos (Nível A), a correspondência com tarifas homologadas pela ANEEL (Nível B) e fornecendo apoio informativo para pedidos de esclarecimento à distribuidora (Nível C). O serviço possui caráter acadêmico e informativo, não substituindo a análise da distribuidora ou consultoria técnica/jurídica.
> - **Dados tratados:** Apenas os campos numéricos e regulatórios necessários à conferência (datas de ciclo e vencimento, consumo em kWh, bandeiras tarifárias, alíquotas tributárias, itens faturados e valores monetários). Nomes, endereços, números de instalação, CPF e dados de pagamento são desconsiderados ou mascarados na etapa de ingestão (`anonimizar()`) e não são registrados no contrato `Fatura`.
> - **Armazenamento e retenção:** A aplicação foi projetada para **processamento efêmero em memória**. Não há previsão de persistência em banco de dados ou disco, e a resposta é configurada com cabeçalho `no-store`. A ausência total de retenção residual em runtime depende da validação do ciclo de vida dos arquivos temporários de upload durante a execução.
> - **Exclusão:** Os dados voláteis de processamento são destruídos com o encerramento da sessão ou fechamento do navegador.
> - **Compartilhamento:** Não há compartilhamento de faturas, imagens ou dados pessoais com terceiros, empresas de cobrança, distribuidoras ou provedores externos de IA. Os modelos de análise são restritos a execução local.
> - **Direitos dos titulares:** Em consonância com o art. 18 da LGPD, o titular tem direito de confirmar a existência de tratamento, ter acesso às informações e solicitar a eliminação de seus dados. Em decorrência do desenho efêmero da ferramenta (sem banco de dados de faturas), não há base mantida para consulta posterior.
> - **Canal de atendimento:** Para dúvidas sobre privacidade, exercício de direitos ou esclarecimentos institucionais, o titular pode entrar em contato com a equipe pelo e-mail oficial: **`faturaaberta@gmail.com`**, com prazo de retorno em até 15 dias úteis.

### 4.2. Atendimento aos Voluntários da Coleta de Faturas

Os voluntários que cederam as faturas F001 a F015 para apoiar os testes do sistema contam com as seguintes garantias:
- Os termos de consentimento assinados estão vinculados individualmente às respectivas faturas no controle interno da F1, sem publicação de dados no repositório público.
- O voluntário pode solicitar, a qualquer momento, a revogação de seu consentimento e a eliminação imediata de sua fatura e respectivo termo, enviando mensagem para **`faturaaberta@gmail.com`**.
- As requisições serão processadas pela responsável de conformidade da F1 no prazo de até 15 dias úteis, com exclusão segura do arquivo na pasta privada e nas eventuais cópias de desenvolvimento.

## 5. Revisão

Este RIPD foi atualizado considerando a arquitetura técnica do Fatura Aberta, a política de dados do projeto, a análise de conformidade da Frente F1 (`docs/conformidade/recomendacoes-juridico-regulatorias.md`) e os controles operacionais estabelecidos para os dados de teste no âmbito do Challenge 2.

Todas as pendências técnicas e formais atribuídas à F1 foram endereçadas:
1. As bases legais (art. 7º, I e V da LGPD) e a definição dos agentes de tratamento (Fatura Aberta como controlador independente) foram devidamente fundamentadas, distinguindo os controles já verificáveis no código das garantias operacionais que dependem de validação em execução.
2. A revisão das permissões de acesso da pasta no Google Drive identificou risco de herança pelo link geral aberto da pasta principal; em 25/11/2026, a responsável da F1 confirmou a configuração efetiva da subpasta das faturas em modo estritamente Restrito, com compartilhamento público por link desativado e acesso exclusivo aos integrantes autorizados.
3. A regra de exclusão definitiva das 15 faturas reais no Google Drive e de eventuais cópias locais utilizadas para testes foi aprovada pela equipe para ocorrer ao término formal das atividades do Challenge 2, com confirmação de descarte pelos integrantes que possuírem cópias.
4. O canal oficial dos titulares foi instituído por meio do e-mail `faturaaberta@gmail.com`, com prazo de resposta definido em até 15 dias, acompanhado da redação integral do Aviso de Privacidade aos usuários da ferramenta.

**Responsável:** Frente F1 — Produto, Pesquisa e Conformidade (Natália Evelin)  
**Par de revisão:** Talita  
**Data da atualização:** 25/11/2026  
**Situação:** Aguardando revisão por pares
