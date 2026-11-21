# SIAI — Sistema Integrado de Análisis e Información

**Vinculación institucional:** Diario Federal  
**Estado:** arquitectura inicial y hoja de ruta  
**Repositorio base de integración:** `Alvarorfontana/centro-informacion`  
**Criterio rector:** la investigación, la calidad de los datos y el análisis son el centro. La inteligencia artificial es una herramienta metodológica, no la identidad del sistema.

## 1. Propósito

Construir una infraestructura modular para captar, ordenar, documentar, relacionar y analizar información periodística, estadística, económica, productiva, ambiental, territorial, científica y geopolítica. El SIAI debe permitir:

- seguir acontecimientos y procesos en Argentina, América Latina y el mundo;
- combinar noticias con estadísticas, documentos, series históricas y datos geoespaciales;
- explicar relaciones entre variables y sectores;
- elaborar indicadores, análisis comparativos, mapas, informes y escenarios;
- producir investigaciones periodísticas propias con fuentes trazables y revisión editorial humana.

El SIAI no debe presentar una estimación como un dato observado ni una simulación como una predicción segura. Cada resultado debe indicar fuente, fecha, unidad, cobertura, metodología, supuestos y límites.

## 2. Áreas temáticas

### I. Economía y sistemas productivos

1. **Economía mundial y macroeconomía:** PBI, actividad, inflación, tasas, deuda, empleo, salarios, consumo, inversión, productividad y cuentas externas.
2. **Producción industrial:** producción manufacturera por país, rama y escala; capacidad instalada, productividad, empleo, costos, inversión, cadenas de valor y desarrollo metalúrgico.
3. **Agricultura, ganadería y alimentación:** cultivos, rindes, existencias, ganadería, pesca, fertilizantes, precios, comercio, seguridad alimentaria y disponibilidad de tierras.
4. **Energía y sistemas energéticos:** petróleo, gas, GNL, carbón, hidroeléctrica, nuclear, solar, eólica, biocombustibles, hidrógeno, redes, almacenamiento, demanda, oferta y costos.
5. **Minería y materiales estratégicos:** litio, cobre, hierro, aluminio, tierras raras, uranio, níquel, cobalto, reservas, extracción, refinación y cadenas de suministro.
6. **Comercio internacional y logística:** exportaciones, importaciones, aranceles, rutas marítimas, puertos, ferrocarriles, carreteras, canales, fletes, seguros y corredores bioceánicos.
7. **Finanzas y mercados:** monedas, reservas, bonos, acciones, crédito, flujos de capital, bancos centrales, futuros, commodities y riesgos financieros.

### II. Territorio y sistemas ambientales

8. **Hidrología y recursos hídricos:** cuencas, caudales, embalses, represas, aguas subterráneas, disponibilidad, sedimentos, inundaciones y sequías.
9. **Clima y cambio climático:** precipitaciones, temperaturas, ENSO (El Niño/La Niña), extremos, tendencias, pronósticos y atribución, distinguiendo escalas temporales.
10. **Suelos, biodiversidad y medioambiente:** humedad, degradación, erosión, desertificación, cobertura y uso del suelo, deforestación, incendios, emisiones, contaminación y ecosistemas.
11. **Pesca, océanos y economía marítima:** capturas, acuicultura, corrientes, temperatura del mar, ecosistemas, puertos, recursos del Atlántico Sur y pesca ilegal.
12. **Infraestructura y desarrollo territorial:** redes viales, ferroviarias, portuarias, eléctricas, agua y saneamiento, vivienda, ciudades, obras e inversión pública y privada.
13. **Riesgos y vulnerabilidad territorial:** exposición de población e infraestructura a inundaciones, sequías, incendios, olas de calor y riesgos industriales o tecnológicos.

### III. Sociedad y transformación global

14. **Geopolítica y relaciones internacionales:** potencias, bloques, conflictos, sanciones, diplomacia, seguridad energética y alimentaria, organismos multilaterales y política exterior.
15. **Demografía y población:** crecimiento, estructura etaria, migraciones, urbanización, distribución territorial y proyecciones.
16. **Trabajo y transformación social:** empleo, desempleo, informalidad, salarios, productividad laboral, calificaciones, automatización, pobreza, desigualdad y movilidad social.
17. **Ciencia, tecnología e innovación:** investigación y desarrollo, patentes, publicaciones, semiconductores, robótica, biotecnología, telecomunicaciones, IA y capacidades tecnológicas.
18. **Salud pública y sistemas sanitarios:** indicadores sanitarios, epidemiología, sistemas de salud, acceso, infraestructura y economía de la salud. El tratamiento de datos personales o sanitarios deberá respetar estrictamente la privacidad y la normativa aplicable.

### IV. Investigación e información periodística transversal

