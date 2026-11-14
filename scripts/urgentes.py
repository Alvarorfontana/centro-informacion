#!/usr/bin/env python3
"""
Agente de Urgentes (como el "flash" de las agencias).

Corre después de cada recolección, cada hora. Busca hechos que muchos medios distintos publicaron
en las últimas horas: eso suele ser una noticia grande. Los deja en datos/urgentes.json y,
si el aviso al celular está configurado, manda una línea por cada urgente nuevo.
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agrupar as AG  # noqa: E402
import recolectar as REC  # noqa: E402

HORAS = 4          # ventana de tiempo que se mira
MIN_MEDIOS = 4     # medios distintos que tienen que contarlo para que sea urgente


def main():
    noticias = json.loads((DATOS / "noticias.json").read_text(encoding="utf-8"))
    ahora = datetime.now(timezone.utc)
    desde = (ahora - timedelta(hours=HORAS)).isoformat()
    recientes = [n for n in AG.todas_las_notas(noticias)
                 if (n.get("fecha") or "") >= desde and not REC.es_ruido(n.get("titulo") or "")]
    AG.MIN_MEDIOS = MIN_MEDIOS
    grupos = AG.agrupar(recientes, ahora=ahora)

    ruta = DATOS / "urgentes.json"
    try:
        previos = json.loads(ruta.read_text(encoding="utf-8")).get("urgentes", [])
    except Exception:  # noqa: BLE001
        previos = []

    urgentes = []
    for g in grupos[:6]:
        ya = next((p for p in previos if AG.jaccard(AG.raices(p["titulo"]), AG.raices(g["titulo"])) >= 0.35), None)
        urgentes.append({"titulo": g["titulo"], "n_medios": g["n_medios"], "paises": g.get("paises", []),
                         "region": g.get("region"), "tema": g.get("tema"), "ejes": g.get("ejes", []),
                         "desde": ya["desde"] if ya else ahora.isoformat(timespec="seconds"),
                         "avisado": bool(ya and ya.get("avisado")),
                         "notas": [{k: n.get(k) for k in ("titulo", "url", "medio", "fecha")} for n in g["notas"][:5]]})

    nuevos = [u for u in urgentes if not u["avisado"]]
    if nuevos:
        try:
            import avisar
            texto = "URGENTE · Diario Federal\n\n" + "\n".join(f"• {u['titulo']} ({u['n_medios']} medios)" for u in nuevos) + "\n\n" + avisar.CENTRO
            res = avisar.mandar(texto)
            if res.startswith("enviado"):
                for u in nuevos:
                    u["avisado"] = True
            print("Aviso:", res)
        except Exception as e:  # noqa: BLE001
            print("No se pudo avisar:", e)

    ruta.write_text(json.dumps({"generado": ahora.isoformat(timespec="seconds"), "ventana_horas": HORAS,
                                "min_medios": MIN_MEDIOS, "urgentes": urgentes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Urgentes: {len(urgentes)} ({len(nuevos)} nuevos) de {len(recientes)} titulares de las últimas {HORAS} horas")


if __name__ == "__main__":
    main()
