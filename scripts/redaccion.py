#!/usr/bin/env python3
"""
Redacción automática del Centro de Información de Diario Federal: 12 agentes en cadena.

Lo corre GitHub Actions dos veces por día (.github/workflows/redaccion.yml), después del recolector.
Lee datos/noticias.json y escribe datos/redaccion.json, que muestra la página en "Redacción automática".

  Selección   1 Monitor Argentina · 2 Monitor local · 3 Monitor Mercosur · 4 Monitor internacional · 5 Jefe de redacción
  Producción  7 Fuentes y autores · 6 Redactor · 8 Verificador · 9 Fotos
  Edición     12 Corrector · 10 Titulador · 11 Enlazador

Ningún agente publica: todo queda como borrador en el Centro y una persona decide qué pasa al diario.
No toca el repositorio del diario. Del diario solo lee su lista pública de notas (para los enlaces).

Las instrucciones de cada agente están en agentes/instrucciones/ y se pueden cambiar sin tocar este código.
De las notas originales solo se guardan datos (medio, autor, fecha, enlace), nunca su texto.
"""

import json
import re
import sys
import time
import traceback
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
AGENTES = RAIZ / "agentes"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agrupar as AG  # noqa: E402
import recolectar as REC  # noqa: E402  (mismos filtros de ruido, ejes y regiones del mundo que el recolector)
from ia import IA, SinClave  # noqa: E402

NAVEGADOR = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 CentroInformacion-DiarioFederal"
DIARIO = "https://www.diariofederal.com.ar"
MERCOSUR = {"Brasil", "Brazil", "Uruguay", "Paraguay", "Bolivia", "Chile", "Venezuela"}
SECCIONES = {"argentina": "Argentina", "local": "Local", "mercosur": "Mercosur", "mundo": "Mundo"}
MONITOR_DE = {"argentina": "monitor-argentina", "local": "monitor-local", "mercosur": "monitor-mercosur", "mundo": "monitor-mundo"}
AGENCIAS = ["EFE", "AFP", "Reuters", "ANSA", "Europa Press", "Noticias Argentinas", "Xinhua", "Sputnik", "DPA", "Bloomberg",
            "Associated Press", "Prensa Latina", "Agência Brasil", "Anadolu", "Telam", "Télam"]
OFICIALES = re.compile(r"(\.gob\.ar|\.gov\.ar|\.gov|\.gob\.[a-z]{2}|\.gov\.[a-z]{2}|\.gub\.uy|boletinoficial|\.un\.org|\.int)$", re.I)


# ───────────────────────── utilidades ─────────────────────────

def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sin_acentos(t):
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower()


