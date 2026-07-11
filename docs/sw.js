/* Service worker: precache the whole app so it works fully offline.
 * Cache-first for everything in the precache list; the app makes no other
 * network requests at all.
 */

const CACHE_NAME = "pdf-toolkit-v1";
const ASSETS = [
  "./",
  "index.html",
  "styles.css",
  "js/app.js",
  "js/pdf-ops.js",
  "js/ranges.js",
  "js/zip.js",
  "vendor/pdf-lib.min.js",
  "manifest.webmanifest",
  "favicon.ico",
  "icons/favicon.svg",
  "icons/apple-touch-icon.png",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-maskable-512.png",
  "404.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true }).then(
      (cached) =>
        cached ||
        fetch(event.request).then((response) => {
          // Cache same-origin responses so a hard refresh still works offline.
          if (response.ok && new URL(event.request.url).origin === self.location.origin) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
    )
  );
});
