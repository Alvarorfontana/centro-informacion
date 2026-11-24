# Plan de IA para el Centro de Información

> Documento de trabajo. Estado: **pendiente de inicio** (idea acordada, sin implementar).
> Objetivo: sumar inteligencia al Centro de Información con costo **$0**, empezando por lo chico y útil.

## Idea central

No entrenar un modelo gigante propio (cuesta millones y no hace falta). Lo realista es un
**sistema por capas**: el archivo propio y los modelos chicos aportan la mayor parte del trabajo,
y un modelo grande abierto solo se usa al final, para profundizar sobre lo ya filtrado.

| Capa | Qué hace | Costo |
|---|---|---|
| 1. Recolección | Robots en GitHub bajan medios provinciales, Boletín Oficial y portales públicos y los guardan en una base | $0 |
| 2. Comprensión | Un modelo chico en español convierte cada texto en "huellas" de significado (embeddings) | $0 |
| 3. Archivo consultable | Millones de textos con búsqueda semántica ("¿qué se dijo del litio en Catamarca desde 2024?") | $0 |
| 4. Detección | Picos de temas por región, montos raros del Boletín, redes de quién aparece con quién | $0 |
| 5. Profundización | Un modelo grande abierto lee solo lo ya filtrado y arma hipótesis (AirLLM en la compu personal) | $0 |
| 6. Mesa | Todo visible en el Centro de Información / mesa de redacción | $0 |

## Qué es realista y qué no

- **Red neuronal chica y propia:** sí, manejable y gratis. Se parte de un modelo chico de texto en
  español ya entrenado (gratis) y se lo ajusta con las notas propias.
- **Modelo tipo Claude/LLM gigante propio:** no. Imposible a este presupuesto.
- **Tablas de números** (precios, producción, clima por día): una red suele rendir peor que
  **XGBoost**, que además entrena en minutos. Usar el método simple.
- **Imágenes** (satelitales tipo DOTS Campo, radar de minerales): conviene partir de un modelo
  **preentrenado** y ajustarlo a la zona.
- **Texto periodístico:** no hace falta entrenar desde cero; fine-tuning de un modelo chico alcanza.

## Kaggle (dónde se entrena)

- Plataforma de Google, gratuita, con computadoras potentes por internet.
- Se trabaja en un "notebook" desde el navegador, sin instalar nada local.
- GPU gratis: ~30 horas por semana. TPU: ~20 horas por semana.
- Cada sesión se corta a las ~9 horas. Las horas **se renuevan cada semana, no se acumulan**.
- Para una red chica esto sobra: entrena en minutos o pocas horas; permite probar y reentrenar varias veces.
- Flujo: subir las notas → entrenar → descargar el modelo → usarlo en los repos (liviano).

## Datos necesarios para arrancar

- Unas **pocas cientos de notas del Diario Federal** bien etiquetadas con:
  - **tema** (política, economía, sociedad, agro, etc.)
  - **provincia / región**
- Con eso se hace el primer fine-tuning y luego el modelo clasifica solo lo que entra al Centro de Información.

## Casos de uso priorizados

1. **Clasificación automática** de cada noticia por provincia y por tema.
2. **Agrupación de duplicados**: juntar las que cuentan lo mismo desde distintos medios.
3. **Alertas de picos**: avisar cuando un tema crece de golpe en una región, antes de que llegue a los medios nacionales.
4. **Boletín Oficial**: detectar contrataciones, decretos o montos fuera de lo normal (material de investigación).
5. **Redes de nombres y empresas**: extraer automáticamente quién aparece con quién en miles de notas/documentos.
6. **Búsqueda en el archivo**: preguntar en lenguaje natural sobre todo lo publicado.

## Límite ético y operativo

La IA **marca pistas, no confirma nada**. La verificación periodística sigue siendo humana.
El sistema propone; el editor decide.

## Primer paso concreto (cuando se retome)

1. Etiquetar unas pocas cientos de notas (tema + provincia).
2. Subirlas a un notebook de Kaggle y hacer el primer fine-tuning de un modelo chico en español.
3. Evaluar aciertos con una muestra aparte.
4. Si funciona, integrarlo al flujo de `datos/redaccion.json` para clasificar automáticamente.

## Pendientes / notas

- **Hecho:** `scripts/exportar_entrenamiento.py` genera `datos/entrenamiento.csv` (775 notas,
  7 clases geográficas confiables) y `docs/kaggle/entrenamiento.ipynb` entrena y evalúa.
- **Falta:** el tema no está etiquetado. El 73 % de las notas está como "General", que no es
  un tema. Ver `docs/DATASET.md`.
- Definir una taxonomía periodística real antes de entrenar tema.
- Definir dónde guardar el modelo entrenado: **Release de GitHub**, no Vercel.
- La clasificación diaria corre en **GitHub Actions**, no consume deploys.
