#!/usr/bin/env python3
"""
"Lo más cubierto": agrupa las notas que cuentan el mismo hecho en distintos medios y las ordena por importancia.

Idea tomada de Horizon (radar de noticias de código abierto), pero sin IA: reglas declaradas y verificables.
  1. Agrupar: dos titulares son el mismo hecho si comparten buena parte de sus palabras importantes
     (similitud de Jaccard sobre raíces de palabras, umbral UMBRAL).
  2. Puntuar cada grupo:
       + 3 por cada medio distinto que lo cuenta  (cuantos más medios, más importante)
       + 2 por cada país distinto                 (repercusión internacional)
       + 1 por cada agencia                       (las agencias marcan agenda)
       + 2 si toca una región argentina            (prioridad federal del diario)
       - 1 por cada 6 horas de antigüedad de la nota más nueva (lo viejo baja)
  3. Solo entran los grupos con al menos MIN_MEDIOS medios distintos.

No lee ni guarda el texto de las notas: trabaja solo con los titulares que ya trae recolectar.py.
"""

import re
import unicodedata
from datetime import datetime, timezone

UMBRAL = 0.28
MIN_MEDIOS = 2
MAXIMO = 40

VACIAS = set("""
para como pero porque sobre entre desde hasta tras ante cuando donde quien quienes cual cuales este esta estos estas
ese esa esos esas aquel tiene tienen tener hace hacen hizo dice dijo segun luego ahora todo todos toda todas otro otra
otros otras mismo misma puede pueden sera seran fueron habia hasta tambien solo sólo mucho muchos mientras contra
nuevo nueva nuevos nuevas despues antes cada sigue siguen ademas casi menos mas muy años anos ayer hoy manana
enero febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre
lunes martes miercoles jueves viernes sabado domingo semana
the and with from that this have will after over about their para pela pelo com uma dos das nos nas
""".split())


def _sin_acentos(t):
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower()


def raices(titulo):
    """Palabras importantes del titular, recortadas a 6 letras para que 'aumentó' y 'aumentos' coincidan."""
    palabras = re.findall(r"[a-z0-9]+", _sin_acentos(titulo))
    return {p[:6] for p in palabras if len(p) >= 4 and not p.isdigit() and p not in VACIAS}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _horas(iso, ahora):
    try:
        return max(0.0, (ahora - datetime.fromisoformat(iso)).total_seconds() / 3600)
    except Exception:  # noqa: BLE001
        return 48.0


def agrupar(notas, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    notas = [n for n in notas if n.get("titulo") and n.get("url")]
    claves = [raices(n["titulo"]) for n in notas]

    # unión de conjuntos: si A se parece a B y B a C, los tres son el mismo hecho
    padre = list(range(len(notas)))

    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i in range(len(notas)):
        if len(claves[i]) < 3:
            continue
        for j in range(i + 1, len(notas)):
            if len(claves[j]) >= 3 and jaccard(claves[i], claves[j]) >= UMBRAL:
                padre[raiz(i)] = raiz(j)

    grupos = {}
    for i, n in enumerate(notas):
        grupos.setdefault(raiz(i), []).append(n)

    salida = []
    for miembros in grupos.values():
        medios = {m.get("medio") for m in miembros if m.get("medio")}
        if len(medios) < MIN_MEDIOS:
            continue
        # una nota por medio, la más reciente
        por_medio = {}
        for m in sorted(miembros, key=lambda x: x.get("fecha") or "", reverse=True):
            por_medio.setdefault(m.get("medio"), m)
        unicas = list(por_medio.values())
        paises = {m.get("pais") for m in unicas if m.get("pais")}
        agencias = sum(1 for m in unicas if "Agencia" in (m.get("tipo") or ""))
        regiones = [m.get("region") for m in unicas if m.get("region")]
        # la región cuenta solo si la nombra más de la mitad de los medios
        region = max(set(regiones), key=regiones.count) if regiones else None
        if region and regiones.count(region) * 2 <= len(unicas):
            region = None
        temas = [m.get("tema") for m in unicas if m.get("tema") and m.get("tema") != "General"]
        tema = max(set(temas), key=temas.count) if temas else "General"
        mas_nueva = max((m.get("fecha") or "" for m in unicas), default="")
        horas = _horas(mas_nueva, ahora) if mas_nueva else 48.0
        detalle = {
            "medios": 3 * len(unicas), "paises": 2 * len(paises), "agencias": agencias,
            "region": 2 if region else 0, "antiguedad": -round(horas / 6, 1),
        }
        puntaje = round(sum(detalle.values()), 1)
        # el titular que representa al grupo: el que más palabras comparte con los demás
        claves_g = [raices(m["titulo"]) for m in unicas]
        idx = max(range(len(unicas)), key=lambda k: sum(jaccard(claves_g[k], c) for c in claves_g))
        salida.append({
            "titulo": unicas[idx]["titulo"],
            "puntaje": puntaje,
            "detalle": detalle,
            "n_medios": len(unicas),
            "paises": sorted(paises),
            "region": region,
            "zona": unicas[idx].get("zona"),
            "tema": tema,
            "ultima": mas_nueva or None,
            "notas": [{k: m.get(k) for k in ("titulo", "url", "medio", "pais", "fecha", "tipo", "via", "region", "zona", "tema", "idioma", "resumen")}
                      for m in sorted(unicas, key=lambda x: x.get("fecha") or "", reverse=True)],
        })

    salida.sort(key=lambda g: g["puntaje"], reverse=True)
    return salida[:MAXIMO]


def todas_las_notas(datos):
    notas = []
    for r in datos.get("regiones", {}).values():
        notas.extend(r.get("notas", []))
    for z in datos.get("zonas", {}).values():
        notas.extend(z.get("notas", []))
    notas.extend(datos.get("rss", []))
    return notas


if __name__ == "__main__":
    # Prueba local sobre el último datos/noticias.json
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).resolve().parent.parent / "datos" / "noticias.json").read_text(encoding="utf-8"))
    ref = datetime.fromisoformat(d["generado"])
    for g in agrupar(todas_las_notas(d), ahora=ref)[:15]:
        print(f"{g['puntaje']:5.1f}  {g['n_medios']} medios  [{g['tema']}/{g['region'] or g['zona']}]  {g['titulo'][:90]}")
        for n in g["notas"][:4]:
            print(f"         · {n['medio']}: {n['titulo'][:80]}")
