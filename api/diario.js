// Lista de las últimas notas publicadas en Diario Federal (lee su RSS público).
// La Central y la Mesa la usan para marcar como "Publicada" lo que ya salió en el diario.
module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'public, max-age=300');
  if (req.method !== 'GET') { res.setHeader('Allow', 'GET'); return res.status(405).json({ ok: false, error: 'Método no permitido.' }); }
  const base = 'https://www.diariofederal.com.ar';
  try {
    const r = await fetch(base + '/rss.xml', { headers: { 'User-Agent': 'CentralDeNoticias-DiarioFederal' } });
    if (!r.ok) return res.status(502).json({ ok: false, error: 'El diario respondió ' + r.status });
    const xml = await r.text();
    const sacar = (b, tag) => { const m = b.match(new RegExp('<' + tag + '[^>]*>([\\s\\S]*?)</' + tag + '>')); return m ? m[1].replace(/^<!\[CDATA\[|\]\]>$/g, '').trim() : ''; };
    const ent = (t) => t.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'");
    const notas = (xml.match(/<item>[\s\S]*?<\/item>/g) || []).slice(0, 150).map((b) => {
      let url = sacar(b, 'link'); if (url && url.startsWith('/')) url = base + url;
      return { titulo: ent(sacar(b, 'title')), url, fecha: sacar(b, 'pubDate') };
    }).filter((n) => n.titulo && n.url);
    return res.status(200).json({ ok: true, notas });
  } catch (e) {
    return res.status(502).json({ ok: false, error: 'No se pudo leer el diario.' });
  }
};