def leer(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return defecto


def instruccion(nombre, **campos):
    t = (AGENTES / "instrucciones" / f"{nombre}.md").read_text(encoding="utf-8")
    for k, v in campos.items():
        t = t.replace("{" + k + "}", str(v))
    return t


def pedir(url, timeout=25, maximo=2_500_000):
    req = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR, "Accept-Language": "es-AR,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        tipo = r.headers.get("Content-Type", "")
        crudo = r.read(maximo)
        cod = "utf-8"
        m = re.search(r"charset=([\w-]+)", tipo)
        if m:
            cod = m.group(1)
        return crudo.decode(cod, "ignore"), r.geturl()


def palabras(html_o_texto):
    return len(re.sub(r"<[^>]+>", " ", html_o_texto or "").split())


class Registro:
    """Lleva el estado de cada agente: qué hizo, cuándo y si falló. Es lo que muestra el panel."""

    def __init__(self, conf):
        self.conf = {a["id"]: a for a in conf["agentes"]}
        self.estado = {a["id"]: {**{k: a[k] for k in ("id", "n", "etapa", "nombre", "hace", "ia", "prendido")},
                                 "resultado": "apagado" if not a.get("prendido", True) else "sin correr", "detalle": "", "produjo": 0}
                       for a in conf["agentes"]}

    def prendido(self, aid):
        return self.conf.get(aid, {}).get("prendido", True)

    def anotar(self, aid, resultado, detalle="", produjo=None):
        e = self.estado[aid]
        if e["resultado"] == "falló" and resultado == "funcionó":
            resultado = "con fallas"  # funcionó en algunos temas y falló en otros
        e["resultado"], e["fin"] = resultado, ahora()
        e.setdefault("inicio", e["fin"])
        if detalle:
            e["detalle"] = detalle[:220]
        if produjo is not None:
            e["produjo"] = produjo

    def empezar(self, aid):
        self.estado[aid]["inicio"] = ahora()

    def lista(self):
        return sorted(self.estado.values(), key=lambda e: e["n"])


# ───────────────────────── 1-4 · monitores ─────────────────────────

def seccion_de(n, claves_local):
    texto = sin_acentos((n.get("titulo") or "") + " " + (n.get("resumen") or ""))
    if any(re.search(r"\b" + re.escape(k) + r"\b", texto) for k in claves_local):
        return "local"
    if n.get("zona") == "mercosur" or n.get("pais") in MERCOSUR:
        return "mercosur"
    if n.get("region") or n.get("zona") in ("argentina", "nacional") or n.get("pais") == "Argentina":
        return "argentina"
    return "mundo"


def monitores(noticias, conf, reg):
    claves_local = [sin_acentos(p) for p in conf["local"]["palabras"]]
    imagenes = {}
    por_seccion = {s: [] for s in SECCIONES}
    for n in AG.todas_las_notas(noticias):
        if REC.es_ruido(n.get("titulo") or ""):
            continue
        if not n.get("ejes"):  # datos viejos o RSS: se marcan los ejes acá también
            n["ejes"] = REC.ejes_de((n.get("titulo") or "") + " " + (n.get("resumen") or ""))
        n.setdefault("region_mundo", REC.PAIS_A_REGION.get(n.get("pais") or ""))
        if n.get("imagen"):
            imagenes[n["url"]] = n["imagen"]
        por_seccion[seccion_de(n, claves_local)].append(n)

    ref = None
    try:
        ref = datetime.fromisoformat(noticias["generado"])
    except Exception:  # noqa: BLE001
        pass
    tope = conf.get("candidatos_por_monitor", 12)
    candidatos = []
    AG.MIN_MEDIOS = 1  # también entran los temas que cuenta un solo medio; el puntaje los deja más abajo
    for sec, notas in por_seccion.items():
        aid = MONITOR_DE[sec]
        if not reg.prendido(aid):
            continue
        reg.empezar(aid)
        try:
            grupos = AG.agrupar(notas, ahora=ref)[:tope]
            for g in grupos:
                for x in g["notas"]:
                    x["imagen"] = imagenes.get(x["url"])
                candidatos.append({"seccion": sec, **g})
            medios = len({n.get("medio") for n in notas})
            reg.anotar(aid, "funcionó", f"{len(notas)} titulares de {medios} medios → {len(grupos)} temas", len(grupos))
        except Exception as e:  # noqa: BLE001
            reg.anotar(aid, "falló", str(e))
    for i, c in enumerate(candidatos):
        c["id"] = i + 1
    return candidatos


# ───────────────────────── 5 · jefe de redacción ─────────────────────────

def parecidos(a, b, umbral=AG.UMBRAL):
    return AG.jaccard(AG.raices(a), AG.raices(b)) >= umbral


def jefe(candidatos, conf, ia, reg, historial):
    cupos = conf["cupos"]
    recientes = [h["titulo"] for h in historial]
    # fuera los temas ya trabajados en los últimos días y los repetidos entre secciones
    limpios = []
    for c in sorted(candidatos, key=lambda c: c["puntaje"], reverse=True):
        if any(parecidos(c["titulo"], t, 0.4) for t in recientes):
            continue
        if any(parecidos(c["titulo"], x["titulo"]) for x in limpios):
            continue
        limpios.append(c)

    def por_reglas():
        menu = []
        for sec, cupo in cupos.items():
            menu += [c for c in limpios if c["seccion"] == sec][:cupo]
        return menu

    if not reg.prendido("jefe"):
        return por_reglas(), "reglas"
    reg.empezar("jefe")
    if not ia.disponible:
        menu = por_reglas()
        reg.anotar("jefe", "sin clave de IA", f"Eligió {len(menu)} temas por puntaje (sin IA no escribe el porqué)", len(menu))
        return menu, "reglas"
    nombres_eje = {e["id"]: e["nombre"] for e in (leer(DATOS / "ejes.json", {}) or {}).get("ejes", [])}
    lista = "\n".join(
        f"#{c['id']} [{SECCIONES[c['seccion']]}] {c['n_medios']} medios" +
        (f" · agenda: {', '.join(nombres_eje.get(e, e) for e in c.get('ejes', []))}" if c.get("ejes") else "") + f" · {c['titulo']}" +
        "".join(f"\n    - {n['medio']}: {n['titulo']}" for n in c["notas"][1:3])
        for c in limpios[:45])
    prompt = instruccion("jefe", cupos=", ".join(f"{SECCIONES[k]} {v}" for k, v in cupos.items())) + \
        ("\n\nYa se trabajaron estos temas en los últimos días, no los repitas:\n" + "\n".join("- " + t for t in recientes[-30:]) if recientes else "") + \
        "\n\nCANDIDATOS:\n" + lista
    try:
        r = ia.json(prompt)
        por_id = {c["id"]: c for c in limpios}
        menu = []
        for x in r.get("menu", []):
            c = por_id.get(int(str(x.get("id", "0")).lstrip("#") or 0))
            if c and c not in menu:
                c["por_que"] = (x.get("por_que") or "").strip()
                menu.append(c)
        total = sum(cupos.values())
        if not menu:
            raise ValueError("la IA no eligió ningún tema válido")
        menu = menu[: total + 2]
        reg.anotar("jefe", "funcionó", f"Eligió {len(menu)} de {len(limpios)} temas", len(menu))
        return menu, "ia"
    except Exception as e:  # noqa: BLE001
        menu = por_reglas()
        reg.anotar("jefe", "falló", f"IA: {e} — eligió por puntaje", len(menu))
        return menu, "reglas"


# ───────────────────────── 7 · fuentes y autores ─────────────────────────

def leer_fuente(url):
    from bs4 import BeautifulSoup
    html, final = pedir(url)
    s = BeautifulSoup(html, "html.parser")

    def meta(*nombres):
        for n in nombres:
            m = s.find("meta", attrs={"property": n}) or s.find("meta", attrs={"name": n})
            if m and m.get("content"):
                return m["content"].strip()
        return None

    autor, fecha = meta("author", "article:author", "parsely-author", "sailthru.author", "dc.creator"), meta("article:published_time", "date", "pubdate", "dc.date")
    for bloque in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(bloque.string or "")
        except Exception:  # noqa: BLE001
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if not isinstance(x, dict):
                continue
            a = x.get("author")
            if a and not autor:
                a = a[0] if isinstance(a, list) and a else a
                autor = a.get("name") if isinstance(a, dict) else a if isinstance(a, str) else None
            if x.get("datePublished") and not fecha:
                fecha = x["datePublished"]
    if autor and autor.startswith("http"):
        autor = autor.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
    if not autor:
        b = s.select_one('[rel="author"], .author-name, .autor, .byline, .firma, [class*="author"] a')
        if b:
            autor = b.get_text(" ", strip=True)[:80] or None

    cuerpo = s.find("article") or s.find(attrs={"itemprop": "articleBody"}) or s
    parrafos = [p.get_text(" ", strip=True) for p in cuerpo.find_all("p")]
    texto = "\n".join(p for p in parrafos if len(p) > 60)[:6000]
    agencias = sorted({a for a in AGENCIAS if re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w])", texto)} |
                      ({"AP"} if re.search(r"\(AP\)|agencia AP\b", texto) else set()))
    oficiales = []
    for a in cuerpo.find_all("a", href=True):
        h = urllib.parse.urljoin(final, a["href"])
        dom = urllib.parse.urlparse(h).netloc.lower()
        if OFICIALES.search(dom) and h not in oficiales:
            oficiales.append(h)
    return {"autor": autor, "fecha_pub": fecha, "imagen": meta("og:image", "twitter:image"), "descripcion": meta("og:description", "description"),
            "agencias": agencias, "oficiales": oficiales[:5], "leida": bool(texto), "palabras": len(texto.split())}, texto


