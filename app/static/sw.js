/* Service Worker hỗ trợ chế độ Offline (PWA) cho Web App Đo Độ Mặn Vi Sai */
const CACHE_STATIC = "salinity-static-v10";
const CACHE_DATA = "salinity-data-v1";

const PRECACHE_URLS = [
  "/",
  "/manifest.json",
  "/favicon.ico",
  "/static/styles.css?v=10",
  "/static/app.js?v=10",
  "/static/logo.svg?v=10",
  "/static/favicon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_STATIC)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_STATIC && k !== CACHE_DATA)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Dữ liệu GET /api/bootstrap và /api/logs: ưu tiên mạng, rớt mạng lấy từ cache
  if (url.pathname === "/api/bootstrap" || url.pathname === "/api/logs") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_DATA).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() =>
          caches.match(req).then(
            (cached) =>
              cached ||
              new Response(
                JSON.stringify({
                  error: "Đang ngoại tuyến và chưa có dữ liệu cache cho mục này.",
                  offline: true,
                }),
                {
                  status: 503,
                  headers: { "Content-Type": "application/json; charset=utf-8" },
                }
              )
          )
        )
    );
    return;
  }

  // Không cache các API GET khác
  if (url.pathname.startsWith("/api/")) return;

  // Trang HTML gốc: Network-first kèm fallback về Cache để luôn cập nhật bản mới khi online
  if (url.pathname === "/" || url.pathname === "/index.html") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE_STATIC).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Tài nguyên tĩnh (/static/*, manifest, favicon): Stale-While-Revalidate (mở tức thì + tự cập nhật nền)
  event.respondWith(
    caches.open(CACHE_STATIC).then((cache) =>
      cache.match(req).then((cached) => {
        const netPromise = fetch(req)
          .then((res) => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => cached);
        return cached || netPromise;
      })
    )
  );
});
