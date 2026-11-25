// Reformula una nota de la mesa con IA gratuita, desde el servidor (la clave no llega al navegador).
// Usa Gemini si está la variable GEMINI_API_KEY en Vercel; si no, Pollinations, que no pide clave.
const ESTILO_URL = '/agentes/instrucciones/estilo.md';

function armarPrompt(n, estilo) {
  return `Sos editor de Diario Federal. Reformulá esta nota con palabras propias, sin cambiar los hechos.

Reglas que no se rompen:
- No inventes nada: ni datos, ni nombres, ni cifras, ni declaraciones. Solo lo que ya está en la nota.
- Mantené las atribuciones ("según…", "informó…") y las citas textuales tal como están.
- Primer párrafo: qué pasó, quién, dónde y cuándo. Cada párrafo aporta un dato nuevo, sin relleno.
- Título informativo y corto (máximo 90 caracteres), sin signos de exclamación. Bajada de una o dos oraciones.
${n.medio ? '- Es material de otro medio (' + n.medio + '): escribí una nota propia y atribuí los datos con "según informó ' + n.medio + '".\n' : ''}${n.instruccion ? '- Pedido del editor: ' + n.instruccion + '\n' : ''}
Guía de estilo:
${estilo || '(sin guía)'}

Nota original:
VOLANTA: ${n.volanta || ''}
TÍTULO: ${n.titulo || ''}
BAJADA: ${n.bajada || ''}
TEXTO:
${n.cuerpo || ''}

Formato del texto: HTML simple solo con <p>, <strong>, <h3> y <blockquote>.
Respondé SOLO con JSON, así:
{"volanta": "...", "titulo": "...", "bajada": "...", "cuerpo_html": "<p>...</p>"}`;
}

async function gemini(prompt, clave) {
  for (const modelo of ['gemini-flash-latest', 'gemini-flash-lite-latest']) {
    const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': clave },
      body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: prompt }] }], generationConfig: { temperature: 0.4, responseMimeType: 'application/json' } })
    });
    if (!r.ok) continue;
    const d = await r.json();
    const t = (((d.candidates || [])[0] || {}).content || {}).parts || [];
    const texto = t.map(p => p.text || '').join('');
    if (texto) return { texto, ia: 'Gemini' };
  }
  return null;
}

async function libre(prompt) {
  const r = await fetch('https://text.pollinations.ai/openai', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'User-Agent': 'CentroInformacion-DiarioFederal' },
    body: JSON.stringify({ model: 'openai', temperature: 0.4, jsonMode: true, response_format: { type: 'json_object' }, messages: [{ role: 'user', content: prompt }] })
  });
  if (!r.ok) return null;
  const d = await r.json();
  const texto = (((d.choices || [])[0] || {}).message || {}).content || '';
  return texto ? { texto, ia: 'IA gratuita de respaldo' } : null;
}

// Respaldo con clave gratuita: Groq (console.groq.com) y OpenRouter (openrouter.ai), si están en Vercel.
async function compatible(url, clave, modelos, prompt, nombre) {
  for (const modelo of modelos) {
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + clave },
        body: JSON.stringify({ model: modelo, temperature: 0.4, response_format: { type: 'json_object' }, messages: [{ role: 'user', content: prompt }] })
      });
      if (!r.ok) continue;
      const d = await r.json();
      const texto = (((d.choices || [])[0] || {}).message || {}).content || '';
      if (texto) return { texto, ia: nombre };
    } catch {}
  }
  return null;
}

// Qué IA está conectada (sin mostrar ninguna clave): lo usa la mesa para el cartelito de estado.
function estadoIA() {
  return {
    gemini: !!process.env.GEMINI_API_KEY,
    groq: !!process.env.GROQ_API_KEY,
    openrouter: !!process.env.OPENROUTER_API_KEY,
    respaldo_sin_clave: true
  };
}

// Traer una nota desde un enlace que pega el editor (una sola página, la que él eligió).
function esPrivado(host) {
  host = String(host || '').toLowerCase();
  return host === 'localhost' || host.endsWith('.local') || host.endsWith('.internal') ||
    /^(127\.|10\.|192\.168\.|169\.254\.|0\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || host === '[::1]' || host.startsWith('[fc') || host.startsWith('[fd');
}
function limpiarTexto(t) {
  const ent = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', laquo: '«', raquo: '»', ldquo: '“', rdquo: '”', lsquo: '‘', rsquo: '’', mdash: '—', ndash: '–', hellip: '…' };
  return String(t || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&([a-z]+);/gi, (m, n) => ent[n.toLowerCase()] || m)
    .replace(/\s+/g, ' ').trim();
}
function meta(html, nombre) {
  const re = new RegExp('<meta[^>]+(?:property|name)=["\']' + nombre + '["\'][^>]*>', 'i');
  const m = html.match(re); if (!m) return '';
  const c = m[0].match(/content=["']([^"']*)["']/i);
  return c ? limpiarTexto(c[1]) : '';
}
async function traerNota(direccion) {
  let u;
  try { u = new URL(String(direccion).trim()); } catch { throw new Error('El enlace no es válido.'); }
  if (!/^https?:$/.test(u.protocol) || esPrivado(u.hostname)) throw new Error('Ese enlace no se puede abrir.');
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 12000);
  let html = '';
  try {
    const r = await fetch(u.href, { redirect: 'follow', signal: ctl.signal, headers: { 'User-Agent': 'Mozilla/5.0 (compatible; CentralDeNoticias-DiarioFederal/1.0)', 'Accept': 'text/html' } });
    if (!r.ok) throw new Error('El sitio respondió con error ' + r.status + '.');
    html = (await r.text()).slice(0, 2000000);
  } catch (e) {
    throw new Error(e.name === 'AbortError' ? 'El sitio tardó demasiado en responder.' : (e.message || 'No se pudo abrir el enlace.'));
  } finally { clearTimeout(t); }
  html = html.replace(/<(script|style|noscript|svg|nav|footer|aside|form)[\s\S]*?<\/\1>/gi, ' ');
  const zona = (html.match(/<article[\s\S]*?<\/article>/i) || [html])[0];
  const parrafos = (zona.match(/<p[\s>][\s\S]*?<\/p>/gi) || []).map(limpiarTexto).filter(p => p.length > 40);
  const titulo = meta(html, 'og:title') || limpiarTexto((html.match(/<h1[\s\S]*?<\/h1>/i) || html.match(/<title[\s\S]*?<\/title>/i) || [''])[0]);
  return {
    titulo,
    bajada: meta(html, 'og:description') || meta(html, 'description'),
    medio: meta(html, 'og:site_name') || u.hostname.replace(/^www\./, ''),
    cuerpo: parrafos.join('\n\n').slice(0, 15000),
    url: u.href
  };
}

