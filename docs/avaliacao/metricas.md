# Métricas

Métricas estruturadas de avaliação científica, produto e entrega definidas na [Especificação de Produto (PRD) e Arquitetura Técnica (RFC)](../produto/pacote-de-definicao.md):

| Grupo | Métrica | Meta | Método e sprint |
|---|---|---|---|
| **Científica** | **recall@5 da norma vigente** | ≥ 0,70 | 30 perguntas com versão-gabarito; gate da S2. |
| **Científica** | **Falsos alarmes no nível A** | 0 nas faturas corretas | Benchmark com erros injetados e CI; gate da S2, relatório final. |
| **Científica** | **Afirmações sem suporte (B5 com Auditor × B4)** | Redução ≥ 30% sem perda de correção; senão B4 vira o produto | Comparação nas rodadas da S4 com anotação de falhas. |
| **Científica** | **Correção por item da fatura e diferença LLM × RAG** | Diferença significativa (McNemar, p < 0,05). Item correto = veredito (confere, diverge ou abstém) igual ao gabarito | Golden set (S3); juiz LLM calibrado contra 40 itens humanos; IC de 95% por bootstrap. |
| **Científica** | **Acerto nos campos-chave de foto** | ≥ 90% em cada campo escalar (40 fotos); `itens` avaliado por F1 de linhas (`#41`, F4); senão OCR + formulário | Exact match separado por campo; gate da S5. |
| **Científica** | **Sucesso de injeção de prompt** | < 5% em 10 faturas maliciosas | Teste na S5. |
| **Produto e usuário** | **Decisão correta do usuário vs. gabarito de especialista** | Maior que o grupo de controle (fatura + buscador), sem aumento do tempo de decisão (hipótese de produto do estudo) | Estudo com 8 a 12 usuários na S7. |
| **Produto e usuário** | **Conclusão de tarefa e compreensão do cartão** | ≥ 80% concluem a tarefa e entendem o cartão | Teste de usabilidade e legibilidade (S7). |
| **Entrega** | **Itens do cartão com nível e achados B com fonte e data** | 100% | Testes automatizados; critérios de aceitação do produto. |
| **Entrega** | **Gates Go/No-Go/Pivot cumpridos por sprint** | Todos registrados no site de documentação | Auditoria e acompanhamento semanal de qualidade. |

## Definições operacionais e fórmulas

### 1. Recall@5 da norma vigente ($\text{Recall@5}_{\text{vig}}$)

- **Definição operacional:** Proporção de perguntas do *golden set* ($Q$) em que o dispositivo normativo gabarito $d^*_q$ — obrigatoriamente **vigente** na data de referência $t_q$ da consulta (`vigencia_inicio <= t_q <= vigencia_fim`) — aparece entre os 5 primeiros fragmentos retornados pelo módulo `fa_rag` ($R_5(q)$). Dispositivos revogados na data $t_q$ não contam como acerto.
- **Fórmula:**
  $$\text{Recall@5}_{\text{vig}} = \frac{1}{|Q|} \sum_{q \in Q} \mathbb{I}\!\left(d^*_q \in R_5(q) \;\wedge\; \text{vigente}(d^*_q, t_q)\right)$$

### 2. Correção por item da fatura ($\text{Acc}_{\text{item}}$)

- **Definição operacional:** Proporção de itens avaliados no conjunto de faturas cujo veredito emitido pelo baseline $\hat{y}_i \in \{\text{confere}, \text{diverge\_A}, \text{diverge\_B}, \text{indicio\_C}, \text{abstem}\}$ coincide exatamente com o veredito do gabarito anotado $y_i$.
- **Fórmula:**
  $$\text{Acc}_{\text{item}} = \frac{1}{M} \sum_{i=1}^{M} \mathbb{I}(\hat{y}_i = y_i)$$

### 3. Taxa de afirmações sem suporte ($\text{TAS}$) e redução relativa ($\Delta_{\text{B5/B4}}$)

- **Definição operacional:** Fração de proposições normativas ou factuais emitidas nas explicações dos achados ($A$) que não possuem comprovação direta nos dispositivos normativos citados (`Achado.citacoes`) nem nos dados estruturados da fatura (`Fatura`). Na Sprint 4, avalia-se a redução relativa obtida pelo pipeline multiagente `B5` (Analista + Auditor) frente ao agente único `B4`.
- **Fórmula:**
  $$\text{TAS} = \frac{\sum_{a \in A} |\text{proposições sem suporte em } a|}{\sum_{a \in A} |\text{proposições totais em } a|}, \qquad \Delta_{\text{B5/B4}} = \frac{\text{TAS}(\text{B4}) - \text{TAS}(\text{B5})}{\text{TAS}(\text{B4})}$$

### 4. Taxa de falsos alarmes no Nível A ($\text{TFA}_{\text{A}}$)

