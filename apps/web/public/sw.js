// Service worker do Fatura Aberta.
// - Páginas: rede primeiro; o cache (por URL) só serve no modo offline.
// - Arquivos do Next com hash no nome (/_next/static/): cache primeiro, porque nunca mudam.
// - Demais arquivos (manifest, ícones): rede primeiro, para não ficarem presos numa versão antiga.
// Respostas da API (outra origem) nunca são guardadas. Troque CACHE ao mudar a estratégia.
const CACHE = "fatura-aberta-v2";
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

function guardar(request, resposta) {
  if (resposta.ok) {
    const copia = resposta.clone();
    caches.open(CACHE).then((cache) => cache.put(request, copia));
  }
  return resposta;
}

function redePrimeiro(request, reserva) {
  return fetch(request)
    .then((resposta) => guardar(request, resposta))
    .catch(() => caches.match(request).then((r) => r ?? (reserva ? caches.match(reserva) : r)));
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(redePrimeiro(request, "/"));
  } else if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(
      caches.match(request).then((guardada) => guardada ?? fetch(request).then((r) => guardar(request, r))),
    );
  } else {
    event.respondWith(redePrimeiro(request));
  }
});
