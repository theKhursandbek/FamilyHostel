/*
 * Service worker — minimal offline-friendly cache for the Telegram Mini App.
 *
 * Strategy:
 *   - Pre-cache the app shell (index.html + built JS/CSS) on install.
 *   - Network-first for /api/v1/ (so data stays fresh; falls back to cache
 *     only on failure).
 *   - Cache-first for static assets (with background revalidation).
 *
 * NOTE: keep this small — Telegram WebView memory is tight.
 */
const CACHE = "hotel-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Network-first for API; never cache POST/auth.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request).catch(() => caches.match(request)),
    );
    return;
  }

  // Cache-first for everything else (static assets, shell).
  event.respondWith(
    caches.match(request).then((cached) => {
      const networked = fetch(request)
        .then((resp) => {
          if (resp.ok && resp.type === "basic") {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => null);
          }
          return resp;
        })
        .catch(() => cached);
      return cached || networked;
    }),
  );
});