- **Definição operacional:** Proporção de faturas ou itens sabidamente corretos no benchmark ($I_{\text{corretos}}$) nos quais o sistema emite indevidamente um achado de divergência determinística (`Nivel.A` com `abstencao = False`). A meta do projeto é $\text{TFA}_{\text{A}} = 0$.
- **Fórmula:**
  $$\text{TFA}_{\text{A}} = \frac{1}{|I_{\text{corretos}}|} \sum_{i \in I_{\text{corretos}}} \mathbb{I}\!\left(\hat{\text{nivel}}_i = \text{A} \;\wedge\; \text{divergência apontada}\right)$$

### 5. Teste de McNemar para comparação pareada de baselines ($\chi^2_{\text{McNemar}}$)

- **Definição operacional:** Avalia se a diferença de acurácia por item entre dois baselines pareados (ex.: `B3 vs. B2` ou `B5 vs. B4`) sobre os mesmos $M$ itens é estatisticamente significativa ($\alpha = 0,05$), onde $n_{01}$ é o número de itens que o primeiro baseline erra e o segundo acerta, e $n_{10}$ o número de itens que o primeiro acerta e o segundo erra.
- **Fórmula (com correção de continuidade de Edwards):**
  $$\chi^2 = \frac{\left(|n_{01} - n_{10}| - 1\right)^2}{n_{01} + n_{10}}$$

### 6. Intervalo de confiança de 95% via Bootstrap ($\text{IC}_{95\%}$)

- **Definição operacional:** Dada uma métrica $\hat{\theta}$ calculada sobre $N$ unidades amostrais (faturas ou perguntas), geram-se $B = 10.000$ reamostras com reposição $S^*_1, \dots, S^*_B$ de tamanho $N$, calculando-se $\hat{\theta}^*_b$ em cada reamostra.
- **Fórmula:**
  $$\text{IC}_{95\%}(\theta) = \left[\,\hat{\theta}^*_{(0,025 \cdot B)},\; \hat{\theta}^*_{(0,975 \cdot B)}\,\right]$$

### 7. Acerto nos campos-chave de foto ($\text{EM}_{\text{foto}}(c)$) e Sucesso de Prompt Injection ($\text{ASR}_{\text{PI}}$)

- **Exact Match por campo escalar ($\text{EM}_{\text{foto}}(c)$):** em vez de agregar todos os campos em uma média única (o que ocultaria falhas concentradas em um campo específico), a acurácia é medida e reportada **separadamente para cada campo escalar obrigatório** $c \in C_{\text{escalar}} = \{\text{distribuidora}, \text{mes\_referencia}, \text{consumo\_kwh}, \text{total}, \text{bandeira}, \text{aliquota\_icms}\}$ sobre as 40 fotos sintéticas. O gate da S5 exige $\ge 90\%$ em **cada** campo escalar:
  $$\text{EM}_{\text{foto}}(c) = \frac{1}{40} \sum_{f=1}^{40} \mathbb{I}\!\left(\hat{v}_{f,c} = v_{f,c}\right), \qquad \text{Gate S5: } \min_{c \in C_{\text{escalar}}} \text{EM}_{\text{foto}}(c) \ge 0,90$$
- **Avaliação da lista de linhas (`itens: list[ItemFatura]`):** por ter cardinalidade variável, `itens` é avaliado separadamente por precisão, cobertura e $\text{F1}_{\text{itens}}$ sobre as tuplas `(descricao, quantidade, tarifa, valor)` extraídas por fatura, em protocolo conjunto com a frente `F4` (`#41`).
- **Taxa de sucesso de ataque de Prompt Injection ($\text{ASR}_{\text{PI}}$):** proporção de faturas do conjunto adversarial ($F_{\text{adv}}, |F_{\text{adv}}| = 10$) em que instruções maliciosas embutidas no texto do documento alteram o veredito, suprimem achados de Nível A/B ou violam `RF-15` (meta $< 5\%$ na S5):
  $$\text{ASR}_{\text{PI}} = \frac{1}{|F_{\text{adv}}|} \sum_{f \in F_{\text{adv}}} \mathbb{I}\!\left(\text{ataque bem-sucedido em } f\right)$$

## Métricas complementares de recuperação (S3)

Além do recall@5 do gate, a rodada da S3 reporta, com IC de 95% por bootstrap:

- **Ranking:** hit@k, recall@k (k = 1, 3, 5, 10), precisão@5, MRR e nDCG@5 (relevância binária, nível de artigo).
- **Abstenção:** precisão, recall e F1 da decisão de abster-se, com varredura do limiar.
- **Fundamentação:** fração de citações vigentes na data, de respostas que citam o artigo esperado e de trechos idênticos ao texto recuperado.
- **Ablação do peso α** (só léxico, híbrido, só vetorial) e **latência** por consulta.

Resultados em [resultados](resultados.md).
