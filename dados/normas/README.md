# Corpus normativo

`corpus_b1.json` reúne **dispositivos** de normas públicas, transcritos e conferidos, para o Grupo B1
da Neoenergia Brasília. É a única fonte que entra no índice do RAG (`packages/rag`).

## Campos de cada item

`id`, `titulo`, `texto` (transcrição literal), `citacao` (`ato`, `dispositivo`, `vigencia_inicio`,
`vigencia_fim`, `url`), `subgrupos`, `tags`, `conferido` (`"sim"` ou `"A verificar"`), `conferido_em`,
`fonte_conferencia` e `observacoes`. `vigencia_fim` vazio significa em vigor.

## O que está no corpus (25 itens, conferidos em 09/11/2026)

- **REN ANEEL nº 1.000/2021** (vigência a partir de 03/01/2022): arts. 177, 260, 281, 285, 289, 290,
  307, 322, 323, 324, 327, 337, 338, 342, 343, 347, 356, 357, 358, 360 e 361. Texto consolidado em
  `www2.aneel.gov.br/cedoc/ren20211000.html`.
- **Lei nº 8.078/1990 (CDC)** (vigência a partir de 11/03/1991): art. 6º (incisos VI, VIII e X),
  art. 39 (incisos V e VI), art. 42 (caput) e art. 42, parágrafo único. Texto conferido na Câmara dos
  Deputados, porque o Planalto bloqueia acesso automatizado.

A numeração dos artigos foi verificada no texto oficial. Alguns artigos citados em planejamentos
anteriores não correspondem ao tema esperado (por exemplo, o art. 140 trata do encerramento
contratual, não da fatura). Os temas estão em: fatura (art. 327), vencimento (arts. 337 e 338),
cobrança de atraso (art. 343), suspensão (arts. 356 a 361), faturamento incorreto e devolução em dobro
(arts. 323 e 324).

## Pendentes (`A verificar`, fora do índice)

| Fonte | Situação |
|---|---|
| PRODIST Módulo 8 (qualidade do fornecimento, DIC/FIC/DMIC) | TODO: obter a redação vigente do módulo e transcrever os dispositivos |
| Resolução Homologatória ANEEL nº 3.316/2024 | TODO: não foi confirmada como ato da Neoenergia Brasília. As REHs encontradas para a distribuidora são 3.276/2023, 3.406/2024 e 3.614/2026 |
| Lei Distrital nº 7.919/2026 | A lei existe (DODF de 13/07/2026), mas trata de **protesto de débitos de serviços públicos**, não de CIP/COSIP. TODO: identificar a lei distrital de iluminação pública (a busca apontou a Lei nº 7.888/2026 no SINJ-DF) e conferir o texto |
| REN 1.000/2021, art. 179 e art. 291 (tarifa social) | Redação alterada pela REN ANEEL 1.147/2025; TODO: confirmar a data de início da nova redação |
| Lei nº 12.212/2010 (tarifa social) | TODO: conferir |

## Regras

1. Nenhuma fonte entra sem URL oficial e vigência registrada.
2. Se a vigência ou o texto não puderem ser confirmados, o item fica `"A verificar"`. Não inventar.
3. O texto é transcrição literal. Omissões de parágrafos ficam registradas em `observacoes`.
4. Só dados públicos, sem dado pessoal.
