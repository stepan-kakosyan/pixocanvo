self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open('pixelwar-v1').then(function(cache) {
      return cache.addAll([
        '/',
        '/static/pixelwar/manifest.json',
        // Add more static assets here
      ]);
    })
  );
});

self.addEventListener('fetch', function(event) {
  event.respondWith(
    caches.match(event.request).then(function(response) {
      return response || fetch(event.request);
    })
  );
});
