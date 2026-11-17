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
${n.instruccion ? '- Pedido del editor: ' + n.instruccion + '\n' : ''}
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

function leerJson(t) {
  const m = String(t).match(/\{[\s\S]*\}/);
  return JSON.parse(m ? m[0] : t);
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') { res.setHeader('Allow', 'POST'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' }); } catch { return res.status(403).json({ ok: false, error: 'Origen no válido.' }); } }
  const n = req.body && typeof req.body === 'object' ? req.body : {};
  if (!n.cuerpo || String(n.cuerpo).trim().length < 80) return res.status(400).json({ ok: false, error: 'La nota no tiene texto suficiente para reformular.' });
  n.cuerpo = String(n.cuerpo).slice(0, 15000); n.instruccion = String(n.instruccion || '').slice(0, 400);
  let estilo = '';
  try { const e = await fetch('https://' + req.headers.host + ESTILO_URL); if (e.ok) estilo = (await e.text()).slice(0, 4000); } catch {}
  const prompt = armarPrompt(n, estilo);
  let out = null;
  try { if (process.env.GEMINI_API_KEY) out = await gemini(prompt, process.env.GEMINI_API_KEY); } catch {}
  try { if (!out) out = await libre(prompt); } catch {}
  if (!out) return res.status(502).json({ ok: false, error: 'La IA no respondió. Probá de nuevo en un minuto.' });
  try {
    const j = leerJson(out.texto);
    if (!j.cuerpo_html) throw new Error('sin texto');
    return res.status(200).json({ ok: true, ia: out.ia, volanta: j.volanta || '', titulo: j.titulo || '', bajada: j.bajada || '', cuerpo_html: j.cuerpo_html });
  } catch {
    return res.status(502).json({ ok: false, error: 'La IA devolvió algo que no se pudo leer. Probá de nuevo.' });
  }
};
