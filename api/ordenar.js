// "Mi nota terminada": el editor trae una nota ya escrita (en ChatGPT, Claude, Gemini, DeepSeek, Kimi o a mano)
// y la mesa la ORDENA sin reescribirla en este esquema fijo:
//   VOLANTA · TÍTULO · COPETE · TEXTO (con sus enlaces) · FUENTES
// Tres maneras de pegarla:
//   1) Con rótulos (Volanta: / Título: / Copete: / Texto: / Fuentes:) → se lee directo, sin IA.
//   2) En código (JSON, Python o Markdown con encabezado ---) → se lee directo, sin IA.
//   3) Texto suelto → la IA separa las partes (Gemini, Groq u OpenRouter; si no, Pollinations).
// Después busca fotos libres en Wikimedia Commons que tengan que ver con la nota, con su crédito.

// ---------- Utilidades ----------
const sinEtiquetas = s => String(s || '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
const escHtml = x => String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const quitarAcentos = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

// Frases de charla con la IA que no son parte de la nota
const CHARLA = /^(ten[eé]s raz[oó]n|claro|perfecto|listo|dale|genial|excelente|por supuesto|aqu[ií] (tienes|est[aá]|va)|ac[aá] (ten[eé]s|est[aá]|va|te)|te (dejo|paso|comparto)|esta es la nota|a continuaci[oó]n|mant[eé]n[eé]? apretado|toc[aá] copiar|copi[aá] (y|este)|pegala|¿quer[eé]s|¿te gustar[ií]a|si quer[eé]s|espero que|nota (completa|lista|terminada)\s*:?$|versi[oó]n (final|corregida)|aqu[ií] est[aá] la)/i;
function quitarCharla(texto) {
  const lineas = String(texto).replace(/\r/g, '').split('\n');
  const esCharla = l => { const t = l.trim().replace(/^[*_#>\s]+/, ''); return t && CHARLA.test(t) && t.length < 400; };
  while (lineas.length && (!lineas[0].trim() || esCharla(lineas[0]))) lineas.shift();
  while (lineas.length && (!lineas[lineas.length - 1].trim() || esCharla(lineas[lineas.length - 1]))) lineas.pop();
  return lineas.filter(l => !/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(l)).join('\n').trim();
}

// Texto común (o Markdown) → HTML simple con párrafos, subtítulos, negritas y enlaces
function enlinea(x) {
  return escHtml(x)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2">$2</a>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|\s)\*([^*\s][^*]*?)\*(?=\s|[.,;:]|$)/g, '$1<em>$2</em>');
}
function aHtml(texto) {
  const t = String(texto || '').trim();
  if (!t) return '';
  if (/<(p|h3|blockquote|ul)\b/i.test(t)) return t; // ya viene en HTML
  // Si casi no hay renglones en blanco, cada renglón es un párrafo
  const pocosBlancos = (t.match(/\n\s*\n/g) || []).length < 2;
  const bloques = (pocosBlancos ? t.split(/\n+/) : t.split(/\n\s*\n/)).map(b => b.trim()).filter(Boolean);
  const out = [];
  let lista = [];
  const cerrarLista = () => { if (lista.length) { out.push('<ul>' + lista.map(i => '<li>' + enlinea(i) + '</li>').join('') + '</ul>'); lista = []; } };
  for (const b of bloques) {
    const lineas = b.split('\n').map(l => l.trim());
    if (lineas.every(l => /^[-•*]\s+/.test(l))) { lista.push(...lineas.map(l => l.replace(/^[-•*]\s+/, ''))); continue; }
    cerrarLista();
    const uno = lineas.join(' ');
    if (/^#{1,6}\s/.test(uno)) out.push('<h3>' + enlinea(uno.replace(/^#+\s*/, '')) + '</h3>');
    else if (/^>\s?/.test(uno)) out.push('<blockquote>' + enlinea(uno.replace(/^>\s?/, '')) + '</blockquote>');
    else if (/^\*\*[^*]{3,90}\*\*$/.test(uno)) out.push('<h3>' + enlinea(uno.replace(/\*\*/g, '')) + '</h3>');
    else out.push('<p>' + enlinea(uno) + '</p>');
  }
  cerrarLista();
  return out.join('\n');
}

// Fuentes: acepta lista de textos, de enlaces o de objetos {medio/titulo/nombre, url}
function normalizarFuentes(f) {
  if (!f) return [];
  const lista = Array.isArray(f) ? f : String(f).split(/\n|·|;/);
  return lista.map(x => {
    if (x && typeof x === 'object') {
      const url = String(x.url || x.link || x.enlace || x.href || '').trim();
      const titulo = sinEtiquetas(x.titulo || x.title || x.nombre || x.medio || x.texto || url);
      return titulo || url ? { medio: sinEtiquetas(x.medio || ''), titulo, url } : null;
    }
    const s = String(x || '').replace(/^\s*[-•*\d.)]+\s*/, '').trim();
    if (!s) return null;
    const md = s.match(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/);
    if (md) return { medio: '', titulo: md[1].trim(), url: md[2] };
    const a = s.match(/<a href="(https?:[^"]+)">([^<]*)<\/a>/);
    if (a) return { medio: '', titulo: a[2] || a[1], url: a[1] };
    const u = s.match(/https?:\/\/\S+/);
    if (u) { const t = s.replace(u[0], '').replace(/[:\-–—\s]+$/, '').trim(); return { medio: '', titulo: sinEtiquetas(t) || u[0], url: u[0].replace(/[).,"]+$/, '') }; }
    return { medio: '', titulo: sinEtiquetas(s), url: '' };
  }).filter(f => f && (f.titulo || f.url)).slice(0, 30);
}

// ---------- 1) Nota con rótulos ----------
const ROTULOS = {
  volanta: /^(volanta|antet[ií]tulo)$/,
  titulo: /^(t[ií]tulo|titular|title)$/,
  bajada: /^(copete|bajada|subt[ií]tulo|resumen|entradilla)$/,
  cuerpo: /^(texto|cuerpo|desarrollo|contenido|texto de la nota|body)$/,
  fuentes: /^(fuentes?|fuentes consultadas|referencias|enlaces|links)$/,
  seccion: /^(secci[oó]n)$/,
  etiquetas: /^(etiquetas|tags)$/,
  foto: /^(foto|imagen|foto principal)$/,
  epigrafe: /^(ep[ií]grafe|cr[eé]dito)$/,
  firma: /^(firma|autor)$/
};
function leerRotulos(texto) {
  const partes = {}; let actual = null, encontrados = 0;
  for (const linea of texto.split('\n')) {
    const m = linea.match(/^\s*[*_#>\s]*([A-Za-zÁÉÍÓÚáéíóúÑñ ]{3,24}?)[*_\s]*[:：][*_\s]*(.*)$/);
    const clave = m && Object.keys(ROTULOS).find(k => ROTULOS[k].test(m[1].trim().toLowerCase()));
    if (clave) { actual = clave; encontrados++; partes[clave] = (partes[clave] ? partes[clave] + '\n' : '') + m[2]; continue; }
    if (actual) partes[actual] = (partes[actual] || '') + '\n' + linea;
  }
  // Arreglo: formato del Redactor IA (VOLANTA / TÍTULO / BAJADA y después el texto, sin rótulo "Texto:")
  if (encontrados >= 1 && partes.titulo && !partes.cuerpo) {
    for (const k of ['bajada', 'titulo', 'volanta']) {
      if (!partes[k]) continue;
      const corte = partes[k].trim().split(/\n\s*\n/);
      if (corte.length > 1) { partes[k] = corte.shift(); partes.cuerpo = corte.join('\n\n'); }
      else if (k === 'bajada' || k === 'titulo') { const l = partes[k].trim().split('\n'); if (l.length > 1) { partes[k] = l.shift(); partes.cuerpo = l.join('\n\n'); } }
      break;
    }
  }
  if (encontrados < 1 || !(partes.titulo && partes.cuerpo)) return null;
  for (const k in partes) partes[k] = partes[k].trim();
  return {
    volanta: partes.volanta, titulo: partes.titulo, bajada: partes.bajada, cuerpo: partes.cuerpo,
    fuentes: partes.fuentes, seccion: partes.seccion, etiquetas: partes.etiquetas,
    foto: partes.foto, epigrafe: partes.epigrafe, firma: partes.firma
  };
}

// ---------- 2) Nota en código: JSON, Python o Markdown con encabezado ----------
// Lector chico de literales de Python (dict, list, str, números, True/False/None) y asignaciones "titulo = '...'".
function leerPython(s) {
  let i = 0;
  const err = () => { throw new Error('python'); };
  const blanco = () => { for (;;) { while (i < s.length && /[\s\\]/.test(s[i])) i++; if (s[i] === '#') { while (i < s.length && s[i] !== '\n') i++; continue; } break; } };
  const esInicioCadena = () => /['"]/.test(s[i] || '') || (/[rRuUfF]/.test(s[i] || '') && /['"]/.test(s[i + 1] || ''));
  function cadena() {
    let crudo = false;
    if (/[rRuUfF]/.test(s[i])) { crudo = /[rR]/.test(s[i]); i++; }
    const q = s[i]; const triple = s.substr(i, 3) === q.repeat(3); i += triple ? 3 : 1;
    let out = '';
    while (i < s.length) {
      if (triple ? s.substr(i, 3) === q.repeat(3) : s[i] === q) { i += triple ? 3 : 1; return out; }
      if (s[i] === '\\' && !crudo) {
        const c = s[i + 1]; i += 2;
        if (c === 'n') out += '\n'; else if (c === 't') out += '\t'; else if (c === '\n') {} else if (c === 'u') { out += String.fromCharCode(parseInt(s.substr(i, 4), 16)); i += 4; } else out += c;
        continue;
      }
      if (!triple && s[i] === '\n') err();
      out += s[i++];
    }
    err();
  }
  function valor() {
    blanco();
    const c = s[i];
    if (c === '{') { i++; const o = {}; for (;;) { blanco(); if (s[i] === '}') { i++; return o; } const k = valor(); blanco(); if (s[i] !== ':') err(); i++; o[String(k)] = valor(); blanco(); if (s[i] === ',') i++; else { blanco(); if (s[i] !== '}') err(); } } }
    if (c === '[' || c === '(') { const fin = c === '[' ? ']' : ')'; i++; const a = []; for (;;) { blanco(); if (s[i] === fin) { i++; return fin === ')' && a.length === 1 && typeof a[0] === 'string' ? a[0] : a; } a.push(valor()); blanco(); if (s[i] === ',') i++; else { blanco(); if (s[i] !== fin) err(); } } }
    if (esInicioCadena()) {
      let t = cadena(); // cadenas pegadas: "a" "b" → "ab"
      for (;;) { const g = i; blanco(); if (esInicioCadena()) t += cadena(); else { i = g; break; } }
      return t;
    }
    const m = s.slice(i).match(/^(True|False|None|-?\d+(?:\.\d+)?)/);
    if (m) { i += m[0].length; return m[0] === 'True' ? true : m[0] === 'False' ? false : m[0] === 'None' ? null : Number(m[0]); }
    const d = s.slice(i).match(/^dict\s*\(/);
    if (d) { i += d[0].length; const o = {}; for (;;) { blanco(); if (s[i] === ')') { i++; return o; } const k = s.slice(i).match(/^\w+/); if (!k) err(); i += k[0].length; blanco(); if (s[i] !== '=') err(); i++; o[k[0]] = valor(); blanco(); if (s[i] === ',') i++; } }
    err();
  }
  // Recorre el archivo: toma las asignaciones de nivel superior y salta todo lo demás (imports, prints, funciones)
  const vars = {};
  while (i < s.length) {
    blanco(); if (i >= s.length) break;
    const a = s.slice(i).match(/^([A-Za-z_]\w*)\s*(?::\s*[\w\[\], ]+)?\s*=(?!=)/);
    if (a) { i += a[0].length; const g = i; try { vars[a[1]] = valor(); } catch { i = g; while (i < s.length && s[i] !== '\n') i++; } continue; }
    if (s[i] === '{') { const g = i; try { vars.__dict = valor(); continue; } catch { i = g; } }
    while (i < s.length && s[i] !== '\n') i++;
  }
  const dicts = Object.values(vars).filter(v => v && typeof v === 'object' && !Array.isArray(v));
  const conNota = dicts.find(d => Object.keys(d).some(k => /^(t[ií]tulo|title|titular|texto|cuerpo|body)$/i.test(k)));
  return conNota || vars;
}
function leerFrontmatter(texto) {
  const m = texto.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) return null;
  const o = {}; let clave = null;
  for (const linea of m[1].split('\n')) {
    const kv = linea.match(/^([\wáéíóúñ]+)\s*:\s*(.*)$/i);
    if (kv) { clave = kv[1]; const v = kv[2].trim().replace(/^["']|["']$/g, ''); o[clave] = v === '' || v === '|' || v === '>' ? '' : v; continue; }
    const it = linea.match(/^\s*-\s+(.*)$/);
    if (it && clave) { if (!Array.isArray(o[clave])) o[clave] = o[clave] ? [o[clave]] : []; o[clave].push(it[1].trim().replace(/^["']|["']$/g, '')); continue; }
    if (clave && linea.trim()) o[clave] = (o[clave] ? o[clave] + ' ' : '') + linea.trim();
  }
  if (m[2].trim()) o.texto = m[2];
  return o;
}
function desdeObjeto(o) {
  if (!o || typeof o !== 'object') return null;
  if (o.nota && typeof o.nota === 'object') o = o.nota;
  const k = {}; for (const x in o) k[quitarAcentos(x)] = o[x];
  const tomar = (...ns) => { for (const n of ns) if (k[n] != null && k[n] !== '') return k[n]; return ''; };
  const cuerpo = tomar('texto', 'cuerpo', 'cuerpo_html', 'body', 'contenido', 'desarrollo', 'parrafos', 'nota');
  const titulo = tomar('titulo', 'title', 'titular');
  if (!titulo || !cuerpo || typeof titulo !== 'string') return null;
  return {
    volanta: tomar('volanta', 'antetitulo', 'kicker'), titulo, bajada: tomar('copete', 'bajada', 'subtitulo', 'resumen', 'summary', 'description', 'descripcion'),
    cuerpo: Array.isArray(cuerpo) ? cuerpo.join('\n\n') : String(cuerpo), fuentes: tomar('fuentes', 'sources', 'referencias', 'enlaces', 'links'),
    seccion: tomar('seccion', 'section', 'categoria'), etiquetas: tomar('etiquetas', 'tags'),
    foto: tomar('foto', 'imagen', 'image'), epigrafe: tomar('epigrafe', 'credito', 'caption'), firma: tomar('firma', 'autor', 'author')
  };
}
function leerCodigo(texto) {
  let t = texto.trim();
  const bloque = t.match(/```[\w-]*[ \t]*\n([\s\S]*?)```/);
  if (bloque) t = bloque[1].trim();
  // JSON
  const a = t.indexOf('{'), z = t.lastIndexOf('}');
  if (a >= 0 && z > a && a < 60) { try { const r = desdeObjeto(JSON.parse(t.slice(a, z + 1))); if (r) return r; } catch {} }
  // Markdown con encabezado ---
  if (/^---\s*\n/.test(t)) { const r = desdeObjeto(leerFrontmatter(t)); if (r) return r; }
  // Python
  if (/^\s*([A-Za-z_]\w*\s*(:\s*\w+\s*)?=\s*(\{|dict\(|["'rRfF(\[])|\{|#|import |from )/m.test(t)) { try { const r = desdeObjeto(leerPython(t)); if (r) return r; } catch {} }
  return null;
}

// ---------- 3) Texto suelto: la IA separa las partes ----------
function armarPrompt(texto, pedido) {
  return `Sos editor de mesa de Diario Federal, un diario argentino. Te llega una nota YA ESCRITA por el director.
Tu trabajo es ORDENARLA en este esquema, sin reescribirla:
VOLANTA (1 a 4 palabras, ej.: "Opinión", "Congreso", "Monitor del Congreso") · TÍTULO · COPETE (1 o 2 oraciones) · TEXTO · FUENTES.

Reglas que no se rompen:
- Respetá su texto: mismas palabras, mismo orden, mismos datos. No agregues ni saques información.
- Borrá todo lo que sea charla con una IA y no parte de la nota: "Tenés razón", "Acá va la nota", "Mantené apretado este mensaje", "¿Querés que…?", separadores, asteriscos.
- El texto pegado puede venir sin saltos de línea: la volanta y el título suelen ser las primeras frases sin punto final, y el copete la oración que sigue. Separalos aunque estén pegados.
- Si ya trae volanta, título o copete, usalos tal cual. Si falta alguno, proponelo con lo que dice la nota (título de hasta 90 caracteres, sin exclamaciones, en mayúscula y minúscula).
- Separá bien los párrafos. Los subtítulos van en <h3>.
- Los enlaces del texto se conservan como <a href="https://…">texto</a>.
- Si al final hay una lista de fuentes o "Fuentes consultadas", sacala del texto y ponela en "fuentes".
- Proponé 3 títulos alternativos, la sección (Internacional, Argentina, Economía, Deportes, Cultura, Tecnología u Opinión) y hasta 5 etiquetas.
- "buscar_foto": 2 o 3 búsquedas para Wikimedia Commons con el NOMBRE COMPLETO de la persona, edificio o institución principal y su país (ej.: "Senado de la Nación Argentina", "Palacio del Congreso de la Nación Argentina", "Javier Milei"). Nunca una palabra sola.
${pedido ? '- Pedido del director: ' + pedido + '\n' : ''}
Nota:
"""
${texto}
"""

Formato del texto: HTML simple solo con <p>, <strong>, <em>, <h3>, <blockquote>, <ul>, <li> y <a>.
Respondé SOLO con JSON, así:
{"volanta":"...","titulo":"...","bajada":"...","cuerpo_html":"<p>...</p>","fuentes":[{"titulo":"...","url":"https://..."}],"titulos_alternativos":["...","...","..."],"seccion":"...","etiquetas":["..."],"buscar_foto":["...","..."],"correcciones":["..."]}`;
}

async function gemini(prompt, clave) {
  for (const modelo of ['gemini-flash-latest', 'gemini-flash-lite-latest', 'gemini-2.5-flash']) {
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
  let s = String(t || '').replace(/^﻿/, '').replace(/```(?:json)?/gi, '').trim();
  const a = s.indexOf('{'), z = s.lastIndexOf('}');
  if (a >= 0 && z > a) s = s.slice(a, z + 1);
  try { return JSON.parse(s); } catch {}
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

// Si ninguna IA responde: volanta y título = primeras líneas cortas, copete = la que sigue, el resto es el texto.
function ordenBasico(texto) {
  const lineas = texto.split(/\n+/).map(l => l.trim().replace(/^[*_#\s]*(volanta|t[ií]tulo|bajada|copete|texto|cuerpo)[*_\s]*:[*_\s]*/i, '')).filter(Boolean);
  let volanta = '', titulo = '', bajada = '';
  if (lineas.length > 3 && lineas[0].length <= 40 && !/[.:]$/.test(lineas[0]) && lineas[1].length <= 160 && !/\.$/.test(lineas[1])) volanta = lineas.shift();
  if (lineas.length > 1 && lineas[0].length <= 160 && !/\.$/.test(lineas[0])) titulo = lineas.shift().replace(/^#+\s*/, '');
  if (lineas.length > 1 && lineas[0].length <= 400) bajada = lineas.shift();
  return { volanta, titulo, bajada, cuerpo: lineas.join('\n\n'), correcciones: ['La IA no respondió: se separaron volanta, título, copete y párrafos por renglones. Revisalos.'] };
}

// Separa la lista final de fuentes del texto ("Fuentes:", "Fuentes consultadas:")
function separarFuentes(cuerpo) {
  const s = String(cuerpo || '');
  const m = s.match(/(?:\n|<p>|<h3>)\s*(?:<strong>|\*\*)?\s*(fuentes(?: consultadas)?|referencias)\s*:?\s*(?:<\/strong>|\*\*)?\s*:?\s*(?:<\/h3>)?([\s\S]*)$/i);
  if (!m || m[2].length > 4000) return { cuerpo: s, fuentes: [] };
  const resto = m[2].replace(/<\/?(p|ul|li|br)\s*\/?>/gi, '\n');
  return { cuerpo: s.slice(0, m.index), fuentes: normalizarFuentes(resto.split('\n')) };
}

// ---------- Fotos ----------
const VACIAS = new Set(['de', 'del', 'la', 'las', 'el', 'los', 'y', 'en', 'a', 'por', 'para', 'con', 'the', 'of', 'and', 'nacion', 'argentina', 'republica']);
const palabras = s => quitarAcentos(s).split(/[^a-z0-9ñ]+/).filter(w => w.length >= 3 && !VACIAS.has(w));

// Fotos libres de Wikimedia Commons, con autor y licencia. Solo se quedan las que nombran lo que se buscó.
async function wikimedia(consulta, maximo) {
  const params = new URLSearchParams({ action: 'query', format: 'json', origin: '*', generator: 'search', gsrnamespace: '6',
    gsrsearch: consulta + ' filetype:bitmap', gsrlimit: '12', prop: 'imageinfo|categories', cllimit: 'max', iiprop: 'url|extmetadata', iiurlwidth: '1200' });
  try {
    const r = await fetch('https://commons.wikimedia.org/w/api.php?' + params, { headers: { 'User-Agent': 'CentralDeNoticias-DiarioFederal/1.0 (contacto@diariofederal.com.ar)' } });
    if (!r.ok) return [];
    const d = await r.json();
    const claves = palabras(consulta);
    const necesarias = Math.min(claves.length, claves.length >= 2 ? 2 : 1);
    return Object.values((d.query || {}).pages || {}).map(p => {
      const ii = (p.imageinfo || [])[0] || {}; const md = ii.extmetadata || {};
      const val = k => sinEtiquetas((md[k] || {}).value);
      const url = ii.thumburl || ii.url || '';
      if (!/^https:/.test(url)) return null;
      // El nombre del archivo, su descripción o sus categorías tienen que nombrar lo buscado
      const donde = quitarAcentos([p.title, val('ImageDescription'), val('ObjectName'), val('Categories'), (p.categories || []).map(c => c.title).join(' ')].join(' '));
      const puntos = claves.filter(w => donde.includes(w)).length;
      if (!claves.length || puntos < necesarias) return null;
      return { url, pagina: ii.descriptionurl || '', fuente: 'Wikimedia Commons', libre: true, licencia: val('LicenseShortName'),
        descripcion: val('ImageDescription').slice(0, 200), busqueda: consulta, puntos, indice: p.index || 99,
        credito: 'Foto: ' + (val('Artist') || 'autor en Wikimedia') + ' / Wikimedia Commons (' + (val('LicenseShortName') || 'licencia libre') + ')' };
    }).filter(Boolean).sort((x, y) => y.puntos - x.puntos || x.indice - y.indice).slice(0, maximo || 3);
  } catch { return []; }
}

// Búsquedas a partir de la nota: instituciones conocidas y nombres propios
function busquedasDesde(titulo, bajada, cuerpo) {
  const t = [titulo, bajada, sinEtiquetas(cuerpo).slice(0, 600)].join('. ');
  const q = [];
  if (/\bsenado\b/i.test(t)) q.push('Senado de la Nación Argentina');
  if (/\bdiputados\b/i.test(t)) q.push('Cámara de Diputados de la Nación Argentina');
  if (/\bcongreso\b/i.test(t)) q.push('Palacio del Congreso de la Nación Argentina');
  if (/\bcasa rosada\b/i.test(t)) q.push('Casa Rosada Buenos Aires');
  const nombres = t.match(/\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+la\s+|de\s+|del\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+/g) || [];
  for (const n of nombres) if (!/^(El|La|Los|Las|Un|Una|En|Si|Con|Por|Diario Federal|Monitor)\b/.test(n) && !q.some(x => quitarAcentos(x).includes(quitarAcentos(n)))) q.push(n);
  return q.slice(0, 4);
}

// ---------- Handler ----------
module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') return res.status(200).json({ ok: true, ia: { gemini: !!process.env.GEMINI_API_KEY, groq: !!process.env.GROQ_API_KEY, openrouter: !!process.env.OPENROUTER_API_KEY } });
  if (req.method !== 'POST') { res.setHeader('Allow', 'GET, POST'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const origin = req.headers.origin;
  if (origin) { try { if (new URL(origin).host !== req.headers.host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' }); } catch { return res.status(403).json({ ok: false, error: 'Origen no válido.' }); } }
  const mesaToken = process.env.MESA_TOKEN;
  if (mesaToken && String(req.headers['x-mesa-token'] || '') !== mesaToken) {
    res.setHeader('X-Mesa-Auth', 'required');
    return res.status(401).json({ ok: false, code: 'TOKEN_REQUIRED', error: 'Falta la clave de la mesa o es incorrecta.' });
  }
  const b = req.body && typeof req.body === 'object' ? req.body : {};
  const original = String(b.texto || '').trim().slice(0, 30000);
  const pedido = String(b.pedido || '').trim().slice(0, 400);
  if (original.length < 120) return res.status(400).json({ ok: false, error: 'Pegá la nota completa (es muy corta para ordenarla).' });

  const r = await ordenar(original, pedido);
  return res.status(200).json(r);
};

async function ordenar(original, pedido) {
  // Primero, sin IA: código o rótulos
  let nota = leerCodigo(original), modo = nota ? 'código' : '';
  const texto = quitarCharla(original);
  if (!nota) { nota = leerRotulos(texto); if (nota) modo = 'rótulos'; }

  let ia = '', extra = {};
  if (nota) {
    ia = 'lectura directa (' + modo + ')';
  } else {
    // Texto suelto: una IA tras otra; si una responde mal, pasa a la siguiente
    const prompt = armarPrompt(texto, pedido);
    const intentos = [];
    if (process.env.GEMINI_API_KEY) intentos.push(() => gemini(prompt, process.env.GEMINI_API_KEY));
    if (process.env.GROQ_API_KEY) intentos.push(() => compatible('https://api.groq.com/openai/v1/chat/completions', process.env.GROQ_API_KEY, ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b'], prompt, 'Groq'));
    if (process.env.OPENROUTER_API_KEY) intentos.push(() => compatible('https://openrouter.ai/api/v1/chat/completions', process.env.OPENROUTER_API_KEY, ['openrouter/free'], prompt, 'OpenRouter', { 'X-Title': 'Central de noticias' }));
    intentos.push(() => compatible('https://text.pollinations.ai/openai', 'libre', ['openai'], prompt, 'IA gratuita de respaldo'));
    for (const intento of intentos) {
      let out = null;
      try { out = await intento(); } catch {}
      if (!out) continue;
      try { const x = leerJson(out.texto); if (x && x.cuerpo_html && x.titulo) { extra = x; nota = { ...x, cuerpo: x.cuerpo_html }; ia = out.ia; break; } } catch {}
    }
    if (!nota) { nota = ordenBasico(texto); ia = 'orden básico (sin IA)'; }
  }

  if (modo) { const c = await corregir(nota); if (c) { Object.assign(nota, c.nota); ia += ' · corregida con ' + c.ia; } }

  const sep = separarFuentes(String(nota.cuerpo || ''));
  const fuentes = normalizarFuentes(nota.fuentes).concat(sep.fuentes);
  const cuerpo_html = aHtml(quitarCharla(sep.cuerpo));

  // Los enlaces que están dentro del texto también van a la lista de fuentes (sin repetir)
  const vistosUrl = new Set(fuentes.map(f => f.url).filter(Boolean));
  for (const m of cuerpo_html.matchAll(/<a href="(https?:[^"]+)">([^<]*)<\/a>/g)) {
    if (!vistosUrl.has(m[1])) { vistosUrl.add(m[1]); fuentes.push({ medio: '', titulo: m[2] || m[1], url: m[1] }); }
  }

  // Fotos: hasta 6, que tengan que ver con la nota
  let busquedas = (Array.isArray(extra.buscar_foto) ? extra.buscar_foto : []).map(s => String(s).trim()).filter(s => s.split(/\s+/).length >= 2);
  busquedas = Array.from(new Set(busquedas.concat(busquedasDesde(sinEtiquetas(nota.titulo), sinEtiquetas(nota.bajada), cuerpo_html)))).slice(0, 4);
  let fotos = [];
  if (nota.foto && /^https:/.test(String(nota.foto))) {
    fotos = [{ url: String(nota.foto), credito: sinEtiquetas(nota.epigrafe) || 'Foto: indicar fuente', fuente: 'enviada con la nota', libre: false }];
  } else {
    const listas = await Promise.all(busquedas.map(q => wikimedia(q, 3)));
    const vistas = new Set();
    for (const l of listas) for (const f of l) if (!vistas.has(f.url) && fotos.length < 6) { vistas.add(f.url); fotos.push(f); }
  }

  const lista = x => (Array.isArray(x) ? x : String(x || '').split(/[,;\n]/)).map(sinEtiquetas).filter(Boolean);
  return {
    ok: true, ia, modo: modo || 'ia',
    volanta: sinEtiquetas(nota.volanta), titulo: sinEtiquetas(nota.titulo), bajada: sinEtiquetas(nota.bajada), cuerpo_html,
    fuentes,
    titulos_alternativos: lista(extra.titulos_alternativos).slice(0, 4),
    seccion: sinEtiquetas(nota.seccion), etiquetas: lista(nota.etiquetas).slice(0, 8), firma: sinEtiquetas(nota.firma),
    correcciones: lista(nota.correcciones).slice(0, 20),
    fotos, busquedas
  };
}

// Corrige solo ortografía, tildes, tipeos y puntuación. No cambia palabras, datos, citas ni enlaces.
// Si la IA no responde, o el texto cambió demasiado, se deja como estaba.
async function corregir(nota) {
  const original = { titulo: String(nota.titulo || ''), bajada: String(nota.bajada || ''), cuerpo: String(nota.cuerpo || '') };
  if (original.cuerpo.length < 80 || original.cuerpo.length > 14000) return null;
  const prompt = `Sos corrector de EL DIARIO (Argentina, español rioplatense). Corregí SOLO ortografía, tildes, tipeos, mayúsculas y puntuación de esta nota.
No cambies palabras, datos, cifras, nombres, citas ni el orden. Los enlaces [texto](https://...) y los subtítulos que empiezan con ## quedan exactamente igual. Mantené los saltos de línea.
Devolvé solo JSON: {"titulo":"...","bajada":"...","cuerpo":"...","correcciones":["qué corregiste, corto"]}

NOTA:
${JSON.stringify(original)}`;
  const intentos = [];
  if (process.env.GROQ_API_KEY) intentos.push(() => compatible('https://api.groq.com/openai/v1/chat/completions', process.env.GROQ_API_KEY, ['llama-3.3-70b-versatile'], prompt, 'Groq'));
  if (process.env.GEMINI_API_KEY) intentos.push(() => gemini(prompt, process.env.GEMINI_API_KEY));
  for (const intento of intentos) {
    let out = null; try { out = await intento(); } catch {}
    if (!out) continue;
    let x = null; try { x = leerJson(out.texto); } catch {}
    if (!x || !x.cuerpo) continue;
    const parecido = (a, b) => { a = String(a || ''); b = String(b || ''); return Math.abs(a.length - b.length) <= Math.max(12, a.length * 0.08); };
    const enlaces = t => (String(t).match(/\]\((https?:[^)\s]+)\)/g) || []).join(' ');
    if (!parecido(original.cuerpo, x.cuerpo) || enlaces(original.cuerpo) !== enlaces(x.cuerpo)) continue;
    const r = { cuerpo: x.cuerpo };
    if (x.titulo && parecido(original.titulo, x.titulo)) r.titulo = x.titulo;
    if (original.bajada && x.bajada && parecido(original.bajada, x.bajada)) r.bajada = x.bajada;
    const hechas = (Array.isArray(x.correcciones) ? x.correcciones : []).map(String).filter(Boolean);
    r.correcciones = [].concat(nota.correcciones || [], hechas.length ? hechas.map(c => 'Corregido: ' + c) : ['Ortografía revisada: sin errores.']);
    return { nota: r, ia: out.ia };
  }
  return null;
}

module.exports._prueba = { ordenar, leerCodigo, leerRotulos, quitarCharla, ordenBasico, aHtml, separarFuentes, busquedasDesde, leerJson };
