# Laboratorio neuronal SIAI — versión inicial

Este módulo agrega capacidad experimental sin modificar la página, los recolectores,
los agentes periodísticos ni los workflows existentes del Centro de Información.

## Qué incluye

- Comparación de persistencia contra regresión ridge interpretable.
- Separación cronológica entrenamiento/prueba (sin mezclar futuro con pasado).
- Métricas MAE, RMSE y R².
- Backtesting de origen móvil expansivo.
- MLP opcional en PyTorch.
- Función de pérdida residual para PINNs, que exige una ecuación física definida
  por cada aplicación. No inventa una ecuación genérica.

## Instalación

El núcleo y las pruebas utilizan únicamente Python estándar:

\`\`\`bash
python -m unittest discover -s laboratorio_neuronal -p 'test_*.py'
\`\`\`

Para entrenar la MLP opcional:

\`\`\`bash
pip install -r laboratorio_neuronal/requirements-neuronal.txt
\`\`\`

## Ejecutar un experimento

El CSV debe estar ordenado cronológicamente y contener columnas numéricas completas:

\`\`\`bash
python laboratorio_neuronal/engine.py datos/serie.csv --target produccion --features energia,empleo,inversion
\`\`\`

Para incluir una MLP PyTorch:

\`\`\`bash
python laboratorio_neuronal/engine.py datos/serie.csv --target produccion --features energia,empleo,inversion --torch-mlp
\`\`\`

## Conectar series oficiales

El conector usa la API pública de Series de Tiempo de Datos Argentina, sin credenciales.
Primero se buscan identificadores de series; después se descargan por ID:

```bash
python laboratorio_neuronal/fuentes/indec_series.py buscar "industria metalúrgica"
python laboratorio_neuronal/fuentes/indec_series.py descargar --ids ID_SERIE_1,ID_SERIE_2 --salida datos/industria/series_metalurgia.csv
```

La descarga guarda un archivo CSV y un archivo lateral `.metadata.json` con la
consulta, los identificadores y la fecha de recuperación. Antes de entrenar un
modelo hay que verificar descripción, unidad, frecuencia, cobertura y licencia
de cada serie. No mezclar series de distinta frecuencia sin una transformación
metodológica explícita.

## Límites y controles

- No descarga ni inventa datos: recibe un CSV de origen documentado.
- No modifica ni publica automáticamente resultados periodísticos.
- La regresión ridge es una referencia inicial; una red neuronal solo se considera
  útil si supera referencias simples en validación temporal.
- Las PINNs necesitan variables, unidades, condiciones de borde/iniciales y una
  ecuación de dominio validada por especialistas.
- Esta entrega no conecta todavía una fuente estadística externa ni se integra
  con la interfaz. Es un primer motor ejecutable y aislado para probar metodología.
