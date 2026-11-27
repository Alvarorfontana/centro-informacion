#!/usr/bin/env python3
"""
Recolector de la pestaña Mundo de la Central.

Lee las fuentes RSS públicas de datos/mundo-fuentes.json (tomadas del catálogo abierto de
World Monitor) y las capas gratuitas del mapa:
  - Sismos de magnitud 4,5 o más de la última semana (Servicio Geológico de EE.UU., USGS).
  - Desastres y alertas en curso (GDACS, sistema de alertas de la ONU y la Comisión Europea).

De cada nota guarda solo título, enlace, fecha y medio. No copia el texto.
Ubica cada nota en el mapa según el país que nombra el título.
Escribe datos/mundo.json, que lee mundo.html.

Corre dentro de recolectar.yml, después de las noticias, con su propio tope de tiempo
(MUNDO_MINUTOS, 5 por defecto) para no comerse los minutos gratis de GitHub.
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import feedparser
except ImportError:
    print("Falta feedparser (pip install feedparser)")
    sys.exit(1)

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
AGENTE = "Mozilla/5.0 (CentroInformacion; uso periodistico)"
PRESUPUESTO = float(os.environ.get("MUNDO_MINUTOS", "5")) * 60
INICIO = time.time()
HORAS = 36            # solo notas de las últimas 36 horas
POR_FUENTE = 6        # hasta 6 notas por medio
TOPE_NOTAS = 3000     # tope total para que el archivo no pese demasiado

# País -> (nombre en castellano, lat, lon, [formas en que puede aparecer en un título]).
PAISES = [
    ("Argentina", -34.6, -64.0, ["argentina", "buenos aires", "milei"]),
    ("Brasil", -14.2, -51.9, ["brasil", "brazil", "brasilia", "sao paulo", "rio de janeiro", "lula"]),
    ("Uruguay", -32.5, -55.8, ["uruguay", "montevideo"]),
    ("Paraguay", -23.4, -58.4, ["paraguay", "asuncion"]),
    ("Bolivia", -16.3, -63.6, ["bolivia", "la paz"]),
    ("Chile", -35.7, -71.5, ["chile", "santiago de chile"]),
    ("Perú", -9.2, -75.0, ["peru", "lima"]),
    ("Colombia", 4.6, -74.3, ["colombia", "bogota"]),
    ("Venezuela", 6.4, -66.6, ["venezuela", "caracas", "maduro"]),
    ("Ecuador", -1.8, -78.2, ["ecuador", "quito", "guayaquil"]),
    ("México", 23.6, -102.6, ["mexico", "mexique", "sheinbaum"]),
    ("Cuba", 21.5, -78.0, ["cuba", "havana", "la habana"]),
    ("Haití", 19.0, -72.3, ["haiti"]),
    ("República Dominicana", 18.7, -70.2, ["dominican republic", "republica dominicana", "santo domingo"]),
    ("Guatemala", 15.8, -90.2, ["guatemala"]),
    ("Honduras", 15.2, -86.2, ["honduras", "tegucigalpa"]),
    ("El Salvador", 13.8, -88.9, ["el salvador", "bukele"]),
    ("Nicaragua", 12.9, -85.2, ["nicaragua", "managua"]),
    ("Costa Rica", 9.7, -83.8, ["costa rica"]),
    ("Panamá", 8.5, -80.8, ["panama"]),
    ("Estados Unidos", 39.8, -98.6, ["estados unidos", "united states", "eeuu", "ee.uu", "u.s.", "washington", "white house", "casa blanca", "pentagon", "pentagono", "trump"]),
    ("Canadá", 56.1, -106.3, ["canada", "ottawa", "toronto"]),
    ("Reino Unido", 54.0, -2.0, ["reino unido", "united kingdom", "britain", "british", "london", "londres", "uk "]),
    ("Irlanda", 53.4, -8.2, ["ireland", "irlanda", "dublin"]),
    ("Francia", 46.2, 2.2, ["francia", "france", "paris", "macron"]),
    ("España", 40.4, -3.7, ["espana", "spain", "madrid", "barcelona", "sanchez"]),
    ("Portugal", 39.4, -8.2, ["portugal", "lisboa", "lisbon"]),
    ("Italia", 41.9, 12.6, ["italia", "italy", "roma", "rome", "meloni", "vaticano", "vatican"]),
    ("Alemania", 51.2, 10.4, ["alemania", "germany", "berlin", "deutschland"]),
    ("Países Bajos", 52.1, 5.3, ["paises bajos", "netherlands", "holanda", "amsterdam"]),
    ("Bélgica", 50.5, 4.5, ["belgica", "belgium", "bruselas", "brussels"]),
    ("Suiza", 46.8, 8.2, ["suiza", "switzerland", "ginebra", "geneva"]),
    ("Austria", 47.5, 14.6, ["austria", "viena", "vienna"]),
    ("Polonia", 51.9, 19.1, ["polonia", "poland", "varsovia", "warsaw"]),
    ("Hungría", 47.2, 19.5, ["hungria", "hungary", "budapest", "orban"]),
    ("Rumania", 45.9, 24.9, ["rumania", "romania", "bucarest"]),
    ("Grecia", 39.1, 21.8, ["grecia", "greece", "atenas", "athens"]),
    ("Suecia", 60.1, 18.6, ["suecia", "sweden", "estocolmo"]),
    ("Noruega", 60.5, 8.5, ["noruega", "norway", "oslo"]),
    ("Finlandia", 61.9, 25.7, ["finlandia", "finland", "helsinki"]),
    ("Dinamarca", 56.3, 9.5, ["dinamarca", "denmark", "copenhague", "groenlandia", "greenland"]),
    ("Serbia", 44.0, 21.0, ["serbia", "belgrado"]),
    ("Ucrania", 48.4, 31.2, ["ucrania", "ukraine", "kiev", "kyiv", "zelensky", "zelenski", "jarkov", "kharkiv", "odesa"]),
    ("Rusia", 61.5, 105.3, ["rusia", "russia", "moscu", "moscow", "kremlin", "putin"]),
    ("Bielorrusia", 53.7, 28.0, ["bielorrusia", "belarus", "minsk"]),
    ("Turquía", 39.0, 35.2, ["turquia", "turkey", "turkiye", "ankara", "estambul", "istanbul", "erdogan"]),
    ("Israel", 31.0, 34.9, ["israel", "tel aviv", "jerusalem", "jerusalen", "netanyahu"]),
    ("Palestina", 31.9, 35.2, ["gaza", "palestin", "cisjordania", "west bank", "hamas"]),
    ("Líbano", 33.9, 35.9, ["libano", "lebanon", "beirut", "hezbol"]),
    ("Siria", 34.8, 38.9, ["siria", "syria", "damasco", "damascus"]),
    ("Irak", 33.2, 43.7, ["irak", "iraq", "bagdad", "baghdad"]),
    ("Irán", 32.4, 53.7, ["iran", "teheran", "tehran"]),
    ("Arabia Saudita", 23.9, 45.1, ["arabia saudita", "saudi", "riad", "riyadh"]),
    ("Emiratos Árabes", 23.4, 53.8, ["emiratos", "emirates", "uae", "dubai", "abu dhabi"]),
    ("Catar", 25.4, 51.2, ["catar", "qatar", "doha"]),
    ("Yemen", 15.6, 48.5, ["yemen", "huti", "houthi"]),
    ("Jordania", 30.6, 36.2, ["jordania", "jordan", "amman"]),
    ("Egipto", 26.8, 30.8, ["egipto", "egypt", "cairo"]),
    ("Libia", 26.3, 17.2, ["libia", "libya", "tripoli"]),
    ("Túnez", 33.9, 9.5, ["tunez", "tunisia"]),
    ("Argelia", 28.0, 1.7, ["argelia", "algeria", "argel"]),
    ("Marruecos", 31.8, -7.1, ["marruecos", "morocco", "rabat"]),
    ("Sudán", 12.9, 30.2, ["sudan", "jartum", "khartoum", "darfur"]),
    ("Sudán del Sur", 6.9, 31.3, ["south sudan", "sudan del sur", "juba"]),
    ("Etiopía", 9.1, 40.5, ["etiopia", "ethiopia", "addis"]),
    ("Somalia", 5.2, 46.2, ["somalia", "mogadiscio", "mogadishu"]),
    ("Kenia", -0.0, 37.9, ["kenia", "kenya", "nairobi"]),
    ("Nigeria", 9.1, 8.7, ["nigeria", "abuja", "lagos"]),
    ("Ghana", 7.9, -1.0, ["ghana", "accra"]),
    ("Senegal", 14.5, -14.5, ["senegal", "dakar"]),
    ("Malí", 17.6, -4.0, ["mali", "bamako"]),
    ("Burkina Faso", 12.2, -1.6, ["burkina"]),
    ("Níger", 17.6, 8.1, ["niger ", "niamey"]),
    ("Chad", 15.5, 18.7, ["chad", "yamena", "n'djamena"]),
    ("Camerún", 7.4, 12.4, ["camerun", "cameroon"]),
    ("Congo (RDC)", -4.0, 21.8, ["congo", "kinshasa", "goma"]),
    ("Uganda", 1.4, 32.3, ["uganda", "kampala"]),
    ("Ruanda", -1.9, 29.9, ["ruanda", "rwanda", "kigali"]),
    ("Tanzania", -6.4, 34.9, ["tanzania"]),
    ("Mozambique", -18.7, 35.5, ["mozambique", "maputo"]),
    ("Angola", -11.2, 17.9, ["angola", "luanda"]),
    ("Zimbabue", -19.0, 29.2, ["zimbabue", "zimbabwe", "harare"]),
    ("Sudáfrica", -30.6, 22.9, ["sudafrica", "south africa", "johannesburg", "pretoria", "ciudad del cabo", "cape town"]),
    ("Madagascar", -18.8, 46.9, ["madagascar"]),
    ("China", 35.9, 104.2, ["china", "beijing", "pekin", "shanghai", "xi jinping", "hong kong"]),
    ("Taiwán", 23.7, 121.0, ["taiwan", "taipei"]),
    ("Japón", 36.2, 138.3, ["japon", "japan", "tokio", "tokyo"]),
    ("Corea del Sur", 35.9, 127.8, ["corea del sur", "south korea", "seul", "seoul"]),
    ("Corea del Norte", 40.3, 127.5, ["corea del norte", "north korea", "pyongyang", "kim jong"]),
    ("India", 20.6, 79.0, ["india", "nueva delhi", "new delhi", "mumbai", "modi"]),
    ("Pakistán", 30.4, 69.3, ["pakistan", "islamabad", "karachi"]),
    ("Afganistán", 33.9, 67.7, ["afganistan", "afghanistan", "kabul", "taliban"]),
    ("Bangladés", 23.7, 90.4, ["banglades", "bangladesh", "dhaka"]),
    ("Sri Lanka", 7.9, 80.8, ["sri lanka", "colombo"]),
    ("Nepal", 28.4, 84.1, ["nepal", "katmandu", "kathmandu"]),
    ("Birmania", 21.9, 95.9, ["birmania", "myanmar", "burma"]),
    ("Tailandia", 15.9, 100.9, ["tailandia", "thailand", "bangkok"]),
    ("Vietnam", 14.1, 108.3, ["vietnam", "hanoi"]),
    ("Camboya", 12.6, 104.9, ["camboya", "cambodia"]),
    ("Malasia", 4.2, 102.0, ["malasia", "malaysia", "kuala lumpur"]),
    ("Singapur", 1.35, 103.8, ["singapur", "singapore"]),
    ("Indonesia", -0.8, 113.9, ["indonesia", "yakarta", "jakarta"]),
    ("Filipinas", 12.9, 121.8, ["filipinas", "philippines", "manila"]),
    ("Kazajistán", 48.0, 66.9, ["kazajistan", "kazakhstan"]),
    ("Georgia", 42.3, 43.4, ["georgia", "tbilisi"]),
    ("Armenia", 40.1, 45.0, ["armenia", "erevan", "yerevan"]),
    ("Azerbaiyán", 40.1, 47.6, ["azerbaiyan", "azerbaijan", "baku"]),
    ("Australia", -25.3, 133.8, ["australia", "sidney", "sydney", "canberra", "melbourne"]),
    ("Nueva Zelanda", -40.9, 174.9, ["nueva zelanda", "new zealand", "wellington"]),
    ("Antártida", -75.0, 0.0, ["antartida", "antarctica"]),
    ("Islas Malvinas", -51.8, -59.5, ["malvinas", "falkland"]),
]


def plano(t):
    t = unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower()
    return " " + re.sub(r"\s+", " ", t) + " "


PATRONES = [(nombre, lat, lon, re.compile(r"(?<![a-z])(" + "|".join(re.escape(f.strip()) for f in formas) + r")(?![a-z])"))
            for nombre, lat, lon, formas in PAISES]


def ubicar(titulo):
    # Se queda con el país que aparece primero en el título.
    t = plano(titulo)
    mejor = None
    for nombre, lat, lon, pat in PATRONES:
        m = pat.search(t)
        if m and (mejor is None or m.start() < mejor[0]):
            mejor = (m.start(), nombre, lat, lon)
    return mejor[1:] if mejor else None


# "Argentina en el mundo": notas de medios extranjeros que hablan de la Argentina.
ARG_LATIN = re.compile(r"(?<![a-z])(argentin\w*|milei|malvinas|falkland\w*|buenos aires|mercosu[rl]|kicillof|vaca muerta|ypf)(?![a-z])")
ARG_OTROS = ["аргентин", "الأرجنتين", "阿根廷", "アルゼンチン", "아르헨티나", "αργεντιν", "ארגנטינה", "अर्जेंटीना", "ارژانتین", "arjantin"]


def habla_de_argentina(titulo):
    if ARG_LATIN.search(plano(titulo)):
        return True
    t = (titulo or "").lower()
    return any(x in t for x in ARG_OTROS)


def sin_tiempo():
    return (time.time() - INICIO) > PRESUPUESTO


def bajar(url, segundos=8):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=segundos) as r:
        return r.read(3_000_000)


def leer_fuente(f, desde):
    if sin_tiempo():
        return f, None, "sin tiempo"
    try:
        d = feedparser.parse(bajar(f["url"]))
    except Exception as e:
        return f, None, type(e).__name__
    notas, comunes = [], 0
    for e in d.entries[:40]:
        t = e.get("published_parsed") or e.get("updated_parsed")
        fecha = datetime(*t[:6], tzinfo=timezone.utc) if t else None
        if fecha and fecha < desde:
            continue
        titulo = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", e.get("title", ""))).strip()
        enlace = e.get("link", "")
        if not titulo or not enlace:
            continue
        arg = habla_de_argentina(titulo)
        # Hasta 6 notas comunes por medio; las que hablan de la Argentina entran todas.
        if not arg and comunes >= POR_FUENTE:
            continue
        n = {"titulo": titulo[:220], "enlace": enlace, "medio": f["nombre"], "seccion": f["seccion"],
             "fecha": (fecha or datetime.now(timezone.utc)).isoformat(timespec="minutes")}
        if f.get("idioma"):
            n["idioma"] = f["idioma"]
        if arg:
            n["argentina"] = True
        else:
            comunes += 1
        lugar = ubicar(titulo)
        if lugar:
            n["pais"], n["lat"], n["lon"] = lugar
        notas.append(n)
    return f, notas, "ok"


def sismos():
    try:
        d = json.loads(bajar("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson", 20))
    except Exception as e:
        print("Sismos: falló", e)
        return []
    out = []
    for x in d.get("features", []):
        p, c = x["properties"], x["geometry"]["coordinates"]
        out.append({"lugar": p.get("place") or "", "magnitud": p.get("mag"), "lat": c[1], "lon": c[0],
                    "fecha": datetime.fromtimestamp(p["time"] / 1000, timezone.utc).isoformat(timespec="minutes"),
                    "enlace": p.get("url", "")})
    return out


TIPOS_GDACS = {"EQ": "Sismo", "TC": "Ciclón", "FL": "Inundación", "VO": "Volcán", "DR": "Sequía", "WF": "Incendio forestal", "TS": "Tsunami"}
NIVEL = {"Green": "verde", "Orange": "naranja", "Red": "rojo"}


def desastres():
    out = []
    try:
        d = json.loads(bajar("https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP?eventlist=EQ;TC;FL;VO;DR;WF;TS", 25))
        for x in d.get("features", []):
            p, g = x.get("properties", {}), x.get("geometry", {})
            if g.get("type") != "Point":
                continue
            u = p.get("url")
            out.append({"tipo": TIPOS_GDACS.get(p.get("eventtype"), p.get("eventtype", "")), "nombre": p.get("name") or p.get("eventname") or "",
                        "pais": p.get("country", ""), "nivel": NIVEL.get(p.get("alertlevel"), p.get("alertlevel", "")),
                        "lat": g["coordinates"][1], "lon": g["coordinates"][0],
                        "desde": p.get("fromdate", ""), "enlace": u.get("report", "") if isinstance(u, dict) else ""})
        if out:
            return out
    except Exception as e:
        print("GDACS (API): falló", e)
    # Respaldo: el RSS público de GDACS, que trae la ubicación de cada evento.
    try:
        r = feedparser.parse(bajar("https://www.gdacs.org/xml/rss.xml", 25))
        for e in r.entries:
            lat, lon = e.get("geo_lat"), e.get("geo_long")
            if not lat and e.get("where"):
                try:
                    lon, lat = e["where"]["coordinates"][:2]
                except Exception:
                    pass
            if not lat:
                continue
            out.append({"tipo": TIPOS_GDACS.get(e.get("gdacs_eventtype", ""), e.get("gdacs_eventtype", "")), "nombre": e.get("title", ""),
                        "pais": e.get("gdacs_country", ""), "nivel": NIVEL.get(e.get("gdacs_alertlevel", ""), e.get("gdacs_alertlevel", "")),
                        "lat": float(lat), "lon": float(lon), "desde": e.get("gdacs_fromdate", ""), "enlace": e.get("link", "")})
    except Exception as e:
        print("GDACS (RSS): falló", e)
    return out


# Traducción al castellano de los títulos, con la IA gratuita que ya usa la Central (scripts/ia.py:
# Gemini, Groq u OpenRouter si hay clave; si no, Pollinations sin clave). Primero las notas de
# "Argentina en el mundo" y las que van al mapa; reusa lo ya traducido en la vuelta anterior.
TRADUCIR_MAX = int(os.environ.get("MUNDO_TRADUCIR", "900"))
TRADUCIR_SEG = float(os.environ.get("MUNDO_TRADUCIR_MINUTOS", "3")) * 60
LOTE = 120


def parece_castellano(n):
    if n.get("idioma") == "es":
        return True
    if n.get("idioma"):
        return False
    t = plano(n["titulo"])
    return len(re.findall(r" (el|la|los|las|del|que|con|para|por|una|en) ", t)) >= 2


def traducir(notas):
    try:
        anterior = {x["enlace"]: x["titulo_es"] for x in json.loads((DATOS / "mundo.json").read_text(encoding="utf-8")).get("notas", []) if x.get("titulo_es")}
    except Exception:
        anterior = {}
    pendientes = []
    for n in notas:
        if parece_castellano(n):
            continue
        if n["enlace"] in anterior:
            n["titulo_es"] = anterior[n["enlace"]]
        else:
            pendientes.append(n)
    pendientes.sort(key=lambda n: (not n.get("argentina"), "lat" not in n))
    pendientes = pendientes[:TRADUCIR_MAX]
    if not pendientes:
        return 0
    try:
        sys.path.insert(0, str(RAIZ / "scripts"))
        from ia import IA
        conf = json.loads((RAIZ / "agentes" / "config.json").read_text(encoding="utf-8")).get("ia", {})
        conf = dict(conf, pausa_segundos=2, espera_maxima_segundos=60)
        ia = IA(conf)
    except Exception as e:
        print("Traducción: sin IA disponible", e)
        return 0
    hechas, inicio = 0, time.time()
    for i in range(0, len(pendientes), LOTE):
        if time.time() - inicio > TRADUCIR_SEG:
            break
        lote = pendientes[i:i + LOTE]
        pedido = ("Traducí al castellano rioplatense neutro, estilo título periodístico, estos titulares de noticias. "
                  "No agregues ni quites información. Devolvé SOLO un JSON con la forma {\"t\": [\"título 1\", \"título 2\", ...]} "
                  "con la misma cantidad y el mismo orden.\n\n" + json.dumps([n["titulo"] for n in lote], ensure_ascii=False))
        try:
            r = ia.json(pedido)
            t = r.get("t") if isinstance(r, dict) else r
            if isinstance(t, list) and len(t) == len(lote):
                for n, tr in zip(lote, t):
                    if isinstance(tr, str) and tr.strip():
                        n["titulo_es"] = tr.strip()[:240]
                        hechas += 1
        except Exception as e:
            print("Traducción: falló un lote", str(e)[:160])
    print(f"Traducción: {hechas} títulos nuevos ({ia.usado or 'sin IA'}); {len(anterior)} ya estaban traducidos.")
    return hechas


# Alertas por Telegram: sismos fuertes y desastres en Sudamérica (con el bot que ya usa la Central).
REGION = {"lat": (-60, 13), "lon": (-92, -30)}
PAISES_REGION = ["argentina", "chile", "uruguay", "paraguay", "bolivia", "brazil", "brasil", "peru", "ecuador", "colombia", "venezuela"]
MAG_MINIMA = 5.5


def en_region(lat, lon):
    return REGION["lat"][0] <= lat <= REGION["lat"][1] and REGION["lon"][0] <= lon <= REGION["lon"][1]


def alertas(salida):
    archivo = DATOS / "mundo-avisos.json"
    primera_vez = not archivo.exists()
    try:
        enviados = json.loads(archivo.read_text(encoding="utf-8")) if not primera_vez else {}
    except Exception:
        enviados = {}
    ahora = datetime.now(timezone.utc)
    ventana = ahora - timedelta(hours=12 if primera_vez else 48)
    nuevas = []
    for s_ in salida["sismos"]:
        if s_.get("magnitud") and s_["magnitud"] >= MAG_MINIMA and en_region(s_["lat"], s_["lon"]) and datetime.fromisoformat(s_["fecha"]) >= ventana:
            clave = s_.get("enlace") or f"sismo{s_['lat']}{s_['lon']}{s_['fecha']}"
            if clave not in enviados:
                nuevas.append((clave, f"🌎 Sismo M{s_['magnitud']} · {s_['lugar']} ({s_['fecha'][:16].replace('T', ' ')} UTC)\n{s_.get('enlace', '')}"))
    for d in salida["desastres"]:
        pais = plano(d.get("pais", ""))
        if not (en_region(d["lat"], d["lon"]) or any(p in pais for p in PAISES_REGION)):
            continue
        if d.get("tipo") == "Sismo":  # los sismos ya salen por el USGS
            continue
        if d.get("nivel") not in ("naranja", "rojo"):
            continue
        clave = d.get("enlace") or f"{d.get('tipo')}{d.get('nombre')}"
        if clave not in enviados:
            nuevas.append((clave, f"⚠️ {d.get('tipo')} · alerta {d.get('nivel') or 's/d'} · {d.get('nombre')}{(' · ' + d['pais']) if d.get('pais') else ''}\n{d.get('enlace', '')}"))
    if not nuevas:
        print("Alertas: nada nuevo en la región.")
        return
    try:
        sys.path.insert(0, str(RAIZ / "scripts"))
        from avisar import telegram
        texto = "Central · Mundo — alertas en la región\n\n" + "\n\n".join(t for _, t in nuevas[:10]) + "\n\nMapa: https://centro-informacion.vercel.app/mundo.html"
        res = telegram(texto)
        print("Alertas:", len(nuevas), "→", res)
        if not res or not str(res).startswith("enviado"):
            return
    except Exception as e:
        print("Alertas: no se pudo avisar", e)
        return
    for clave, _ in nuevas:
        enviados[clave] = ahora.isoformat(timespec="minutes")
    limite = (ahora - timedelta(days=10)).isoformat()
    enviados = {k: v for k, v in enviados.items() if v >= limite}
    archivo.write_text(json.dumps(enviados, ensure_ascii=False, indent=0), encoding="utf-8")


def main():
    fuentes = json.loads((DATOS / "mundo-fuentes.json").read_text(encoding="utf-8"))["fuentes"]
    desde = datetime.now(timezone.utc) - timedelta(hours=HORAS)
    notas, ok, fallan = [], 0, 0
    with ThreadPoolExecutor(max_workers=48) as ex:
        futuros = [ex.submit(leer_fuente, f, desde) for f in fuentes]
        for fu in as_completed(futuros):
            f, ns, estado = fu.result()
            if ns is None:
                fallan += 1
            else:
                ok += 1
                notas.extend(ns)
    vistos, unicas = set(), []
    for n in sorted(notas, key=lambda n: n["fecha"], reverse=True):
        clave = plano(n["titulo"])[:90]
        if clave in vistos:
            continue
        vistos.add(clave)
        unicas.append(n)
    arg = [n for n in unicas if n.get("argentina")]
    resto = [n for n in unicas if not n.get("argentina")][:max(TOPE_NOTAS - len(arg), 0)]
    unicas = sorted(arg + resto, key=lambda n: n["fecha"], reverse=True)
    traducir(unicas)
    salida = {
        "actualizado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "periodo_horas": HORAS,
        "fuentes": {"total": len(fuentes), "funcionan": ok, "fallan": fallan},
        "notas": unicas,
        "sismos": sismos(),
        "desastres": desastres(),
    }
    salida["argentina"] = sum(1 for n in unicas if n.get("argentina"))
    (DATOS / "mundo.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ubicadas = sum(1 for n in unicas if "lat" in n)
    print(f"Mundo: {len(unicas)} notas ({ubicadas} en el mapa) de {ok} fuentes; {fallan} fallaron. "
          f"{salida['argentina']} hablan de la Argentina. {len(salida['sismos'])} sismos, {len(salida['desastres'])} desastres. {int(time.time() - INICIO)} s.")
    alertas(salida)


if __name__ == "__main__":
    main()
