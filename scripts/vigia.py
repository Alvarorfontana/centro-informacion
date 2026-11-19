"""
Vigía de copias: busca si alguien levantó notas de Diario Federal sin citar.

Una vez por semana (GitHub Actions, gratis):
  1. Lee las últimas notas del RSS público del diario.
  2. De cada nota saca una frase textual del cuerpo (no el título, que se repite en todos lados).
  3. Le pide a Gemini (clave gratis GEMINI_API_KEY) que busque esa frase en Google con su herramienta de búsqueda.
  4. Abre cada página encontrada y comprueba si de verdad tiene texto copiado de la nota.
  5. Guarda todo en datos/vigia.json y avisa por Telegram solo lo nuevo.

Las redes (Facebook, Instagram, X, TikTok) no dejan leer sus páginas: si aparecen, se avisan como "revisar a mano".
No toca el diario ni publica nada.
"""

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ia import clave, leer_json  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "datos" / "vigia.json"
DIARIO = "https://www.diariofederal.com.ar"
PROPIOS = ("diariofederal.com.ar", "centro-informacion", "vercel.app", "pages.dev", "github.com")
REDES = ("facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com", "threads.net", "youtube.com", "linkedin.com", "t.me")
UA = {"User-Agent": "Mozilla/5.0 (VigiaDiarioFederal)"}

MAX_NOTAS = int(os.environ.get("VIGIA_MAX_NOTAS", "12"))   # notas por vuelta (cada una es 1 búsqueda en Gemini)
DIAS = int(os.environ.get("VIGIA_DIAS", "10"))              # antigüedad máxima de las notas a revisar
MODELOS = ["gemini-flash-latest", "gemini-2.5-flash"]


# ---------- utilidades ----------

def bajar(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        final = r.geturl()
        crudo = r.read(2_500_000)
        enc = r.headers.get_content_charset() or "utf-8"
    return final, crudo.decode(enc, errors="replace")


def normal(t):
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ ]+", " ", t).split()


def tejas(palabras, n=8):
    return {" ".join(palabras[i:i + n]) for i in range(max(0, len(palabras) - n + 1))}


def texto_de_html(html):
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "nav", "header", "footer", "aside", "form"]):
        t.decompose()
    cont = s.find("article") or s.find("main") or s.body or s
    return [p.get_text(" ", strip=True) for p in cont.find_all("p") if len(p.get_text(strip=True)) > 60]


def dominio(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:  # noqa: BLE001
        return ""


# ---------- 1. notas del diario ----------

def notas_recientes():
    import feedparser
    _, xml = bajar(DIARIO + "/rss.xml")
    feed = feedparser.parse(xml)
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS)
    notas = []
    for e in feed.entries:
        url = e.get("link") or ""
        if url.startswith("/"):
            url = DIARIO + url
        f = e.get("published_parsed")
        fecha = datetime(*f[:6], tzinfo=timezone.utc) if f else None
        if fecha and fecha < limite:
            continue
        notas.append({"titulo": e.get("title", "").strip(), "url": url, "fecha": fecha.isoformat() if fecha else ""})
        if len(notas) >= MAX_NOTAS:
            break
    return notas


def frase_distintiva(parrafos):
    """Una frase del cuerpo, de 12 a 16 palabras, del segundo o tercer párrafo (lo más propio de la nota)."""
    orden = parrafos[1:4] + parrafos[4:] + parrafos[:1]
    for p in orden:
        for o in re.split(r"(?<=[.!?])\s+", p):
            pal = o.strip().strip('"“”«»').split()
            if len(pal) >= 14 and not re.search(r"[“”\"«»]", o):  # evita citas textuales de terceros
                medio = max(0, (len(pal) - 14) // 2)
                return " ".join(pal[medio:medio + 14]).strip(",;:")
    return ""


# ---------- 2. búsqueda con Gemini + Google ----------

def buscar(frase, titulo, key):
    prompt = (
        "Buscá en Google páginas web y publicaciones en redes sociales que reproduzcan este texto de un diario argentino, "
        "aunque sea con pequeños cambios. Buscá la frase exacta entre comillas y también el título.\n"
        f'Frase: "{frase}"\nTítulo: "{titulo}"\n'
        "Ignorá diariofederal.com.ar. Respondé SOLO un JSON así: "
        '{"resultados":[{"url":"...","sitio":"...","por_que":"..."}]}. Si no encontrás nada, lista vacía.'
    )
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "tools": [{"google_search": {}}],
              "generationConfig": {"temperature": 0.1}}
    for modelo in MODELOS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(),
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        for vuelta in range(2):
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    d = json.loads(r.read().decode())
                return extraer(d)
            except urllib.error.HTTPError as e:
                print(f"  Gemini {modelo}: HTTP {e.code}")
                if e.code in (429, 503) and vuelta == 0:
                    time.sleep(40)
                    continue
                break
            except Exception as e:  # noqa: BLE001
                print(f"  Gemini {modelo}: {str(e)[:100]}")
                break
    return []


