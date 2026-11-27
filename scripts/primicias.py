#!/usr/bin/env python3
"""
Agente de Primicias regionales: enterarse primero de lo que pasa en las provincias.

Idea: las noticias de las provincias suelen salir antes en los diarios regionales y
recién después (o nunca) en los medios nacionales. Este agente corre cada hora, después
de recolectar, y hace dos cosas:

  1. Primicias: hechos de las últimas 24 horas que cuentan dos o más medios regionales
     distintos y que ningún medio nacional levantó todavía. Avisa al celular las nuevas.
  2. Seguimiento: guarda cada primicia 72 horas y anota cuándo y qué medio nacional la
     levantó. Con eso arma el ranking de los diarios regionales que más se adelantan.
     Se mide de una recolección a otra (cada hora), porque los RSS solo traen lo último.

Trabaja solo con titulares, enlaces y horarios que ya trae recolectar.py (RSS y GDELT,
fuentes que permiten su lectura). No entra a ninguna app ni copia el texto de las notas.
Deja todo en datos/primicias.json.
"""

import json
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agrupar as AG  # noqa: E402
import recolectar as REC  # noqa: E402

HORAS = 24            # ventana para buscar primicias
GUARDAR_HORAS = 72    # cuánto se sigue cada primicia esperando que la levante un nacional
MIN_REGIONALES = 2    # medios regionales distintos para confiar en el hecho
MAX_AVISOS = 3        # primicias por aviso, para no llenar el celular

# Medios nacionales (nombre de la fuente RSS o dominio que trae GDELT). El resto de los
# medios argentinos cuenta como regional o local.
CLAVES_NAC = ["infobae", "perfil", "cronista", "pagina12", "pagina/12", "lanacion", "la nacion", "clarin", "ambito",
              "todo noticias", "tn.com.ar", "noticias argentinas", "na · ", "tiempo argentino", "tiempoar", "eldestape",
              "el destape", "letra p", "letrap", "chequeado", "iprofesional", "ole.com.ar", "c5n", "minutouno", "a24.com",
              "cadena3", "telefe", "eltrece", "eldiarioar", "eldiario.ar", "baenegocios", "cenital", "lapoliticaonline",
              "la politica online", "infocielo", "urgente24"]


def _norm(t):
    return unicodedata.normalize("NFD", t or "").encode("ascii", "ignore").decode().lower().strip()


def clave_medio(medio):
    """'Río Negro' y 'rionegro.com.ar' son el mismo diario."""
    m = _norm(medio)
    for suf in (".com.ar", ".com", ".ar", ".net", ".info"):
        if m.endswith(suf):
            m = m[: -len(suf)]
    return "".join(ch for ch in m.split("(")[0] if ch.isalnum())


def es_nacional(medio):
    m = _norm(medio)
    return m in ("tn", "ole", "na") or any(c in m for c in CLAVES_NAC)


def _fecha(x):
    try:
        f = datetime.fromisoformat(x)
        return f if f.tzinfo else f.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def notas_argentinas(noticias, desde):
    notas, vistos = [], set()
    for n in AG.todas_las_notas(noticias):
        f = _fecha(n.get("fecha"))
        if (n.get("pais") != "Argentina" or not f or f < desde or not n.get("url") or n["url"] in vistos
                or REC.es_ruido(n.get("titulo") or "")):
            continue
        vistos.add(n["url"])
        notas.append(dict(n, _f=f, _nac=es_nacional(n.get("medio")), _k=AG.raices(n["titulo"])))
    return notas


def mismo_hecho(claves_a, claves_b):
    return any(AG.jaccard(a, b) >= AG.UMBRAL for a in claves_a for b in claves_b)


def buscar_primicias(notas, ahora):
    AG.MIN_MEDIOS = 1
    grupos = AG.agrupar([{k: v for k, v in n.items() if not k.startswith("_")} for n in notas], ahora=ahora)
    AG.MIN_MEDIOS = 2
    salida = []
    for g in grupos:
        # agrupar() deja la nota más nueva de cada medio: se recuperan todas las del hecho
        sets = [AG.raices(m["titulo"]) for m in g["notas"]]
        G = [n for n in notas if mismo_hecho([n["_k"]], sets)]
        reg = [n for n in G if not n["_nac"]]
        if not reg or any(n["_nac"] for n in G):
            continue
        medios = {}
        for n in sorted(reg, key=lambda n: n["_f"]):
            medios.setdefault(clave_medio(n.get("medio")), n.get("medio"))
        if len(medios) < MIN_REGIONALES:
            continue
        primero = min(reg, key=lambda n: n["_f"])
        salida.append({"titulo": primero["titulo"], "region": g.get("region") or primero.get("region"), "tema": g.get("tema"),
                       "ejes": g.get("ejes", []), "primer_medio": primero.get("medio"),
                       "primera_hora": primero["_f"].isoformat(timespec="minutes"),
                       "medios_regionales": list(medios.values()),
                       "notas": [{k: n.get(k) for k in ("titulo", "url", "medio", "fecha")}
                                 for n in sorted(reg, key=lambda n: n["_f"])[:6]]})
    # Las más confirmadas y las que tocan la agenda del diario, primero
    salida.sort(key=lambda x: (len(x["medios_regionales"]) + 2 * bool(x["ejes"]), x["primera_hora"]), reverse=True)
    return salida