function leerJson(t) {
  const m = String(t).match(/\{[\s\S]*\}/);
  return JSON.parse(m ? m[0] : t);
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') return res.status(200).json({ ok: true, ia: estadoIA() });
  if (req.method !== 'POST') { res.setHeader('Allow', 'GET, POST'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' }); } catch { return res.status(403).json({ ok: false, error: 'Origen no válido.' }); } }
  // Clave de la mesa: si MESA_TOKEN está configurada en Vercel, el pedido tiene que traerla.
  // Sin esa variable el endpoint sigue funcionando como antes (así la mesa no se rompe al desplegar).
  const mesaToken = process.env.MESA_TOKEN;
  if (mesaToken) {
    const enviado = String(req.headers['x-mesa-token'] || '');
    if (enviado !== mesaToken) {
      res.setHeader('X-Mesa-Auth', 'required');
      return res.status(401).json({ ok: false, code: 'TOKEN_REQUIRED', error: 'Falta la clave de la mesa o es incorrecta. Volvé a cargarla.' });
    }
  }
  const n = req.body && typeof req.body === 'object' ? req.body : {};
  // Nota traída de un enlace: se baja esa página y se usa como material, citando al medio.
  let fuente = null;
  if (n.url && (!n.cuerpo || String(n.cuerpo).trim().length < 80)) {
    try {
      const t = await traerNota(n.url);
      if (t.cuerpo.length < 80) return res.status(422).json({ ok: false, error: 'No pude leer el texto de esa página (puede estar cerrada o armada con apps). Copiá el texto y pegalo.' });
      n.titulo = n.titulo || t.titulo; n.bajada = n.bajada || t.bajada; n.cuerpo = t.cuerpo;
      fuente = { medio: t.medio, titulo: t.titulo, url: t.url };
    } catch (e) {
      return res.status(422).json({ ok: false, error: (e.message || 'No se pudo abrir el enlace.') + ' Si no anda, copiá el texto y pegalo.' });
    }
  } else if (n.url) {
    try { const u = new URL(String(n.url)); fuente = { medio: u.hostname.replace(/^www\./, ''), titulo: '', url: u.href }; } catch {}
  }
  if (fuente) n.medio = fuente.medio;
  if (!n.cuerpo || String(n.cuerpo).trim().length < 80) return res.status(400).json({ ok: false, error: 'La nota no tiene texto suficiente para reformular.' });
  n.cuerpo = String(n.cuerpo).slice(0, 15000); n.instruccion = String(n.instruccion || '').slice(0, 400);
  let estilo = '';
  try { const e = await fetch('https://' + req.headers.host + ESTILO_URL); if (e.ok) estilo = (await e.text()).slice(0, 4000); } catch {}
  const prompt = armarPrompt(n, estilo);
  let out = null;
  try { if (process.env.GEMINI_API_KEY) out = await gemini(prompt, process.env.GEMINI_API_KEY); } catch {}
  try { if (!out && process.env.GROQ_API_KEY) out = await compatible('https://api.groq.com/openai/v1/chat/completions', process.env.GROQ_API_KEY, ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b'], prompt, 'Groq'); } catch {}
  try { if (!out && process.env.OPENROUTER_API_KEY) out = await compatible('https://openrouter.ai/api/v1/chat/completions', process.env.OPENROUTER_API_KEY, ['openrouter/free'], prompt, 'OpenRouter'); } catch {}
  try { if (!out) out = await libre(prompt); } catch {}
  if (!out) return res.status(502).json({ ok: false, error: process.env.GEMINI_API_KEY ? 'La IA no respondió. Probá de nuevo en un minuto.' : 'Gemini no está conectada (falta GEMINI_API_KEY en Vercel) y la IA de respaldo no respondió. Probá de nuevo en un minuto.' });
  try {
    const j = leerJson(out.texto);
    if (!j.cuerpo_html) throw new Error('sin texto');
    return res.status(200).json({ ok: true, ia: out.ia, volanta: j.volanta || '', titulo: j.titulo || '', bajada: j.bajada || '', cuerpo_html: j.cuerpo_html, fuente });
  } catch {
    return res.status(502).json({ ok: false, error: 'La IA devolvió algo que no se pudo leer. Probá de nuevo.' });
  }
};