def fuentes(tema, reg, textos):
    salida = []
    for n in tema["notas"][:4]:
        f = {k: n.get(k) for k in ("medio", "url", "titulo", "pais", "tipo", "fecha", "idioma")}
        try:
            datos, texto = leer_fuente(n["url"])
            f.update(datos)
            textos[n["url"]] = texto
        except Exception as e:  # noqa: BLE001
            f.update({"leida": False, "error": str(e)[:100]})
            textos[n["url"]] = ""
        if not f.get("imagen"):
            f["imagen"] = n.get("imagen")
        f["resumen"] = n.get("resumen")
        salida.append(f)
    return salida


# ───────────────────────── 6 · redactor ─────────────────────────

PERMITIDAS = {"p", "strong", "b", "em", "i", "h3", "blockquote", "br", "a"}


def limpiar_html(html):
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html or "", "html.parser")
    for t in s.find_all(["script", "style", "iframe", "noscript"]):
        t.decompose()
    for t in s.find_all(True):
        if t.name not in PERMITIDAS:
            t.unwrap()
        else:
            t.attrs = {k: v for k, v in t.attrs.items() if t.name == "a" and k in ("href", "class")}
    texto = str(s).strip()
    if texto and not texto.startswith("<"):
        texto = "<p>" + texto + "</p>"
    return texto


