# Dataset de entrenamiento

Estado: **primera versión generada desde `datos/noticias.json`**. Sirve para entrenar
el clasificador geográfico. **No sirve todavía para clasificar tema.**

Se regenera con:

```bash
python scripts/exportar_entrenamiento.py
```

Salidas:

| Archivo | Para qué |
|---|---|
| `datos/entrenamiento.csv` | Subir a Kaggle como Dataset. Codificado en UTF-8 con BOM (abre bien en Excel). |
| `datos/entrenamiento.jsonl` | Mismo contenido, una nota por línea. Para scripts. |

## Columnas

| Columna | Qué es | Origen |
|---|---|---|
| `texto` | Título + resumen de la nota | `noticias.json` |
| `tema` | Tema asignado por el recolector | reglas de palabras clave |
| `zona` | argentina / mercosur / mundo | recolector |
| `region` | Región si la nota es provincial; vacío si no | recolector o mapa de medios |
| `provincia` | Provincia, solo si hay evidencia | `datos/provincias.json` |
| `confianza_region` | `recolector` / `medio` / vacío | — |
| `alcance` | **Etiqueta geográfica completa**: una de las 5 regiones, `nacional`, `mercosur` o `mundo` | derivada de `zona` + medio |
| `idioma` | Siempre `es`: las notas en portugués se descartan | — |
| `medio`, `fecha`, `url` | Metadatos | recolector |

## Qué quedó bien: `alcance`

775 notas, 7 clases, **100 % de cobertura**:

| Clase | Notas |
|---|---|
| mundo | 306 |
| nacional | 190 |
| norte-grande | 146 |
| patagonia | 68 |
| cuyo | 25 |
| buenos-aires | 20 |
| centro | 20 |

La etiqueta se construye con **evidencia dura**, no con adivinanza: se mira qué medio
publica. Si es un diario provincial (`La Gaceta (Tucumán)`), la nota va a esa provincia.
Si es un medio nacional (`Clarín`), la nota es de alcance `nacional`.

Eso último no es un hueco: una nota sobre el presupuesto nacional **no pertenece a
ninguna provincia**. `nacional` es una respuesta correcta y frecuente.

## Qué quedó mal: `tema`

| Tema | Notas |
|---|---|
| **General** | **563 (73 %)** |
| Geopolítica | 87 |
| Política | 52 |
| Economía | 23 |
| Sociedad | 18 |
| Energía | 18 |
| Agro y clima | 14 |

`General` **no es un tema**: es el cajón de "no lo pude clasificar". El recolector usa
reglas de palabras clave y lo que no matchea cae ahí. Entrenar con esto produce un
modelo que aprende a decir "General" y acierta el 73 % por la razón equivocada.

Por eso el notebook **descarta las `General`** cuando la tarea es `tema`, y deja solo
212 notas. Con 212 notas y 6 clases el resultado va a ser flojo, y así debe informarse.

## Una decisión que conviene no revertir

**No se busca el nombre de la provincia en el texto.** Se probó y daba etiquetas falsas:

- una nota sobre Puerto Rico quedó como `San Juan`,
- una nota sobre un accidente en Adamuz (España) quedó como `Córdoba`.

`Córdoba`, `Santa Fe`, `Mendoza`, `San Juan` y `La Rioja` son también ciudades de
España, Estados Unidos y Puerto Rico. Un dataset con etiquetas inventadas es peor que
no tener dataset, porque el modelo aprende el error y lo repite con seguridad.

Si se quiere más cobertura geográfica, el camino correcto es **ampliar la tabla
`medios` / `dominios` de `datos/provincias.json`** con medios provinciales reales, no
afojar la regla.

## Próximo paso

1. Entrenar `alcance` en Kaggle con `docs/kaggle/entrenamiento.ipynb` y comparar contra
   la línea de base. Si gana, ya hay valor: el Centro de Información puede ordenar por
   región sin que nadie lo haga a mano.
2. Para `tema`: definir una taxonomía periodística real (las secciones del diario), y
   etiquetar las 563 `General`. Se puede ayudar con IA sobre lotes chicos, pero la
   revisión de una muestra tiene que ser humana.
3. Recién con etiquetas buenas tiene sentido entrenar tema.

## Lo que no hay que hacer

- No entrenar `tema` incluyendo `General` y festejar el 73 % de acierto.
- No publicar el modelo en Vercel: va a un *Release* de GitHub o queda local.
- No usar el modelo para decidir publicación. Marca pistas y ordena; la verificación
  sigue siendo humana.