- Monitoreo nacional, regional e internacional de noticias y acontecimientos.
- Seguimiento de organismos, empresas, sectores, personas públicas y procesos.
- Expedientes temáticos que vinculen noticias, documentos, datos y antecedentes.
- Contraste de fuentes, cronologías, detección de discrepancias y trazabilidad.
- Análisis estadístico, econométrico, geoespacial y documental.
- Elaboración de informes, gráficos, mapas, alertas y propuestas de cobertura.
- Revisión editorial humana antes de publicar.

## 3. Infraestructura común

El SIAI se organizará en capas, no como 18 aplicaciones aisladas:

1. **Captación:** RSS, APIs oficiales, descargas de series, documentos, datos abiertos, imágenes satelitales y fuentes periodísticas.
2. **Registro y catálogo:** inventario de fuentes, indicadores, conjuntos de datos, licencias, cobertura, periodicidad y responsables.
3. **Almacenamiento:** PostgreSQL para datos estructurados; PostGIS para geometrías; almacenamiento de objetos para documentos, imágenes y archivos; formatos columnares como Parquet para series y grandes volúmenes cuando corresponda.
4. **Normalización y calidad:** unidades, monedas, calendarios, códigos geográficos, valores faltantes, duplicados, revisiones y metadatos.
5. **Análisis:** estadística descriptiva, econometría, series temporales, análisis espacial, modelos físicos y aprendizaje automático.
6. **Validación:** pruebas retrospectivas (backtesting), comparación con modelos de referencia, intervalos de incertidumbre, análisis de sensibilidad y registro de versiones.
7. **Presentación:** tableros, mapas, gráficos, informes y API para los productos editoriales.
8. **Publicación:** integración con Diario Federal mediante un flujo de borrador, verificación, edición y aprobación humana.

## 4. Métodos y herramientas

La selección de métodos dependerá del problema y de la calidad de los datos:

- **Estadística y econometría:** indicadores, regresiones, modelos de panel, modelos de estado, causalidad con diseños apropiados y análisis de sensibilidad.
- **Series temporales:** modelos de referencia estacionales, ETS/ARIMA y modelos multivariados; aprendizaje automático y redes neuronales solo cuando aporten mejoras demostrables.
- **PyTorch:** entrenamiento e inferencia de redes neuronales, modelos temporales, clasificación, detección de patrones y visión por computadora.
- **PINNs:** problemas donde existan ecuaciones físicas o restricciones conocidas, especialmente hidrología, dinámica de fluidos, energía y procesos industriales. No son el método general para pronosticar economía o redactar noticias.
- **GIS y teledetección:** PostGIS, raster, Sentinel, Landsat, MODIS, VIIRS, ERA5 y otros productos cuya disponibilidad, licencia y frecuencia se verifiquen.
- **Optimización:** programación matemática, simulación Monte Carlo, análisis de escenarios y optimización restringida.
- **Procesamiento de lenguaje:** clasificación temática, agrupamiento de acontecimientos, extracción de entidades, cronologías y asistencia a la redacción, siempre con referencias a las fuentes.

Ningún modelo se incorporará a producción sin comparar su desempeño con métodos simples y documentar sus limitaciones.

## 5. Fuentes de referencia a integrar progresivamente

El catálogo debe contemplar, entre otras, las siguientes instituciones y sistemas. Su inclusión en esta lista no significa que ya estén conectados ni que todas sus series tengan acceso abierto:

- **Argentina:** INDEC, BCRA, Secretaría de Energía, CAMMESA, organismos agropecuarios, Servicio Meteorológico Nacional, INA, IGN, CONAE, ministerios y provincias.
- **Economía y desarrollo:** Banco Mundial, FMI, CEPAL, OCDE, UNCTAD y bancos centrales.
- **Producción y comercio:** UNIDO, OMC/WTO, UN Comtrade, FAOSTAT y oficinas estadísticas nacionales.
- **Energía y minería:** IEA, Energy Institute, OPEP, USGS y organismos nacionales.
- **Clima y agua:** NOAA, WMO/OMM, NASA, Copernicus, ECMWF, UNESCO y servicios hidrológicos nacionales.
- **Territorio y ambiente:** FAO, UNEP, Global Forest Watch y programas satelitales públicos.
- **Población y sociedad:** ONU, OIT/ILO, UNHCR y oficinas nacionales de estadística.
- **Ciencia y tecnología:** UNESCO, WIPO y repositorios científicos abiertos.

Para cada fuente se registrarán URL o endpoint, responsable, licencia, condiciones de uso, frecuencia, cobertura temporal y geográfica, formato, fecha de última actualización y procedimiento de descarga.

## 6. Relación con los proyectos existentes

La integración será gradual y respetará la separación entre productos:

