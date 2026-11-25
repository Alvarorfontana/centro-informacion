// "Mi nota terminada": el editor trae una nota ya escrita (en ChatGPT, Claude, Gemini, DeepSeek, Kimi o a mano)
// y la mesa la ORDENA sin reescribirla: separa volanta, título y bajada, arma los párrafos, corrige tipeos,
// propone títulos alternativos y busca fotos libres en Wikimedia Commons con su crédito.
// Las claves quedan en el servidor (Vercel): Gemini, Groq u OpenRouter; si no hay ninguna, Pollinations.

function armarPrompt(texto, pedido) {
  return `Sos editor de mesa de Diario Federal, un diario argentino. Te llega una nota YA ESCRITA por el director.
Tu trabajo es ORDENARLA, no reescribirla.

Reglas que no se rompen:
- Respetá su texto: mismas palabras, mismo orden, mismos datos. No agregues ni saques información.
- Solo corregí errores de tipeo, ortografía y puntuación evidentes. Anotá cada corrección en "correcciones".
- Borrá lo que sea charla con una IA y no parte de la nota (por ejemplo "Acá tenés la nota:", "¿Querés que la acorte?", separadores ---, asteriscos de formato).
- Si el texto ya trae volanta, título o bajada, usalos tal cual. Si falta alguno, proponelo con lo que dice la nota (título informativo de hasta 90 caracteres, sin signos de exclamación, en mayúscula y minúscula).
- Separá bien los párrafos. Si hay subtítulos, van en <h3>.
- Los enlaces se conservan: [texto](https://…) o direcciones sueltas pasan a <a href="https://…">texto</a>.
- Proponé 3 títulos alternativos, la sección (Internacional, Argentina, Economía, Deportes, Cultura, Tecnología u Opinión), hasta 5 etiquetas, y 2 o 3 búsquedas cortas para encontrar una foto (nombres propios de personas, lugares o instituciones que aparecen, sin verbos).
${pedido ? '- Pedido del director: ' + pedido + '\n' : ''}
Nota:
"""
${texto}
"""

Formato del cuerpo: HTML simple solo con <p>, <strong>, <em>, <h3>, <blockquote>, <ul>, <li> y <a>.
Respondé SOLO con JSON, así:
{"volanta":"...","titulo":"...","bajada":"...","cuerpo_html":"<p>...</p>","titulos_alternativos":["...","...","..."],"seccion":"...","etiquetas":["..."],"buscar_foto":["...","..."],"correcciones":["..."]}`;
}

async function gemini(prompt, clave) {
  for (const modelo of ['gemini-flash-latest', 'gemini-flash-lite-latest']) {
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${modelo}:generateContent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': clave },
        body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: prompt }] }], generationConfig: { temperature: 0.2, maxOutputTokens: 32768, responseMimeType: 'application/json' } })
      });
      if (!r.ok) continue;
      const d = await r.json();
      const texto = ((((d.candidates || [])[0] || {}).content || {}).parts || []).map(p => p.text || '').join('');
      if (texto) return { texto, ia: 'Gemini' };
    } catch {}
  }
  return null;
}

async function compatible(url, clave, modelos, prompt, nombre, extra) {
  for (const modelo of modelos) {
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json', Authorization: 'Bearer ' + clave }, extra || {}),
        body: JSON.stringify({ model: modelo, temperature: 0.2, response_format: { type: 'json_object' }, messages: [{ role: 'user', content: prompt }] })
      });
      if (!r.ok) continue;
      const d = await r.json();
      const texto = (((d.choices || [])[0] || {}).message || {}).content || '';
      if (texto) return { texto, ia: nombre };
    } catch {}
  }
  return null;
}

