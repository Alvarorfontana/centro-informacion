"""
Etiqueta el tema de las noticias con la IA gratis del Centro de Información.

El problema que resuelve: el recolector clasifica por palabras clave y lo que no
matchea cae en "General", que no es un tema. Hoy son 563 de 775 notas.

Cómo se hace, y por qué se puede confiar:

  1. Se le pide a la IA una etiqueta de una lista CERRADA de secciones. Si inventa
     una que no está en la lista, se descarta. No se acepta texto libre.
  2. Se guarda la confianza que declara. Las dudosas (menos de 0,6) quedan marcadas
     para que una persona las mire, en vez de esconderlas.
  3. Se procesa por lotes y se guarda a medida que avanza: si se corta, retoma donde
     quedó. No se repite lo ya hecho.
  4. Con --medir se corre sobre las 212 notas que YA tienen tema y se compara contra
     la etiqueta original. Ese número dice si las etiquetas nuevas merecen confianza.
     Si la IA coincide poco con lo que ya estaba, el problema es la IA, y se ve antes
     de tocar el dataset.

Uso:

    python scripts/etiquetar_temas.py --probar        # muestra el prompt, no llama a nada
    python scripts/etiquetar_temas.py --limite 24     # prueba con 24 notas
    python scripts/etiquetar_temas.py                 # todas las "General"
    python scripts/etiquetar_temas.py --medir         # examen contra las ya etiquetadas
    python scripts/etiquetar_temas.py --todos         # reetiqueta todo, sin importar el tema actual

Salida: datos/temas-ia.jsonl (una línea por nota, se puede retomar).
"""

import argparse
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ia import IA, SinClave  # noqa: E402
from notas import clave_nota, es_portugues, limpiar  # noqa: E402

ORIGEN = os.path.join(BASE, "datos", "noticias.json")
CONFIG = os.path.join(BASE, "agentes", "config.json")
SALIDA = os.path.join(BASE, "datos", "temas-ia.jsonl")

# Lista cerrada de secciones. La descripción es lo que lee la IA para decidir.
# "Sociedad" está definida en angosto a propósito: si se define amplia, se come todo
# y volvemos a tener el problema de "General" con otro nombre.
TAXONOMIA = [
    ("Política", "política ARGENTINA: gobierno nacional, provincias, municipios, congreso, elecciones argentinas, partidos, gobernadores, funcionarios, campaña"),
    ("Economía", "inflación, dólar, salarios, impuestos, comercio, empresas, presupuesto, empleo, deuda, bancos"),
    ("Internacional", "guerras, conflictos armados, diplomacia entre países, organismos internacionales (ONU, UE), cumbres, crisis humanitarias"),
    ("Sociedad", "vivienda, transporte público, género, niñez, religión, migración, consumidores, comunidad, historias de vida"),
    ("Justicia y seguridad", "causas judiciales, detenidos, policía, delitos, tribunales, narcotráfico, corrupción, condenas"),
    ("Salud", "enfermedades, hospitales, medicamentos, salud pública, epidemias, obras sociales"),
    ("Educación", "escuelas, universidades, docentes, clases, alumnado, paros docentes, becas"),
    ("Agro y campo", "soja, maíz, ganadería, cosecha, exportaciones agropecuarias, productores, sequía, precios del campo"),
    ("Energía y minería", "petróleo, gas, litio, electricidad, tarifas de servicios, minas, Vaca Muerta, combustibles"),
    ("Medio ambiente", "clima, incendios, contaminación, biodiversidad, agua, cambio climático, COP"),
    ("Deportes", "fútbol, torneos, selecciones, clubes, atletas, competencias"),
    ("Cultura y espectáculos", "cine, música, teatro, libros, artistas, premios, televisión, series"),
    ("Ciencia y tecnología", "investigación, inteligencia artificial, innovación, descubrimientos, ciencia, internet"),
]

ETIQUETAS = [nombre for nombre, _ in TAXONOMIA]
CLAVE_LOTE = "notas"


