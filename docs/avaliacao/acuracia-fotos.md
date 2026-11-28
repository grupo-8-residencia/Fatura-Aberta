# Acurácia por campo da leitura de foto (S5, #41)

Gate da S5: **acerto ≥ 90% em cada campo-chave, em 40 fotos**. Se algum campo-chave ficar abaixo,
o plano de contingência é OCR mais formulário de confirmação.

> **Situação:** medição feita em 27/11/2026 com **40 fotos sintéticas** (não reais) e dois modelos
> de visão locais. Os seis campos-chave passaram nos dois modelos. A decisão do time segue pendente
> (ver abaixo). As 7 fotos reais continuam fora do repositório e não entraram nesta medição.

## O que é medido

A leitura que o produto faz: foto → `ExtratorOllama` (modelo de visão local, `fa_extracao.vlm`) →
`extrair_candidata` (descarta e anonimiza dados pessoais). A medição compara a candidata com um
gabarito conferido à mão, **antes** da confirmação do usuário. Ou seja, mede quanto o usuário vai
precisar corrigir, não o resultado depois da correção.

| Campo | Campo-chave? | Como conta acerto |
|---|---|---|
| `mes_referencia` | sim | Mês e ano iguais |
| `consumo_kwh` | sim | Número igual |
| `total` | sim | Número igual |
| `aliquota_icms` | sim | Número igual (12,00 = 12) |
| `bandeira` | sim | Texto igual, sem diferença de caixa |
| `leitura_anterior`, `leitura_atual`, `distribuidora`, `grupo_tarifario` | não | Igualdade, como acima |
| `itens` | não | Linhas com descrição e valor corretos; soma dos itens igual ao total (± R$ 0,01) |

**Campos-chave: proposta da F4, a confirmar com a F5 (Pedro).** São os que entram no recálculo da
fatura. A lista está em `CAMPOS_CHAVE` de `scripts/acuracia_por_campo.py` e pode ser trocada com
`--campos-chave`.

**Regra para a bandeira no gabarito:** usar a cor **cobrada** no item `Acrés. Band.`, não a frase
"bandeira em vigor" de `INFORMAÇÕES IMPORTANTES`, que em várias fotos diverge (ver o mapa do layout
em [F4](../frentes/f4.md)). O prompt do modelo pede a mesma coisa.

## Amostra

- **Meta:** 40 fotos de faturas Neoenergia Brasília B1, com termo de consentimento (F1).
- **Hoje:** 7 fotos recebidas na coleta da S2.
- **Como completar:** pedir mais fotos à F1. Se não houver faturas novas a tempo, completar com
  novas fotos das mesmas faturas variando luz, ângulo, distância e papel dobrado. Nesse caso o
  relatório declara quantas faturas distintas há, porque fotos da mesma fatura não são
  independentes, e mostra o acerto também por fatura.
- Fotos fora do escopo (outra distribuidora, outro grupo, captura de tela) não entram.

## Como rodar (local, fora do Git)

1. Coloque as fotos em `faturas-reais/fotos/` com nomes neutros: `foto-01.jpg`, `foto-02.jpg`...
2. Suba o Ollama e baixe o modelo: `ollama pull qwen2.5vl:3b`.
3. Gere o gabarito em branco e a extração:

    ```bash
    FA_VLM_MODELO=qwen2.5vl:3b uv run python scripts/extrair_fotos.py --gabarito-modelo
    ```

4. Copie `faturas-reais/avaliacao/gabarito-modelo.json` para `gabarito.json` e preencha **olhando
   as fotos**, sem abrir o `previsto.json`, para não se ancorar na leitura do modelo. Valores como
   estão impressos (`81,95`, `10/2026`); `null` quando o campo não aparece na foto.
5. Meça:

    ```bash
    uv run python scripts/acuracia_por_campo.py \
      faturas-reais/avaliacao/previsto.json faturas-reais/avaliacao/gabarito.json \
      --saida faturas-reais/avaliacao/relatorio.md
    ```

6. Copie para a seção Resultado só a tabela do `relatorio.md` (contagens e percentuais) e o
   `metadados.json` (modelo, digest, latência). Nenhum valor de fatura vai para o Git.

Para comparar modelos, repita os passos 3 e 5 com outro `FA_VLM_MODELO`, gravando em outra pasta
(`--saida`). Candidatos a conferir na biblioteca do Ollama: `qwen2.5vl:3b` (padrão),
`qwen2.5vl:7b`, `gemma3:4b` e `llama3.2-vision:11b`. A rodada deve ser na máquina de medição do
time ([ADR-002](../arquitetura/decisoes/adr-002-llm-local.md)), porque um modelo de visão de 7B não
roda em tempo útil em notebook sem GPU.

