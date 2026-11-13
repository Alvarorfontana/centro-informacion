#!/usr/bin/env python3
"""
Recolector del Centro de Información de Diario Federal.

Lo corre GitHub Actions cada hora (.github/workflows/recolectar.yml). Trae:
  1. GDELT (gratis y abierto): noticias de medios argentinos por región del país,
     del Mercosur y del mundo, más el volumen diario de menciones de cada región.
  2. RSS de agencias y medios (datos/fuentes-rss.json): solo título, enlace, fecha
     y medio. No se copia el texto de las notas.

Escribe datos/noticias.json, que lee la página. Cada fuente queda con su estado
(funciona / falla) para saber qué está conectado de verdad.
"""

import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
AGENTE = "Mozilla/5.0 (CentroInformacion; uso periodistico)"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"

# Mismas regiones que usa el sitio del diario (src/lib/regiones.ts).
REGIONES = {
    "norte-grande": {"nombre": "Norte Grande", "detalle": "NEA y NOA",
        "consulta": '(Corrientes OR Misiones OR Chaco OR Formosa OR Jujuy OR Salta OR Tucuman OR Catamarca OR "Santiago del Estero" OR "La Rioja")'},
    "centro": {"nombre": "Centro", "detalle": "Córdoba, Santa Fe y Entre Ríos",
        "consulta": '(Cordoba OR "Santa Fe" OR "Entre Rios" OR Rosario OR Parana)'},
    "cuyo": {"nombre": "Cuyo", "detalle": "Mendoza, San Juan y San Luis",
        "consulta": '(Mendoza OR "San Juan" OR "San Luis")'},
    "patagonia": {"nombre": "Patagonia", "detalle": "De La Pampa a Tierra del Fuego",
        "consulta": '(Neuquen OR "Rio Negro" OR Chubut OR "Santa Cruz" OR "Tierra del Fuego" OR "La Pampa" OR Bariloche OR "Vaca Muerta")'},
    "buenos-aires": {"nombre": "Buenos Aires", "detalle": "Provincia y Ciudad",
        "consulta": '(bonaerense OR Kicillof OR "La Plata" OR "Mar del Plata" OR "Bahia Blanca" OR conurbano OR "Jorge Macri")'},
}
ZONAS = {
    "nacional": {"nombre": "Argentina · nacional", "consulta": '(Milei OR Congreso OR "Casa Rosada" OR gobernadores OR inflacion) sourcecountry:AR'},
    "mercosur": {"nombre": "Mercosur y región", "consulta": '(Mercosur OR Lula OR Brasil OR Paraguay OR Uruguay OR Bolivia OR Chile) sourcelang:spanish'},
    "mundo": {"nombre": "Mundo", "consulta": '(guerra OR elecciones OR "Naciones Unidas" OR China OR "Estados Unidos" OR Europa) sourcelang:spanish'},
}

# Región del mundo según el país del medio (GDELT da el país en inglés; los RSS, en castellano).
REGIONES_MUNDO = {
    "América Latina": ["Argentina", "Brasil", "Brazil", "Uruguay", "Paraguay", "Bolivia", "Chile", "Peru", "Perú", "Colombia", "Venezuela", "Ecuador",
                       "Mexico", "México", "Cuba", "Dominican Republic", "República Dominicana", "Guatemala", "Honduras", "El Salvador", "Nicaragua",
                       "Costa Rica", "Panama", "Panamá", "Puerto Rico"],
    "Norteamérica": ["United States", "Estados Unidos", "Canada", "Canadá"],
    "Europa": ["Spain", "España", "France", "Francia", "Germany", "Alemania", "United Kingdom", "Reino Unido", "Italy", "Italia", "Portugal", "Belgium",
               "Netherlands", "Switzerland", "Austria", "Poland", "Ukraine", "Ucrania", "Russia", "Rusia", "Sweden", "Norway", "Ireland", "Greece"],
    "Medio Oriente": ["Israel", "Iran", "Irán", "Turkey", "Turquía", "Qatar", "Catar", "Saudi Arabia", "United Arab Emirates", "Lebanon", "Syria", "Iraq", "Egypt", "Egipto"],
    "Asia": ["China", "Japan", "Japón", "Corea del Sur", "South Korea", "India", "Vietnam", "Indonesia", "Philippines", "Singapore", "Pakistan", "Taiwan"],
    "África": ["South Africa", "Sudáfrica", "Nigeria", "Kenya", "Morocco", "Marruecos", "Algeria", "Angola", "Ethiopia"],
    "Oceanía": ["Australia", "New Zealand", "Nueva Zelanda", "Fiji"],
}
PAIS_A_REGION = {p: r for r, ps in REGIONES_MUNDO.items() for p in ps}

