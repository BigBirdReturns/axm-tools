/* Service worker for the PTA tracker. Plain static file — this repo has no
 * build step, so there is no precache manifest to bake in; the strategy is
 * runtime caching with the freshness rules a live tracker needs:
 *
 *   - ./data/*.json  → network-first, cache fallback. The tracker's data is
 *     nightly-fresh when online; offline you get the last-seen data, and the
 *     page's existing staleness banner tells the reader how old it is.
 *   - everything else (the page, manifest, icons) → cache-first with a
 *     background refresh, so an installed app boots instantly and offline,
 *     and picks up deploys on the next online visit.
 *
 * Bump CACHE when the caching strategy itself changes (content updates flow
 * through the refresh logic on their own).
 */
const CACHE = "pta-tracker-v1";
const PRECACHE = ["./", "./manifest.json", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Live tracker data: network-first so an online reader always sees the
  // nightly refresh; the cached copy is the offline fallback.
  if (url.pathname.includes("/data/") && url.pathname.endsWith(".json")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req)),
    );
    return;
  }

  // Shell and assets: cache-first for instant/offline boot, refreshed in the
  // background so the next visit gets any deploy.
  event.respondWith(
    caches.match(req).then((hit) => {
      const refresh = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit ?? refresh;
    }),
  );
});
