# Demonstração da S5: texto + PDF

Roteiro para reproduzir, a partir de um clone limpo, o fluxo **PDF sintético + pergunta em texto**.
Tudo é fictício: nenhum dado pessoal e nenhuma fatura real. Contexto e limites em
[Processamento multimodal](../arquitetura/multimodal.md).

## Artefatos versionados

| Artefato | Caminho |
|---|---|
| PDF sintético (texto selecionável) | `docs/assets/demo-s5/fatura-sintetica-demo.pdf` |
| Gerador do PDF | `scripts/gerar_pdf_demo.py` |
| Pergunta da demonstração | `docs/assets/demo-s5/pergunta-demo.txt` |
| Resultado real de `/extrair` e `/perguntar` | `docs/assets/demo-s5/evidencias/resultado-*.json` |
| Telas e vídeo do fluxo | `docs/assets/demo-s5/evidencias/01…04-*.png`, `fluxo.webm` |
| Log dos testes | `docs/assets/demo-s5/evidencias/log-testes.txt` |

Pergunta: `O consumo informado confere com as leituras do medidor?`

## Pré-requisitos

- Docker com Compose v2.
- Para os testes e para regerar o PDF: [uv](https://docs.astral.sh/uv/) 0.12 (instala o Python 3.12).
- Para recapturar as telas (opcional): Node 20.9+.

## Passo a passo

```bash
git clone https://github.com/grupo-8-residencia/Fatura-Aberta.git
cd Fatura-Aberta
git checkout dev   # os artefatos da S5 ficam na dev até o release na branch padrão (main)
cp .env.example .env            # sem segredos: só host e porta da API
docker compose -f infra/docker-compose.yml up --build -d
```

Sem `FA_LLM_PROVEDOR` os agentes rodam sem LLM (modo extrativo): não é preciso Ollama.

1. Abra <http://127.0.0.1:3000>.
2. Em **Enviar o PDF da fatura**, escolha `docs/assets/demo-s5/fatura-sintetica-demo.pdf`.
3. Confira os campos preenchidos (mês 06/2026, consumo 120 kWh, total 130,40).
4. Em **Sua pergunta**, cole o texto de `pergunta-demo.txt`.
5. Clique em **Confirmar e conferir**.

**Resultado esperado:** na aba Conferência aparece "Resposta à sua pergunta" repetindo a pergunta,
citando mês, consumo e total do PDF, com "Consumo medido: confere" e três citações da REN ANEEL
1.000/2021 com vigência; abaixo, os cartões de decisão de nível A.

### Pela linha de comando (sem a tela)

Primeiro extraia os campos em `/extrair` (a análise não roda aqui), confira os valores extraídos e só depois envie a `fatura` confirmada para `/perguntar` (enviar `pdf_base64` direto para `/perguntar` é rejeitado com HTTP 422):

```bash
PDF=$(base64 < docs/assets/demo-s5/fatura-sintetica-demo.pdf | tr -d '\n')
curl -s http://127.0.0.1:8000/extrair -H 'content-type: application/json' \
  -d "{\"pdf_base64\":\"$PDF\"}" > /tmp/extraido.json
cat /tmp/extraido.json          # etapa de conferência: ajuste .fatura se necessário antes de seguir
PERGUNTA=$(tr -d '\n' < docs/assets/demo-s5/pergunta-demo.txt)
uv run python -c '
import json, sys
fatura = json.load(open("/tmp/extraido.json", encoding="utf-8"))["fatura"]
print(json.dumps({"pergunta": sys.argv[1], "fatura": fatura}, ensure_ascii=False))
' "$PERGUNTA" | curl -s http://127.0.0.1:8000/perguntar -H 'content-type: application/json' -d @-
```

### Testes e PDF

```bash
uv sync --all-packages --locked
uv run pytest tests/e2e/test_fluxo_multimodal.py tests/scripts/test_pdf_demo.py -v
uv run python scripts/gerar_pdf_demo.py   # regera o PDF (idêntico ao versionado)
```

### Telas e vídeo (opcional)

```bash
npm install --prefix /tmp/fa-pw playwright-core
npx --prefix /tmp/fa-pw playwright-core install chromium
NODE_PATH=/tmp/fa-pw/node_modules node scripts/demo/capturar_telas.cjs
```

Se o Chromium já estiver instalado, aponte `FA_CHROMIUM` para o executável.

### Encerrar

```bash
docker compose -f infra/docker-compose.yml down
```

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Porta 3000 ou 8000 ocupada | Outro processo local | Pare o outro processo ou mude o mapeamento em `infra/docker-compose.yml` |
| A tela diz que não falou com a API | API ainda subindo ou fora do ar | `docker compose -f infra/docker-compose.yml ps` e aguarde `healthy` |
| Erro de CORS no navegador | Acesso por outro host que não `localhost:3000` | Use `http://127.0.0.1:3000` ou `localhost:3000`, ou configure `FA_CORS_ORIGINS` |
| "Não foi possível responder" / `agentes_indisponiveis` | Tempo dos agentes excedido | Tente de novo; os achados do motor continuam na resposta |
| "PDF sem camada de texto" | Arquivo escaneado | Use o PDF sintético da demonstração ou digite os dados |