// Lee el JSON de la IA aunque venga con ```json, texto alrededor o saltos de línea sin escapar.
function leerJson(t) {
  let s = String(t || '').replace(/^\uFEFF/, '').replace(/```(?:json)?/gi, '').trim();
  const a = s.indexOf('{'), z = s.lastIndexOf('}');
  if (a >= 0 && z > a) s = s.slice(a, z + 1);
  try { return JSON.parse(s); } catch {}
  // Reparar: escapar saltos de línea y tabulaciones que quedaron dentro de las comillas
  let fuera = '', dentro = false, esc = false;
  for (const c of s) {
    if (dentro) {
      if (esc) { esc = false; fuera += c; continue; }
      if (c === '\\') { esc = true; fuera += c; continue; }
      if (c === '"') { dentro = false; fuera += c; continue; }
      if (c === '\n') { fuera += '\\n'; continue; }
      if (c === '\r') continue;
      if (c === '\t') { fuera += '\\t'; continue; }
      fuera += c;
    } else { if (c === '"') dentro = true; fuera += c; }
  }
  return JSON.parse(fuera.replace(/,\s*([}\]])/g, '$1'));
}

// Si ninguna IA devuelve algo legible, la mesa igual ordena lo básico: título, párrafos y enlaces.
function ordenBasico(texto) {
  const limpio = texto.replace(/\r/g, '').replace(/^\s*(-{3,}|\*{3,})\s*$/gm, '').replace(/\*\*(.+?)\*\*/g, '$1');
  const bloques = limpio.split(/\n\s*\n/).map(b => b.replace(/\s*\n\s*/g, ' ').trim()).filter(Boolean);
  let titulo = '';
  if (bloques.length > 1 && bloques[0].length <= 140 && !/[.:]$/.test(bloques[0])) titulo = bloques.shift().replace(/^#+\s*/, '');
  const esc = x => x.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const enlaces = x => esc(x)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2">$2</a>');
  const cuerpo = bloques.map(b => /^#+\s/.test(b) ? '<h3>' + enlaces(b.replace(/^#+\s*/, '')) + '</h3>' : '<p>' + enlaces(b) + '</p>').join('\n');
  const nombres = Array.from(new Set((titulo + '. ' + bloques.slice(0, 2).join('. ')).match(/\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+la\s+|de\s+|del\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+/g) || [])).slice(0, 3);
  return { volanta: '', titulo, bajada: '', cuerpo_html: cuerpo, titulos_alternativos: [], seccion: '', etiquetas: [],
    buscar_foto: nombres, correcciones: ['La IA no respondió bien: se ordenaron solo los párrafos. Revisá el título y la bajada.'] };
}
const sinEtiquetas = s => String(s || '').replace(/<[^>]+>/g, '').trim();

// Fotos libres de Wikimedia Commons, con autor y licencia (mismo criterio que el agente de fotos).
async function wikimedia(consulta, maximo) {
  const params = new URLSearchParams({ action: 'query', format: 'json', origin: '*', generator: 'search', gsrnamespace: '6',
    gsrsearch: consulta + ' filetype:bitmap', gsrlimit: String(maximo || 4), prop: 'imageinfo', iiprop: 'url|extmetadata', iiurlwidth: '1200' });
  try {
    const r = await fetch('https://commons.wikimedia.org/w/api.php?' + params, { headers: { 'User-Agent': 'CentralDeNoticias-DiarioFederal/1.0 (contacto@diariofederal.com.ar)' } });
    if (!r.ok) return [];
    const d = await r.json();
    return Object.values((d.query || {}).pages || {}).map(p => {
      const ii = (p.imageinfo || [])[0] || {}; const md = ii.extmetadata || {};
      const val = k => sinEtiquetas((md[k] || {}).value);
      const url = ii.thumburl || ii.url || '';
      if (!/^https:/.test(url)) return null;
      return { url, pagina: ii.descriptionurl || '', fuente: 'Wikimedia Commons', libre: true, licencia: val('LicenseShortName'),
        descripcion: val('ImageDescription').slice(0, 200), busqueda: consulta,
        credito: 'Foto: ' + (val('Artist') || 'autor en Wikimedia') + ' / Wikimedia Commons (' + (val('LicenseShortName') || 'licencia libre') + ')' };
    }).filter(Boolean);
  } catch { return []; }
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') return res.status(200).json({ ok: true });
  if (req.method !== 'POST') { res.setHeader('Allow', 'GET, POST'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' }); } catch { return res.status(403).json({ ok: false, error: 'Origen no válido.' }); } }
  const mesaToken = process.env.MESA_TOKEN;
  if (mesaToken && String(req.headers['x-mesa-token'] || '') !== mesaToken) {
    res.setHeader('X-Mesa-Auth', 'required');
    return res.status(401).json({ ok: false, code: 'TOKEN_REQUIRED', error: 'Falta la clave de la mesa o es incorrecta.' });
  }
  const b = req.body && typeof req.body === 'object' ? req.body : {};
  const texto = String(b.texto || '').trim().slice(0, 20000);
  const pedido = String(b.pedido || '').trim().slice(0, 400);
  if (texto.length < 120) return res.status(400).json({ ok: false, error: 'Pegá la nota completa (es muy corta para ordenarla).' });

  const prompt = armarPrompt(texto, pedido);
  // Se prueba una IA tras otra: si una no responde o devuelve algo ilegible, pasa a la siguiente.
  const intentos = [];
  if (process.env.GEMINI_API_KEY) intentos.push(() => gemini(prompt, process.env.GEMINI_API_KEY));
  if (process.env.GROQ_API_KEY) intentos.push(() => compatible('https://api.groq.com/openai/v1/chat/completions', process.env.GROQ_API_KEY, ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b'], prompt, 'Groq'));
  if (process.env.OPENROUTER_API_KEY) intentos.push(() => compatible('https://openrouter.ai/api/v1/chat/completions', process.env.OPENROUTER_API_KEY, ['openrouter/free'], prompt, 'OpenRouter', { 'X-Title': 'Central de noticias' }));
  intentos.push(() => compatible('https://text.pollinations.ai/openai', 'libre', ['openai'], prompt, 'IA gratuita de respaldo'));

  let j = null, ia = '';
  for (const intento of intentos) {
    let out = null;
    try { out = await intento(); } catch {}
    if (!out) continue;
    try { const x = leerJson(out.texto); if (x && x.cuerpo_html) { j = x; ia = out.ia; break; } } catch {}
  }
  if (!j) { j = ordenBasico(texto); ia = 'Orden básico'; }

  // Fotos: hasta 6, sin repetir, a partir de las búsquedas que propuso la IA
  const busquedas = (Array.isArray(j.buscar_foto) ? j.buscar_foto : []).map(s => String(s).trim()).filter(Boolean).slice(0, 3);
  const listas = await Promise.all(busquedas.map(q => wikimedia(q, 3)));
  const vistas = new Set(), fotos = [];
  for (const l of listas) for (const f of l) if (!vistas.has(f.url) && fotos.length < 6) { vistas.add(f.url); fotos.push(f); }

  return res.status(200).json({
    ok: true, ia,
    volanta: sinEtiquetas(j.volanta), titulo: sinEtiquetas(j.titulo), bajada: sinEtiquetas(j.bajada), cuerpo_html: String(j.cuerpo_html),
    titulos_alternativos: (j.titulos_alternativos || []).map(sinEtiquetas).filter(Boolean).slice(0, 4),
    seccion: sinEtiquetas(j.seccion), etiquetas: (j.etiquetas || []).map(sinEtiquetas).filter(Boolean).slice(0, 8),
    correcciones: (j.correcciones || []).map(sinEtiquetas).filter(Boolean).slice(0, 20),
    fotos, busquedas
  });
};
