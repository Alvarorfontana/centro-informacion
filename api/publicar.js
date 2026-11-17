// Puente seguro entre la Mesa Operativa y la API editorial de Diario Federal.
// El token vive exclusivamente como variable de entorno de Vercel; nunca se envía al navegador.
module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ ok: false, error: 'Método no permitido.' });
  }
  const origin = req.headers.origin;
  const host = req.headers.host;
  if (origin) {
    try {
      if (new URL(origin).host !== host) return res.status(403).json({ ok: false, error: 'Origen no autorizado.' });
    } catch {
      return res.status(403).json({ ok: false, error: 'Origen no válido.' });
    }
  }
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
  const token = process.env.DIARIO_ARTICULOS_API_TOKEN;
  if (!token) {
    return res.status(503).json({
      ok: false,
      code: 'PUBLISHING_NOT_CONFIGURED',
      error: 'Falta configurar DIARIO_ARTICULOS_API_TOKEN en las variables de entorno del proyecto centro-informacion.'
    });
  }
  const payload = req.body && typeof req.body === 'object' ? req.body : null;
  if (!payload || !payload.titulo || !payload.contenido_html || !['borrador', 'publicado'].includes(payload.estado)) {
    return res.status(400).json({ ok: false, error: 'El paquete editorial está incompleto o tiene un estado no válido.' });
  }
  if (payload.estado === 'publicado' && process.env.DIARIO_PERMITIR_PUBLICAR !== 'true') {
    return res.status(403).json({ ok: false, code: 'PUBLISHING_DISABLED', error: 'La publicación directa está desactivada. Activá DIARIO_PERMITIR_PUBLICAR=true después de configurar y probar el publicador.' });
  }
  // Solo los campos que acepta la API del diario: un campo de más o vacío hace rechazar la nota.
  const CAMPOS = ['titulo', 'bajada', 'categoria', 'autor', 'contenido_html', 'estado', 'slug', 'fecha', 'volanta', 'imagen_url', 'epigrafe', 'etiquetas', 'fuentes', 'video_url'];
  const limpio = {};
  for (const k of CAMPOS) {
    const v = payload[k];
    if (v === undefined || v === null || v === '' || (Array.isArray(v) && !v.length)) continue;
    limpio[k] = v;
  }
  const endpoint = process.env.DIARIO_ARTICULOS_API_URL || 'https://www.diariofederal.com.ar/api/v1/articulos';
  try {
    const upstream = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(limpio)
    });
    const raw = await upstream.text();
    let data;
    try { data = JSON.parse(raw); } catch { data = { message: raw.slice(0, 1200) }; }
    return res.status(upstream.status).json({ ok: upstream.ok, upstreamStatus: upstream.status, result: data });
  } catch (error) {
    return res.status(502).json({ ok: false, error: 'No se pudo contactar la API de Diario Federal.', detail: String(error && error.message || error) });
  }
};
