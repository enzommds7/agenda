const CACHE_NAME = 'agenda-cache-v1';
const urlsToCache = [
  './index.html',
  './style.css',
  './app.js',
  './icon.svg'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  if (event.request.url.includes('firestore') || event.request.url.includes('firebase')) {
    return; // Don't cache Firebase API calls
  }
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});