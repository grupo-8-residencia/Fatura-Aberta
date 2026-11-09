# Deploy, observabilidade e carga

## Execução local com Docker

```bash
docker compose -f infra/docker-compose.yml up --build
```

A interface fica em `http://127.0.0.1:3000` e a API em
`http://127.0.0.1:8000`. As duas portas são vinculadas apenas à máquina local.
Use `docker compose -f infra/docker-compose.yml down` para encerrar os serviços.

## Observabilidade mínima

- `GET /saude` confirma disponibilidade e versão da API.
- `GET /metricas` expõe apenas quantidade de análises e duração média; não contém
  conteúdo, identificadores ou valores de faturas.
- Logs operacionais registram indisponibilidade dos agentes, sem registrar a fatura.

## Teste de carga leve

Com a API em execução, rode:

```bash
uv run python scripts/teste_carga_leve.py
```

O comando faz requisições sintéticas concorrentes a `POST /analisar` e mostra taxa
de sucesso, latência média e p95. Ele não usa dados reais.

## Publicação externa

Esta configuração prepara a aplicação para contêineres, mas não publica uma URL
pública sozinha. A publicação requer a escolha de um provedor e credenciais do
repositório; depois disso, a URL e o procedimento de rollback devem ser registrados
nesta página.
