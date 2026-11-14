# Centro de Información · Diario Federal

Herramienta interna de inteligencia periodística, separada del sitio público del diario.

- `index.html`: la página (noticias en vivo, regiones de Argentina, expedientes, mapa, fuentes, flujo).
- `scripts/recolectar.py`: trae titulares reales de GDELT y de los RSS de `datos/fuentes-rss.json`.
- `.github/workflows/recolectar.yml`: corre el recolector cada hora y guarda `datos/noticias.json`.
- `scripts/primicias.py`: agente de Primicias regionales. Cada hora busca hechos que cuentan dos o más diarios de provincia y ningún nacional, avisa al celular y anota cuándo los levanta un nacional (ranking de los diarios que se adelantan). Guarda `datos/primicias.json`.
- `datos/ejes.json`: la agenda que la agencia busca a propósito (Gobierno, PJ, FMI, energía, guerras…).
- `scripts/redaccion.py` + `agentes/`: los 12 agentes de redacción automática (ver `agentes/LEEME.md`).
- `.github/workflows/redaccion.yml`: corre los agentes a las 5:40 y 15:40 y guarda `datos/redaccion.json`.

Solo se guarda título, medio, fecha y enlace de cada nota, nunca el texto.
Los expedientes de la página son ejemplos hasta que se conecte la verificación.

Guías para redactar y verificar (para personas y agentes):
- `guias/estandares-editoriales.md`: fuentes, controles antes del /admin, estilo y correcciones.
- `guias/periodismo-de-investigacion.md`: método de expedientes, fuentes argentinas y acceso a la información.

Para sumar una fuente RSS: agregarla en `datos/fuentes-rss.json` y correr el workflow a mano
(pestaña Actions → Recolectar noticias → Run workflow). En "Fuentes y agencias" se ve si respondió.

## Clave de la mesa (opcional)

Los endpoints `/api/publicar` y `/api/reformular` aceptan el header `X-Mesa-Token`.
Si configurás `MESA_TOKEN` en Vercel (Settings -> Environment Variables), los endpoints
solo responden a quien tenga esa clave: la mesa la pide una vez por navegador y la guarda.
Si la variable no existe, todo sigue funcionando como antes.

## Idioma de los borradores

Los agentes escriben en castellano, así que `scripts/redaccion.py` descarta los titulares
en portugués (u otro idioma sin tildes del castellano) antes de armar el menú.