# Agenda de la agencia (datos/ejes.json): temas que se buscan a propósito y sirven para marcar las notas.
try:
    EJES = json.loads((DATOS / "ejes.json").read_text(encoding="utf-8")).get("ejes", [])
except Exception:  # noqa: BLE001
    EJES = []


def ejes_de(texto):
    """Ejes de la agenda que toca un titular. Las siglas (PJ, PASO, FMI) se buscan respetando mayúsculas."""
    plano = sin_acentos(texto)
    hallados = []
    for e in EJES:
        for p in e.get("palabras", []):
            if p.isupper():
                ok = re.search(r"\b" + re.escape(p) + r"\b", texto)
            else:
                ok = re.search(r"\b" + re.escape(sin_acentos(p).lower()) + r"\b", plano.lower())
            if ok:
                hallados.append(e["id"]); break
    return hallados


# Palabras para asignar región a las notas que llegan por RSS (como deducirRegion del diario).
CLAVES = {
    "norte-grande": ["Corrientes", "Misiones", "Chaco", "Formosa", "Jujuy", "Salta", "Tucuman", "Catamarca", "Santiago del Estero", "La Rioja", "Posadas", "Resistencia", "NEA", "NOA", "Norte Grande"],
    "centro": ["Cordoba", "Santa Fe", "Entre Rios", "Rosario", "Llaryora", "Pullaro", "Frigerio"],
    "cuyo": ["Mendoza", "San Juan", "San Luis", "Cornejo", "Cuyo"],
    "patagonia": ["Neuquen", "Rio Negro", "Chubut", "Santa Cruz", "Tierra del Fuego", "La Pampa", "Bariloche", "Ushuaia", "Vaca Muerta", "Patagonia"],
    "buenos-aires": ["bonaerense", "Kicillof", "La Plata", "Mar del Plata", "Bahia Blanca", "Conurbano", "conurbano", "CABA", "Ciudad de Buenos Aires"],
}
TEMAS = {
    "Política": ["Milei", "Congreso", "Senado", "Diputados", "gobernador", "elecciones", "peronismo", "Kicillof", "ministro", "presidente"],
    "Economía": ["inflacion", "dolar", "FMI", "economia", "precios", "salarios", "reservas", "exportaciones", "Mercosur"],
    "Energía": ["Vaca Muerta", "petroleo", "gas", "litio", "energia", "YPF", "mineria", "electricidad"],
    "Agro y clima": ["cosecha", "soja", "trigo", "sequia", "lluvias", "crecida", "inundacion", "Parana", "clima", "campo"],
    "Sociedad": ["paro", "sindicato", "CGT", "protesta", "salud", "educacion", "universidad", "jubilados"],
    "Geopolítica": ["guerra", "China", "Estados Unidos", "Rusia", "Ucrania", "Israel", "OTAN", "ONU", "Trump"],
}


def sin_acentos(t):
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode()


def region_de(texto):
    # "calle/avenida Corrientes" es Buenos Aires, no la provincia
    t = re.sub(r"\b(calle|avenida|av\.)\s+Corrientes", "Buenos Aires", sin_acentos(texto), flags=re.I)
    mejor, puntos = None, 0
    for r, claves in CLAVES.items():
        n = sum(len(re.findall(r"\b" + re.escape(c) + r"\w*", t)) for c in claves)
        if n > puntos:
            mejor, puntos = r, n
    return mejor