def construir_prompt(notas):
    definiciones = "\n".join(f"- {nombre}: {detalle}" for nombre, detalle in TAXONOMIA)
    entradas = []
    for n in notas:
        titulo = limpiar(n.get("titulo"))[:180]
        resumen = limpiar(n.get("resumen"))[:280]
        texto = titulo if not resumen else f"{titulo}. {resumen}"
        entradas.append(f'{n["_id"]}. {texto}')

    return (
        "Sos editor de un diario argentino. Clasificá cada nota en UNA de estas secciones.\n\n"
        f"{definiciones}\n\n"
        "Reglas:\n"
        "- Elegí siempre una de la lista, aunque dudes. No inventes secciones nuevas.\n"
        "- La sección describe el TEMA de la nota, no el país donde pasa. Una nota sobre el "
        "presupuesto de España es Economía; una sobre una escuela en Chile es Educación.\n"
        "- 'Internacional' es solo para guerras, conflictos, diplomacia entre países y "
        "organismos internacionales. No la uses como cajón de 'noticia extranjera'.\n"
        "- No uses una sección como comodín: si hay dos candidatas posibles, elegí la que "
        "describa el hecho principal del título.\n"
        "- En 'confianza' poné un número entre 0 y 1: cuánto seguro estás. Si dudás, bajalo.\n\n"
        "Devolvé SOLO este JSON, sin explicaciones:\n"
        '{"notas": [{"id": 1, "tema": "Economía", "confianza": 0.9}]}\n\n'
        "Notas a clasificar:\n" + "\n".join(entradas)
    )


