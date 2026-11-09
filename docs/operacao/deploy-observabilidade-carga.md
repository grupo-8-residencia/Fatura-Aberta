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

### Revisão de privacidade dos logs

Antes de aceitar um deploy, envie à API somente uma fatura sintética com um marcador
fictício no campo `distribuidora` (por exemplo, `MARCADOR_TESTE_44`). Confira os logs
da API e do provedor: o marcador, o corpo da requisição e os valores da fatura não
devem aparecer. Repita com uma requisição inválida para cobrir erros de validação.
Registre data, ambiente e resultado da revisão, sem copiar o corpo da requisição
para a documentação. Não use faturas reais neste teste.

**Evidência local (09/11/2026):** uma requisição válida e uma inválida com
marcador fictício retornaram HTTP 200 e 422. A inspeção dos logs do contêiner
mostrou método, caminho e status, sem o marcador ou corpo. A revisão dos logs
do provedor continua pendente.

## Teste de carga leve

Com a API em execução, rode:

```bash
uv run python scripts/teste_carga_leve.py
```

O comando faz 100 requisições sintéticas a `POST /analisar`, com 5 simultâneas.
A meta proposta para a S6 é **100% de respostas HTTP 200 e p95 ≤ 2.000 ms**,
com a aplicação já ativa. O comando sai com erro se a meta não for atingida.
Ele não usa dados reais. Para medir o serviço público, rode:

```bash
uv run python scripts/teste_carga_leve.py --url https://URL-DA-API
```

Documente a data, a URL, a quantidade de requisições, a concorrência, a taxa de
sucesso e o p95. A execução local não substitui a medição pública. A meta acima
precisa do aceite da equipe antes de encerrar a issue.

**Evidência local (09/11/2026):** com API e interface em Docker Compose,
100/100 respostas HTTP 200, 5 requisições simultâneas, p95 de 7 ms em
`127.0.0.1`. A interface e `/saude` responderam HTTP 200. A medição pública
continua pendente.

## Publicação externa (Render)

1. A partir da `dev` atual, crie um **Web Service Docker** para a API com
   `infra/Dockerfile.api` e contexto de build `.` (raiz do repositório).
   Configure `FA_API_PORT=8000`, `PORT=8000` e health check `/saude`.
2. Anote a URL HTTPS da API. Crie outro **Web Service Docker** para a interface,
   com `apps/web/Dockerfile` e contexto de build `apps/web`. Configure
   `NEXT_PUBLIC_API_URL` com a URL HTTPS da API **antes do build** e `PORT=3000`.
3. Anote a URL HTTPS da interface. Na API, configure `FA_CORS_ORIGINS` com essa
   origem exata, sem caminho (por exemplo, `https://minha-interface.onrender.com`),
   e faça novo deploy da API. Não use `*`. A interface deve ser reconstruída se
   `NEXT_PUBLIC_API_URL` mudar.
4. Confirme `GET /saude`, abra a interface e envie uma fatura sintética pelo
   formulário. Depois execute o teste de carga e a revisão de logs acima.

O `infra/docker-compose.yml` é apenas para desenvolvimento local: suas portas
são vinculadas a `127.0.0.1` e o build da interface aponta para a API local.
Não o use como configuração de deploy público. Configure segredos somente no
painel do provedor, nunca em `NEXT_PUBLIC_*` nem no Git.

**URLs públicas:** pendentes de criação dos serviços.

### Rollback

Se o deploy apresentar falhas, no painel do Render abra o serviço afetado,
vá a **Deploys** e use **Rollback** em uma versão anterior aprovada. Confirme
`/saude` e o fluxo sintético depois da reversão. O rollback pelo painel
desativa o deploy automático; reative-o depois de corrigir o problema.