def tema_de(texto):
    t = sin_acentos(texto).lower()
    mejor, puntos = "General", 0
    for tema, claves in TEMAS.items():
        n = sum(1 for c in claves if sin_acentos(c).lower() in t)
        if n > puntos:
            mejor, puntos = tema, n
    return mejor


def pedir(url, intentos=3):
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(6 * (i + 1))
    raise ultimo


def gdelt(consulta, modo="artlist", periodo="3d", maximo=40):
    params = {"query": consulta, "mode": modo, "format": "json", "timespan": periodo, "sort": "datedesc"}
    if modo == "artlist":
        params["maxrecords"] = str(maximo)
    url = GDELT + "?" + urllib.parse.urlencode(params)
    crudo = pedir(url)
    time.sleep(6)  # GDELT pide no más de una consulta cada 5 segundos
    try:
        return json.loads(crudo.decode("utf-8", "ignore"))
    except json.JSONDecodeError:
        # GDELT contesta texto plano cuando la consulta no le gusta
        raise ValueError(crudo.decode("utf-8", "ignore")[:200])


def fecha_gdelt(s):
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return None


# Deportes y espectáculos no sirven para la agenda del diario: se descartan.
RUIDO = re.compile(r"\b(f[uú]tbol|torneo|goles?|gan[oó] \d|partido de|copa (argentina|libertadores|sudamericana)|selecci[oó]n argentina de|"
                   r"tenis|f[oó]rmula 1|automovilismo|rally|entrenador|t[eé]cnico de la selecci[oó]n|manchester|real madrid|barcelona fc|nations league|champions league|copa de campeones|camiseta|mundial de clubes|rugby|los pumas|las leonas|v[oó]ley|b[aá]squet|hockey|boxeo|golf|boca juniors|river plate|clausura|apertura 20\d\d|playoffs?|serie a|premier league|la liga|nba|"
                   r"espect[aá]culos?|far[aá]ndula|reality|telenovela|famos[oa]s?|cantante|show en vivo|recital|hor[oó]scopo|receta|musical|taquilla|estreno|pel[ií]cula|netflix|streaming)\b", re.I)


def limpiar_titulo(t):
    """Saca el nombre del medio pegado al título ("Titular :: Diario X", "Titular - Medio", "Titular | Medio")."""
    t = re.sub(r"\s+", " ", t or "").strip()
    t = re.sub(r"\s+(::|\||–|—)\s+[^:|–—]{2,60}$", "", t)
    t = re.sub(r"\s*::\s*[^:]{2,60}$", "", t)
    t = re.sub(r"\s+-\s+[A-ZÁÉÍÓÚ][^-]{1,40}$", "", t)
    return t.strip()


def es_ruido(titulo):
    return bool(RUIDO.search(sin_acentos(titulo).replace("ó", "o")) or RUIDO.search(titulo))


def nota_gdelt(a, region=None, zona=None):
    titulo = limpiar_titulo(a.get("title") or "")
    return {
        "titulo": titulo,
        "url": a.get("url"),
        "medio": a.get("domain"),
        "pais": a.get("sourcecountry"),
        "idioma": a.get("language"),
        "fecha": fecha_gdelt(a.get("seendate", "")),
        "imagen": a.get("socialimage") or None,
        "region": region or region_de(titulo),
        "zona": zona or ("argentina" if (a.get("sourcecountry") == "Argentina") else None),
        "tema": tema_de(titulo),
        "via": "GDELT",
    }


