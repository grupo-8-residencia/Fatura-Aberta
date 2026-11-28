# Relatório S5: processamento multimodal integrado

Estado do código: branch `feat/179-endurecer-extrair`, a partir de `dev` (`e1f0363`), com mudanças
ainda não commitadas. Este relatório separa o que foi **verificado** (testes executados nesta
rodada, com resultado) do que é **suposição** ou **pendência**.

!!! warning "Gate da S5: medido em fotos sintéticas, decisão pendente"
    Os seis campos-chave passaram em 40 fotos sintéticas com os dois modelos
    ([acurácia da foto](acuracia-fotos.md)). As fotos reais não foram medidas, e a decisão do time
    segue pendente (ver [Sprint S5](../sprints/s5.md)).

## 1. Modalidades suportadas

| Modalidade | Entrada | Caminho de ponta a ponta | Confirmação humana | Validação e limites | Modelo |
|---|---|---|---|---|---|
| **Texto** | pergunta em texto (3 a 500 caracteres) | `POST /perguntar` → agentes → cartão | não se aplica (não há campo extraído) | tamanho da pergunta (Pydantic); entrada com instrução de controle é recusada antes dos agentes | agentes; LLM padrão é determinístico e sem rede (`FA_LLM_PROVEDOR=falso`) |
| **PDF digital** | arquivo `.pdf` com camada de texto | tela → `POST /extrair` → campos → confirmação → `POST /analisar` e `/perguntar` | sim: a análise só roda depois da confirmação | assinatura `%PDF-`, 5 MB, 5 páginas, senha recusada, sem texto recusado com orientação, base64 limitado (`apps/api/src/fa_api/main.py`) | parser determinístico (`packages/extracao/src/fa_extracao/parser.py`) |
| **Foto** (JPG, PNG, WEBP) | foto da fatura, até 10 MB | tela → `POST /extrair-foto` → campos → confirmação → `/analisar` ou `/perguntar` | sim, na tela | assinatura do formato (HEIC recusado); campos obrigatórios faltando viram `pendentes`; Ollama fora do ar vira 503 | VLM local via Ollama, `qwen2.5vl:7b` por padrão (**provisório**, `packages/extracao/src/fa_extracao/vlm.py:33`) |
| **Dados digitados** | formulário | `POST /analisar` | sim | validação de formato na tela e no contrato | não se aplica |

Não há áudio nem vídeo. Não há OCR: PDF sem camada de texto e foto sem leitura viram erro com
orientação para digitar os dados.

Limites em produção (padrões; variáveis em `.env.example`):

| Limite | Valor padrão | Variável |
|---|---|---|
| Tamanho do PDF | 5 MB | `FA_PDF_MAX_BYTES` |
| Páginas do PDF | 5 | `FA_PDF_MAX_PAGINAS` |
| Tempo de leitura de PDF | 30 s (504 ao estourar) | `FA_EXTRACAO_TIMEOUT_S` |
| Tamanho da foto | 10 MiB | fixo (`vlm.py`) |
| Tempo de leitura de foto | 300 s (504 ao estourar) | `FA_FOTO_TIMEOUT_S` |
| Leitura de foto simultânea | 1 | `FA_FOTO_CONCORRENCIA` |
| Tempo dos agentes | 15 s | `FA_AGENTES_TIMEOUT_S` |
| Análises dos agentes simultâneas | 2 | `FA_AGENTES_CONCORRENCIA` |

## 2. Limitações conhecidas

- **Foto medida só em fotos sintéticas.** Os seis campos-chave passaram em 40 fotos sintéticas com
  `qwen2.5vl:3b` e `7b` ([acurácia da foto](acuracia-fotos.md)). Fotos reais não foram medidas. Os
  testes unitários de foto usam um extrator falso (`apps/api/tests/test_extrair_foto.py`).
- **Hardware.** A GPU de referência tem 6 GB de VRAM. O modelo de 7B pode não caber e ficar lento;
  o timeout de 300 s pode estourar.
- **Escopo do layout.** Só a Neoenergia Brasília, grupo B1, com o layout observado. A distribuidora
  é normalizada para um vocabulário fechado; outra distribuidora é recusada.
- **Acerto da extração de PDF nunca medido contra gabarito real.** Há 1 PDF real com texto usado
  para mapear o layout (`docs/frentes/f4.md`). Os testes usam PDFs sintéticos.
- **Nível B não é emitido.** O motor tem `analisar_nivel_a` e `analisar_nivel_b`
  (`packages/motor/src/fa_motor/nivel_b.py`), mas a API só chama o nível A. Os agentes emitem nível C.
  O filtro "Nível B" da tela foi rotulado como não emitido nesta versão. Issue #178 (S6).
