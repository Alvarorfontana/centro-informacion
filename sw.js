// Service worker de la Central: permite instalarla como app.
// Versión 3: la página siempre se pide fresca a la red (sin copias viejas guardadas en el teléfono)
// y recibe notas con el botón "Compartir" de Android (ChatGPT, Claude, Gemini, etc.) para la Mesa.
const VERSION = 'central-v3';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== 'compartido').map(k => caches.delete(k)))).then(() => self.clients.claim())
));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method === 'POST' && url.pathname === '/compartir') {
    e.respondWith((async () => {
      try {
        const f = await e.request.formData();
        const d = { titulo: f.get('titulo') || '', texto: f.get('texto') || '', enlace: f.get('enlace') || '' };
        const c = await caches.open('compartido');
        await c.put('/compartido-pendiente', new Response(JSON.stringify(d), { headers: { 'Content-Type': 'application/json' } }));
      } catch (err) {}
      return Response.redirect('/mesa-redaccion-operativa.html?compartido=1', 303);
    })());
    return;
  }
  if (e.request.method !== 'GET') return;
  if (e.request.mode === 'navigate' || /\.(html|json)$/.test(url.pathname)) {
    e.respondWith(fetch(e.request, { cache: 'no-store' }).catch(() => fetch(e.request)));
  }
});
