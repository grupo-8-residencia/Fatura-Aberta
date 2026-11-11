# Golden set (Dataset Card preliminar)

Conjunto congelado das rodadas de avaliação da S3 (issue S3-01). Esta é uma versão **preliminar**: as
perguntas ainda não passaram por revisão humana.

## Conteúdo

| Arquivo | Itens | Origem |
|---|---|---|
| `dados/golden-set/perguntas.jsonl` | 120 perguntas | escritas à mão a partir dos dispositivos do [corpus](../arquitetura/rag.md) |
| `dados/golden-set/faturas_sinteticas.jsonl` | 200 faturas | geradas por `scripts/gerar_golden_set.py` com semente fixa |
| `dados/golden-set/distribuicao_anotadores.md` | 180 itens | 30 por pessoa, sorteio com semente fixa |
| `dados/golden-set/checksums.sha256` | 3 hashes | SHA-256 do conjunto congelado |

Para conferir a integridade: `.venv/bin/python scripts/gerar_golden_set.py --verificar`.

## Perguntas

| Categoria | Perguntas |
|---|---|
| Tarifas B1 | 18 |
| Bandeiras | 11 |
| Medição estimada | 20 |
| Devolução em dobro | 26 |
| CIP/COSIP | 8 |
| Encargos e multas | 18 |
| Corte e notificação | 19 |

Cada pergunta traz `data_referencia`, `citacao_canonica` (ids do corpus), `resposta_esperada`,
`abstencao_esperada` e `tipo`:

- `normativa` (97): o corpus cobre o tema.
- `vigencia` (12): a data é anterior à entrada em vigor da REN ANEEL 1.000/2021 (03/01/2022), então a
  resposta esperada é a abstenção. Servem para separar B2 de B3.
- `fora_do_corpus` (5): perguntas sobre CIP/COSIP que a Lei Distrital 7.888/2026 não responde (valor,
  alíquota, multa por atraso da CIP). A resposta esperada é a abstenção.
- `lacuna` (6): o corpus cobre só parte do tema (parágrafos não transcritos). A resposta esperada
  marca o `TODO:` e exige que o sistema não afirme além do texto.

## Faturas sintéticas

Cada fatura tem 3 linhas (energia, adicional de bandeira e uma contribuição genérica), leituras,
consumo, alíquota de ICMS e total. Cerca de metade recebe uma de seis anomalias injetadas: consumo
diferente das leituras, total que não fecha, valor de energia incoerente, adicional de bandeira
incorreto, item duplicado e alíquota de ICMS incoerente. O gabarito vem da construção.

!!! warning "Parâmetros sintéticos"
    As tarifas, o adicional de bandeira e a alíquota usados na geração são **valores inventados para
    produzir aritmética coerente**. Não são as tarifas da Neoenergia Brasília. A planilha ANEEL de
    `dados/tarifas/` ainda não foi validada para bandeira.

## Anotação humana

O kit de anotação (um CSV por pessoa e a revisão das 120 perguntas) está em
`dados/golden-set/anotacoes/`. Instruções para quem anota: [Como anotar](anotacao.md). Enquanto o time
não devolver os CSV preenchidos, a revisão humana segue **pendente**.

## Limitações

- Revisão humana pendente em todos os itens. Seis pessoas anotando 30 itens cobrem 180 dos 320; o
  restante fica com o gabarito de construção. TODO: decidir sobre uma segunda rodada.
- As perguntas dependem de um corpus de 28 dispositivos (REN 1.000/2021, CDC e Lei Distrital
  7.888/2026); PRODIST e a REH de tarifas estão pendentes.
- As faturas não têm layout de PDF nem foto; servem às checagens do nível A, não à extração.
- Nenhuma fatura real, dado pessoal ou segredo faz parte do conjunto.

## Uso

Os baselines B2 e B3 usam as perguntas ([resultados](resultados.md)). As faturas servem à avaliação do
motor de nível A e dos agentes nas sprints seguintes.
