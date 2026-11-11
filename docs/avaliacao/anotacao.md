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

Em vez de planilha, o time pode responder numa página privada de anotação (código em
`avaliacao/anotacao/pagina.html`). Ela tem três filas: os 30 itens do golden set, 20 perguntas para
revisar e, quando a rodada S3 terminar, os itens de calibração do juiz.

- **Acesso:** a página é compartilhada pelo dono (Pedro) como Contributor. Cada pessoa escolhe seu
  usuário do GitHub na primeira visita; a escolha fica ligada à conta e um nome já escolhido aparece
  bloqueado. É autodeclaração: o Pedro confere os nomes antes de consolidar.
- **Salvamento:** automático, em uma área privada de cada pessoa. Nada precisa ser baixado.
- **Enviar:** o botão "Enviar respostas" copia suas respostas para a pasta de entregas, que só o dono e
  editores leem. Pode enviar de novo até a rodada ser fechada.
- **Juiz às cegas:** a página mostra só a saída do sistema e a evidência. O veredito do juiz automático
  e a resposta da outra pessoa ficam fora da página até as 80 decisões estarem travadas.
- **Revisão das 120 perguntas:** 20 por pessoa, sorteadas com semente fixa
  (`dados/golden-set/anotacoes/distribuicao-revisao.json`), sem repetição.

### Se a sua conta só consegue ler a página

Quem está fora da organização do dono abre a página como leitor e não grava no banco. A página detecta
isso, salva as respostas no próprio navegador e troca o botão por **Baixar minhas respostas**. Mande o
arquivo `respostas-<usuario>.json` ao Pedro. O importador aceita esses arquivos individuais junto com o
export do banco: `scripts/importar_anotacoes.py respostas-*.json`.

### Do banco para o repositório

1. O dono exporta as entregas do banco para um JSON (formato no cabeçalho de
   `scripts/importar_anotacoes.py`).
2. Simular (não grava nada): `.venv/bin/python scripts/importar_anotacoes.py export.json`
3. Gravar nos CSV, com backup e registro em `importacoes.jsonl`:
   `.venv/bin/python scripts/importar_anotacoes.py export.json --aplicar`
4. Rodar `scripts/consolidar_anotacoes.py` (golden set) e `avaliacao/calibrar_juiz.py` (juiz).

O importador recusa a entrada inteira se houver id fora do que foi atribuído, resposta fora do formato,
"não" sem correção e justificativa, ou conflito com uma anotação já gravada. Reaplicar o mesmo JSON não
muda nada.
