// Service worker mínimo: permite instalar la Central como app.
// No guarda copias: siempre trae las noticias frescas de la red.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