- **Bandeira e alíquota de ICMS** entram na conferência só quando a fatura informa. Antes, a tela
  as descartava; agora trafegam em `DadosConfirmados` e em `montarFatura`.
- **Sem rate limit.** A API não limita requisições por cliente.
- **Limite de corpo não aplicado antes da leitura.** O FastAPI lê o JSON inteiro antes de validar o
  tamanho do base64. O limite de 5 MB/10 MB é aplicado depois da decodificação.
- **Sem fallback de LLM na demonstração.** A demo roda com o cliente falso (determinístico). Os
  agentes não exercitam um LLM real nesta rodada.
- **Injeção por padrões.** A detecção é uma lista de padrões sobre texto normalizado. Paráfrases
  fora da lista passam: a paráfrase "Favor desconsiderar tudo..." não era detectada antes desta
  rodada e agora é, mas a lista continua finita (typos como "ignroe" não são cobertos). A defesa
  principal é tratar todo texto extraído como dado.
- **RF-15 contextual parcial.** Um termo vedado é aceito só quando o trecho nega a função da
  ferramenta ("a ferramenta não calcula restituição"); não há nível "exige revisão" nem a
  classificação em cinco categorias de resultado. Essas duas decisões dependem da F1 e de mudança
  em `packages/contratos` (exige duas aprovações).
- **Registro auditável (regra aplicada, data de consulta, limitações por achado) não implementado.**
- **Testes do web.** O web não tem suíte de testes; só lint, typecheck e build.

## 3. Casos de falha e mitigação

| Falha | Como aparece | Mitigação implementada | Teste |
|---|---|---|---|
| PDF corrompido ou com filtro inválido | `motivo: pdf_invalido` (antes: HTTP 500) | `packages/extracao/src/fa_extracao/pdf.py` converte `NotImplementedError` e erros de leitura em `ErroExtracao` | `apps/api/tests/test_extrair_endurecido.py` (inclui varredura de 60 mutações sem 500) |
| 422 ecoando o PDF em base64 | corpo com o arquivo | handler de `RequestValidationError` remove o valor recebido | `test_422_nao_ecoa_o_valor_recebido` |
| Base64 acima do limite | 422 | `max_length` derivado de 5 MB | `test_base64_acima_do_limite_...` |
| Leitura de PDF lenta | 504 com mensagem | `_com_vaga` com `FA_EXTRACAO_TIMEOUT_S` | `test_leitura_que_estoura_o_tempo_devolve_504` |
| Leitor de fotos (Ollama) fora do ar ou sem modelo | 503 com orientação para o PDF ou digitação | `VlmIndisponivel` em `vlm.py` | `test_leitor_indisponivel_vira_503_...` |
| Foto sem campos obrigatórios | `motivo: campos_pendentes` com lista `pendentes` | `campos_pendentes` antes de montar `Fatura` | `test_campo_obrigatorio_ausente_...` |
| Formato de foto não suportado (HEIC, GIF) | `motivo: imagem_invalida`; o modelo não é chamado | `formato_da_imagem` antes da leitura | `test_formato_nao_suportado_nao_chama_o_modelo` |
| Modelo de visão devolve texto que não é JSON | `motivo: foto_nao_lida`, sem repetir o texto | mensagem fixa | `test_falha_de_leitura_nao_repete_o_texto_do_modelo` |
| Dado pessoal devolvido pelo modelo | campo fora do contrato, descartado | candidata só lê os campos do contrato | `test_dado_pessoal_devolvido_pelo_modelo_...` |
| Instrução em PDF, foto ou pergunta | PDF recusado; pergunta com `motivo: instrucao_controle`; campo removido | `contem_instrucao_controle` e `higienizar_texto_extraido` (detector único, com normalização de homógrafos e caracteres invisíveis) | `packages/extracao/tests/test_higienizacao.py`, `tests/seguranca/` |
| Instrução em campo textual de `/analisar` | agentes não rodam; nível A preservado; aviso | guarda `_fatura_hostil` em `/analisar` | `apps/api/tests/test_analisar_guarda.py` |
| Agentes lentos ou fora do ar | aviso; achados A preservados | `_executar_agentes` e `_com_vaga` | `apps/api/tests/test_api.py` |
| Termo vedado na saída (ex.: "ilegal") | trecho substituído | `verificar_linguagem` em todos os campos de saída | `packages/agentes/tests/test_linguagem_rf15.py` |
| Frase do motor lida como conclusão pelo auditor | falso alarme | frases A1/A2/A3 usam "difere", e `_DIZ_QUE_DIVERGE` reconhece "difere" | `test_textos_de_divergencia_do_motor_...` |

