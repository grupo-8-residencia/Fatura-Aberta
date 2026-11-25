/**
 * Captura as telas e o vídeo do fluxo da demonstração da S5 (PDF sintético + pergunta versionada).
 *
 * Pré-requisito: a aplicação no ar (docker compose -f infra/docker-compose.yml up --build) e o
 * pacote playwright-core instalado FORA do repositório, com um Chromium disponível:
 *   npm install --prefix /tmp/fa-pw playwright-core && npx --prefix /tmp/fa-pw playwright-core install chromium
 *   NODE_PATH=/tmp/fa-pw/node_modules node scripts/demo/capturar_telas.cjs
 * Variáveis: FA_WEB_URL (padrão http://127.0.0.1:3000) e FA_CHROMIUM (caminho do executável).
 */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright-core");

const RAIZ = path.resolve(__dirname, "../..");
const PASTA = path.join(RAIZ, "docs/assets/demo-s5");
const SAIDA = path.join(PASTA, "evidencias");
const URL = process.env.FA_WEB_URL ?? "http://127.0.0.1:3000";
const PERGUNTA = fs.readFileSync(path.join(PASTA, "pergunta-demo.txt"), "utf8").trim();

(async () => {
  fs.mkdirSync(SAIDA, { recursive: true });
  const navegador = await chromium.launch({
    executablePath: process.env.FA_CHROMIUM || undefined,
  });
  const contexto = await navegador.newContext({
    viewport: { width: 1280, height: 900 },
    recordVideo: { dir: SAIDA, size: { width: 1280, height: 900 } },
  });
  // Pula a introdução para ir direto ao fluxo.
  await contexto.addInitScript(() => {
    try {
      window.localStorage.setItem("fatura-aberta-onboarding-visto", "1");
    } catch {}
  });
  const pagina = await contexto.newPage();
  const foto = (nome) => pagina.screenshot({ path: path.join(SAIDA, nome), fullPage: true });

  await pagina.goto(URL);
  await pagina.waitForSelector("#pdf-fatura");
  const onboarding = pagina.getByRole("button", { name: /começar|entendi|pular|fechar/i });
  if (await onboarding.count()) await onboarding.first().click().catch(() => {});
  await foto("01-envio-pdf.png");

  await pagina.setInputFiles("#pdf-fatura", path.join(PASTA, "fatura-sintetica-demo.pdf"));
  await pagina.getByText("Campos lidos do PDF").waitFor();
  await foto("02-confirmacao.png");

  await pagina.fill("#pergunta", PERGUNTA);
  await foto("03-pergunta.png");

  await pagina.getByRole("button", { name: "Confirmar e conferir" }).click();
  await pagina.getByRole("heading", { name: "Resposta à sua pergunta" }).waitFor({ timeout: 60000 });
  await pagina.waitForTimeout(500);
  await foto("04-cartao-resposta.png");

  const video = pagina.video();
  await contexto.close();
  if (video) fs.renameSync(await video.path(), path.join(SAIDA, "fluxo.webm"));
  await navegador.close();
  console.log("Telas e vídeo salvos em docs/assets/demo-s5/evidencias/");
})().catch((erro) => {
  console.error(erro);
  process.exit(1);
});
