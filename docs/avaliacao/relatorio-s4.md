# Relatório S4: B4 × B5 e ablação do Auditor

!!! warning "Resultado negativo para o B5 como foi construído"
    O Auditor da #36 elimina as afirmações sem suporte (15,0% das respostas do B4 → 0%), mas ao custo de
    **14,2 pontos de acerto** (91,7% → 77,5%; McNemar exato p = 1,5×10⁻⁵, 17 perguntas perdidas e nenhuma
    ganha). Pelo gate da S4 (`index.md`: reduzir sem perda de correção), **o B5 não passa**. A revisão
    humana das 17 perdas (18/11) confirmou que 12 eram respostas fiéis barradas por regras do Auditor e 5
    tinham extrapolação real (veja [Falhas anotadas](#falhas-anotadas)). **Decisão de 18/11/2026: o produto
    adota o T5** (4 agentes; seção T5), que mantém o Auditor sem o custo de acerto.

!!! success "Rodada T5 (18/11/2026): o sistema multiagentes resolve a perda do B5"
    Com os 4 agentes (política T5: o rascunho barrado pelo Auditor cai na resposta extrativa do
    Pesquisador, em vez de abstenção), o acerto nas 120 perguntas foi **93,3% [88,3%; 97,5%]**, com
    **0 JSON inválido** em 106 chamadas ao LLM, 0% de respostas com afirmação sem suporte (por construção:
    o T5 só entrega o que o Auditor aprovou ou o trecho literal da norma), 0 violação do
    RF-15, 0 citação inventada e 0 fora de vigência. O T5 supera o B5 (23 × 3, McNemar exato p = 8,8×10⁻⁵)
    e empata, sem diferença significativa, com o B4 (7 × 3, p = 0,34) e com o T2 (2 × 0, p = 0,50).
    Detalhes na [seção T5](#rodada-t5-sistema-multiagentes-corpus-de-39-dispositivos).

Fonte: [`avaliacao/resultados/s4-b4-b5.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s4-b4-b5.json)
(registros e braços por pergunta) e
[`s4-b4-b5-comparacao.json`](https://github.com/grupo-8-residencia/Fatura-Aberta/blob/dev/avaliacao/resultados/s4-b4-b5-comparacao.json)
(métricas, ICs e gate). Gerado por `avaliacao/rodada_s4.py`.

## O que foi medido

| Item | Valor |
|---|---|
| Conjunto | as **120 perguntas** do golden set (cobertura 120/120 por id, nenhuma inválida, nenhuma duplicada). As 200 faturas ficam fora: o Analista responde sobre a norma, e nas faturas o motor determinístico já venceu na S3 |
| Gerador | `gpt-oss:20b` (digest `17052f91a42e`), via Ollama, temperatura 0, semente 42 |
| SHA-256 do `checksums.sha256` do golden set | `87aae527…f40453` |
| Recuperação | `IndiceHibrido`, B1, top-5, limiar de abstenção 0,30 (corpus de 28 dispositivos; hash do corpus gravado no cabeçalho dos resultados) |
| Estatística | bootstrap percentil B = 10.000, semente 42; McNemar pareado (qui-quadrado de Edwards e binomial exato) |
| Chamadas ao LLM | 106 (nas outras 14 perguntas nenhum dispositivo passou do limiar e o Analista nem chama o LLM); 0 JSON inválido; 8,9 s por chamada em média |

**Uma chamada, dois braços.** B4 e B5 partilham a mesma saída do Analista para cada pergunta. O B4 emite
todas as afirmações propostas; o B5 passa essa mesma saída pelo Auditor com abstenção forçada (qualquer
reprovação vira abstenção). Assim, a diferença entre os dois é só o Auditor. Um terceiro braço,
**B5 estrutural**, repete o Auditor sem o limite de cobertura de palavras (`cobertura_minima = 0`), mantendo
citação, vigência, números e RF-15.

**Acerto** segue a regra da S3: se a pergunta exige abstenção, acerta quem se abstém; senão, acerta quem
responde e cita o artigo canônico do golden set.

**"Afirmação sem suporte"** NÃO usa o juiz LLM, reprovado na calibração da S3 (κ = 0,03). É a reprovação
por uma verificação determinística do Auditor, aplicada em cada afirmação emitida: citação ausente,
inventada ou divergente, dispositivo fora de vigência, número ou cobertura de palavras sem lastro nos
dispositivos citados, ou expressão proibida do RF-15.

!!! info "Nada foi ajustado com este conjunto"
    O prompt do Analista (hash `8666300a…`) e o limiar 0,30 vêm da #36 e da S3; nenhum foi mexido aqui.
    Por isso as 120 perguntas são, nesta rodada, **teste**. Duas ressalvas de contaminação: o limiar 0,30
    foi calibrado na S3 com erros observados neste mesmo golden set (veja o relatório S3), e o formato de
    pergunta (escrita a partir do texto dos dispositivos) tende a favorecer a recuperação. Trate os níveis
    absolutos como otimistas; a comparação B4 × B5 é pareada e não depende disso.

## Gate B5 × B4

| Critério | B4 | B5 | Diferença B5 − B4 [IC 95%] | Veredito |
|---|---|---|---|---|
| Respostas com afirmação sem suporte | 15,0% [9,2; 21,7] (18 de 120) | 0,0% | −15,0 pp [−21,7; −9,2] | não aplicável: 0% por construção (o B5 só emite o que o Auditor aprova); não é evidência de que o B5 seja melhor |
| Redução relativa | | | 100% (IC 100%; 100%) | ≥ 30% atingida |
| Acerto | 91,7% [86,7; 95,8] | 77,5% [70,0; 85,0] | −14,2 pp [−20,8; −8,3] | perda significativa |
| McNemar (B4 acerta e B5 erra / o inverso) | | | 17 / 0; χ² = 15,06; p = 1,0×10⁻⁴; exato p = 1,5×10⁻⁵ | significativo |

**Decisão.** Se o gate fosse só "B5 tão bom quanto o B4 em afirmações sem suporte", ele passaria. Mas o
gate da S4 no protocolo exige redução **sem perda de correção**, e a perda é grande e significativa. Logo:
**B5 reprovado, B4 é a arquitetura do produto**, e o resultado negativo entra no relatório científico.

!!! warning "A redução de 100% é por construção"
    O B5 só emite afirmações que passaram nas mesmas verificações que definem "sem suporte", então a taxa
    dele é zero por definição. O número informativo é o do B4 (15%) e o preço pago em abstenções. A medida
    também **não vê** erro que passe nas verificações determinísticas (três casos abaixo). Uma métrica
    independente exigiria um juiz calibrado ou anotação humana de todas as respostas, o que não existe
    ainda.

## Ablação: com e sem Auditor

| Métrica | B4 (sem Auditor) | B5 (Auditor completo) | B5 estrutural (sem cobertura de palavras) |
|---|---|---|---|
| Acerto [IC 95%] | **91,7%** [86,7; 95,8] | 77,5% [70,0; 85,0] | 79,2% [71,7; 85,8] |
| Acerto, perguntas normativas (97) | 93,8% | 78,4% | 80,4% |
| Acerto, lacuna (6) | 3 de 6 | 1 de 6 | 1 de 6 |
| Acerto, vigência (12) | 11 de 12 | 11 de 12 | 11 de 12 |
| Acerto, fora do corpus (5) | 5 de 5 | 5 de 5 | 5 de 5 |
| Taxa de abstenção | 18,3% | 33,3% | 31,7% |
| Abstenção correta nas 17 que a exigem | 94,1% | 94,1% | 94,1% |
| Abstenção indevida nas 103 respondíveis | 5,8% | 23,3% | 21,4% |
| Afirmações emitidas / sem suporte | 134 / 18 | 114 / 0 | 116 / 2 |
| Respostas com afirmação sem suporte | 15,0% [9,2; 21,7] | 0,0% | 1,7% [0,0; 4,2] |
| Perguntas com citação inventada | 2 | 0 | 0 |
| Perguntas com citação fora de vigência | 0 | 0 | 0 |
| Perguntas com expressão proibida (RF-15) | 3 | 0 | 0 |

- O Auditor **não ajudou nas abstenções que importam**: as abstenções corretas (vigência e fora do corpus)
  já eram feitas pelo recuperador com limiar. O ganho dele é só nas afirmações emitidas.
- O filtro de vigência da recuperação funcionou: **0 citações fora de vigência** em B4 e B5, então esta
  regra do Auditor não tinha o que pegar nesta rodada.
- A cobertura de palavras responde por pouco da perda (2 perguntas a menos acertadas: 77,5% contra 79,2%).
  O grosso vem da regra de números, da citação e do RF-15.
- No B5 estrutural, 2 afirmações ainda são reprovadas na própria medição porque a medição usa a cobertura
  completa; o braço mostra o efeito de afrouxar a regra, não uma configuração testada como produto.

## Falhas anotadas

!!! info "Revisão humana das 17 perdas do B5 (Pedro, 18/11/2026)"
    A classificação foi proposta pelo agente, lendo cada afirmação ao lado do dispositivo citado, e
    **revisada por uma pessoa (Pedro)**, que concordou com as 17: **12 fiéis** (o Auditor errou ao barrar) e
    **5 com extrapolação** (o Auditor acertou). Não houve dupla anotação: é uma revisão de um só
    avaliador. As tabelas das 3 respostas erradas não detectadas e das 6 sem resposta, mais abaixo,
    continuam só com o rótulo do agente.

    **Nuances registradas na revisão:**

    - **Granularidade de id (GS-Q014 e GS-Q040):** os sufixos `327::VI` e `322::I` não existem porque o
      corpus indexa o caput com os incisos num só trecho. O conteúdo é fiel (no GS-Q040, a regra vale para
      o grupo B); o Auditor tratou uma diferença de granularidade como citação inventada.
    - **Falsos positivos do RF-15 (GS-Q045 e GS-Q074):** as respostas só descrevem direitos previstos na
      norma ("devolução em dobro", "restituição"), sem calcular valor nem aconselhar; o filtro de linguagem
      barrou indevidamente.
    - **Premissa ausente e resposta parcial (GS-Q099 e GS-Q070):** no GS-Q099 a resposta está
      materialmente certa, mas o art. 360 (que exige a notificação prévia) não estava na evidência
      recuperada para sustentar a ligação com o art. 361; o Auditor acertou ao barrar. No GS-Q070 a citação
      do art. 4º, IV é fiel, mas o trecho não responde se a contestação ocorre junto com a conta.

### Auditor barrou resposta que o B4 acertou (17 perguntas)

| Pergunta | Motivo do Auditor | Anotação |
|---|---|---|
| GS-Q014 | citação inventada (`ren1000-art-327::VI`) | O modelo inventou o sufixo do id (o dispositivo `ren1000-art-327` existe); a afirmação é fiel. Citação barrada com razão formal, resposta correta |
| GS-Q040 | citação inventada (`ren1000-art-322::I`) | Idem |
| GS-Q033 | cobertura 0,44 e números "1.000", "2021" | **Falso positivo**: paráfrase fiel do art. 289; os números são do nome do ato, que o Auditor não considera |
| GS-Q037 | cobertura 0,38 e "1.000", "2021" | **Falso positivo**: paráfrase fiel do art. 281, parágrafo único |
| GS-Q045 | RF-15 e número "323" | **Falso positivo**: afirmação fiel ao art. 323 § 2º; o "323" vem da citação do artigo |
| GS-Q059 | número "6" | **Falso positivo**: art. 6º, VIII do CDC, fiel |
| GS-Q067 | "1.000", "2021", "323" | **Falso positivo**: fiel ao art. 323 § 3º |
| GS-Q071 | "2026", "7.888" | **Falso positivo**: o nome da lei vem do ato citado |
| GS-Q074 | RF-15 ("restituição") e "2026", "7.888" | **Falso positivo**: o art. 4º da lei distrital trata de restituição; é a descrição de um direito, não a estimativa de uma restituição |
| GS-Q089 | cobertura 0,55 | **Falso positivo**: "60 meses" ≈ "cinco anos" é inferência direta do art. 347 |
| GS-Q097 | "1.000", "2021" | **Falso positivo** (a terceira de três afirmações, todas fiéis ao art. 361) |
| GS-Q103 | "1.000", "2021", "357" | **Falso positivo**: fiel ao parágrafo único do art. 357 |
| GS-Q063 | RF-15 e cobertura | **Extrapolação real**: "incluindo tributos" não está no § 2º do art. 323 |
| GS-Q070 | cobertura 0,66 e "2026", "7.888" | **Ambígua**: a afirmação sobre "canais institucionais" para impugnação vai além do texto recuperado |
| GS-Q080 | cobertura 0,44 | **Extrapolação leve**: "mas não é obrigada" é inferência de "pode ser realizada" |
| GS-Q099 | cobertura 0,59 e números do ato | **Extrapolação**: liga "sem notificação prévia" ao art. 361 (a notificação é o art. 360) |
| GS-Q108 | cobertura 0,43 | **Extrapolação**: "caracteriza descumprimento das exigências legais" não está no § 1º do art. 360 |

Resumo: **12 de 17 são falsos positivos ou barreiras formais sobre respostas fiéis**; 5 têm extrapolação
real ou ambígua que o Auditor acertou em barrar.

### A causa da perda

A perda tem **duas partes**, não uma. Dos 17 casos em que só o B4 acerta: 12 foram barrados apenas por
`sem_suporte` (regra de números ou de cobertura de palavras); 3 por `linguagem_proibida` (GS-Q045 e GS-Q063 por "devolução em
dobro", GS-Q074 por "restituição"); 2 por citação com id inventado (`::VI` e `::I`). "Devolução em dobro"
é o termo literal do art. 323, § 2º da REN 1.000, e a lista do RF-15 barra o termo de direito, não só a
estimativa de valor: é um **segundo defeito de regra**, a tratar na próxima rodada, também sem ajustar com
este golden set.

**Regra de números.** A regra de números compara todo número da afirmação com o texto de `titulo + texto` dos dispositivos
citados. Quando o modelo escreve "REN ANEEL nº 1.000/2021, art. 323" ou "Lei nº 7.888/2026", esses
números estão na **citação** (ato e dispositivo), que não entra no texto de comparação, e a afirmação é
reprovada mesmo sendo fiel. É um defeito de projeto da regra do Auditor (#36), observado aqui, e não um
erro do gerador. **Não foi corrigido nesta rodada**, para não ajustar a regra com o próprio conjunto de
teste. A correção (incluir ato e dispositivo da citação no texto de comparação e medir de novo) deve ser
validada em perguntas novas, fora deste golden set (por exemplo, o conjunto de
`avaliacao/resultados/s3-perguntas-novas-out-of-sample.json`).

!!! warning "Repetir a rodada depois do #139 (feito em 18/11: veja a seção T5)"
    Os níveis absolutos dependem de um corpus de 28 dispositivos; o #139 leva o corpus a 39. A rodada
    precisa ser repetida depois dele. Para isso o script grava o hash do corpus (`sha256_corpus`) e
    **recusa** retomar ou recomputar as métricas se o corpus mudou, em vez de misturar respostas antigas
    com recuperação nova.

### Respostas erradas que o Auditor não detecta (B4 e B5 iguais)

| Pergunta | O que aconteceu | Anotação |
|---|---|---|
| GS-Q041 | Recuperou o art. 324 mas citou o 323 (caput) para "até quando se cobra quando a culpa foi do consumidor" | A afirmação é fiel ao dispositivo citado, mas o dispositivo certo (art. 324) não foi usado: erro de **seleção de fonte** |
| GS-Q043 | Respondeu sobre revisão da CIP para uma pergunta sobre fatura estimada | **Irrelevante**: a recuperação trouxe só a lei distrital; a resposta é fiel à fonte e não responde à pergunta |
| GS-Q120 | A pergunta exige abstenção (devolução de pagamento duplicado, sem dispositivo vigente que a responda); o Analista respondeu com o CDC art. 42, parágrafo único | **Falha de abstenção**: o Auditor confere lastro, não relevância, então não barra |

Esses três erros mostram o limite do desenho: o Auditor verifica se a afirmação tem lastro no dispositivo
citado, mas não se o dispositivo responde à pergunta. É onde um juiz de relevância ou revisão humana seria
necessário.

### O Analista não respondeu mesmo com o dispositivo certo recuperado

GS-Q028, GS-Q087, GS-Q091 e GS-Q105 devolveram lista vazia de afirmações com o dispositivo canônico
entre os recuperados (B4 e B5 abstêm-se por igual). GS-Q018 e GS-Q024 se abstiveram porque a recuperação
não trouxe o dispositivo canônico (art. 307; no GS-Q024 nenhum dispositivo passou do limiar). O GS-Q066
foi respondido pelo B4 com afirmação **sem lastro** (art. 360 § 2º citado para "corrigir fatura errada"),
e o Auditor corretamente o barrou (resposta errada convertida em abstenção, sem custo de acerto).

## Rodada T5: sistema multiagentes (corpus de 39 dispositivos)

Rodada de 18/11/2026 com o sistema de 4 agentes (`packages/agentes/src/fa_agentes/orquestrador.py`), sobre o
**corpus atual de 39 dispositivos** (PR #139) e a recuperação atual (PR #135). B4, B5 e T5 partilham a
mesma chamada do Analista por pergunta; T2 é a resposta extrativa do Pesquisador na mesma recuperação.
Fonte: `avaliacao/resultados/s4-t5.json` e `s4-t5-comparacao.json` (hash do corpus no cabeçalho).

| Braço | Acerto [IC 95%] | Abstenção | Respostas com afirmação sem suporte | RF-15 | Cit. inventada |
|---|---|---|---|---|---|
| B4 (Analista sem Auditor) | 90,0% [84,2%; 95,0%] | 20,0% | 14,2% | 2 | 1 |
| B5 (Auditor estrito) | 76,7% [69,2%; 84,2%] | 34,2% | 0% (por construção) | 0 | 0 |
| T2 (extrativo do Pesquisador) | 91,7% [86,7%; 96,7%] | 11,7% | 0% (trecho literal) | 0 | 0 |
| **T5 (4 agentes)** | **93,3% [88,3%; 97,5%]** | 11,7% | 0% (por construção) | 0 | 0 |

| Comparação (McNemar, pareado) | Só o primeiro acerta | Só o segundo acerta | p exato |
|---|---|---|---|
| B4 × B5 | 16 | 0 | 3,1×10⁻⁵ |
| T5 × B5 | 23 | 3 | 8,8×10⁻⁵ |
| T5 × B4 | 7 | 3 | 0,34 |
| T5 × T2 | 2 | 0 | 0,50 |

O 0% de "sem suporte" do T5, como o do B5, é **por construção**: o T5 só entrega o que passou nas mesmas
regras que definem "sem suporte", ou o trecho literal da norma. O que mede o T5 é o **acerto**. O RF-15 do
T2 e do T5 é medido no texto que seria entregue (os trechos do Pesquisador): nenhum dos trechos tem termo
vedado; se tivesse, o Orquestrador entregaria só a referência ao dispositivo.

**De onde veio a resposta do T5:** 79 perguntas com o texto do Analista aprovado pelo Auditor, 27 com a
resposta extrativa (o Auditor barrou o rascunho) e 14 com abstenção (o Pesquisador não achou dispositivo
vigente acima do limiar, e o LLM nem foi chamado). Por tipo: normativa 96,9%, vigência 83,3%, lacuna
83,3% e fora do corpus 60,0%.

**Leitura:**

1. **A política T5 elimina o custo do Auditor.** O B5 perde 16 perguntas para o B4; o T5 não perde
   nenhuma para o T2 e entrega o texto do LLM em 79 das 120, sempre com fonte e sem afirmação sem suporte.
2. **O ganho sobre o T2 não é significativo** (2 perguntas). O que o T5 acrescenta ao T2 é a redação
   (afirmações curtas em vez de trechos longos da norma), não acerto; a legibilidade só é medida com
   usuários na S7.
3. **Nenhuma resposta inválida.** Nas 106 chamadas do Analista, o JSON veio sempre no esquema. Na S3, o T4
   teve 16 inválidas com outro prompt e mais contexto (veja o diagnóstico no relatório S3).
4. **B4 × B5 se repete no corpus novo** (90,0% × 76,7%, 16 × 0), o que confirma o resultado da rodada de
   28 dispositivos.

**Faturas (200, `s4-t5-faturas.json`).** O veredito vem do motor e acerta 200/200 (o mesmo 100% circular
do B1 na S3). Os agentes explicaram 284 itens: os 84 divergentes receberam norma citada (18 com o texto do
Analista aprovado, 66 com a resposta extrativa) e os 200 itens de ICMS ficaram em abstenção, porque o
corpus não tem norma de ICMS. **Nenhum rascunho contradisse o veredito do motor** (`veredito_alterado` = 0),
nenhuma mensagem teve termo vedado pelo RF-15 e todas as mensagens passaram na autoconferência do
Comunicador. Latência média de 15,7 s por fatura com chamada ao LLM.

!!! warning "Limites desta rodada"
    - **Dentro da amostra.** O limiar de 0,30 e os ajustes de recuperação do #135 usaram erros do próprio
      golden set; os níveis absolutos são otimistas. As comparações entre braços são pareadas e não
      dependem disso.
    - **"Sem suporte" é a medida determinística do Auditor**, não um juiz: o juiz LLM foi reprovado na
      calibração (PR #162). Erro factual que passe nas regras determinísticas não aparece aqui.
    - **Explicações das faturas:** só 18 de 84 saíram com o texto do LLM. Nas outras 66 entrou o trecho
      literal: em 33 o Auditor barrou o rascunho por `sem_suporte` (regra de números ou de cobertura de
      palavras, as mesmas da perda do B5) e nas demais o Analista não propôs afirmação aproveitável.

## Limites e próximos passos

1. **Revisão das falhas por um só avaliador.** As 17 perdas do B5 foram revisadas por uma pessoa (18/11);
   as 3 + 6 das outras tabelas seguem só com o rótulo do agente. Falta a dupla anotação.
2. **A taxa do B5 é zero por construção.** Sem juiz calibrado ou anotação completa, "afirmação sem suporte"
   mede só o que as regras determinísticas veem.
3. **Uma só rodada, temperatura 0, semente 42:** não há variância entre execuções; o IC do bootstrap cobre
   só a amostragem das perguntas.
4. **Contaminação parcial** do limiar 0,30 e do formato das perguntas (veja o aviso acima).
5. **Próximo passo recomendado:** corrigir a regra de números do Auditor (considerar ato e dispositivo da
   citação), medir de novo em perguntas fora deste golden set, e só então decidir sobre o B5 ou sobre um
   híbrido (B4 com as verificações de citação e de RF-15 como proteção, sem a regra de cobertura).
6. As faturas (200) não foram avaliadas no B4/B5: o motor determinístico segue como o caminho das contas
   (S3), e o Analista entra como explicação normativa.

## Como reproduzir

```bash
FA_LLM_PROVEDOR=ollama uv run python avaliacao/rodada_s4.py --etapa tudo   # retomável, ~20 min
uv run python avaliacao/rodada_s4.py --etapa metricas                       # recalcula sem LLM
```

A rodada grava depois de cada pergunta (escrita atômica), usa trava por PID, reaproveita o cache em disco
do cliente e **recusa retomar** se mudarem o modelo, o digest, o golden set, o prompt do Analista, o limiar
ou o top-k. Os testes (`tests/avaliacao/test_rodada_s4.py`) usam o cliente falso e gravam só em `tmp_path`.