def material(tema, fts, textos, tope=2500):
    partes = []
    for i, f in enumerate(fts, 1):
        cab = f"[{i}] {f.get('medio')}" + (f" ({f['pais']}" + (f", {f['tipo']}" if f.get("tipo") else "") + ")" if f.get("pais") else "") + \
            (f" — autor: {f['autor']}" if f.get("autor") else "") + (f" — {str(f.get('fecha_pub') or f.get('fecha') or '')[:10]}")
        texto = textos.get(f["url"]) or f.get("descripcion") or f.get("resumen") or ""
        partes.append(f"{cab}\nTítulo: {f.get('titulo')}\nTexto: {texto[:tope]}")
    return f"TEMA: {tema['titulo']}\n\nFUENTES:\n" + "\n\n".join(partes)


def redactor(tema, fts, textos, ia):
    total = sum(len((textos.get(f["url"]) or "").split()) for f in fts)
    mn, mx = (350, 550) if total > 300 else (150, 250)
    prompt = instruccion("redactor", min=mn, max=mx, estilo=instruccion("estilo")) + "\n\n" + material(tema, fts, textos)
    r = ia.json(prompt)
    html = limpiar_html(r.get("cuerpo_html", ""))
    if palabras(html) < 60:
        raise ValueError("el borrador vino vacío o muy corto")
    return {"cuerpo_html": html, "region": r.get("region") or tema.get("region") or "", "tema": r.get("tema") or tema.get("tema"),
            "falta": r.get("falta"), "breve": total <= 300}


# ───────────────────────── 8 · verificador ─────────────────────────

def verificacion_base(tema, fts):
    medios = {f.get("medio") for f in fts}
    return {"independientes": len(medios), "paises": sorted({f["pais"] for f in fts if f.get("pais")}),
            "estatal": [f["medio"] for f in fts if f.get("tipo") == "Agencia estatal"],
            "oficiales": sorted({o for f in fts for o in (f.get("oficiales") or [])})[:5],
            "agencias_citadas": sorted({a for f in fts for a in (f.get("agencias") or [])}),
            "leidas": sum(1 for f in fts if f.get("leida"))}


def verificador(borr, tema, fts, textos, ia):
    prompt = instruccion("verificador") + "\n\nBORRADOR:\n" + re.sub(r"<[^>]+>", " ", borr["cuerpo_html"]) + "\n\n" + material(tema, fts, textos, 3000)
    r = ia.json(prompt)
    est = str(r.get("estado", "")).lower()
    est = "rojo" if "rojo" in est else "verde" if "verde" in est else "amarillo"
    return {"estado": est, "sin_respaldo": r.get("sin_respaldo") or [], "contradicciones": r.get("contradicciones") or [], "observaciones": r.get("observaciones") or []}


