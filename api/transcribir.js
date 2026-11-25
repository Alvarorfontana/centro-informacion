// Pasa a texto lo que el editor le dice al micrófono del Redactor IA.
// El teléfono graba el audio y lo manda acá; la clave queda en el servidor (variables de Vercel).
// Primero Groq (Whisper, gratis), y si no hay clave o falla, Gemini.

const EXT = { 'audio/webm': 'webm', 'audio/mp4': 'mp4', 'audio/x-m4a': 'm4a', 'audio/m4a': 'm4a', 'audio/ogg': 'ogg', 'audio/mpeg': 'mp3', 'audio/wav': 'wav', 'audio/aac': 'm4a' };

async function conGroq(buf, tipo, clave) {
  for (const modelo of ['whisper-large-v3-turbo', 'whisper-large-v3']) {
    try {
      const fd = new FormData();
      fd.append('file', new Blob([buf], { type: tipo }), 'audio.' + (EXT[tipo] || 'webm'));
      fd.append('model', modelo);
      fd.append('language', 'es');
      fd.append('response_format', 'json');
      const r = await fetch('https://api.groq.com/openai/v1/audio/transcriptions', {
        method: 'POST', headers: { Authorization: 'Bearer ' + clave }, body: fd
      });
      if (!r.ok) continue;
      const d = await r.json();
      if (d && d.text && d.text.trim()) return d.text.trim();
    } catch {}
  }
  return '';
}

async function conGemini(base64, tipo, clave) {
  for (const modelo of ['gemini-flash-latest', 'gemini-flash-lite-latest']) {
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': clave },
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [
            { inline_data: { mime_type: tipo, data: base64 } },
            { text: 'Transcribí textualmente este audio, que está en español rioplatense. Devolvé solo lo que se dice, con puntuación, sin comentarios ni comillas.' }
          ] }],
          generationConfig: { temperature: 0 }
        })
      });
      if (!r.ok) continue;
      const d = await r.json();
      const t = ((((d.candidates || [])[0] || {}).content || {}).parts || []).map(p => p.text || '').join('').trim();
      if (t) return t;
    } catch {}
  }
  return '';
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  const groq = !!process.env.GROQ_API_KEY, gemini = !!process.env.GEMINI_API_KEY;
  if (req.method === 'GET') return res.status(200).json({ ok: true, disponible: groq || gemini, ia: { groq, gemini } });
  if (req.method !== 'POST') { res.setHeader('Allow', 'GET, POST'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' }); } catch { return res.status(403).json({ ok: false, error: 'Origen no válido.' }); } }
  const mesaToken = process.env.MESA_TOKEN;
  if (mesaToken && String(req.headers['x-mesa-token'] || '') !== mesaToken) {
    res.setHeader('X-Mesa-Auth', 'required');
    return res.status(401).json({ ok: false, code: 'TOKEN_REQUIRED', error: 'Falta la clave de la mesa o es incorrecta.' });
  }
  if (!groq && !gemini) return res.status(503).json({ ok: false, error: 'No hay IA para pasar el audio a texto (falta GROQ_API_KEY o GEMINI_API_KEY).' });

  const b = req.body && typeof req.body === 'object' ? req.body : {};
  const audio = String(b.audio || '').replace(/^data:[^,]*,/, '');
  const tipo = (String(b.tipo || 'audio/webm').split(';')[0].trim().toLowerCase()) || 'audio/webm';
  if (audio.length < 1000) return res.status(400).json({ ok: false, error: 'No llegó audio. Probá de nuevo.' });
  if (audio.length > 4200000) return res.status(413).json({ ok: false, error: 'El audio es muy largo: hablá menos de 3 minutos por vez.' });

  const buf = Buffer.from(audio, 'base64');
  let texto = '', ia = '';
  if (groq) { texto = await conGroq(buf, tipo, process.env.GROQ_API_KEY); if (texto) ia = 'Groq'; }
  if (!texto && gemini) { texto = await conGemini(audio, tipo, process.env.GEMINI_API_KEY); if (texto) ia = 'Gemini'; }
  if (!texto) return res.status(502).json({ ok: false, error: 'No pude entender el audio. Probá de nuevo, más cerca del micrófono.' });
  return res.status(200).json({ ok: true, texto, ia });
};
