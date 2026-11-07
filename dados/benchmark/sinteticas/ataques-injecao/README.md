# Casos sintéticos de injeção por imagem

Os arquivos desta pasta são descrições textuais de imagens sintéticas, sem
faturas ou dados pessoais. Eles representam ataques que devem ser aplicados
após OCR/VLM e antes de enviar texto à camada de agentes.

| Caso | Vetor | Resultado esperado |
|---|---|---|
| `01-ignore-instrucoes.txt` | instrução em português | removida pela higienização |
| `02-system-prompt.txt` | referência ao prompt de sistema | removida pela higienização |
| `03-misto.txt` | texto legítimo junto da injeção | valor legítimo preservado; instrução removida |

O conjunto é deliberadamente sintético. A execução e as mitigações estão em
`docs/seguranca/injecao-por-imagem.md`.