# ───────────────────────── 12 · corrector ─────────────────────────

def corrector(html, ia):
    r = ia.json(instruccion("corrector", estilo=instruccion("estilo")) + "\n\nBORRADOR:\n" + html)
    nuevo = limpiar_html(r.get("cuerpo_html", ""))
    a, b = palabras(html), palabras(nuevo)
    if not (0.75 * a <= b <= 1.25 * a):  # si recortó o agregó demasiado, se queda el original
        raise ValueError(f"la corrección cambió demasiado el largo ({a} → {b} palabras)")
    return nuevo, (r.get("cambios") or "").strip()


# ───────────────────────── 10 · titulador ─────────────────────────

def titulador(html, ia):
    r = ia.json(instruccion("titulador") + "\n\nBORRADOR:\n" + re.sub(r"<[^>]+>", " ", html))
    tit = [t.strip() for t in (r.get("titulos") or []) if isinstance(t, str) and t.strip()][:3]
    baj = [t.strip() for t in (r.get("bajadas") or []) if isinstance(t, str) and t.strip()][:2]
    if not tit:
        raise ValueError("no propuso títulos")
    return tit, baj


# ───────────────────────── 9 · fotos ─────────────────────────

def nombres_propios(titulo):
    pal = re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+(?:\s+(?:de\s+)?[A-ZÁÉÍÓÚÑ][\wáéíóúñ]+)*", titulo or "")
    vacias = {"El", "La", "Los", "Las", "Un", "Una", "En", "Por", "Con", "Para", "Tras", "Qué", "Cómo", "Quién", "Sin", "Ante"}
    return [p for p in pal if p not in vacias and len(p) > 3][:2]


