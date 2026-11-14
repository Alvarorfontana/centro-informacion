# Integración de Mesa Operativa

## Entrada de agentes
La mesa consulta `/datos/redaccion.json`, el mismo archivo que publica el Centro de Información. Al abrirla carga los borradores y conserva títulos alternativos, bajadas, cuerpo HTML, fuentes, fotos, créditos y verificación. El botón **Sincronizar agentes** vuelve a consultar el feed.

Los borradores nuevos se incorporan a la bandeja. Las notas que el editor ya modificó no se sobrescriben automáticamente.

## Salida al sitio Diario Federal
La mesa envía los paquetes a `/api/publicar`. El puente se ejecuta en Vercel y guarda el token solo en el servidor; nunca en el navegador.

### Variables necesarias en Vercel

En el proyecto `centro-informacion`:
- `DIARIO_ARTICULOS_API_TOKEN`: mismo valor que `ARTICULOS_API_TOKEN` configurado en el proyecto `diario`.
- `DIARIO_ARTICULOS_API_URL`: opcional; por defecto `https://www.diariofederal.com.ar/api/v1/articulos`.
- `DIARIO_PERMITIR_PUBLICAR`: dejar sin activar hasta probar el envío de borradores; para habilitar publicación real debe ser `true`.

En el proyecto Vercel `diario`, la API existente necesita:
- `ARTICULOS_API_TOKEN`
- `PUBLICACION_GITHUB_TOKEN` o `GITHUB_PAT`
- `PUBLICACION_GITHUB_REPO`
- `PUBLICACION_GITHUB_BRANCH`
- `PUBLICACION_PERMITIR_PUBLICAR=true` solo cuando se autorice la publicación real.

No colocar tokens en HTML, JavaScript del navegador, archivos del repositorio ni mensajes de chat. Después de cargar variables en Vercel, redeplegar ambos proyectos.

## Límites actuales
La edición y el historial de la mesa siguen siendo locales al navegador. No hay guardado central multiusuario ni colaboración simultánea. El puente de publicación queda instalado, pero no puede enviar hasta que se configuren los secretos indicados y se pruebe primero con borradores.
