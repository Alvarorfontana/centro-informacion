# Catálogo inicial de fuentes SIAI

Este catálogo registra fuentes institucionales, estadísticas, empresariales, sectoriales e internacionales para el Sistema Integrado de Análisis e Información.

## Estado y alcance

- Es un inventario inicial de fuentes identificadas.
- **No afirma que todas tengan API.**
- `api_documented` significa que existe documentación institucional o técnica localizada.
- `download_available` significa que la fuente publica informes o archivos descargables; todavía puede requerir extracción documental.
- `ingestion_tested: false` indica que la descarga automatizada no fue ejecutada ni validada en este commit.
- Las licencias y condiciones de reutilización deben comprobarse por conjunto de datos o documento.

## Estructura

El archivo `fuentes-v1.json` contiene para cada fuente:

- identificador estable;
- entidad publicadora y tipo de fuente;
- sectores y temas;
- modalidad de acceso y formatos;
- URL de consulta o documentación;
- periodicidad y licencia, cuando se conocen;
- estado de verificación y notas de procedencia.

## Próximas etapas técnicas

1. Verificar endpoints y formatos con consultas reales, respetando límites de uso.
2. Implementar conectores separados por modalidad: API/JSON, CSV, XLSX, PDF y extracción HTML/RSS.
3. Descargar muestras y conservar originales, fecha de captura, URL, checksum y metadatos.
4. Normalizar unidades, períodos, geografía y nombres de entidades sin borrar los valores originales.
5. Incorporar pruebas automáticas, monitoreo de cambios y registro de errores.
6. Ampliar el inventario a cámaras, empresas, sindicatos, universidades, centros tecnológicos, organismos provinciales e internacionales.

## Fuentes de documentación de este primer relevamiento

- Datos Argentina CKAN: https://www.datos.gob.ar/acerca/ckan
- APIs Datos Argentina: https://datosgobar.github.io/datosgobar-landing-apis/
- API BCRA: https://www.bcra.gob.ar/en/central-bank-api-catalog/
- Datos productivos: https://www.argentina.gob.ar/produccion/datos-productivos
- ADIMRA: https://www.adimra.org.ar/informes-y-comunicados
- Cámara Argentina del Acero: https://www.acero.org.ar/estadisticas/
- UIA: https://www.uia.org.ar/centro-de-estudios/1338/sectores-industriales/
- CAME: https://sistema.came.org.ar/entidades-asociadas
- Observatorio Nacional de Cámaras Empresarias: https://www.argentina.gob.ar/node/254974

## Restricciones de integración

Este catálogo es aditivo y no modifica recolectores, agentes, workflows, interfaz ni producción existentes. Los conectores deberán integrarse mediante contratos de datos versionados y mantenerse aislados hasta completar pruebas.
