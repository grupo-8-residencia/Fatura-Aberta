# fa-contratos

Contratos Pydantic v2 compartilhados por todas as frentes: `Fatura`, `ItemFatura`, `Achado` (com nível A/B/C) e `Citacao`.

- Os modelos são imutáveis e rejeitam campos desconhecidos.
- `Fatura` **não tem** campos de dados pessoais (nome, endereço, instalação) de propósito.
- Toda mudança aqui usa a label `contrato` e exige **2 aprovações** (ver `CONTRIBUTING.md`).
- Congelamento da v1: issue da Sprint 2.
