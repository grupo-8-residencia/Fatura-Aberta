# ADR-003 — Modelo de linguagem do produto (triagem e protocolo de escolha)

| | |
|---|---|
| **Status** | proposta: triagem documental feita; **falta a medição local** (nenhum modelo foi recomendado ainda) |
| **Data** | 2026-11-11 |
| **Decisores** | Pedro (Tech Lead, F5), com revisão da Raissa |
| **Relação com a ADR-002** | a [ADR-002](adr-002-llm-local.md) fixa os modelos do **experimento** da S3 e não muda. Esta ADR trata do modelo do **produto**. |

## Contexto

O experimento da S3 usa `gpt-oss:20b` (gerador) e `qwen3:14b` (juiz) para que a comparação entre os
quatro testes seja reproduzível. Isso não diz qual modelo o produto deve usar: o produto tem outros
critérios (custo por consulta, latência, memória, licença de uso comercial, português do Brasil, saída
estruturada com citação e abstenção). Esta ADR registra a triagem dos candidatos e o protocolo da
escolha. **Ela não escolhe um vencedor**; a recomendação entra neste mesmo arquivo depois da medição.

Restrições: nenhum dado do projeto vai para provedor externo nesta etapa, nenhuma chamada paga, e a
máquina de medição é um Mac com 24 GB de memória unificada. O macOS reserva parte dessa memória, então
o limite prático para pesos mais cache de contexto fica perto de 16 a 18 GB. Tamanho de arquivo não é
memória usada: o cache de contexto (6.144 tokens na S3) soma-se aos pesos.

## Candidatos

Tags e tamanhos conferidos na biblioteca do Ollama em 11/11/2026. Licença, contexto e saída
estruturada vêm dos cartões dos modelos; **o que não foi confirmado está marcado**.

| Candidato (tag) | Pesos | Contexto | Licença | Cabe em ~16 GB? |
|---|---|---|---|---|
| `gpt-oss:20b` (atual) | 13 GB | 128K | Apache 2.0 | sim (já usado) |
| `qwen3:14b` (atual, juiz) | 9,3 GB | 128K | Apache 2.0 | sim (já usado) |
| `gemma4:12b` | 7,7 a 8,0 GB | 256K | Apache 2.0 (a confirmar no cartão da versão) | sim |
| `gemma4:26b` (MoE, 3,8B ativos) | 16 a 19 GB | 256K | Apache 2.0 (idem) | no limite; medir swap |
| `qwen3.5:9b` | 6,6 a 7,6 GB | 256K | Apache 2.0 | sim |
| `qwen3.5:27b` | 17 a 20 GB | 256K | Apache 2.0 | no limite; provável swap |
| `qwen3.6:35b` (MoE, 3B ativos) | 23 GB | 256K | Apache 2.0 | **não** com 24 GB |
| `qwen3.8:27b` | 18 GB | 256K | Apache 2.0 | no limite; provável swap |
| `Polygl0t/Tucano2-qwen-3.7B-Instruct` (Hugging Face, não é tag oficial do Ollama) | ~4 GB (a converter) | a verificar | **a verificar** | sim |

Referências de terceiros (placares agregados) colocam Qwen3.8 27B e Gemma 4 acima do `gpt-oss:20b` em
benchmarks gerais. Esses placares não medem português jurídico, vigência nem abstenção, e não entram na
decisão. O artigo do Tucano 2 (arXiv 2603.03543) mostra um modelo pequeno específico para português
competitivo na faixa de 3 a 4B, com desempenho menor em seguir instruções.

## Critérios (definidos antes de medir)

**Eliminatórios** (como na regra da S3):

1. 0 respostas inválidas e 0 violações do RF-15 na amostra de triagem.
2. Cabe na máquina de medição sem swap sustentado (pressão de memória "crítica" ou mais de 2 GB de swap
   durante a rodada elimina).
3. Licença permite uso comercial.
4. Sem chamada externa: o modelo roda local.

**De comparação** (fronteira de Pareto entre acerto, latência p95 e memória de pico):

acerto no B3, citações inventadas, citações fora de vigência, abstenção correta, latência p50 e p95,
tokens por segundo, tempo de carga e memória de pico. A escolha final não pode se basear só em
parâmetros, velocidade ou placar público. Se dois candidatos empatarem (diferença menor que 1 ponto
percentual de acerto), vence o de menor memória de pico.

## Protocolo da medição

1. **Quando:** só depois de a rodada da S3 terminar, para não competir por memória com ela.
2. **Instalação:** um modelo por vez (`ollama pull`), conferindo espaço livre e memória antes. Os modelos
   da S3 não são removidos; os temporários são removidos no fim da medição de cada um.
3. **Triagem (exploratória):** 30 perguntas estratificadas por categoria e 30 faturas (as mesmas ids para
   todos), com o prompt do B3, temperatura 0 e os mesmos parâmetros de contexto. A semente da amostra fica
   registrada no JSON.
4. **Confirmação:** os 2 melhores da triagem rodam no restante do golden set, **depois** da revisão
   humana (#32) e em ids que não participaram da triagem. A triagem não vale como validação do vencedor.
5. **Registro por modelo:** tag, digest, quantização, tamanho, memória de pico, swap, tempo de carga,
   contexto efetivo usado, suporte a saída estruturada, e as limitações observadas.

## Resultado

Ainda não há. Esta seção será preenchida com a tabela medida e a recomendação, e o status passará de
"proposta" para "aceita" só depois de revisão do time.

## Consequências

- A S3 segue com a ADR-002; trocar o modelo do produto não invalida o experimento.
- Se nenhum candidato passar nos critérios eliminatórios, o produto fica com o `gpt-oss:20b` e a ADR
  registra o motivo.
- Um modelo de nuvem só entra em outra ADR, com análise de LGPD e de custo, e nunca com faturas reais.
