# Web (F6)

Web app em Next.js com o fluxo de envio, confirmação de campos e cartão de decisão (nível de evidência, estados de confere/divergência/abstenção e linguagem cautelosa). Consome `POST /analisar` da API.

```bash
cd apps/web
npm install
npm run dev
```

As versões estão fixas em `package.json` (sem `latest`) e o `package-lock.json` está versionado; use `npm ci` para instalações reproduzíveis. O CI exige `npm audit --audit-level=high` sem achados.
