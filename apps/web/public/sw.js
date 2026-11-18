// Service worker do Fatura Aberta: a página vem da rede (com o cache só para o modo offline),
// e os arquivos estáticos vêm do cache. Respostas da API (outra origem) nunca são guardadas.
const CACHE = "fatura-aberta-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icones/192.png", "/icones/512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((chaves) => Promise.all(chaves.filter((c) => c !== CACHE).map((c) => caches.delete(c)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((resposta) => {
          const copia = resposta.clone();
          caches.open(CACHE).then((cache) => cache.put("/", copia));
          return resposta;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(
      (guardada) =>
        guardada ??
        fetch(request).then((resposta) => {
          if (resposta.ok) {
            const copia = resposta.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copia));
          }
          return resposta;
        }),
    ),
  );
});