- **Centro de Información · Diario Federal:** base operativa inicial para monitoreo de noticias, regiones, expedientes, fuentes y agentes editoriales. Ya dispone de recolector GDELT/RSS, agenda temática y agentes que generan borradores; debe evolucionar hacia expedientes enriquecidos con datos y fuentes estadísticas.
- **Diario Federal (sitio público):** seguirá siendo el producto editorial y de publicación. No se modificará como parte de esta primera etapa.
- **Observatorio Agro:** conservará su especialización agroambiental y geoespacial; aportará indicadores y análisis al SIAI mediante interfaces documentadas.
- **Investigación industrial y metalúrgica:** tendrá un módulo sectorial de producción, capacidad instalada, empleo, comercio, energía, inversión y productividad.
- **Diario Federal Studio:** seguirá siendo el entorno de producción audiovisual, reutilizando investigaciones e informes aprobados.

Los repositorios y despliegues actuales no se fusionarán ni reemplazarán. La interoperabilidad se resolverá mediante API, contratos de datos y exportaciones versionadas.

## 7. Primer producto operativo: SIAI v0.1

El primer incremento debe ser útil y verificable antes de entrenar modelos complejos:

1. Catálogo de las 18 áreas, subáreas, indicadores y fuentes.
2. Registro normalizado de series con unidad, frecuencia, geografía y período.
3. Panel inicial de economía, producción, energía, agroclima e hidrología.
4. Expedientes periodísticos que conecten acontecimientos con indicadores y documentos.
5. Comparación histórica y entre países cuando las series sean comparables.
6. Fichas metodológicas y control de calidad para cada indicador.
7. Exportación de gráficos, tablas e informes para la mesa editorial.

### Casos demostradores

- **Economía e industria argentina:** producción, capacidad instalada, empleo, salarios, energía, importaciones y exportaciones, con foco inicial en metalurgia.
- **Sequía y producción agropecuaria:** ENSO, precipitaciones, humedad del suelo, estado de cultivos, rindes y exportaciones.
- **Cuenca del Plata:** precipitaciones, caudales, niveles de ríos, embalses, alertas y exposición territorial.
- **Energía y actividad económica:** generación, demanda, fuentes, costos y relación con actividad industrial.
- **Producción global:** comparar producción industrial, comercio y cadenas de suministro de países seleccionados.

## 8. Reglas de calidad y publicación

- Diferenciar claramente dato observado, estimación, escenario y pronóstico.
- No completar vacíos con cifras inventadas ni presentar datos sintéticos como reales.
- Conservar fuente, fecha de consulta, versión, unidad y metodología.
- Documentar cambios metodológicos y revisiones de series.
- Mostrar incertidumbre y limitaciones cuando corresponda.
- Evitar afirmaciones causales a partir de correlaciones simples.
- Mantener trazabilidad desde el gráfico o párrafo hasta el dato de origen.
- No publicar automáticamente: la decisión editorial final corresponde a una persona.
- Respetar licencias, privacidad, derechos de autor y condiciones de uso de cada fuente.

## 9. Hoja de ruta

### Fase 0 — Inventario y diseño
- Auditar los repositorios y módulos existentes.
- Definir contratos de datos, identificadores, catálogo y arquitectura de API.
- Priorizar fuentes verificables y evaluar sus condiciones de acceso.

### Fase 1 — Base común
- Construir el catálogo de fuentes e indicadores.
- Normalizar series históricas y metadatos.
- Incorporar controles de calidad, registros de actualización y trazabilidad.

### Fase 2 — Primeros tableros
- Economía e industria.
- Agroclima y suelo.
- Hidrología y energía.
- Comparaciones internacionales de producción y comercio.

### Fase 3 — Modelos y simulaciones
- Establecer modelos estadísticos de referencia.
- Implementar backtesting y evaluación.
- Incorporar PyTorch en problemas donde mejore resultados.
- Probar PINNs en casos físicos bien definidos y con datos suficientes.

### Fase 4 — Integración periodística
- Vincular acontecimientos con series e indicadores.
- Crear expedientes de investigación reutilizables.
- Generar gráficos e informes con fuentes citadas.
- Incorporar el flujo de revisión y aprobación editorial.

### Fase 5 — Ampliación internacional
- Agregar áreas y países según disponibilidad y calidad de datos.
- Desarrollar análisis comparativos, escenarios y productos especializados.

## 10. Criterio de éxito

El SIAI estará aportando valor cuando pueda responder preguntas periodísticas y de investigación con datos rastreables, series comparables, métodos explícitos y resultados reproducibles; cuando detecte relaciones que merezcan investigación; y cuando reduzca el tiempo entre la aparición de un acontecimiento, su análisis y la publicación de una explicación sólida.

**Principio final:** primero fuentes y datos confiables; después métodos adecuados; luego análisis y simulación; finalmente comunicación periodística clara y responsable.
