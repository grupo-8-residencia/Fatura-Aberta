# Política de segurança

O Fatura Aberta lida com faturas de energia, que têm **dados pessoais** (nome, endereço, número da instalação). O repositório é público: trate qualquer vazamento como incidente.

## Se uma fatura real, segredo ou token for enviado ao repositório

1. **Não apague só no próximo commit**: o histórico continua público.
2. Avise **imediatamente** o Tech Lead (`@pedrohpsantos`) por mensagem direta, sem repetir o conteúdo em issue ou PR.
3. Segredo ou token: **revogue e gere outro** antes de qualquer outra ação.
4. O Tech Lead, com a F6, reescreve o histórico, pede a remoção de caches e PRs no GitHub e avisa quem já clonou.
5. Registre o incidente (sem dados pessoais) em `docs/conformidade/politica-de-dados.md`.

## Como reportar uma vulnerabilidade

Use **Security > Report a vulnerability** (aviso privado do GitHub) neste repositório. Não abra issue pública com detalhes de exploração.

TODO (F6): definir prazo de resposta e canal alternativo de contato.