def extraer(d):
    cand = (d.get("candidates") or [{}])[0]
    texto = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []))
    vistos = []
    try:
        for r in (leer_json(texto) or {}).get("resultados", []):
            if r.get("url"):
                vistos.append({"url": r["url"], "sitio": r.get("sitio", ""), "por_que": r.get("por_que", "")})
    except Exception:  # noqa: BLE001
        pass
    # Las fuentes reales que usó Google (vienen como enlaces de redirección; se resuelven después)
    for ch in (cand.get("groundingMetadata") or {}).get("groundingChunks", []) or []:
        w = ch.get("web") or {}
        if w.get("uri"):
            vistos.append({"url": w["uri"], "sitio": w.get("title", ""), "por_que": "fuente de la búsqueda"})
    return vistos


# ---------- 3. comprobar ----------

def comprobar(cand, tejas_nota):
    """Abre la página y mide cuánto texto de la nota contiene. Devuelve el hallazgo o None."""
    url = cand["url"]
    try:
        final, html = bajar(url)
    except Exception:  # noqa: BLE001
        final, html = url, ""
    dom = dominio(final) or cand.get("sitio", "").lower()
    if any(p in dom for p in PROPIOS):
        return None
    if any(dom == r or dom.endswith("." + r) for r in REDES):
        return {"url": final, "sitio": dom, "estado": "revisar", "coincidencia": None,
                "detalle": "Red social: no se puede leer sola, hay que abrirla"}
    if not html:
        return None
    pag = tejas(normal(" ".join(texto_de_html(html))))
    if not pag:
        return None
    comunes = len(pag & tejas_nota)
    prop = comunes / max(1, len(tejas_nota))
    if comunes < 3:
        return None
    cita = DIARIO.split("//")[1].removeprefix("www.") in html.lower() or "diario federal" in html.lower()
    estado = "copia" if prop >= 0.25 else "fragmento"
    return {"url": final, "sitio": dom, "estado": estado, "coincidencia": round(prop * 100),
            "cita_al_diario": cita, "detalle": f"{round(prop * 100)}% del texto coincide" + (" · menciona al diario" if cita else " · sin citar al diario")}


# ---------- principal ----------

def main():
    key = clave("GEMINI_API_KEY")
    if not key:
        print("Falta GEMINI_API_KEY: el vigía no puede buscar.")
        return
    previo = {}
    if SALIDA.exists():
        try:
            previo = json.loads(SALIDA.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            previo = {}
    conocidos = {h["url"] for h in previo.get("hallazgos", [])}

    notas = notas_recientes()
    print(f"Revisando {len(notas)} notas")
    hallazgos, nuevos, revisadas = list(previo.get("hallazgos", [])), [], []
    for n in notas:
        try:
            _, html = bajar(n["url"])
        except Exception as e:  # noqa: BLE001
            print("  no pude abrir", n["url"], e)
            continue
        parrafos = texto_de_html(html)
        frase = frase_distintiva(parrafos)
        if not frase:
            continue
        tj = tejas(normal(" ".join(parrafos)))
        print("•", n["titulo"][:80], "→", frase)
        encontrados = buscar(frase, n["titulo"], key)
        revisadas.append({"titulo": n["titulo"], "url": n["url"], "frase": frase, "candidatos": len(encontrados)})
        for c in encontrados:
            h = comprobar(c, tj)
            if not h or h["url"] in conocidos:
                continue
            h.update({"nota": n["titulo"], "nota_url": n["url"], "detectado": datetime.now(timezone.utc).isoformat()})
            conocidos.add(h["url"])
            hallazgos.append(h)
            nuevos.append(h)
        time.sleep(6)

    SALIDA.write_text(json.dumps({
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "revisadas": revisadas,
        "hallazgos": hallazgos[-300:],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(nuevos)} hallazgos nuevos")

    if nuevos or os.environ.get("VIGIA_AVISAR_SIEMPRE"):
        import avisar
        lineas = ["Vigía de copias · Diario Federal", f"{len(revisadas)} notas revisadas · {len(nuevos)} hallazgos nuevos", ""]
        etiqueta = {"copia": "🔴 Copia", "fragmento": "🟠 Fragmento", "revisar": "🔎 Revisar"}
        for h in nuevos[:15]:
            lineas += [f"{etiqueta.get(h['estado'], '•')} · {h['sitio']} — {h['detalle']}", f"   Nota: {h['nota'][:90]}", f"   {h['url']}", ""]
        try:
            print("Aviso:", avisar.mandar("\n".join(lineas)))
        except Exception as e:  # noqa: BLE001
            print("No se pudo avisar:", e)


if __name__ == "__main__":
    main()
