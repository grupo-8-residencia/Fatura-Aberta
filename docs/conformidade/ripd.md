# RIPD simplificado

Responsável: F1 (Sprint 1). Par de revisão: Talita.

!!! info "Rascunho técnico"
    As seções 1 a 4 foram redigidas a partir do que o código e a [política de dados](politica-de-dados.md)
    já fazem hoje. **O que exige decisão ou julgamento jurídico continua como `TODO` e precisa da F1:**
    base legal, controlador e operadores, local das faturas reais e revisão. Este documento não é
    parecer jurídico.

## 1. Descrição do tratamento

- **Dados tratados:** a fatura de energia elétrica residencial (grupo B1, Neoenergia Brasília). Ela
  contém dados pessoais (nome, endereço, número da instalação, às vezes CPF) e dados de consumo e
  cobrança. O contrato `Fatura` **não tem campo** para dado pessoal: o que sai da extração são só
  leituras, consumo, bandeira, alíquota, itens e total.
- **Titulares:** consumidores residenciais que enviam a própria fatura ao produto e voluntários que
  cederam faturas reais para os testes (termo de consentimento, fora do Git).
- **Finalidade:** conferir se os números da fatura são coerentes (nível A), compará-los com a tabela
  oficial da ANEEL (nível B) e, quando não for possível confirmar, orientar um pedido de esclarecimento
  à distribuidora (nível C). Nos testes, as faturas reais servem só para validar o parser e a leitura
  de foto.
- **Base legal:** TODO (F1): confirmar com a Talita e, se possível, com o docente de Direito (#4) qual
  base se aplica ao uso pelo consumidor e qual ao uso das faturas cedidas para teste (consentimento,
  art. 7º, I, da Lei nº 13.709/2018, é a hipótese provável para os voluntários).
- **Controlador e operadores:** TODO (F1): definir quem é o controlador no projeto acadêmico e se há
  operadores (hospedagem, provedor de LLM).

## 2. Fluxo dos dados

1. **Entrada:** o usuário envia o PDF ou a foto da fatura (a interface web chama `POST /analisar`).
2. **Extração:** o parser (`fa_extracao`) lê só os campos de uma lista explícita e `anonimizar()`
   remove nome, endereço, instalação, CPF, CNPJ e e-mail de qualquer texto que precise ser registrado.
   Foto: o modelo de visão roda **localmente** e o resultado só vira `Fatura` depois da confirmação do
   usuário (`confirmar()`). Instruções embutidas na imagem são higienizadas.
3. **Análise:** o motor (`fa_motor`) e a busca normativa (`fa_rag`) trabalham só com o contrato
   `Fatura`, sem dado pessoal. O LLM, quando usado, também recebe só esse contrato (ADR-002: modelo
   local, sem envio a terceiros).
4. **Saída:** o cartão de decisão, com nível, descrição e citação com vigência.
5. **Guarda:** a API **não persiste a fatura**; o resultado vive na sessão do usuário. Os logs registram
   o tipo do erro, não o conteúdo da fatura.
6. **Faturas reais de teste:** ficam em pasta privada fora do Git, com acesso restrito, e serão
   excluídas ao fim do Challenge, inclusive as cópias locais. TODO (F1): registrar o local combinado,
   quem tem acesso e a data limite de exclusão.

## 3. Riscos e medidas

| Risco | Medida |
|---|---|
| Fatura real publicada no Git | Hook de pre-commit que bloqueia PDF e imagens, o mesmo bloqueio repetido no CI, gitleaks e revisão do par |
| Dados pessoais em logs | A API registra só o tipo do erro; `anonimizar()` limpa texto antes de qualquer registro |
| Dados pessoais enviados a serviço externo | Foto lida por VLM **local**; o LLM do experimento roda local (Ollama, ADR-002); as faturas do benchmark são sintéticas |
| Dado pessoal saindo do parser | O contrato `Fatura` não tem campo para dado pessoal e o parser só lê campos de uma lista explícita |
| Instrução maliciosa dentro da imagem (injeção de prompt) | Higienização do texto lido e testes de injeção (`docs/seguranca/injecao-por-imagem.md`) |
| Cópia local de fatura real esquecida | Regra de excluir as cópias ao fim do Challenge; TODO (F1): lembrete e data limite |
| Termo de consentimento sem vínculo com a fatura | O vínculo individual está `A verificar` em `docs/produto/coleta-faturas.md`; nenhuma fatura é processada antes disso |
| Resposta do produto induzir o usuário a erro jurídico | Linguagem de evidência (A, B, C), verificador RF-15 e a [fronteira jurídica](fronteira-juridica.md) |

## 4. Direitos dos titulares

- **Consumidores que usam o produto:** como a fatura não é guardada, não há registro a acessar,
  corrigir ou eliminar depois da sessão. TODO (F1): confirmar essa leitura e redigir o aviso ao usuário.
- **Voluntários que cederam faturas:** podem pedir a exclusão a qualquer momento pelo canal combinado
  na coleta. TODO (F1): registrar o canal e o prazo de resposta.

## 5. Revisão

- **Revisor:** TODO (Talita, par de revisão da F1)
- **Data:** TODO