def leer_hechas():
    hechas = {}
    if not os.path.exists(SALIDA):
        return hechas
    with open(SALIDA, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                dato = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if dato.get("clave"):
                hechas[dato["clave"]] = dato
    return hechas


def guardar(datos):
    with open(SALIDA, "a", encoding="utf-8") as f:
        for dato in datos:
            f.write(json.dumps(dato, ensure_ascii=False) + "\n")


def elegir_notas(noticias, args, hechas):
    # Las notas en portugués no van al dataset: no se gastan pedidos en ellas.
    noticias = [n for n in noticias if not es_portugues(n)]

    if args.medir:
        # Solo las que ya tienen un tema real: son el examen.
        candidatas = [n for n in noticias if limpiar(n.get("tema")) not in ("", "General")]
    elif args.todos:
        candidatas = [n for n in noticias if len(limpiar(n.get("titulo"))) >= 15]
    else:
        candidatas = [
            n for n in noticias
            if limpiar(n.get("tema")) in ("", "General") and len(limpiar(n.get("titulo"))) >= 15
        ]

    if not args.repetir:
        candidatas = [n for n in candidatas if clave_nota(n) not in hechas]

    if args.limite:
        candidatas = candidatas[: args.limite]
    return candidatas


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    p = argparse.ArgumentParser(description="Etiqueta el tema de las noticias con IA.")
    p.add_argument("--limite", type=int, default=0, help="Procesar como máximo N notas.")
    p.add_argument("--lote", type=int, default=12, help="Notas por pedido a la IA (por defecto 12).")
    p.add_argument("--todos", action="store_true", help="Reetiquetar todas, no solo las 'General'.")
    p.add_argument("--medir", action="store_true", help="Correr sobre las ya etiquetadas y comparar.")
    p.add_argument("--repetir", action="store_true", help="No saltear las que ya están en la salida.")
    p.add_argument("--probar", action="store_true", help="Mostrar el prompt y salir, sin llamar a la IA.")
    args = p.parse_args()

    with open(ORIGEN, encoding="utf-8") as f:
        noticias = json.load(f).get("rss", [])

    hechas = leer_hechas()
    pendientes = elegir_notas(noticias, args, hechas)

    print(f"Noticias en origen:     {len(noticias)}")
    print(f"Ya etiquetadas antes:   {len(hechas)}")
    print(f"A procesar en esta vuelta: {len(pendientes)}")
    print(f"Lote: {args.lote} notas por pedido → {-(-len(pendientes) // args.lote)} pedidos")

    if not pendientes:
        print("\nNo hay nada para hacer.")
        return

    if args.probar:
        muestra = pendientes[: min(args.lote, len(pendientes))]
        preparadas = [{"_id": i + 1, **n} for i, n in enumerate(muestra)]
        print("\n=== PROMPT QUE SE ENVIARÍA ===\n")
        print(construir_prompt(preparadas))
        return

    with open(CONFIG, encoding="utf-8") as f:
        conf = json.load(f)
    ia = IA(conf.get("ia", {}))

    if not ia.disponible:
        raise SystemExit("No hay ninguna IA configurada. Revisá agentes/config.json o las claves.")

    print(f"\nProveedor: {ia.usado or 'se resuelve en el primer pedido'}")
    print("Empezando…\n")

    procesadas = 0
    errores = 0
    inicio = time.time()

    for comienzo in range(0, len(pendientes), args.lote):
        lote = pendientes[comienzo : comienzo + args.lote]
        preparadas = [{"_id": i + 1, **n} for i, n in enumerate(lote)]

        try:
            respuesta = ia.json(construir_prompt(preparadas))
        except (SinClave, RuntimeError) as e:
            errores += 1
            print(f"  lote {comienzo // args.lote + 1}: falló ({str(e)[:110]})")
            continue

        devueltas = respuesta.get(CLAVE_LOTE) or respuesta.get("resultados") or []
        por_id = {}
        for item in devueltas:
            if not isinstance(item, dict):
                continue
            try:
                por_id[int(item.get("id"))] = item
            except (TypeError, ValueError):
                continue

        filas = []
        for preparada in preparadas:
            item = por_id.get(preparada["_id"], {})
            tema = limpiar(item.get("tema"))
            try:
                confianza = float(item.get("confianza", 0))
            except (TypeError, ValueError):
                confianza = 0.0
            confianza = max(0.0, min(1.0, confianza))

            inventada = bool(tema) and tema not in ETIQUETAS
            if not tema or inventada:
                tema = "Sin clasificar"
                confianza = 0.0

            filas.append({
                "clave": clave_nota(preparada),
                "tema": tema,
                "confianza": round(confianza, 2),
                "tema_original": limpiar(preparada.get("tema")),
                "titulo": limpiar(preparada.get("titulo"))[:120],
                "inventada": inventada,
            })

        guardar(filas)
        procesadas += len(filas)

        # Resumen en vivo: así se ve la calidad mientras corre.
        resumen = {}
        for fila in filas:
            resumen[fila["tema"]] = resumen.get(fila["tema"], 0) + 1
        print(f"  lote {comienzo // args.lote + 1}: {resumen}")

    transcurrido = time.time() - inicio
    print(f"\nProcesadas: {procesadas} | Lotes fallidos: {errores} | Tiempo: {transcurrido / 60:.1f} min")
    print(f"Guardado en: {SALIDA}")

    if args.medir:
        medir()


def medir():
    """Compara las etiquetas nuevas contra las que ya tenía la nota."""
    if not os.path.exists(SALIDA):
        print("No hay nada para medir todavía.")
        return

    with open(SALIDA, encoding="utf-8") as f:
        datos = [json.loads(l) for l in f if l.strip()]

    comparables = [d for d in datos if d.get("tema_original") and d["tema_original"] != "General"]
    if not comparables:
        print("\nNo hay notas con tema original para comparar. Corré con --medir.")
        return

    # El recolector usa nombres más amplios que la taxonomía nueva.
    equivalencias = {
        "geopolítica": "Internacional",
        "geopolitica": "Internacional",
        "agro y clima": "Agro y campo",
        "energía": "Energía y minería",
        "energia": "Energía y minería",
    }

    coinciden = 0
    detalle = []
    for d in comparables:
        original = d["tema_original"].strip().lower()
        original = equivalencias.get(original, d["tema_original"].strip())
        acierto = original.lower() == d["tema"].strip().lower()
        coinciden += acierto
        if not acierto:
            detalle.append((d["tema_original"], d["tema"], d["confianza"], d["titulo"]))

    total = len(comparables)
    print(f"\n=== EXAMEN CONTRA LAS YA ETIQUETADAS ===")
    print(f"Comparables: {total}")
    print(f"Coinciden:   {coinciden}  ({100 * coinciden / total:.1f} %)")
    print(f"Discrepan:   {total - coinciden}")

    if detalle:
        print("\nPrimeras discrepancias (para revisar a mano, son las interesantes):")
        for original, nueva, confianza, titulo in detalle[:15]:
            print(f"  antes: {original:<22} ahora: {nueva:<24} ({confianza:.2f})")
            print(f"    {titulo}")


if __name__ == "__main__":
    main()
