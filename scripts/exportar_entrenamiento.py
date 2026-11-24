"""Exporta las noticias del Centro de Información a un set de entrenamiento.

Lee datos/noticias.json (lo que junta el recolector) y escribe:

  - datos/entrenamiento.jsonl  (una fila JSON por noticia)
  - datos/entrenamiento.csv    (mismo contenido, para subir a Kaggle)

Columnas: texto, tema, zona, region, provincia, confianza_region, medio, fecha, url

Qué hace además de copiar:
  - Deduplica por texto (la misma nota aparece en varios medios).
  - Descarta las notas en portugués: el modelo va a ser en castellano.
  - Completa la provincia y la región con datos/provincias.json, que usa reglas
    verificables (medio provincial, dominio conocido, nombres de provincias en el texto).
  - Marca con tema "General" las que el recolector no pudo clasificar. Esas no
    sirven para entrenar tema: son el cajón de "no sé", no una categoría.

Uso:
    python scripts/exportar_entrenamiento.py
"""

import csv
import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from provincias import MapaProvincias  # noqa: E402

ORIGEN = os.path.join(BASE, "datos", "noticias.json")
SALIDA_JSONL = os.path.join(BASE, "datos", "entrenamiento.jsonl")
SALIDA_CSV = os.path.join(BASE, "datos", "entrenamiento.csv")

CAMPOS = [
    "texto",
    "tema",
    "zona",
    "region",
    "provincia",
    "confianza_region",
    "alcance",
    "idioma",
    "medio",
    "fecha",
    "url",
]

IDIOMAS_PORTUGUES = {"pt", "português", "portugues", "portugués", "portuguese"}


def limpiar(valor):
    """Saca espacios repetidos y saltos de línea."""
    return " ".join(str(valor or "").split())


def es_portugues(nota):
    idioma = normalizar_idioma(nota.get("idioma"))
    if idioma in IDIOMAS_PORTUGUES:
        return True
    medio = (nota.get("medio") or "").lower()
    return "agência brasil" in medio or "agencia brasil" in medio or "folha" in medio


def normalizar_idioma(valor):
    return limpiar(valor).lower()


def main():
    # En Windows la consola suele venir en cp1252 y rompe con acentos y símbolos.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    if not os.path.exists(ORIGEN):
        raise SystemExit(f"No existe {ORIGEN}. Corré primero el recolector.")

    with open(ORIGEN, encoding="utf-8") as f:
        datos = json.load(f)

    mapa = MapaProvincias()
    filas = []
    descartadas_pt = 0

    for nota in datos.get("rss", []):
        if es_portugues(nota):
            descartadas_pt += 1
            continue

        titulo = limpiar(nota.get("titulo"))
        resumen = limpiar(nota.get("resumen"))
        texto = (titulo + ". " + resumen).strip(". ").strip()
        if len(texto) < 20:
            continue

        medio = limpiar(nota.get("medio"))
        zona = limpiar(nota.get("zona")) or "sin-zona"
        # El campo region que ya trae la noticia manda; si está vacío, se calcula.
        region_previa = limpiar(nota.get("region"))
        provincia, region_calc, alcance = mapa.detectar(medio, zona)

        if region_previa:
            region = region_previa
            confianza = "recolector"
        elif region_calc:
            region = region_calc
            confianza = "medio"
        else:
            region = ""
            confianza = ""

        filas.append({
            "texto": texto,
            "tema": limpiar(nota.get("tema")) or "General",
            "zona": zona,
            "region": region,
            "provincia": provincia or "",
            "confianza_region": confianza,
            "alcance": alcance,
            "idioma": "es",
            "medio": medio,
            "fecha": limpiar(nota.get("fecha")),
            "url": limpiar(nota.get("url")),
        })

    # Sacar duplicados por texto (mismo titular repetido en varios medios).
    vistos = set()
    unicas = []
    for fila in filas:
        clave = fila["texto"].lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        unicas.append(fila)

    if not unicas:
        raise SystemExit("No se generó ninguna fila. Revisá datos/noticias.json.")

    with open(SALIDA_JSONL, "w", encoding="utf-8") as f:
        for fila in unicas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    with open(SALIDA_CSV, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(unicas)

    total = len(unicas)
    con_region = sum(1 for f in unicas if f["region"])
    con_provincia = sum(1 for f in unicas if f["provincia"])
    con_tema = sum(1 for f in unicas if f["tema"] != "General")

    print(f"Noticias leídas:       {len(datos.get('rss', []))}")
    print(f"Descartadas (portugués): {descartadas_pt}")
    print(f"Únicas (sin repetir):    {total}")
    print(f"Escrito: {SALIDA_JSONL}")
    print(f"Escrito: {SALIDA_CSV}")

    def pct(n):
        return f"{100 * n / total:5.1f}%"

    print("\nCobertura de etiquetas:")
    print(f"  tema (no \"General\"): {con_tema:4d}  {pct(con_tema)}")
    print(f"  provincia:         {con_provincia:4d}  {pct(con_provincia)}")
    print(f"  región:            {con_region:4d}  {pct(con_region)}")

    print("\nTema:")
    for tema, cantidad in Counter(f["tema"] for f in unicas).most_common():
        print(f"  {cantidad:4d}  {tema}")

    print("\nAlcance (la etiqueta geográfica completa):")
    for alcance, cantidad in Counter(f["alcance"] for f in unicas).most_common():
        print(f"  {cantidad:4d}  {alcance}")

    print("\nRegión (solo las etiquetadas):")
    for region, cantidad in Counter(f["region"] for f in unicas if f["region"]).most_common():
        print(f"  {cantidad:4d}  {region}")

    print("\nProvincia (solo las etiquetadas):")
    for provincia, cantidad in Counter(f["provincia"] for f in unicas if f["provincia"]).most_common():
        print(f"  {cantidad:4d}  {provincia}")

    print("\nZona:")
    for zona, cantidad in Counter(f["zona"] for f in unicas).most_common():
        print(f"  {cantidad:4d}  {zona}")


if __name__ == "__main__":
    main()
