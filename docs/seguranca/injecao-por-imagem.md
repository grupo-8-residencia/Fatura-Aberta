# Teste de injeção de prompt por documento e pergunta

## Bateria da S5-03

`dados/benchmark/sinteticas/ataques-injecao/casos.json` contém **10 casos**:
cinco PDFs digitais sintéticos com instruções no texto extraído e cinco
perguntas hostis anexadas a um PDF sintético válido. A fatura base tem
divergência controlada entre leitura (130 kWh) e consumo informado (120 kWh).
Os PDFs são gerados de forma determinística por
`uv run python scripts/gerar_ataques_injecao.py`; o teste também verifica que
os binários versionados são idênticos aos gerados.

Comando de reprodução:

```bash
uv run pytest tests/seguranca/test_injecao_documentos.py -s -q
```

**Resultado local em 27/11/2026:** `ASR_PI: 0/10 = 0%` (2 testes aprovados).
Para cada caso, o teste passou por `/extrair` e `/perguntar`. PDFs hostis foram
recusados antes do parser e dos agentes; perguntas hostis receberam abstenção
sem chegar aos agentes, com os achados determinísticos de nível A/B preservados.
A saída não repetiu o comando malicioso nem violou o verificador RF-15. A meta
de RNF-03, **menos de 5%**, foi atendida **neste conjunto específico**.

| Vetor | Casos | Falha observada | Mitigação |
|---|---:|---|---|
| Texto de PDF digital | 5 | 0 | Detecção de comandos explícitos após extração; erro neutro `instrucao_controle` |
| Pergunta com PDF | 5 | 0 | Abstenção antes do agente; achados A/B preservados |

A detecção por padrões não cobre todas as paráfrases, grafias adversariais ou
instruções indiretas. Esse risco residual fica **aceito para a demonstração
local da S5** e deve ser reavaliado com conjunto independente e modelo local
ativo antes de exposição pública. O teste usa o pipeline padrão sem LLM local;
portanto, 0% não demonstra robustez de um LLM/VLM real.

## Vetor imagem

O texto encontrado em imagem é **dado não confiável**. O
conjunto sintético versionado em `dados/benchmark/sinteticas/ataques-injecao/`
cobre comandos em português, referências ao prompt de sistema e mistura de
texto legítimo com instruções em inglês.

### Resultado da fronteira de texto

O teste automatizado passa cada caso pela fronteira de extração:

1. padrões de controle são substituídos por um marcador explícito;
2. os valores legítimos da fatura permanecem disponíveis;
3. somente o texto higienizado poderá ser entregue à integração de agentes.

| Falha | Mitigação | Estado |
|---|---|---|
| Instrução de controle no OCR/VLM | `higienizar_texto_extraido`, testes no CI e separação entre dados e instruções | Mitigação parcial |
| Novo padrão de ataque | Adicionar caso sintético e expressão de bloqueio; revisar pela F4/F5 | Monitorado |
| Agente indisponível ou lento | Timeout de 15 s; nível A continua disponível | Implementada |

O conjunto de imagem atual contém **três transcrições textuais**, sem imagem
binária e sem execução do VLM. O risco de injeção pela imagem em um modelo real
permanece **pendente da S5-01 (#40)** e não entra no denominador de 10 PDFs e
perguntas acima. A integração de imagem deve repetir a medição com imagens
sintéticas e o VLM ativo antes de habilitar o upload de fotos no produto.
