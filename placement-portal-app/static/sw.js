/*
 * Minimal service worker for Add-to-Home-Screen support.
 *
 * Deliberately does NOT cache anything under /api/ — this app's data
 * changes constantly (approvals, applications, status updates) and we
 * just spent Milestone 8 making sure Redis cache invalidation keeps
 * responses fresh. A service worker caching API responses on top of
 * that would silently reintroduce the exact staleness bug we fixed.
 * Only the static app shell (HTML/CSS/icons) is cached.
 */
const CACHE_NAME = "placement-portal-shell-v2";
const SHELL_ASSETS = [
  "/",
  "/static/manifest.json",
  "/static/icons/icon-192.svg",
  "/static/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only ever handle same-origin GET requests. Without these guards the
  // fetch handler also intercepts things it has no business touching —
  // browser-extension requests (chrome-extension://, used by devtools
  // extensions), cross-origin CDN requests (Bootstrap/Vue), and non-GET
  // requests — and Cache.put() throws on unsupported schemes like
  // chrome-extension://, which is exactly what caused the console error.
  if (request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  // Never intercept API calls — always go to the network so data stays live.
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // Network-first for the app shell, falling back to cache when offline.
  event.respondWith(
    fetch(request)
      .then((response) => {
        const responseClone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
        return response;
      })
      .catch(() => caches.match(request))
  );
});

