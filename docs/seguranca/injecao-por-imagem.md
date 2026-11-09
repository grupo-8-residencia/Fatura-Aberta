# Teste de injeção de prompt por imagem

O texto encontrado em imagem é **dado não confiável**, não uma instrução. O
conjunto sintético versionado em `dados/benchmark/sinteticas/ataques-injecao/`
cobre comandos em português, referências ao prompt de sistema e mistura de
texto legítimo com instruções em inglês.

## Resultado

O teste automatizado passa cada caso pela fronteira de extração:

1. padrões de controle são substituídos por um marcador explícito;
2. os valores legítimos da fatura permanecem disponíveis;
3. somente o texto higienizado poderá ser entregue à integração de agentes.

| Falha | Mitigação | Estado |
|---|---|---|
| Instrução de controle no OCR/VLM | `higienizar_texto_extraido`, testes no CI e separação entre dados e instruções | Mitigação parcial |
| Novo padrão de ataque | Adicionar caso sintético e expressão de bloqueio; revisar pela F4/F5 | Monitorado |
| Agente indisponível ou lento | Timeout de 15 s; nível A continua disponível | Implementada |

Não há aceitação implícita de instruções da imagem. Casos que escaparem da
higienização devem ser registrados como incidente e bloqueados até a correção.
