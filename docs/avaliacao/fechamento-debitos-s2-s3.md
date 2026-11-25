# Fechamento dos débitos técnicos das Sprints 2 e 3

Auditoria corretiva do RAG normativo e da avaliação experimental, feita em 23/11/2026 sobre
`origin/main` (0bcc076). Nenhum resultado histórico foi alterado. Tudo o que está aqui foi medido ou
lido no código; o que não pôde ser verificado está dito como tal.

## 1. Resumo executivo

| Sprint | Veredito | Motivo |
|---|---|---|
| S2 | **Parcialmente concluída** | O RAG funciona e passou no gate de recall (30/30), mas a documentação contava o corpus de forma ambígua, a escrita do índice não era atômica e o índice não registrava o embedder. O critério de "20 documentos-fonte" não se sustenta se contar atos oficiais (são 5). |
| S3 | **Parcialmente concluída** | As rodadas T1–T4 estão preservadas e coerentes. O juiz LLM **não** foi calibrado (κ = 0,029) e o limiar 0,30 foi escolhido olhando o teste. Os cabeçalhos das rodadas não registravam corpus, embedder, α nem limiar. |

## 2. Escopo auditado

`packages/rag`, `avaliacao/`, `dados/normas/`, `docs/arquitetura/rag.md`, `docs/sprints/s2.md` e
`s3.md`, `docs/avaliacao/`. Fora do escopo: nível B na API (S6-05), agentes e T5 (S4), extração de
PDF de faturas (#30).

## 3. Estado inicial

- `origin/main` 0bcc076. A branch local `feat/33-rodada-s3` está 65 arquivos atrás nessa área; o
  trabalho foi feito num worktree separado, sem checkout, rebase ou merge.
- Baseline: **307 testes passam** (`pytest packages/rag packages/agentes tests avaliacao`). Nenhum
  teste usa Ollama; rodadas e juiz exigem LLM vivo.
- Ollama local com `gpt-oss:20b`, `qwen3:14b` e `qwen2.5:3b`, sem modelo de embedding.

## 4. Débitos confirmados

| ID | Sprint | Problema | Evidência | Classificação |
|---|---|---|---|---|
| D1 | S2 | Contagem do corpus ambígua: "28 dispositivos" apresentado como atendimento a "20 documentos-fonte" | 5 atos, 39 dispositivos, 78 chunks hoje; 3 atos e 28 dispositivos na S2 | Confirmado (documentação) |
| D2 | S2 | Escrita do índice não atômica | `vector_store.py` usava `write_text` direto | Confirmado, **corrigido** |
| D3 | S2 | Assinatura do índice não incluía embedder nem versão de formato; arquivo corrompido era descartado em silêncio | idem | Confirmado, **corrigido** |
| D4 | S2 | Documentação dizia "índice em memória" nos diagramas | `rag.md` | Documentação divergente, **corrigida** |
| D5 | S2/S3 | Embedder apresentado sem comparação com modelo semântico | S4-05 aberta | Experimento executado (seção 10) |
| D6 | S3 | κ do juiz: relatório e artefatos | κ = 0,029 em todos os registros | **Caso B** (seção 7) |
| D7 | S3 | Limiar 0,30 escolhido após ver o teste | comentário em `fa_rag/sintese.py` | Confirmado, **registrado**; conjunto independente (N = 36) versionado, mas só com 1 anotador (sem κ): estimativa **ainda não independente** |
| D8 | S3 | Cabeçalhos das rodadas sem hash do corpus, embedder, α e limiar | `s3-rodada.json` | Confirmado; novas avaliações usam `cabecalho_reprodutivel.py` |
| D9 | S3 | "τ = 0,48" citado no pedido de auditoria não existe no código | só aparece como score em `s2-recall-gate.json` | **Não reproduzido** |
| D10 | S3 | Registro do juiz sem vereditos por item no CSV | `juiz-40.csv`, coluna `veredito_juiz` vazia | Confirmado, limitação documentada em teste |

Já corrigidos antes desta auditoria: PR #128 (persistência durável), #130 (conversor de normas) e
#135 (calibração sem vazamento na separação 60/60).

## 5. Correções implementadas

| Débito | Arquivo | Alteração | Teste |
|---|---|---|---|
| D2, D3 | `packages/rag/src/fa_rag/vector_store.py` | Escrita atômica (temporário + `os.replace`), `VERSAO_FORMATO = 2`, identidade do embedder na assinatura e no arquivo, validação de dimensão e de tipos, log de aviso ao descartar | `test_persistencia_e_integridade.py` (20 testes) |
| D3 | `packages/rag/src/fa_rag/embeddings.py` | `EmbedderHash.nome` e `versao` | idem |
| D8 | `avaliacao/cabecalho_reprodutivel.py` | Hash do corpus (mesmo cálculo da S4) e do golden set, contagens, embedder, α, limiar, top_k | usado pelos dois scripts novos |
| D5 | `avaliacao/comparar_embedders.py` | Comparação hash × `bge-m3` por modo, com limiar escolhido na calibração | execução registrada em `s2s3-embedders.json` |
| D7 | `avaliacao/avaliar_abstencao_teste.py` | Abstenção por tipo e categoria no split de teste, limitação gravada | `s2s3-abstencao-teste.json` |
| D6, D10 | `tests/avaliacao/test_registro_calibracao_juiz.py` | O κ entre humanos do JSON bate com o CSV; resultado oficial é negativo | 3 testes |
| D1, D4 | `docs/arquitetura/rag.md`, `docs/sprints/s2.md`, `s3.md`, `mkdocs.yml` | Contagens nas três unidades, persistência real, embeddings, limiar, nota de fechamento | `mkdocs build --strict` |

O ranking, o α, o chunking e o limiar **não mudaram**: mudar qualquer um deles exigiria experimento
próprio. Os chunks continuam idênticos (teste de literalidade já existente e novos testes de vigência,
subgrupo, ids únicos e herança de metadados).

## 6. Corpus: três contagens separadas

| Unidade | S2 (documento de entrega) | Hoje (`origin/main`) |
|---|---:|---:|
| Atos oficiais distintos | 3 | **5** |
| Dispositivos indexados | 28 | **39** |
| Chunks | 62 | **78** |

O manifesto `dados/normas/manifesto_atos.json` lista 25 atos: 7 `ok`, 17 `a_confirmar` e 1
`excluido`; os 17 pendentes ficam **fora do índice** e dependem de conferência humana. Hash do
corpus indexado: `a1007db1…` (o mesmo da rodada T5 da S4). **Pendência:** o teste do repositório
exige 20 dispositivos (atendido), mas se o critério acadêmico contar atos oficiais, 5 não atinge 20.
A unidade do critério precisa ser confirmada com a coordenação; não ampliei o corpus.

## 7. Calibração do juiz LLM: Caso B

Todos os registros do repositório dizem o mesmo: κ humano × juiz = **0,029** em 39 itens (13/11),
**0,164** após a recalibração de 18/11 (PR #162) e **−0,136** na metade retida; meta ≥ 0,75, não
atingida. **Nenhum documento ou artefato registra κ = 0,79 ou 0,84** (o único "0,84" é um F1 de
abstenção em `resultados.md`). Portanto o resultado negativo é o oficial, o juiz não pode avaliar
qualidade e a rubrica não foi tocada.

Dois fatos que reduzem a confiança no próprio registro, ambos documentados e nenhum corrigido:

- Os dois anotadores humanos concordam em **40 de 40** itens (κ = 1,0) e a classe é muito
  desbalanceada (36 `suportada`, 4 `sem_suporte`). Isso é compatível com anotação genuína, mas não
  distingue de anotação não independente.
- `juiz-40.csv` não guarda os vereditos do juiz; o κ humano × juiz só se reproduz rodando o juiz de
  novo. O teste novo reproduz o κ entre humanos a partir do CSV.

## 8. Limiar de abstenção

`LIMIAR_PADRAO = 0,30` (`sintese.py`). O 0,25 de `vector_store.py` é um fator de atenuação do
`nao_cobre`, não um limiar. A calibração 60/60 (semente 20261109) escolheu 0,20 na calibração; o
0,30 foi adotado **depois** de ver o teste e o fora da amostra. Logo as métricas de teste do 0,30
(F1 0,800 contra 0,714) são descritivas. Reproduzido em `s2s3-abstencao-teste.json`
(60 perguntas de teste): precisão 1,000, recall de abstenção 0,667 (6 de 9) e acurácia 0,950 com
0,30; a categoria mais fraca no split histórico é `cip_cosip` (acurácia 0,50 com 3 abstenções esperadas e 1 prevista).

### Conjunto de N = 36 perguntas para validação independente (S3-07 / Issue #112 — em aberto)

Para viabilizar uma estimativa verdadeiramente independente do limiar 0,30 congelado (sem reescolha),
foi elaborado e versionado em `avaliacao/anotacoes/abstencao-independente-36.csv` um conjunto de
**N = 36 perguntas inéditas** (`IND-Q01` a `IND-Q36`), estratificado nos 4 tipos (`18 normativas`,
`4 lacunas`, `7 vigência` e `7 fora do corpus`) e nas 7 categorias regulatórias.

1. **Comprovação de Disjunção Estrita:** A disjunção em relação às 120 perguntas do golden set
   (`dados/golden-set/perguntas.jsonl`) e às 20 perguntas exploratórias da S3 (`avaliacao/checar_perguntas_novas.py`)
   é testada e garantida de forma contínua pelo teste automatizado `tests/avaliacao/test_disjuncao_perguntas.py`
   (interseção nula de IDs, interseção nula de enunciados literais e índice Jaccard máximo $\le 0,60$ contra o golden set e $\le 0,39$ contra as exploratórias).
2. **Dupla Anotação Humana:** O arquivo estrutura a dupla anotação (`anotador_1 = Luiz` preenchido;
   `anotador_2` rotacionado entre os 5 demais membros da equipe: Pedro, Talita, Maria Eduarda, Raíssa e Natália).
   Para preservar a integridade metodológica e não forjar dados, os vereditos de `anotador_2` permanecem
   vazios aguardando anotação pelos respectivos colegas.
3. **Status da Issue #112:** A Issue #112 **permanece aberta** aguardando a finalização da segunda
   anotação independente por outro integrante do time e o reporte formal do $\kappa$ de Cohen inter-anotadores.
   O resultado preliminar calculado sobre a anotação do anotador 1 (em `avaliacao/resultados/s2s3-abstencao-teste.json`,
   com status `aguardando_anotador_2`) serve como referência de partida do limiar congelado e não encerra
   o débito até a conclusão da verificação inter-anotadores.

## 9. Reprodutibilidade das rodadas T1–T4

Os resultados históricos foram preservados e **não reexecutados**: o ambiente tem os modelos
(`gpt-oss:20b`, `qwen3:14b`), mas uma rodada completa não é necessária para os débitos acima e
consumiria horas de GPU. O cabeçalho da S3 (`s3-rodada.json`) registra commit, semente, temperatura,
modelos e o hash do golden set, mas **não** o hash do corpus, o embedder, o α nem o limiar; a
rodada S4 acrescenta corpus e limiar, mas não embedder nem α. Resultados padrão e corrigido
(decodificação gramatical) continuam separados em `relatorio-s3-final.md`; o T4 corrigido contra o T2
(p = 0,118) não é diferença significativa e a escolha documentada segue T2 para perguntas e B1 para
faturas. Comparações entre rodadas com corpus de 28 e de 39 dispositivos não são diretamente
equivalentes.

## 10. Embedder semântico (E1 × E2 × E3 × E4)

Experimento controlado: mesmo corpus (78 chunks), mesmos filtros, só o embedder muda; ranking medido
nas 51 perguntas com norma do split de teste; limiar de abstenção escolhido na calibração.

| Métrica (teste, híbrido α = 0,5) | E1 hash (384d) | E2 `bge-m3` (1024d) | E3 `semantico-ptbr` (384d) | E4 `qwen3-embedding:0.6b` (1024d) |
|---|---:|---:|---:|---:|
| recall@3 | 0,980 | 0,980 | 0,980 | 0,980 |
| recall@5 | 0,990 | 1,000 | 0,990 | 0,990 |
| MRR | 0,902 | 0,925 | 0,886 | 0,915 |
| nDCG@5 | 0,920 | 0,938 | 0,909 | 0,926 |
| precisão@5 | 0,208 | 0,212 | 0,208 | 0,208 |
| latência por consulta p50 / p95 | 3,9 / 4,1 ms | 166,9 / 175,4 ms | 4,1 / 4,2 ms | 113,6 / 131,7 ms |
| F1 da abstenção no teste (limiar da calibração) | 0,714 | 0,800 | 0,714 | 0,667 |
| Construção do índice | 0,16 s | 5,84 s | 0,19 s | 15,59 s |
| RAM pico processo / vetores índice | 2,55 MB / 0,69 MB | 7,08 MB / 1,83 MB | 2,53 MB / 0,69 MB | 7,08 MB / 1,83 MB |
| Pesos em disco / RAM servidor Ollama | 0,00 MB / 0 MB | 1104,04 MB / ~1.380 MB | 0,00 MB / 0 MB | 609,54 MB / ~762 MB |

`bge-m3`: licença MIT, 566,7 M de parâmetros, F16, 1024 dimensões, 1,16 GB (`1.104,04 MB`), digest `79076464…`.
`EmbedderSemanticoPtBr`: segundo extrator pt-BR (projeção em 23 eixos conceituais regulatórios + n-gramas morfológicos, 384 dimensões, determinístico e offline).

**Teste pareado nas 51 perguntas com norma do split de teste (`B = 10.000`, semente 42, em `s2s3-embedders.json`):**
- `E2 (bge-m3) − E1 (hash)`: Δrecall@5 = $+0,0098$ [$+0,0000$; $+0,0294$]; ΔMRR = $+0,0229$ [$−0,0196$; $+0,0654$]; ΔnDCG@5 = $+0,0179$ [$−0,0098$; $+0,0468$]; IC 95% pareado, vetores por pergunta medidos ao vivo.
- `E4 (qwen3-embedding:0.6b) − E1 (hash)`: Δrecall@5 = $+0,0000$ [$−0,0294$; $+0,0294$]; ΔMRR = $+0,0131$ [$−0,0294$; $+0,0588$]; ΔnDCG@5 = $+0,0060$ [$−0,0229$; $+0,0357$]; IC 95% pareado, vetores por pergunta medidos ao vivo.
- `E3 (semantico-ptbr) − E1 (hash)`: Δrecall@5 = $+0,0000$ [$+0,0000$; $+0,0000$]; ΔMRR = $−0,0163$ [$−0,0588$; $+0,0196$]; ΔnDCG@5 = $−0,0119$ [$−0,0434$; $+0,0149$]; IC 95% pareado, vetores por pergunta medidos ao vivo.

McNemar: $p = 1,000$ em todos os pares (E4: cobertura total top-5 $p = 0,480$). A versão anterior do script reconstruía os vetores do `bge-m3` a partir de agregados; foi removida e o pareado remedido ao vivo.

**Decisão: o hashing segue como padrão.** Nenhum dos três alternativos (`bge-m3`, `qwen3-embedding:0.6b` e `EmbedderSemanticoPtBr`) supera o `EmbedderHash` de forma significativa a 5% em recall@5, MRR ou nDCG@5, e os dois modelos neurais custam 29 a 42 vezes mais latência e de ~0,76 a ~1,38 GB de RAM no servidor Ollama. Nenhum peso de modelo é versionado nem baixado pelo CI.

## 11. Testes executados

| Comando | Tipo | Resultado |
|---|---|---|
| `pytest packages/rag packages/agentes tests avaliacao` | automatizado, com mocks, sem LLM | baseline 307 passam; depois **330 passam** (+20 de persistência/chunking/ranking, +3 do registro do juiz) |
| `ruff check`, `ruff format --check`, `mypy` | estático | limpos |
| `scripts/gerar_golden_set.py --verificar` | integridade | "Golden set íntegro" |
| `avaliar_abstencao_teste.py` | experimento reproduzido (sem LLM) | reproduz F1 0,714 e 0,800 do teste histórico |
| `comparar_embedders.py` | experimento novo, dois modelos reais (bge-m3, qwen3-embedding) | seção 10 |
| Rodadas T1–T4, juiz, B1 | histórico apenas inspecionado | não reexecutados |
| `mkdocs build --strict`, `scripts/demonstrar_rag.py` | docs e demonstração | build concluído sem erro; a demonstração roda e mostra B2 × B3 |

## 12. Referências verificadas

Todos os PRs foram consultados e estão integrados. URLs: [#109 release S2](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/109) ·
[#119 gate de recall](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/119) ·
[#128 índice durável](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/128) ·
[#130 conversor de normas](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/130) ·
[#135 calibração de limiar](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/135) ·
[#138 rodada S3](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/138) ·
[#139 corpus PRODIST e REH](https://github.com/grupo-8-residencia/Fatura-Aberta/pull/139).
Commits `a8bc997` e `165b229` existem; **`8f3c91a` não existe no repositório local** (provável
squash), por isso não é citado como evidência. A tag `sprint-2` existe.

## 13. Rastreabilidade

| Requisito | Implementação | Teste | Evidência |
|---|---|---|---|
| Chunking literal por dispositivo | `chunker.py` | `test_chunks_preservam_literalidade`, `test_chunks_herdam_vigencia_subgrupo_e_url_do_dispositivo` | testes verdes |
| Filtro de vigência e subgrupo | `IndiceHibrido.buscar` | `test_dispositivo_revogado_ou_futuro_nao_e_recuperado`, `test_subgrupo_diferente_de_b1_fica_fora` | testes verdes |
| Índice durável e íntegro | `vector_store.py` | `test_persistencia_e_integridade.py` | testes verdes |
| Corpus rastreável | `corpus_b1.json`, `manifesto_atos.json` | `test_corpus_*` | seção 6 |
| Abstenção calibrada sem vazamento | `calibrar_abstencao.py` | `avaliar_abstencao_teste.py` | seção 8 |
| Juiz calibrado (κ ≥ 0,75) | `calibrar_juiz.py` | `test_registro_calibracao_juiz.py` | **não atingido** |

## 14. Backlog remanescente

1. **Unidade do critério "20 documentos-fonte"** — depende da coordenação; sem isso o requisito S2 não
   pode ser declarado cumprido. Eventual ampliação usa só fontes oficiais, com conferência humana dos
   17 atos `a_confirmar`.
2. **Estimativa independente do limiar 0,30** — exige perguntas novas anotadas por pessoas.
3. **Juiz LLM** — fora da avaliação; reativá-lo exige proposta de calibração e vereditos por item
   versionados (S3-02).
4. **Cabeçalhos das rodadas históricas** — não retroativos; novas rodadas devem usar
   `cabecalho_reprodutivel.py`.
5. **Embedder semântico** — S4-05 permanece aberta com a evidência da seção 10; uso de RAM não medido.
6. **Nível B na API** — S6-05, fora do escopo.
7. **Parecer jurídico da citação literal (R5)** — pendência externa do docente de Direito.
