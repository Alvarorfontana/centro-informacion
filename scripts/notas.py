"""
Dos ayudas que comparten los scripts que trabajan con noticias.

Se pusieron acá para no duplicarlas ni crear imports cruzados raros entre
exportar_entrenamiento.py y etiquetar_temas.py.
"""

import hashlib

IDIOMAS_PORTUGUES = {"pt", "português", "portugues", "portugés", "portuguese"}


def limpiar(valor):
    """Saca espacios repetidos y saltos de línea."""
    return " ".join(str(valor or "").split())


def clave_nota(nota):
    """Identificador estable de una noticia, para no repetir trabajo entre corridas.

    Usa la URL, que es lo más estable. Si no hay URL, cae al título.
    """
    url = limpiar(nota.get("url"))
    if url:
        return url
    return "sha1:" + hashlib.sha1(limpiar(nota.get("titulo")).encode("utf-8")).hexdigest()


def es_portugues(nota):
    """El modelo que entrenamos es en castellano: las notas en portugués no sirven."""
    if limpiar(nota.get("idioma")).lower() in IDIOMAS_PORTUGUES:
        return True
    medio = limpiar(nota.get("medio")).lower()
    return "agência brasil" in medio or "agencia brasil" in medio or "folha" in medio
