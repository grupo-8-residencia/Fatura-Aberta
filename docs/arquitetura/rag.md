# RAG normativo (F2)

O RAG da Fatura Aberta recupera **dispositivos** de normas públicas vigentes e só responde com o que
recuperou. Quando nenhum dispositivo cobre a pergunta, o sistema se abstém.

## Arquitetura

```mermaid
flowchart TD
    A["Ingestão de normas<br/>dados/normas/corpus_b1.json"] --> B["Chunking por dispositivo<br/>caput, parágrafo, inciso"]
    B --> C["Geração de embeddings<br/>EmbedderHash (offline) ou modelo pt-BR"]
    C --> D["Banco vetorial / índice híbrido<br/>IndiceHibrido<br/>(vetores em disco, opcional)"]
    Q["Pergunta + data de referência + subgrupo B1"] --> E["Filtro temporal de vigência<br/>e de subgrupo"]
    D --> E
    E --> F["Recuperação top-k<br/>α · vetorial + (1 − α) · léxico"]
    F --> G{"score ≥ limiar?"}
    G -- sim --> H["Síntese com citação rastreável<br/>ato, dispositivo, vigência, link"]
    G -- não --> I["Abstenção<br/>sem fonte, sem resposta"]
```

## Pipeline de ingestão, ponta a ponta

```mermaid
flowchart LR
    A["1. Coleta<br/>texto consolidado oficial<br/>(ANEEL, Câmara, SINJ-DF)"] --> B["2. Limpeza<br/>remove notas de redação,<br/>links e dispositivos revogados"]
    B --> C["3. Conferência<br/>literalidade, URL oficial,<br/>vigência (conferido = sim)"]
    C --> D["4. Chunking<br/>caput, §, parágrafo único, inciso"]
    D --> E["5. Embedding<br/>vetor L2-normalizado"]
    E --> F["6. Indexação<br/>IndiceHibrido<br/>(vetores em disco, opcional)"]
    C -. "não conferido" .-> X["Fora do índice<br/>(A verificar)"]
```