def wikimedia(consulta, maximo=2):
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": "6", "gsrsearch": f"{consulta} filetype:bitmap",
              "gsrlimit": str(maximo), "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1000"}
    txt, _ = pedir("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params))
    paginas = (json.loads(txt).get("query") or {}).get("pages", {})
    fotos = []
    for p in paginas.values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata") or {}
        val = lambda k: re.sub(r"<[^>]+>", "", (md.get(k) or {}).get("value", "")).strip()  # noqa: E731
        fotos.append({"url": ii.get("thumburl") or ii.get("url"), "pagina": ii.get("descriptionurl"),
                      "credito": f"Foto: {val('Artist') or 'autor en Wikimedia'} / Wikimedia Commons ({val('LicenseShortName') or 'licencia libre'})",
                      "descripcion": val("ImageDescription")[:200], "licencia": val("LicenseShortName"), "fuente": "Wikimedia Commons", "libre": True})
    return fotos


def fotos(tema, fts):
    salida, vistas = [], set()
    for f in fts:
        if f.get("imagen") and f["imagen"] not in vistas:
            vistas.add(f["imagen"])
            salida.append({"url": f["imagen"], "pagina": f["url"], "credito": f"Foto: {f.get('medio')}", "fuente": f.get("medio"),
                           "descripcion": f.get("titulo"), "libre": False})
    for nombre in nombres_propios(tema["titulo"]):
        try:
            for x in wikimedia(nombre):
                if x["url"] and x["url"] not in vistas:
                    vistas.add(x["url"]); salida.append(x)
        except Exception:  # noqa: BLE001
            pass
    return salida[:5]


# ───────────────────────── 11 · enlazador ─────────────────────────

def notas_del_diario():
    """Lista pública de notas del diario (RSS o sitemap). Solo lectura: no toca el repositorio del diario."""
    errores = []
    for ruta in ("/rss.xml", "/feed.xml", "/rss/", "/sitemap-0.xml", "/sitemap.xml"):
        try:
            txt, _ = pedir(DIARIO + ruta)
        except Exception as e:  # noqa: BLE001
            errores.append(f"{ruta}: {str(e)[:40]}"); continue
        items = re.findall(r"<item>.*?</item>", txt, re.S)
        notas = []
        for it in items:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            l = re.search(r"<link>(.*?)</link>", it, re.S)
            if t and l:
                notas.append({"titulo": re.sub(r"\s+", " ", t.group(1)).strip(), "url": l.group(1).strip()})
        if not notas:
            for u in re.findall(r"<loc>(.*?)</loc>", txt):
                slug = u.rstrip("/").rsplit("/", 1)[-1]
                if "/notas/" in u or "/nota/" in u or slug.count("-") >= 3:
                    notas.append({"titulo": slug.replace("-", " "), "url": u.strip()})
        if notas:
            return notas, ruta
        errores.append(f"{ruta}: sin notas")
    raise RuntimeError("; ".join(errores))


def enlazar(html, enlaces):
    """Pone cada enlace sobre la primera palabra del texto que coincide, sin tocar enlaces ya puestos.
    enlaces: lista de (palabras_clave_normalizadas, url, clase, titulo)."""
    from bs4 import BeautifulSoup, NavigableString
    s = BeautifulSoup(html, "html.parser")
    puestos = []
    for claves, url, clase, titulo in enlaces:
        hecho = False
        for nodo in list(s.find_all(string=True)):
            if hecho:
                break
            if nodo.find_parent("a") or not isinstance(nodo, NavigableString):
                continue
            texto = str(nodo)
            for m in re.finditer(r"[\wÁÉÍÓÚáéíóúÑñ][\wÁÉÍÓÚáéíóúÑñ./-]*", texto):
                w = sin_acentos(m.group(0)).rstrip(".")
                if any(w == c or (len(c) >= 5 and w.startswith(c)) for c in claves):
                    a = s.new_tag("a", href=url, attrs={"class": clase, "title": titulo})
                    a.string = m.group(0)
                    nodo.replace_with(NavigableString(texto[:m.start()]), a, NavigableString(texto[m.end():]))
                    hecho = True
                    puestos.append({"url": url, "clase": clase, "titulo": titulo, "palabra": m.group(0)})
                    break
    return str(s), puestos


def enlazador(borr, tema, fts, diario):
    enlaces = []
    # externos (azul): el nombre de cada medio citado lleva a su nota
    for f in fts:
        medio = (f.get("medio") or "").strip()
        if not medio or not f.get("url"):
            continue
        base = sin_acentos(re.sub(r"^www\.|\.(com|net|org)(\.[a-z]{2})?$", "", medio).split(" (")[0])
        claves = {base} | ({base.split(".")[0]} if "." in base else set())
        genericas = {"espanol", "noticias", "diario", "agencia", "castellano", "press", "mundo", "news", "radio", "medio"}
        primera = sin_acentos(medio.split()[0]).strip("/.,") if medio.split() else ""
        if len(primera) > 3 and primera not in genericas:
            claves.add(primera)
        claves -= genericas
        enlaces.append((sorted(claves - {""}), f["url"], "externo", f"Fuente: {medio}"))
    # internos (rojo): notas anteriores del diario sobre lo mismo
    relacionadas = []
    if diario:
        clave = AG.raices(tema["titulo"] + " " + re.sub(r"<[^>]+>", " ", borr["cuerpo_html"])[:600])
        def parecido(n):
            r = AG.raices(n["titulo"])
            return len(clave & r) / (len(r) or 1)
        for n in sorted(diario, key=parecido, reverse=True)[:3]:
            comunes = clave & AG.raices(n["titulo"])
            if len(comunes) >= 2 and parecido(n) >= 0.3:
                relacionadas.append(n)
                enlaces.append((sorted(comunes, key=len, reverse=True), n["url"], "interno", f"Diario Federal: {n['titulo']}"))
    html, puestos = enlazar(borr["cuerpo_html"], enlaces)
    return html, puestos, relacionadas


# ───────────────────────── la cadena ─────────────────────────

def correr(nombre_agente, reg, ia, fn, *args):
    """Corre un agente sobre un tema. Devuelve el resultado o None, y deja anotado qué pasó."""
    if not reg.prendido(nombre_agente):
        return None
    reg.empezar(nombre_agente)
    try:
        return fn(*args)
    except SinClave:
        reg.anotar(nombre_agente, "sin clave de IA", "No hay ninguna IA disponible")
    except Exception as e:  # noqa: BLE001
        reg.anotar(nombre_agente, "falló", str(e))
        traceback.print_exc()
    return None


def main():
    import os
    horas = os.environ.get("SALTEAR_SI_RECIENTE", "").strip()
    previa = leer(DATOS / "redaccion.json") or {}
    if horas and previa.get("generado"):
        edad = (datetime.now(timezone.utc) - datetime.fromisoformat(previa["generado"])).total_seconds() / 3600
        if edad < float(horas):
            print(f"La última vuelta fue hace {edad:.1f} horas: no hace falta otra todavía.")
            return 0
    conf = leer(AGENTES / "config.json")
    noticias = leer(DATOS / "noticias.json")
    if not noticias:
        print("No hay datos/noticias.json todavía: primero tiene que correr el recolector.")
        return 1
    reg = Registro(conf)
    ia = IA(conf.get("ia", {}))
    hist_ruta = DATOS / "redaccion-historial.json"
    historial = [h for h in (leer(hist_ruta, []) or []) if h.get("fecha", "") >= (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()]

    candidatos = monitores(noticias, conf, reg)
    menu, como = jefe(candidatos, conf, ia, reg, historial)
    print(f"Menú del día: {len(menu)} temas (elegidos por {como}) de {len(candidatos)} candidatos", flush=True)

    try:
        diario, ruta_diario = notas_del_diario()
        print(f"Diario: {len(diario)} notas leídas de {ruta_diario}", flush=True)
    except Exception as e:  # noqa: BLE001
        diario, ruta_diario = [], None
        print(f"Diario: no pude leer la lista de notas ({e})", flush=True)

    cuenta = {k: 0 for k in reg.estado}
    borradores = []
    for i, tema in enumerate(menu, 1):
        print(f"[{i}/{len(menu)}] {SECCIONES[tema['seccion']]} · {tema['titulo'][:90]}", flush=True)
        textos = {}
        b = {"id": f"{datetime.now(timezone.utc):%Y%m%d}-{i:02d}", "seccion": tema["seccion"], "por_que": tema.get("por_que", ""),
             "titulo_tema": tema["titulo"], "puntaje": tema["puntaje"], "n_medios": tema["n_medios"], "paises": tema.get("paises", []),
             "region": tema.get("region") or "", "tema": tema.get("tema"), "ejes": tema.get("ejes", []),
             "region_mundo": next((n.get("region_mundo") for n in tema["notas"] if n.get("region_mundo")), None), "titulos": [], "bajadas": [], "cuerpo_html": "", "fotos": [],
             "enlaces": [], "relacionadas": [], "verificacion": {}, "fuentes": []}

        fts = correr("fuentes", reg, ia, fuentes, tema, reg, textos)
        if fts is None:
            fts = [{k: n.get(k) for k in ("medio", "url", "titulo", "pais", "tipo", "fecha", "resumen", "imagen")} for n in tema["notas"][:4]]
        else:
            cuenta["fuentes"] += 1
        b["fuentes"] = [{k: v for k, v in f.items() if k != "descripcion"} for f in fts]

        r = correr("redactor", reg, ia, redactor, tema, fts, textos, ia)
        if r:
            cuenta["redactor"] += 1
            b.update({k: v for k, v in r.items() if v})

        b["verificacion"] = verificacion_base(tema, fts)
        if b["cuerpo_html"]:
            v = correr("verificador", reg, ia, verificador, b, tema, fts, textos, ia)
            if v:
                cuenta["verificador"] += 1
                b["verificacion"].update(v)
            c = correr("corrector", reg, ia, corrector, b["cuerpo_html"], ia)
            if c:
                cuenta["corrector"] += 1
                b["cuerpo_html"], b["correccion"] = c
            t = correr("titulador", reg, ia, titulador, b["cuerpo_html"], ia)
            if t:
                cuenta["titulador"] += 1
                b["titulos"], b["bajadas"] = t
        if not b["titulos"]:
            b["titulos"] = [tema["titulo"]]

        ph = correr("fotos", reg, ia, fotos, tema, fts)
        if ph is not None:
            cuenta["fotos"] += 1
            b["fotos"] = ph

        if b["cuerpo_html"]:
            e = correr("enlazador", reg, ia, enlazador, b, tema, fts, diario)
            if e:
                cuenta["enlazador"] += 1
                b["cuerpo_html"], b["enlaces"], b["relacionadas"] = e
        borradores.append(b)

    # resumen de lo que hizo cada agente de producción y edición
    detalle = {
        "fuentes": lambda: f"Leyó {sum(sum(1 for f in b['fuentes'] if f.get('leida')) for b in borradores)} de {sum(len(b['fuentes']) for b in borradores)} notas originales; "
                           f"{sum(1 for b in borradores for f in b['fuentes'] if f.get('autor'))} con autor",
        "redactor": lambda: f"{cuenta['redactor']} borradores de {len(borradores)} temas",
        "verificador": lambda: " · ".join(f"{sum(1 for b in borradores if b['verificacion'].get('estado') == e)} {e}" for e in ("verde", "amarillo", "rojo")),
        "corrector": lambda: f"Corrigió {cuenta['corrector']} borradores",
        "titulador": lambda: f"Tituló {cuenta['titulador']} borradores",
        "fotos": lambda: f"{sum(len(b['fotos']) for b in borradores)} fotos propuestas ({sum(1 for b in borradores for f in b['fotos'] if f.get('libre'))} libres)",
        "enlazador": lambda: f"{sum(1 for b in borradores for x in b['enlaces'] if x['clase'] == 'interno')} enlaces al diario y "
                             f"{sum(1 for b in borradores for x in b['enlaces'] if x['clase'] == 'externo')} a fuentes" +
                             ("" if ruta_diario else " (no pude leer la lista de notas del diario)"),
    }
    for aid, fn in detalle.items():
        e = reg.estado[aid]
        if not e["prendido"]:
            continue
        if e["resultado"] == "sin correr":
            if cuenta[aid]:
                e["resultado"] = "funcionó"
            elif e["ia"] and not ia.disponible:
                e["resultado"] = "sin clave de IA"
            else:
                e["resultado"] = "esperando borradores"
        if e["resultado"] == "esperando borradores":
            e["detalle"] = "Trabaja sobre los borradores del Redactor, que todavía no escribió ninguno"
        elif e["resultado"] not in ("sin clave de IA",):
            e["detalle"] = (fn() + (f" · último error: {e['detalle']}" if e["resultado"] in ("falló", "con fallas") and e.get("detalle") else ""))[:260]
        else:
            e["detalle"] = "Falta cargar la clave gratuita de Gemini o Groq en GitHub (ver LEEME de agentes)"
        e["produjo"] = cuenta[aid]
        e.setdefault("fin", ahora())

    elegidos = {id(t) for t in menu}
    reserva = [{"seccion": c["seccion"], "titulo": c["titulo"], "n_medios": c["n_medios"], "puntaje": c["puntaje"], "region": c.get("region"), "ejes": c.get("ejes", []),
                "tema": c.get("tema"), "notas": [{k: n.get(k) for k in ("medio", "url", "titulo", "fecha", "pais")} for n in c["notas"][:4]]}
               for c in sorted(candidatos, key=lambda c: c["puntaje"], reverse=True) if id(c) not in elegidos][:40]

    salida = {"generado": ahora(), "noticias_de": noticias.get("generado"), "eleccion": como,
              "ia": {"disponible": ia.disponible, "usado": ia.usado, "llamadas": ia.llamadas},
              "diario": {"notas": len(diario), "desde": ruta_diario},
              "agentes": reg.lista(), "menu": borradores, "reserva": reserva}
    (DATOS / "redaccion.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    historial += [{"fecha": ahora(), "titulo": b["titulo_tema"]} for b in borradores]
    hist_ruta.write_text(json.dumps(historial[-120:], ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for e in reg.estado.values() if e["resultado"] == "funcionó")
    print(f"Listo: {len(borradores)} temas, {cuenta['redactor']} borradores, {ok} de 12 agentes funcionaron, {ia.llamadas} pedidos a la IA ({ia.usado or 'sin IA'}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
