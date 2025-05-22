const CACHE_NAME = "hail-science-trivia";
const STATIC_ASSETS = [
  "/",
  "/static/"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();             // activate right away
  console.log('SW: Installed');
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  console.log('SW: Activated');
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(
      cached => cached || fetch(event.request)
    )
  );
  console.log('SW: Fetched');
});

self.addEventListener('push', function(event) {
  const data = event.data.json();
  const title = data.title || 'Hail Science Trivia';
  const options = {
    body: data.body,
    icon: '/static/favicon.ico'
  };

  event.waitUntil(self.registration.showNotification(title, options));
  console.log('SW: Pushed');
});
