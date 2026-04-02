const CACHE_VERSION = "__CACHE_VERSION__";
const SHELL_CACHE = `padesce-shell-${CACHE_VERSION}`;
const PAGE_CACHE = `padesce-pages-${CACHE_VERSION}`;
const DATA_CACHE = `padesce-data-${CACHE_VERSION}`;
const PRECACHE_URLS = __PRECACHE_URLS__;
const DATA_PATH_HINTS = [
  "/reporting/api/",
  "/formations/classes/api/",
  "/deploiement/live/",
  "/backup/api/status/",
  "/consultant/",
];

function isCacheableResponse(response) {
  return Boolean(response && response.ok && response.type !== "opaqueredirect");
}

function isNavigationRequest(request) {
  return request.mode === "navigate" || request.destination === "document";
}

function isDataRequest(url, request) {
  const accept = request.headers.get("accept") || "";
  return accept.includes("application/json") || DATA_PATH_HINTS.some((prefix) => url.pathname.startsWith(prefix));
}

async function notifyClients(type, payload = {}) {
  const clients = await self.clients.matchAll({ includeUncontrolled: true, type: "window" });
  for (const client of clients) {
    client.postMessage({ type, ...payload });
  }
}

async function cacheResponse(cacheName, request, response) {
  if (!isCacheableResponse(response)) {
    return response;
  }
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  return response;
}

async function staleWhileRevalidate(request, cacheName, event) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const networkPromise = fetch(request)
    .then(async (response) => {
      await cacheResponse(cacheName, request, response);
      return response;
    })
    .catch(() => null);

  if (cached) {
    if (event) {
      event.waitUntil(
        networkPromise.then((response) => {
          if (response) {
            return notifyClients("PADESCE_CACHE_REFRESHED", { url: request.url });
          }
          return null;
        }),
      );
    }
    return cached;
  }

  const response = await networkPromise;
  if (response) {
    return response;
  }
  if (cached) {
    return cached;
  }
  throw new Error("cache-miss");
}

function offlineDocumentResponse() {
  return new Response(
    `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PADESCE hors ligne</title>
  <meta name="theme-color" content="#7c3aed">
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background: linear-gradient(180deg, #fdfcff 0%, #fbf9ff 100%);
      color: #23153b;
      font-family: "Segoe UI", "Poppins", sans-serif;
    }
    .panel {
      width: min(520px, 100%);
      padding: 24px;
      border-radius: 24px;
      background: rgba(255, 255, 255, 0.94);
      border: 1px solid rgba(109, 77, 168, 0.16);
      box-shadow: 0 18px 44px rgba(76, 29, 149, 0.14);
    }
    h1 {
      margin: 0 0 10px;
      color: #4c1d95;
      font-size: 1.25rem;
    }
    p {
      margin: 0;
      color: #78669d;
      line-height: 1.55;
    }
  </style>
</head>
<body>
  <section class="panel">
    <h1>Mode hors ligne actif</h1>
    <p>Les dernières pages et données déjà visitées restent disponibles. Dès que la connexion revient, PADESCE remettra le cache à jour automatiquement.</p>
  </section>
</body>
</html>`,
    {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
      },
    },
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(PRECACHE_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("padesce-") && ![SHELL_CACHE, PAGE_CACHE, DATA_CACHE].includes(key))
          .map((key) => caches.delete(key)),
      ).then(() => self.clients.claim()),
    ),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }
  if (url.pathname === "/service-worker.js" || url.pathname === "/accounts/logout/") {
    return;
  }

  if (isNavigationRequest(request)) {
    event.respondWith(
      staleWhileRevalidate(request, PAGE_CACHE, event).catch(async () => {
        const cache = await caches.open(PAGE_CACHE);
        const cached = await cache.match(request);
        return cached || offlineDocumentResponse();
      }),
    );
    return;
  }

  if (request.destination === "style" || request.destination === "script" || request.destination === "image" || request.destination === "font") {
    event.respondWith(staleWhileRevalidate(request, SHELL_CACHE, event).catch(() => Response.error()));
    return;
  }

  if (isDataRequest(url, request)) {
    event.respondWith(staleWhileRevalidate(request, DATA_CACHE, event).catch(() => Response.error()));
    return;
  }

  event.respondWith(staleWhileRevalidate(request, PAGE_CACHE, event).catch(() => Response.error()));
});

self.addEventListener("message", (event) => {
  if (!event.data || event.data.type !== "PADESCE_WARM_CACHE" || !Array.isArray(event.data.urls)) {
    return;
  }

  event.waitUntil(
    caches.open(PAGE_CACHE).then(async (cache) => {
      for (const rawUrl of event.data.urls) {
        if (!rawUrl) {
          continue;
        }
        try {
          const request = new Request(rawUrl, { credentials: "same-origin" });
          const response = await fetch(request);
          if (isCacheableResponse(response)) {
            await cache.put(request, response.clone());
          }
        } catch (error) {
          // Ignore warm-cache failures while offline.
        }
      }
    }),
  );
});
