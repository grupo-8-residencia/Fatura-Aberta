# Corpus normativo

`corpus_b1.json` reúne **dispositivos** de normas públicas, transcritos e conferidos, para o Grupo B1
da Neoenergia Brasília. É a única fonte que entra no índice do RAG (`packages/rag`).

## Campos de cada item

`id`, `titulo`, `texto` (transcrição literal), `citacao` (`ato`, `dispositivo`, `vigencia_inicio`,
`vigencia_fim`, `url`), `subgrupos`, `tags`, `conferido` (`"sim"` ou `"A verificar"`), `conferido_em`,
`fonte_conferencia` e `observacoes`. `vigencia_fim` vazio significa em vigor.

## O que está no corpus (39 itens, conferidos em 09–11/11/2026)

- **REN ANEEL nº 1.000/2021** (vigência a partir de 03/01/2022): arts. 177, 260, 281, 285, 289, 290,
  307, 322, 323, 324, 327, 337, 338, 342, 343, 347, 356, 357, 358, 360 e 361. Texto consolidado em
  `www2.aneel.gov.br/cedoc/ren20211000.html`.
- **REN ANEEL nº 956/2021 — PRODIST Módulo 8** (vigência base a partir de 01/01/2022): Seção 8.2
  (itens 170–173, 177–179, 214, 216, 219, 222–224, 227, 234 e 235) e Anexo 8.B (Tabelas 4 e 5 para
  baixa tensão ≤ 2,3 kV). Texto conferido no PDF oficial `aren20251137_Prodist_modulo_8_v14.pdf`
  vinculado em `gov.br/aneel`.
- **REH ANEEL nº 3.614/2026 — Neoenergia Brasília** (vigência de 22/10/2026 a 21/10/2027): arts. 2º,
  3º (e § 3º sobre adicional de bandeiras), 5º, 6º, 11 e Tabelas 2, 3 e 5 (tarifas B1 e serviços
  cobráveis do Grupo B). Texto conferido em cópia integral da norma e validado ao centavo contra
  `dados/tarifas/aneel_neoenergia_brasilia_b1_2026.xlsx`.
- **Lei nº 8.078/1990 (CDC)** (vigência a partir de 11/03/1991): art. 6º (incisos VI, VIII e X),
  art. 39 (incisos V e VI), art. 42 (caput) e art. 42, parágrafo único. Texto conferido na Câmara dos
  Deputados, porque o Planalto bloqueia acesso automatizado.

- **Lei Distrital nº 7.888/2026** (Lei de Defesa dos Usuários do Serviço de Iluminação Pública;
  vigência a partir da publicação no DODF nº 84, de 11/05/2026): art. 1º, art. 2º, inciso III e art. 4º.
  Texto compilado do SINJ-DF. A lei garante informação e revisão da CIP, mas não fixa valor nem alíquota.

A numeração dos artigos foi verificada no texto oficial. Alguns artigos citados em planejamentos
anteriores não correspondem ao tema esperado (por exemplo, o art. 140 trata do encerramento
contratual, não da fatura). Os temas estão em: fatura (art. 327), vencimento (arts. 337 e 338),
cobrança de atraso (art. 343), suspensão (arts. 356 a 361), faturamento incorreto e devolução em dobro
(arts. 323 e 324), qualidade/continuidade DIC, FIC e DMIC (PRODIST Módulo 8) e tarifas B1 vigentes
(REH 3.614/2026).

## Pendentes (`A verificar`, fora do índice)

| Fonte | Situação |
|---|---|
| Resolução Homologatória ANEEL nº 3.316/2024 | Descartada para o corpus da distribuidora: não é ato da Neoenergia Brasília; substituída no corpus pela REH vigente **3.614/2026** (sucedendo 3.276/2023, 3.406/2024 e 3.542/2025) |
| Lei Distrital nº 7.919/2026 | Não é a lei de iluminação pública: trata de protesto cartorário de débitos de serviços públicos (DODF de 13/07/2026). Fora do escopo; a lei de CIP é a nº 7.888/2026, já no corpus |
| PRODIST Módulo 8, item 221 e 225.1 (REN ANEEL nº 1.147/2025) | Alterados pela REN 1.147/2025 com vigência escalonada em 2026; TODO: confirmar a data exata de produção de efeitos antes de incluir |
| REN 1.000/2021, art. 179 e art. 291 (tarifa social) | Redação alterada pela REN ANEEL 1.147/2025; TODO: confirmar a data de início da nova redação |
| Lei nº 12.212/2010 (tarifa social) | TODO: conferir |

## Manifesto de atos e conversor (F4)

`manifesto_atos.json` é o inventário dos atos normativos candidatos ao corpus: nome, vigência,
URL oficial, `status` (`ok`, `a_confirmar` ou `excluido`), origem e observações. Um ato `excluido`
não conta (por exemplo, o Decreto 8.426/2015 trata de PIS/COFINS sobre receitas financeiras, não da
fatura). `status = ok` significa ato e vigência conferidos; o resto precisa de conferência.

`scripts/converter_norma.py` transforma o texto de uma norma em itens candidatos, sem alterar o
`corpus_b1.json`:

```bash
# um ato (HTML ou PDF, por URL ou arquivo)
uv run python scripts/converter_norma.py --arquivo norma.pdf --url-oficial https://... \
    --ato "REN ANEEL nº 1.000/2021" --prefixo ren1000 --vigencia-inicio 2022-01-03 --artigos 327,343

# todos os atos do manifesto que tiverem arquivo em normas_baixadas/
uv run python scripts/converter_norma.py --manifesto dados/normas/manifesto_atos.json
```

- Os servidores da ANEEL e do Planalto bloqueiam acesso automatizado: baixe a norma no navegador e
  salve em `normas_baixadas/<prefixo>.pdf` (ou `.html`). Essa pasta e `candidatos/` (a saída) estão no
  `.gitignore`, porque **PDF não entra no Git**.
- Todo item sai com `conferido = "A verificar"` e `titulo = "A PREENCHER"`; o índice o ignora até
  uma pessoa comparar com o texto oficial, preencher `titulo` e `tags` e marcar `"sim"`.
- A limpeza tira cabeçalhos, rodapés, numeração de página e as notas de redação. As notas removidas
  vão para `observacoes`, porque indicam quando o dispositivo mudou; trechos revogados ou vetados
  ficam no texto e são sinalizados.
- Limites: só captura artigos (`Art. N`), não anexos nem tabelas de tarifa; PDF escaneado, sem texto,
  não funciona; o nome de quem assina a norma pode ficar no fim do último artigo.

## Regras

1. Nenhuma fonte entra sem URL oficial e vigência registrada.
2. Se a vigência ou o texto não puderem ser confirmados, o item fica `"A verificar"`. Não inventar.
3. O texto é transcrição literal. Omissões de parágrafos ficam registradas em `observacoes`.
4. Só dados públicos, sem dado pessoal.