## Privacidade

- As fotos, o `previsto.json`, o gabarito e o relatório bruto ficam em `faturas-reais/`, ignorada
  pelo Git; o hook `bloquear-binarios` também recusa imagens fora das pastas liberadas.
- A imagem vai só ao Ollama local e não é gravada em disco pelo extrator; não há cache de respostas.
- O esquema pedido ao modelo não tem campos para nome, endereço, CPF ou instalação, e a candidata
  descarta e anonimiza qualquer coisa fora da lista.
- O `metadados.json` tem só contagens, mensagens de erro escritas pelo projeto e latências.

## Resultado

Fotos: 40 faturas sintéticas distintas (`GS-F001` a `GS-F040` do golden set, nas ordens do arquivo),
renderizadas e degradadas por `scripts/gerar_fotos_sinteticas.py` (rotação, brilho, desfoque, ruído
e compressão JPEG, com semente fixa). O gabarito é o dado desenhado em cada foto. Relatórios:
`avaliacao/resultados/s5-fotos/`.

Campos-chave (escalares de `metricas.md`), iguais nos dois modelos:

| Campo | Avaliados | Acertos qwen2.5vl:3b | Acertos qwen2.5vl:7b | Campo-chave |
|---|---|---|---|---|
| `distribuidora` | 40 | 40 (100%) | 40 (100%) | sim |
| `mes_referencia` | 40 | 40 (100%) | 40 (100%) | sim |
| `consumo_kwh` | 40 | 40 (100%) | 40 (100%) | sim |
| `total` | 40 | 40 (100%) | 40 (100%) | sim |
| `bandeira` | 40 | 40 (100%) | 40 (100%) | sim |
| `aliquota_icms` | 40 | 40 (100%) | 40 (100%) | sim |

Itens (não entram no gate):

| Métrica | qwen2.5vl:3b | qwen2.5vl:7b |
|---|---|---|
| Linhas corretas (descrição, quantidade, tarifa, valor) | 79 de 124 (64%) | 72 de 124 (58%) |
| Soma das linhas igual ao total lido | 34 de 40 (85%) | 8 de 40 (20%) |

Modelo e digest: `qwen2.5vl:3b` (`fb90415cde1e`) e `qwen2.5vl:7b` (`5ced39dfa4ba`). Rodadas de
27/11/2026, sem falhas de extração (40 de 40 em cada). Latência por foto, na GPU de 6 GB:

| Modelo | p50 | p95 | máx. |
|---|---|---|---|
| `qwen2.5vl:3b` | 14,8 s | 16,0 s | 144,5 s (primeira foto, com carga do modelo) |
| `qwen2.5vl:7b` | 50,8 s | 56,3 s | 61,2 s |

Antes da rodada final, uma rodada anterior foi interrompida para corrigir o ruído das fotos, que não
era reproduzível. Só a rodada final, sobre as fotos atuais, vale.

Limitações desta medição: as fotos são sintéticas, com um layout escrito pelo próprio projeto. Elas
tendem a ser mais limpas que fotos reais, então 100% aqui não prova acerto em foto de celular. A
verificação de sanidade do avaliador (trocar valores de propósito) fez a taxa cair como esperado.

## Decisão do gate

| Decisão | Critério | O que acontece |
|---|---|---|
| **Go** | Todos os campos-chave ≥ 90% nas 40 fotos | A foto segue com VLM e confirmação obrigatória do usuário. |
| **Pivot** | Algum campo-chave < 90% | OCR mais formulário de confirmação. O formulário já existe (`confirmar()`); o OCR entra como outro `ExtratorDeFoto`, sem mudar o resto do fluxo. |
| **No-Go** | Menos de 40 fotos até o fim da S5 | A medição não vale como gate; registrar a amostra parcial como exploratória e replanejar com a F1. |

**Resultado medido:** os seis campos-chave passaram nos dois modelos, então o critério Go foi
atingido nas fotos sintéticas. Recomendação técnica: `qwen2.5vl:3b` tem os mesmos acertos nos
campos-chave, leitura de itens melhor e é cerca de 3,4 vezes mais rápido nesta GPU. Hoje o código
usa `qwen2.5vl:3b` como padrão (`packages/extracao/src/fa_extracao/vlm.py`), escolhido pela medição.

**Decisão do time:** pendente. Um Go nas fotos sintéticas precisa ser confirmado com fotos reais
antes de a foto sair de "em validação" no produto.
