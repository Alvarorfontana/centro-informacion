// Adaptador: corre en Cloudflare Pages las mismas funciones de api/ que usaba Vercel,
// así hay una sola copia del código. Las claves salen de las variables del proyecto en Cloudflare.
export function adaptar(handler) {
  return async ({ request, env }) => {
    globalThis.process = globalThis.process || {};
    globalThis.process.env = env;
    const url = new URL(request.url);
    const headers = {};
    request.headers.forEach((v, k) => { headers[k] = v; });
    headers.host = url.host;
    let body = null;
    try { body = await request.json(); } catch {}
    let status = 200;
    const out = new Headers();
    let respuesta = null;
    const res = {
      setHeader(k, v) { out.set(k, v); return res; },
      status(s) { status = s; return res; },
      json(o) { out.set('Content-Type', 'application/json; charset=utf-8'); respuesta = new Response(JSON.stringify(o), { status, headers: out }); return res; }
    };
    await handler({ method: request.method, headers, body }, res);
    return respuesta || new Response(null, { status: 204, headers: out });
  };
}
