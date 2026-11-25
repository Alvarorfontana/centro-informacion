// Charla con la IA del diario (Redactor): el editor le escribe o le dicta lo que quiere y la IA responde.
// La clave queda en el servidor (variables de Vercel): GROQ_API_KEY primero, después OpenRouter y Gemini,
// y si no hay ninguna, Pollinations, que no pide clave.
const ESTILO_URL = '/agentes/instrucciones/estilo.md';

function sistema(estilo) {
  return `Sos el redactor con IA de EL DIARIO (Diario Federal), un medio argentino con mirada federal.
Hablás en español rioplatense, claro y directo, sin vueltas ni relleno.

Ayudás al director en lo que te pida: escribir notas, títulos, bajadas, resúmenes, preguntas para entrevistas,
ideas de cobertura, posteos para redes o revisar un texto.

Reglas que no se rompen:
- No inventes datos, cifras, nombres ni declaraciones. Si te falta información, decilo y preguntá, o dejá [COMPLETAR] en ese lugar.
- Si el editor te pasa material de otro medio, escribí con palabras propias y atribuí: "según informó…".
- Mantené las citas textuales tal como te las dan.
- Si el texto trae enlaces escritos así: [texto](https://…), conservalos en ese mismo formato dentro de la nota.
- Si el editor te trae una nota de la Mesa para trabajarla, hacé solo los cambios que te pide y devolvé la nota completa con el formato de abajo.

Cuando te pida una nota, entregala siempre con este formato, en texto simple:
VOLANTA: …
TÍTULO: … (informativo, máximo 90 caracteres, sin signos de exclamación)
BAJADA: … (una o dos oraciones)

Después, el cuerpo en párrafos cortos. El primer párrafo dice qué pasó, quién, dónde y cuándo.
Para todo lo demás, respondé normal, como un colega de la redacción.

Guía de estilo del diario:
${estilo || '(sin guía)'}`;
}

async function compatible(url, clave, modelos, mensajes, nombre, extra) {
  for (const modelo of modelos) {
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json', Authorization: 'Bearer ' + clave }, extra || {}),
        body: JSON.stringify({ model: modelo, temperature: 0.6, messages: mensajes })
      });
      if (!r.ok) continue;
      const d = await r.json();
      const texto = (((d.choices || [])[0] || {}).message || {}).content || '';
      if (texto) return { texto, ia: nombre };
    } catch {}
  }
  return null;
}

async function gemini(mensajes, clave) {
  const sys = mensajes[0].content;
  const contents = mensajes.slice(1).map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] }));
  for (const modelo of ['gemini-flash-latest', 'gemini-flash-lite-latest']) {
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': clave },
        body: JSON.stringify({ systemInstruction: { parts: [{ text: sys }] }, contents, generationConfig: { temperature: 0.6 } })
      });
      if (!r.ok) continue;
      const d = await r.json();
      const texto = ((((d.candidates || [])[0] || {}).content || {}).parts || []).map(p => p.text || '').join('');
      if (texto) return { texto, ia: 'Gemini' };
    } catch {}
  }
  return null;
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') {
    return res.status(200).json({ ok: true, ia: { groq: !!process.env.GROQ_API_KEY, openrouter: !!process.env.OPENROUTER_API_KEY, gemini: !!process.env.GEMINI_API_KEY, respaldo_sin_clave: true } });
  }
  if (req.method !== 'POST') { res.setHeader('Allow', 'GET, POST'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' }); } catch { return res.status(403).json({ ok: false, error: 'Origen no válido.' }); } }
  const mesaToken = process.env.MESA_TOKEN;
  if (mesaToken && String(req.headers['x-mesa-token'] || '') !== mesaToken) {
    res.setHeader('X-Mesa-Auth', 'required');
    return res.status(401).json({ ok: false, code: 'TOKEN_REQUIRED', error: 'Falta la clave de la mesa o es incorrecta.' });
  }
  const b = req.body && typeof req.body === 'object' ? req.body : {};
  const historial = (Array.isArray(b.mensajes) ? b.mensajes : [])
    .filter(m => m && (m.rol === 'yo' || m.rol === 'ia') && String(m.texto || '').trim())
    .slice(-16)
    .map(m => ({ role: m.rol === 'ia' ? 'assistant' : 'user', content: String(m.texto).slice(0, 12000) }));
  if (!historial.length || historial[historial.length - 1].role !== 'user') return res.status(400).json({ ok: false, error: 'Escribile algo a la IA.' });

  let estilo = '';
  try { const e = await fetch('https://' + req.headers.host + ESTILO_URL); if (e.ok) estilo = (await e.text()).slice(0, 4000); } catch {}
  try { const g = await fetch('https://' + req.headers.host + '/agentes/instrucciones/guia-redaccion.md'); if (g.ok) estilo += '\n\n' + (await g.text()).slice(0, 2000); } catch {}
  const mensajes = [{ role: 'system', content: sistema(estilo) }, ...historial];

  let out = null;
  if (process.env.GROQ_API_KEY) out = await compatible('https://api.groq.com/openai/v1/chat/completions', process.env.GROQ_API_KEY, ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b'], mensajes, 'Groq');
  if (!out && process.env.OPENROUTER_API_KEY) out = await compatible('https://openrouter.ai/api/v1/chat/completions', process.env.OPENROUTER_API_KEY, ['openrouter/free'], mensajes, 'OpenRouter', { 'X-Title': 'Central de noticias' });
  if (!out && process.env.GEMINI_API_KEY) out = await gemini(mensajes, process.env.GEMINI_API_KEY);
  if (!out) out = await compatible('https://text.pollinations.ai/openai', 'libre', ['openai'], mensajes, 'IA gratuita de respaldo');
  if (!out) return res.status(502).json({ ok: false, error: 'La IA no respondió. Probá de nuevo en un minuto.' });
  return res.status(200).json({ ok: true, ia: out.ia, texto: out.texto });
};