def leer_rss(fuente):
    import feedparser  # se instala en el workflow
    crudo = pedir(fuente["url"], intentos=2)
    feed = feedparser.parse(crudo)
    if not feed.entries:
        raise ValueError("el feed no trae notas")
    notas = []
    for e in feed.entries[:25]:
        fecha = None
        for k in ("published_parsed", "updated_parsed"):
            if getattr(e, k, None):
                fecha = datetime(*getattr(e, k)[:6], tzinfo=timezone.utc).isoformat()
                break
        titulo = limpiar_titulo(getattr(e, "title", "") or "")
        if es_ruido(titulo):
            continue
        # resumen corto que el propio medio publica en su RSS (sin HTML, hasta 400 caracteres)
        resumen = re.sub(r"<[^>]+>", " ", getattr(e, "summary", "") or "")
        resumen = re.sub(r"\s+", " ", resumen).strip()
        if resumen.lower().startswith(titulo.lower()[:40]):
            resumen = resumen[len(titulo):].strip(" .:-")
        if len(resumen) > 400:
            resumen = resumen[:400].rsplit(" ", 1)[0] + "…"
        notas.append({
            "titulo": titulo, "resumen": resumen or None, "url": getattr(e, "link", None), "medio": fuente["nombre"], "pais": fuente.get("pais"),
            "idioma": fuente.get("idioma"), "fecha": fecha, "imagen": None,
            "region": region_de(titulo) or fuente.get("region"), "zona": fuente.get("zona"), "tema": tema_de(titulo),
            "via": "RSS", "tipo": fuente.get("tipo"),
        })
    return notas


