# Como anotar o golden set

Este guia é para quem recebeu um CSV de anotação do [golden set](golden-set.md) (issue #32). Cada
pessoa confere **30 itens**: 12 perguntas e 18 faturas sintéticas. Além disso, o time revisa as 120
perguntas em `revisao-perguntas.csv`.

!!! warning "Você confere, não inventa"
    O gabarito que está no CSV é uma **proposta** (vem da construção do conjunto). Seu trabalho é
    dizer se concorda e, quando não concordar, apontar a correção e o motivo. Não preencha por
    palpite: se não tiver certeza, escreva isso no comentário.

## Onde está o seu arquivo

`dados/golden-set/anotacoes/<seu-usuario-github>.csv`, por exemplo `dados/golden-set/anotacoes/mariadenis.csv`.

| Coluna | Quem preenche | O que é |
|---|---|---|
| `id` | já vem pronta | `GS-Q...` (pergunta) ou `GS-F...` (fatura) |
| `tipo` | já vem pronta | `pergunta` ou `fatura` |
| `enunciado` | já vem pronta | a pergunta ou o resumo da fatura com itens e total |
| `gabarito_proposto` | já vem pronta | o que o conjunto considera correto |
| `concorda` | **você** | `sim` ou `não` (só esses valores) |
| `correcao` | você, se `concorda = não` | o gabarito que você acha correto |
| `comentario` | você | justificativa curta; cite o dispositivo ou a conta |

## O que conferir em uma pergunta

1. A pergunta está clara e responde-se com o corpus (ver [RAG](../arquitetura/rag.md))?
2. A **resposta esperada** bate com o texto do dispositivo citado em `Citação canônica`?
3. A **citação canônica** é o dispositivo certo (artigo, parágrafo, inciso)?
4. A **abstenção esperada** faz sentido? Perguntas com data anterior a 03/01/2022 (antes da
   REN ANEEL 1.000/2021), de tema fora do corpus ou de lacuna devem terminar em abstenção ou em
   resposta que sinalize o limite (`TODO:`), sem afirmar além do texto.
5. A data de referência está coerente com a pergunta?

## O que conferir em uma fatura

As faturas são **sintéticas**, com tarifas inventadas (R$ 0,80/kWh e adicionais fictícios). Não
compare com a sua conta real nem com tarifas oficiais.

1. **Leituras e consumo:** `leitura atual − leitura anterior` é igual ao consumo informado?
2. **Itens:** energia = consumo × tarifa; adicional de bandeira = consumo × adicional da bandeira;
   há algum item repetido?
3. **Total:** a soma dos itens é o total informado?
4. **ICMS:** a alíquota informada é coerente com as demais faturas (20%)?
5. Compare com o `gabarito_proposto`: o veredito da fatura (`confere` ou `diverge_A`), o veredito de
   cada item e a anomalia injetada estão certos?

## Regras de linguagem

- Use **linguagem de evidência**: "o valor diverge do esperado", "o item aparece duas vezes", "o
  total não fecha". Nunca escreva que algo é "ilegal", "fraude" ou que a distribuidora "errou de
  propósito". A ferramenta aponta indícios, não faz juízo jurídico.
- Em dúvida jurídica, escreva "precisa de confirmação" e cite o dispositivo; não conclua.
- **Não cole dados pessoais nem faturas reais** (nome, CPF, endereço, número de instalação, foto de
  conta). Os comentários vão para o repositório.

## Como devolver

1. Abra o CSV em planilha (Excel, LibreOffice ou Google Planilhas) importando como UTF-8, ou em um
   editor de texto.
2. Preencha só `concorda`, `correcao` e `comentario`. Não altere `id`, `tipo`, `enunciado` nem
   `gabarito_proposto`, e não reordene nem apague linhas.
3. Salve como **CSV UTF-8** com o mesmo nome do arquivo.
4. Abra um PR para `dev` com o seu arquivo (`feat(avaliacao): anotação de <usuario> (#32)`) ou envie
   ao time, que faz o commit.

## Para o time: acompanhar e consolidar

```bash
.venv/bin/python scripts/consolidar_anotacoes.py            # progresso, divergências e pendências
.venv/bin/python scripts/consolidar_anotacoes.py --aplicar  # só imprime o que mudaria
```

O consolidador nunca altera o golden set. Aplicar as correções e **recongelar os hashes**
(`scripts/gerar_golden_set.py`) é decisão do time, depois de discutir cada divergência. O kit é
regenerado de forma determinística por `scripts/gerar_kit_anotacao.py`; atenção: regenerar sobrescreve
os CSV, então só faça isso antes da distribuição.

## Anotar pela página (recomendado)

Em vez de planilha, o time pode responder numa página de anotação, sem login e sem banco
(`avaliacao/anotacao/pagina.html`, gerada por `avaliacao/anotacao/construir_pagina.py`). Ela tem três
filas: os 30 itens do golden set, 20 perguntas para revisar e, quando a rodada S3 terminar, os itens de
calibração do juiz.

- **Acesso:** qualquer pessoa com o link, sem login. Cada pessoa escolhe o usuário do GitHub e digita o
  **código pessoal** que o Pedro enviou em particular; só então os itens dela abrem. O código não está no
  Git nem no HTML (a página guarda apenas um verificador).
- **Salvamento:** automático, no navegador. Para continuar em outro aparelho ou depois de limpar o
  navegador, cole na página o último texto copiado ("Continuar de outro aparelho").
- **Resumo antes de entregar:** a página lista quantos itens estão completos, quais faltam e se há
  alterações depois da última cópia.
- **Entregar:** **Copiar minhas respostas** gera um texto assinado com o código pessoal (HMAC-SHA256), com
  um recibo de 8 caracteres. Cole numa mensagem para o Pedro (ou salve como `respostas-<usuario>.json`).
- **Juiz às cegas:** a página mostra só a saída do sistema e a evidência. O veredito do juiz automático e
  a resposta da outra pessoa não entram no HTML.
- **Revisão das 120 perguntas:** 20 por pessoa, sorteadas com semente fixa
  (`dados/golden-set/anotacoes/distribuicao-revisao.json`), sem repetição.

### Dos arquivos para o repositório

1. Salve cada entrega como um arquivo `respostas-<usuario>.json`.
2. Simular (não grava nada), verificando as assinaturas com os códigos:
   `.venv/bin/python scripts/importar_anotacoes.py respostas-*.json --codigos .local/anotacao/codigos.json`
3. Gravar nos CSV, com backup e registro em `importacoes.jsonl`: o mesmo comando com `--aplicar`.
4. Rodar `scripts/consolidar_anotacoes.py` (golden set) e `avaliacao/calibrar_juiz.py` (juiz).

O importador recusa tudo se houver id fora do que foi atribuído, resposta fora do formato, "não" sem
correção e justificativa, ou conflito com uma anotação já gravada. Reaplicar os mesmos arquivos não muda
nada. Uma entrega com assinatura inválida, ou sem assinatura (sem `--aceitar-sem-assinatura`), é recusada: a
identidade é comprovada pelo código pessoal, não pelo nome escolhido.

Os códigos são gerados por `avaliacao/anotacao/construir_pagina.py` em `.local/anotacao/codigos.json`
(fora do Git). Para incluir os itens do juiz depois da rodada, rode o script de novo e republique a página;
os códigos se mantêm.
