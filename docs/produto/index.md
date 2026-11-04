# Produto

## Visão

O **Fatura Aberta** é uma plataforma aberta, transparente e auditável desenvolvida para a verificação automatizada de faturas de energia elétrica de consumidores residenciais (**Grupo B1**) atendidos pela **Neoenergia Brasília** no Distrito Federal. O sistema processa documentos em formato digital (PDF nativo) ou capturas de imagem (fotografias de faturas impressas), gerando um **cartão de decisão** estruturado que analisa a conformidade de cada item faturado em relação à regulamentação vigente e às tabelas tarifárias homologadas, acompanhada pela citação explícita do dispositivo legal, ato normativo e período de vigência aplicável.

## Diferencial

- **Auditabilidade pontual e transparência medida**, não "IA que acha erro".
- Código, regras e cálculos abertos.
- Rastreabilidade regulatória: citação por dispositivo, com ato normativo e período de vigência.
- Publicação transparente de métricas de falso-positivo (falso alarme).
- Benchmark público reproduzível com faturas sintéticas e erros injetados.
- Acoplamento exclusivo a fontes de dados oficiais e nenhum interesse comercial.

## Níveis formais de evidência e regras do produto

!!! nivel-a "Nível A (Checagem Determinística)"
    Validação matemática e lógica direta com base nos dados contidos na própria fatura (histórico de leitura, consumo medido, somatório de itens, parcela até 80 kWh e alíquota de ICMS impressa). **É o único nível emitido de forma automatizada pelo motor de regras.**

!!! nivel-b "Nível B (Confronto Tarifário Oficial)"
    Identificação de divergências em relação às tabelas homologadas pela ANEEL (TUSD, TE e bandeira). A resposta é contextualizada com base na base tarifária recuperada na data do processamento, indicando a fonte, data e versão de referência.

!!! nivel-c "Nível C (Análise Contextual e Assistida)"
    Identificação de inconsistências regulatórias complexas não confirmadas automaticamente. Nesses casos, o sistema formula minuta padronizada para requerimento de esclarecimentos perante a distribuidora e orienta o encaminhamento aos órgãos de proteção ao consumidor (Procon-DF ou Defensoria Pública).

- **Fronteiras Técnicas (Non-Goals):** estão expressamente fora do escopo atestar a ilegalidade jurídica de cobranças, calcular montantes financeiros de restituição, oferecer pareceres advocatícios, peticionar automaticamente perante concessionárias ou órgãos reguladores, e processar faturas fora do Grupo B1 (como água/Caesb, alta tensão Grupo A, geração distribuída ou telecomunicações).

## Páginas desta seção

- [Pacote de definição (PRD e RFC)](pacote-de-definicao.md)
- [Personas](personas.md)
- [Lean Inception](lean-inception.md)
- [Critérios de aceite](criterios-aceite.md)
