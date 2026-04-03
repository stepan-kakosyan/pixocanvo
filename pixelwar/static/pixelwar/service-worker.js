const CACHE_VERSION = 'pixelwar-v3';
const APP_SHELL_URL = '/';
const PRECACHE_ASSETS = [
  APP_SHELL_URL,
  '/static/pixelwar/manifest.json',
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_VERSION).then(function(cache) {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys
          .filter(function(key) { return key !== CACHE_VERSION; })
          .map(function(key) { return caches.delete(key); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

self.addEventListener('fetch', function(event) {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET') {
    return;
  }

  // Never cache API responses; always hit network for fresh state.
  if (url.pathname.startsWith('/api/') || url.pathname.includes('/api/')) {
    return;
  }

  // Network-first for document navigations so users always receive latest app shell.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(function() {
        return caches.match(request).then(function(cachedResponse) {
          if (cachedResponse) {
            return cachedResponse;
          }
          return caches.match(APP_SHELL_URL);
        });
      })
    );
    return;
  }

  // Cache-first for same-origin static assets.
  if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(function(response) {
        if (response) {
          return response;
        }
        return fetch(request).then(function(networkResponse) {
          const toCache = networkResponse.clone();
          caches.open(CACHE_VERSION).then(function(cache) {
            cache.put(request, toCache);
          });
          return networkResponse;
        });
      })
    );
  }
});