def main():
    DATOS.mkdir(exist_ok=True)
    salida = {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"), "regiones": {}, "zonas": {}, "rss": [], "estado": []}

    for rid, r in REGIONES.items():
        consulta = f"{r['consulta']} sourcecountry:AR"
        reg = {"nombre": r["nombre"], "detalle": r["detalle"], "notas": [], "volumen": []}
        try:
            datos = gdelt(consulta)
            # GDELT trae notas que nombran la provincia en cualquier parte del texto: solo se
            # asigna la región si el título la menciona; las demás quedan como nacionales.
            reg["notas"] = []
            for a in datos.get("articles", []):
                n = nota_gdelt(a, zona="argentina")
                if es_ruido(n["titulo"]):
                    continue
                if n["region"] == rid:
                    reg["notas"].append(n)
                else:
                    salida.setdefault("_sueltas", []).append(n)
            salida["estado"].append({"fuente": f"GDELT · {r['nombre']}", "ok": True, "notas": len(reg["notas"])})
        except Exception as e:  # noqa: BLE001
            salida["estado"].append({"fuente": f"GDELT · {r['nombre']}", "ok": False, "error": str(e)[:160]})
        try:
            vol = gdelt(consulta, modo="timelinevolraw", periodo="14d")
            serie = (vol.get("timeline") or [{}])[0].get("data", [])
            # GDELT da puntos cada 15 minutos o por día según el período: se suman por día
            por_dia = {}
            for p in serie:
                dia = str(p.get("date", ""))[:8]
                por_dia[dia] = por_dia.get(dia, 0) + int(p.get("value", 0) or 0)
            reg["volumen"] = [[d, por_dia[d]] for d in sorted(por_dia)][-14:]
        except Exception as e:  # noqa: BLE001
            salida["estado"].append({"fuente": f"GDELT volumen · {r['nombre']}", "ok": False, "error": str(e)[:160]})
        salida["regiones"][rid] = reg
        print(f"región {rid}: {len(reg['notas'])} notas, {len(reg['volumen'])} días de volumen", flush=True)

    for zid, z in ZONAS.items():
        try:
            datos = gdelt(z["consulta"], maximo=50)
            notas = [n for n in (nota_gdelt(a, zona=zid) for a in datos.get("articles", [])) if not es_ruido(n["titulo"])]
            salida["zonas"][zid] = {"nombre": z["nombre"], "notas": notas}
            salida["estado"].append({"fuente": f"GDELT · {z['nombre']}", "ok": True, "notas": len(notas)})
        except Exception as e:  # noqa: BLE001
            salida["zonas"][zid] = {"nombre": z["nombre"], "notas": []}
            salida["estado"].append({"fuente": f"GDELT · {z['nombre']}", "ok": False, "error": str(e)[:160]})
        print(f"zona {zid}: {len(salida['zonas'][zid]['notas'])} notas", flush=True)

    # agenda: cada eje se busca a propósito en medios argentinos (y del mundo hispano para Mercosur, EE.UU. y guerras)
    salida["ejes"] = {}
    for e in EJES:
        try:
            datos = gdelt(e["consulta"], maximo=30)
            notas = []
            for a in datos.get("articles", []):
                n = nota_gdelt(a)
                if es_ruido(n["titulo"]):
                    continue
                n["ejes"] = [e["id"]]
                notas.append(n)
            salida["ejes"][e["id"]] = {"nombre": e["nombre"], "notas": notas}
            salida["estado"].append({"fuente": f"GDELT · agenda {e['nombre']}", "ok": True, "notas": len(notas)})
        except Exception as ex:  # noqa: BLE001
            salida["ejes"][e["id"]] = {"nombre": e["nombre"], "notas": []}
            salida["estado"].append({"fuente": f"GDELT · agenda {e['nombre']}", "ok": False, "error": str(ex)[:160]})
        print(f"eje {e['id']}: {len(salida['ejes'][e['id']]['notas'])} notas", flush=True)

    # notas de las búsquedas regionales cuyo título no nombra la región: van a "nacional"
    sueltas = salida.pop("_sueltas", [])
    if sueltas:
        salida["zonas"].setdefault("nacional", {"nombre": ZONAS["nacional"]["nombre"], "notas": []})["notas"].extend(sueltas)

    fuentes = json.loads((DATOS / "fuentes-rss.json").read_text(encoding="utf-8"))
    for f in fuentes:
        try:
            notas = leer_rss(f)
            salida["rss"].extend(notas)
            salida["estado"].append({"fuente": f["nombre"], "ok": True, "notas": len(notas), "tipo": f.get("tipo"), "via": "RSS"})
        except Exception as e:  # noqa: BLE001
            salida["estado"].append({"fuente": f["nombre"], "ok": False, "error": str(e)[:160], "tipo": f.get("tipo"), "via": "RSS"})
        print(f"rss {f['nombre']}: {salida['estado'][-1]}", flush=True)

    # sin duplicados por enlace; cada nota queda marcada con sus ejes de agenda y su región del mundo
    vistos = {}
    grupos = [*(r["notas"] for r in salida["regiones"].values()), *(z["notas"] for z in salida["zonas"].values()), salida["rss"],
              *(e["notas"] for e in salida["ejes"].values())]
    for grupo in grupos:
        unicas = []
        for n in grupo:
            if not (n.get("url") and n.get("titulo")):
                continue
            ejes = sorted(set(n.get("ejes", [])) | set(ejes_de(n["titulo"] + " " + (n.get("resumen") or ""))))
            if n["url"] in vistos:
                previa = vistos[n["url"]]  # ya estaba: se le suman los ejes
                previa["ejes"] = sorted(set(previa.get("ejes", [])) | set(ejes))
                continue
            n["ejes"] = ejes
            n["region_mundo"] = PAIS_A_REGION.get(n.get("pais") or "")
            vistos[n["url"]] = n
            unicas.append(n)
        grupo[:] = unicas

    # "Lo más cubierto": el mismo hecho contado por varios medios, ordenado por importancia (scripts/agrupar.py)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from agrupar import agrupar, todas_las_notas
        salida["cubierto"] = agrupar(todas_las_notas(salida))
        print(f"lo más cubierto: {len(salida['cubierto'])} hechos con 2 o más medios", flush=True)
    except Exception as e:  # noqa: BLE001
        salida["cubierto"] = []
        print(f"lo más cubierto: falló ({e})", flush=True)

    (DATOS / "noticias.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for e in salida["estado"] if e["ok"])
    print(f"Listo: {ok} de {len(salida['estado'])} fuentes respondieron, {len(vistos)} notas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