def seguir(seguimiento, notas):
    """Marca las primicias guardadas que ya levantó un medio nacional."""
    nac = [n for n in notas if n["_nac"]]
    for p in seguimiento:
        if p.get("levantada"):
            continue
        claves = [AG.raices(x["titulo"]) for x in p.get("notas", [])] or [AG.raices(p["titulo"])]
        t0 = _fecha(p["primera_hora"])
        hits = [n for n in nac if n["_f"] >= t0 and mismo_hecho([n["_k"]], claves)]
        if hits:
            h = min(hits, key=lambda n: n["_f"])
            p["levantada"] = {"medio": h.get("medio"), "url": h.get("url"), "fecha": h["_f"].isoformat(timespec="minutes"),
                              "horas_despues": round((h["_f"] - t0).total_seconds() / 3600, 1)}
    return seguimiento


def ranking(seguimiento):
    """Qué diarios regionales publican primero lo que después levantan los nacionales."""
    r = {}
    for p in seguimiento:
        lev = p.get("levantada")
        if not lev:
            continue
        x = r.setdefault(p["primer_medio"], {"medio": p["primer_medio"], "levantadas": 0, "horas": []})
        x["levantadas"] += 1
        x["horas"].append(lev["horas_despues"])
    return sorted(({"medio": x["medio"], "levantadas": x["levantadas"],
                    "mediana_horas_de_ventaja": sorted(x["horas"])[len(x["horas"]) // 2]} for x in r.values()),
                  key=lambda x: x["levantadas"], reverse=True)[:10]


def main(ahora=None):
    noticias = json.loads((DATOS / "noticias.json").read_text(encoding="utf-8"))
    ahora = ahora or datetime.now(timezone.utc)
    ruta = DATOS / "primicias.json"
    try:
        previo = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        previo = {}

    notas = notas_argentinas(noticias, ahora - timedelta(hours=GUARDAR_HORAS))
    recientes = [n for n in notas if n["_f"] >= ahora - timedelta(hours=HORAS)]
    primicias = buscar_primicias(recientes, ahora)

    # Seguimiento: lo guardado antes + las primicias nuevas, durante GUARDAR_HORAS
    limite = (ahora - timedelta(hours=GUARDAR_HORAS)).isoformat()
    seg = [p for p in previo.get("seguimiento", []) if p.get("primera_hora", "") >= limite]
    for p in primicias:
        ya = next((q for q in seg if AG.jaccard(AG.raices(q["titulo"]), AG.raices(p["titulo"])) >= 0.35), None)
        p["avisado"] = bool(ya and ya.get("avisado"))
        if ya:
            ya.update({k: p[k] for k in ("medios_regionales", "notas")})
        else:
            seg.append(dict(p))
    seg = seguir(seg, notas)
    # Si un nacional ya la levantó, deja de ser primicia
    levantadas = [AG.raices(q["titulo"]) for q in seg if q.get("levantada")]
    primicias = [p for p in primicias if not any(AG.jaccard(AG.raices(p["titulo"]), k) >= 0.35 for k in levantadas)]

    nuevas = [p for p in primicias if not p["avisado"]][:MAX_AVISOS]
    if nuevas:
        try:
            import avisar
            texto = ("PRIMICIA REGIONAL · Diario Federal\nLo cuentan diarios de provincia y todavía no los nacionales.\n\n"
                     + "\n".join(f"• {p['titulo']} ({', '.join(p['medios_regionales'][:3])})" for p in nuevas)
                     + "\n\n" + avisar.CENTRO.replace("#agentes", "#edicion"))
            r = avisar.mandar(texto)
            if r.startswith("enviado"):
                avisadas = {p["titulo"] for p in nuevas}
                for x in primicias + seg:
                    if x["titulo"] in avisadas:
                        x["avisado"] = True
            print("Aviso:", r)
        except Exception as e:  # noqa: BLE001
            print("No se pudo avisar:", e)

    salida = {"generado": ahora.isoformat(timespec="seconds"), "ventana_horas": HORAS,
              "primicias": primicias[:15], "quien_se_adelanta": ranking(seg),
              "seguimiento": sorted(seg, key=lambda p: p["primera_hora"], reverse=True)[:200]}
    ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Primicias: {len(primicias)} ({len(nuevas)} nuevas); en seguimiento {len(seg)}, "
          f"{sum(1 for p in seg if p.get('levantada'))} ya levantadas por nacionales; {len(recientes)} titulares argentinos")


if __name__ == "__main__":
    main()