A coleta e a limpeza são assistidas por `scripts/converter_norma.py` (F4) e conferidas por pessoa; o
resultado é o `corpus_b1.json`, que é a entrada reproduzível do restante do pipeline. A coleta
continua **manual** e a conferência **humana**; o conversor (PR #130, já integrado) só acelera a
limpeza e não substitui a revisão. Ele lê
PDF ou HTML, separa por artigo, tira cabeçalhos, rodapés e notas de redação, e grava itens
candidatos com `conferido = "A verificar"`: nada entra no índice sem conferência humana. O inventário
dos atos está em `dados/normas/manifesto_atos.json`.

1. **Curadoria.** Cada dispositivo é transcrito do texto oficial e conferido. O item guarda `id`,
   `titulo`, `texto`, `citacao` (`ato`, `dispositivo`, `vigencia_inicio`, `vigencia_fim`, `url`),
   `subgrupos`, `tags`, `conferido`, `conferido_em` e `fonte_conferencia`. Itens que não foram
   conferidos ficam como `"A verificar"` e **não entram no índice**.
2. **Carga.** `fa_rag.carregar_corpus()` valida cada citação com o contrato `Citacao`, recusa campos
   faltando e ids repetidos.
3. **Chunking.** `chunkar_dispositivo()` quebra em caput, parágrafos (`§ nº` e `Parágrafo único.`) e
   incisos. Cada chunk herda a citação com o dispositivo refinado (por exemplo, `art. 323, § 2º`).
4. **Embeddings.** `criar_embedder()` escolhe o extrator por `FA_RAG_EMBEDDER` (padrão `hash`).
5. **Índice.** `IndiceHibrido.do_corpus()` guarda os vetores normalizados e as frequências de termos. Com
   `arquivo_vetores=Path(...)` o índice é **durável**: os vetores vão para um JSON com a versão do
   formato, o nome e a versão do embedder, a dimensão e a assinatura dos textos. A gravação é atômica
   (arquivo temporário e `os.replace`), então uma falha no meio nunca deixa índice parcial. Na carga,
   qualquer divergência (corpus, embedder, dimensão, formato ou arquivo corrompido) descarta o arquivo
   com aviso em log, recalcula e regrava. Só os vetores são persistidos; as frequências de termos do
   ramo léxico são recalculadas na construção, a partir do corpus.
6. **Consulta.** `buscar(consulta, data_referencia=..., subgrupos={"B1"})` filtra, ordena e devolve
   `ResultadoBusca` com `score`, `score_vetorial` e `score_lexico`.
7. **Síntese.** `responder()` monta o texto só com trechos literais dos chunks recuperados.

Para ver tudo funcionando: `.venv/bin/python scripts/demonstrar_rag.py`.

## Estratégia de chunking

O chunk é o **dispositivo**, não uma janela de caracteres. Uma janela de 400 caracteres cortaria um
inciso pela metade ou misturaria o caput de um artigo com o parágrafo de outro, e a citação deixaria
de apontar para um lugar exato da norma.

- **Valor probatório.** Um achado nível B precisa citar ato, dispositivo e vigência. Com um chunk por
  artigo, parágrafo ou inciso, a citação do resultado é exatamente a do trecho que o sustenta.
- **Incisos e alíneas ficam com o caput ou o parágrafo**, porque sozinhos perdem o sentido (“I - 3 dias
  úteis” só faz sentido sob “antecedência de pelo menos”).
- **Vigência por dispositivo.** Cada chunk filtra pela vigência da própria citação.
- **Literalidade.** Os chunks, juntos, reproduzem o texto do dispositivo sem alteração (há teste).

## Estratégia de embeddings

| Aspecto | `EmbedderHash` (padrão do CI) | Modelo multilíngue pt-BR (extensão) |
|---|---|---|
| Dimensão | 384, fixa | 384 a 1024, conforme o modelo |
| Como funciona | hashing de unigramas, bigramas e trigramas de caracteres, com blake2b | rede neural pré-treinada |
| Semântica | só sobreposição lexical e morfológica | captura sinônimos e paráfrases |
| Rede e custo | nenhum; roda offline | download do modelo ou chamada de API |
| Latência | microssegundos por texto | dezenas de ms em CPU, mais com API |
| Determinismo | total | depende de versão do modelo |

O padrão é o hashing porque o CI não pode depender de rede, e porque o resultado precisa ser
reprodutível. O custo é recall menor em perguntas em linguagem de usuário. Um modelo pt-BR entra
implementando o protocolo `Embedder` (`dim` e `embed(textos)`), sem mudar o resto do pacote. **Não há
modelo semântico externo adotado como padrão**. A comparação controlada (com teste pareado via
bootstrap e McNemar e medição de RAM) entre o hashing (`EmbedderHash`), o `bge-m3` (`EmbedderOllama`,
licença MIT, 1024 dimensões, ~1,10 GB em disco e ~1,38 GB de RAM no servidor Ollama) e o segundo
extrator conceitual pt-BR (`EmbedderSemanticoPtBr`, 384 dimensões, offline) está em
`avaliacao/resultados/s2s3-embedders.json` e resumida em
[fechamento dos débitos S2/S3](../avaliacao/fechamento-debitos-s2-s3.md): as diferenças de ranking
não têm significância estatística a 5%, o custo de latência do `bge-m3` é cerca de 140 vezes maior e
o hashing segue como padrão.

Os vetores são L2-normalizados, então o cosseno é o produto interno. Como os pesos do hashing não são
negativos, o cosseno fica em [0, 1].

## Busca híbrida

```
score = α · score_vetorial + (1 − α) · score_léxico        (α padrão = 0,5)
```

- `score_vetorial`: cosseno entre consulta e chunk.
- `score_léxico`: cobertura dos termos da consulta ponderada por IDF, em [0, 1]. Um termo que não
  existe no corpus pesa contra, e por isso uma pergunta fora do assunto tem score baixo.
- **Filtros estritos antes do ranking**: `vigente_em(data_referencia)` e interseção com o subgrupo
  (`B1`). Chunk sem subgrupo declarado não passa.
- `filtrar_vigencia=False` reproduz o baseline B2 da avaliação (RAG sem filtro de vigência).

## Resposta fundamentada e abstenção

`responder()` aceita apenas resultados com `score ≥ 0,30` (`LIMIAR_PADRAO`, em `fa_rag/sintese.py`), transcreve
o trecho literal e anexa as citações. Abaixo do limiar a resposta é uma abstenção fixa. O texto nunca
usa “ilegal” e nunca calcula valor de ressarcimento.

## Limitações conhecidas

- O corpus tem apenas dispositivos conferidos, em três unidades que não se confundem: **5 atos
  oficiais** (REN ANEEL nº 1.000/2021, REH nº 3.614/2026, REN nº 956/2021 com o PRODIST Módulo 8, CDC
  e Lei Distrital nº 7.888/2026), **39 dispositivos** e **78 chunks**. Na S2 eram 3 atos, 28
  dispositivos e 62 chunks. O manifesto `dados/normas/manifesto_atos.json` inventaria 25 atos, dos
  quais 17 ainda `a_confirmar`; eles ficam fora do índice. O teste do repositório exige 20
  **dispositivos** auditáveis (atendido com 39). Se o critério acadêmico de "20 documentos-fonte"
  contar atos oficiais distintos, 5 atos **não o atendem**; a unidade do critério precisa ser
  confirmada com a coordenação antes de declarar o requisito cumprido.
- A data `vigencia_inicio` é a da entrada em vigor do ato. Dispositivos alterados depois têm a nota
  correspondente em `observacoes`.
- O limiar 0,30 foi escolhido depois de observar o split de teste e o fora da amostra; as métricas de
  teste dele são descritivas, não independentes (ver o fechamento dos débitos S2/S3). O α = 0,5 segue o
  valor histórico e não foi recalibrado.
