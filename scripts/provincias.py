"""
Etiqueta provincia y región de una noticia argentina, sin inventar nada.

La regla es una sola y es verificable: se mira QUIÉN publica. Si el diario es
provincial, la nota va a esa provincia; si es nacional, la nota es de alcance
nacional. No se busca el nombre de la provincia en el texto a propósito:
"Córdoba", "San Juan", "Santa Fe" y "Mendoza" son también ciudades de España,
Puerto Rico y Estados Unidos, y eso generaba etiquetas falsas (una nota de
Puerto Rico terminaba como "San Juan").

Cuando no hay provincia, el alcance queda "nacional". Es una etiqueta real, no
un hueco: una nota sobre el presupuesto nacional no pertenece a ninguna provincia.

Uso desde otro script:

    from provincias import MapaProvincias
    mapa = MapaProvincias()
    provincia, region, alcance = mapa.detectar("La Gaceta (Tucumán)", "argentina")
    # -> ("Tucumán", "norte-grande", "norte-grande")

    provincia, region, alcance = mapa.detectar("Clarín", "argentina")
    # -> (None, None, "nacional")

    provincia, region, alcance = mapa.detectar("Anadolu (castellano)", "mundo")
    # -> (None, None, "mundo")
"""

import json
import os
import re
import unicodedata

RUTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos", "provincias.json"
)


def normalizar(texto):
    """Minúsculas, sin acentos y sin signos raros, para comparar nombres."""
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


class MapaProvincias:
    def __init__(self, ruta=RUTA):
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)

        self.provincia_de_region = {}
        for region, provincias in datos.get("regiones", {}).items():
            for provincia in provincias:
                self.provincia_de_region[normalizar(provincia)] = {
                    "provincia": provincia,
                    "region": region,
                }

        self.medios = {normalizar(k): v for k, v in (datos.get("medios") or {}).items()}
        self.dominios = {normalizar(k): v for k, v in (datos.get("dominios") or {}).items()}
        self.medios_nacionales = {
            normalizar(m) for m in (datos.get("medios_nacionales") or [])
        }

    def provincia(self, medio):
        """Devuelve la provincia del medio, o None si no es un medio provincial conocido."""
        clave = normalizar(medio)
        return self.medios.get(clave) or self.dominios.get(clave)

    def es_nacional(self, medio):
        return normalizar(medio) in self.medios_nacionales

    def region_de(self, provincia):
        dato = self.provincia_de_region.get(normalizar(provincia))
        return dato["region"] if dato else None

    def detectar(self, medio, zona):
        """Devuelve (provincia, region, alcance).

        alcance: una de las cinco regiones, "nacional" o "mundo".
        """
        provincia = self.provincia(medio)
        if provincia:
            region = self.region_de(provincia)
            if region:
                return provincia, region, region

        if normalizar(zona) == "mundo":
            return None, None, "mundo"
        if normalizar(zona) == "mercosur":
            return None, None, "mercosur"
        return None, None, "nacional"
