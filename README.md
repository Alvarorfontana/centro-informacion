# Centro de Información · Diario Federal

Herramienta interna de inteligencia periodística, separada del sitio público del diario.

- `index.html`: la página (noticias en vivo, regiones de Argentina, expedientes, mapa, fuentes, flujo).
- `scripts/recolectar.py`: trae titulares reales de GDELT y de los RSS de `datos/fuentes-rss.json`.
- `.github/workflows/recolectar.yml`: corre el recolector cada hora y guarda `datos/noticias.json`.

Solo se guarda título, medio, fecha y enlace de cada nota, nunca el texto.
Los expedientes de la página son ejemplos hasta que se conecte la verificación.

Guías para redactar y verificar (para personas y agentes):
- `guias/estandares-editoriales.md`: fuentes, controles antes del /admin, estilo y correcciones.
- `guias/periodismo-de-investigacion.md`: método de expedientes, fuentes argentinas y acceso a la información.

Para sumar una fuente RSS: agregarla en `datos/fuentes-rss.json` y correr el workflow a mano
(pestaña Actions → Recolectar noticias → Run workflow). En "Fuentes y agencias" se ve si respondió.