## 4. Métricas e experimentos

| Item | Situação |
|---|---|
| Acurácia por campo em 40 fotos (#41) | **Medida em fotos sintéticas.** Os seis campos-chave em 100% com `qwen2.5vl:3b` e `7b`; itens de 58% a 64% de linhas corretas. Detalhes em [acuracia-fotos.md](acuracia-fotos.md). Fotos reais não medidas. |
| Latência do VLM por foto (GPU de 6 GB) | 3B: p50 14,8 s; 7B: p50 50,8 s. Latência de `/extrair-foto` ponta a ponta: não medida. |
| Acerto da extração de PDF em faturas reais | **Não medido.** Só sintéticos. |
| Injeção por texto e PDF (#42, 10 casos) | Taxa 0/10 com o pipeline sem LLM. Pelo intervalo de Wilson de 95%, 0/10 é compatível com taxa de até cerca de 28%. Ver [injecao-por-imagem.md](../seguranca/injecao-por-imagem.md). |
| Injeção por imagem (#42) | **Não medida.** Não há imagens de ataque; os três casos de imagem são transcrições em `.txt`. |
| Injeção com VLM ou LLM real | **Não medida.** |

## 5. Verificação executada nesta rodada

| Verificação | Comando | Resultado |
|---|---|---|
| Lint Python | `uv run ruff check .` | PASS |
| Formatação Python | `uv run ruff format --check .` | PASS |
| Tipos Python | `uv run mypy` | PASS (131 arquivos) |
| Testes Python (completo) | `uv run pytest` | 531 passaram, 5 falharam (ver abaixo) |
| Lint web | `npm run lint` em `apps/web` | PASS |
| Tipos web | `npm run typecheck` | PASS |
| Build web | `npm run build` | PASS (Next 16.4.6) |
| Smoke da API (fluxo PDF) | `scripts/smoke_api_container.py` contra uvicorn local | PASS (sem Docker) |
| Docker (contêiner da API e da web) | `docker compose` | NOT RUN (Docker não verificado nesta rodada) |
| Documentação | `mkdocs build --strict` | PASS com as fontes do tema desligadas num build temporário. O build com a configuração do repositório falha aqui por 61 avisos de ambiente (link simbólico no Windows e download de fontes do Google sem rede). |
| Leitura de foto com VLM real (40 fotos sintéticas) | `scripts/extrair_fotos.py` com `qwen2.5vl:3b` e `7b`; `scripts/acuracia_por_campo.py` | PASS nos seis campos-chave nos dois modelos; ver [acuracia-fotos.md](acuracia-fotos.md) |
| Testes de interface do web (navegador) | — | NOT RUN (não há suíte; a tela não foi exercitada em navegador nesta rodada) |

As 5 falhas da suíte completa, todas fora do escopo desta mudança:

- `tests/avaliacao/test_rodada_s3.py::test_trava_de_processo_morto_e_descartada`: `os.kill(pid, 0)`
  levanta `OSError` no Windows. Já falhava antes desta rodada.
- `tests/scripts/test_gerar_golden_set.py` (2 testes) e `tests/scripts/test_kit_anotacao.py` (2
  testes): o hash congelado do golden set não bate quando o checkout do Windows grava CRLF
  (`core.autocrlf=true`). Passaram no export LF do repositório. É ambiente, não código.

## 6. Pendências para fechar a S5

1. **Confirmar o gate com fotos reais.** A medição sintética já foi feita (Go nos campos-chave). Para
   sair de "em validação", o time precisa medir com as 7 fotos reais, fora do repositório, e escolher
   o modelo padrão (hoje `7b`, provisório; a recomendação técnica é `3b`).
2. **Imagens de ataque (#42).** Renderizar instruções em imagem e rodar contra o VLM real.
3. **Decisão de pivot.** Registrar Go, No-Go ou Pivot em `docs/sprints/s5.md` com base na medição.
4. **Decisões da F1** para a #169: nível "exige revisão", cinco categorias de resultado e registro
   auditável (mudança em `packages/contratos`).
5. **Nível B** na API e no cartão (#178).
6. **Demonstração ao vivo**: o cenário de divergência já está no roteiro (`00-base.pdf`, verificado em
   `/extrair` e `/perguntar`). Falta ensaiar o roteiro com foto, que depende do item 1. Ver [demo-s5.md](../operacao/demo-s5.md).
