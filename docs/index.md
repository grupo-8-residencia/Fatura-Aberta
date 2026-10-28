---
title: Início
hide:
  - navigation
  - toc
---

# Fatura Aberta

**Um verificador aberto e auditável de faturas de energia elétrica residencial (grupo B1) da Neoenergia Brasília (DF).** Você envia a fatura (PDF ou foto) e recebe um cartão de decisão que mostra, item por item, se a cobrança confere com as regras e tarifas vigentes, com a citação exata da norma: ato, artigo ou inciso e vigência.

Nosso diferencial é a **transparência medida**, não uma "IA que acha erro": código, regras e cálculos abertos; citação por dispositivo com data de vigência; taxa de falsos alarmes publicada; benchmark público com erros injetados; nenhum interesse comercial.

## Níveis de evidência

Todo resultado do produto carrega um nível. Nenhum deles diz "ilegal" nem estima restituição: usamos linguagem de evidência e, quando faz sentido, encaminhamos para o Procon-DF ou a Defensoria.

!!! nivel-a "Nível A: conferido com a própria fatura"
    Checagem determinística com dados da própria fatura: leituras, somas, linhas, fórmula do ICMS com a alíquota impressa, parcela até 80 kWh. **É o único nível emitido automaticamente.**

!!! nivel-b "Nível B: diverge da tabela oficial que conseguimos obter"
    Divergência contra a tabela oficial da ANEEL versionada (TUSD+TE e bandeira). Sai sempre com a **fonte e a data da tabela**.

!!! nivel-c "Nível C: indício que não dá para confirmar"
    Algo que parece estranho, mas que não conseguimos confirmar. Vira um **pedido de esclarecimento** à distribuidora.

## Por onde começar

<div class="grid cards" markdown>

-   :material-file-document-outline: **[Produto](produto/index.md)**

    ---

    Visão, personas, Lean Inception e critérios de aceite.

-   :material-sitemap-outline: **[Arquitetura](arquitetura/index.md)**

    ---

    Pipeline determinístico, os dois agentes, contratos e decisões (ADRs).

-   :material-chart-box-outline: **[Avaliação](avaliacao/index.md)**

    ---

    Protocolo dos baselines B1 a B5, métricas e resultados.

-   :material-source-pull: **[Como contribuir](contribuir/index.md)**

    ---

    Fluxo de trabalho, convenções e como rodar o projeto.

</div>

!!! warning "Privacidade em primeiro lugar"
    Fatura real **nunca** entra no Git: ela contém nome, endereço e número da instalação. No repositório só entram faturas sintéticas ou anonimizadas. Veja a [política de dados](conformidade/politica-de-dados.md).
