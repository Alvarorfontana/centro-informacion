# Mesa de Redacción Operativa — Diario Federal

## Alcance incorporado

La página `/mesa-redaccion-operativa.html` agrega una mesa editorial local-first sin reemplazar la mesa original ni los módulos del Centro de Información.

Incluye:
- Bandeja de notas y edición de sección, título, bajada, firma, etiquetas y cuerpo.
- Flujo de estados: Borrador IA, En edición, Para revisión, Aprobada, Programada, Publicada y Archivada.
- Asignación de responsable y fecha de entrega.
- Historial de hasta 30 versiones por nota y restauración de una versión.
- Biblioteca multimedia local con créditos/epígrafes.
- Importación del JSON producido por los agentes desde `datos/redaccion.json`.
- Exportación de respaldo JSON, nota HTML y paquete JSON compatible con el contrato de publicación del Diario Federal.
- Sanitización del HTML admitido al guardar y al previsualizar.

## Persistencia y costos

Esta versión no crea recursos, no usa Vercel Blob, no agrega servicios externos y no genera costos de infraestructura. Los datos se guardan en el almacenamiento local del navegador. Por ello, no se comparten automáticamente entre computadoras o integrantes de la redacción. Exportar respaldos permite trasladar datos manualmente.

El historial local no equivale todavía a un registro central e inmutable de Git. No se afirma que exista colaboración multiusuario.

## Integración de publicación existente

El repositorio del Diario Federal contiene el endpoint `POST /api/v1/articulos`. La implementación requiere un token Bearer y variables de entorno de servidor para el repositorio de destino. La Mesa Operativa no guarda ni solicita esos secretos en el navegador: prepara un paquete JSON para integración segura posterior. No publica automáticamente.

## Próximos pasos técnicos sin costo adicional

1. Configurar en el servidor existente la autenticación de la mesa y el uso de la API de publicación, sin exponer credenciales al navegador.
2. Diseñar persistencia compartida con GitHub Actions/archivos versionados, respetando cuotas gratuitas y evitando operaciones destructivas.
3. Incorporar control de concurrencia para evitar que dos editores sobrescriban cambios.
4. Validar publicación en entorno de prueba antes de habilitar publicación efectiva.

## Acceso

Desde `centro-mando.html`, elegir “Mesa operativa avanzada”. La Mesa de Redacción original permanece disponible.
