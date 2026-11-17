// Service worker de la Central: permite instalarla como app.
// Versión 2: la página siempre se pide fresca a la red (sin copias viejas guardadas en el teléfono).
const VERSION = 'central-v2';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k)))).then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  if (e.request.mode === 'navigate' || /\.(html|json)$/.test(new URL(e.request.url).pathname)) {
    e.respondWith(fetch(e.request, { cache: 'no-store' }).catch(() => fetch(e.request)));
  }
});
