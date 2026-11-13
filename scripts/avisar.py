"""
Aviso cuando terminan los agentes. Primero por Telegram (gratis: un bot propio creado con @BotFather);
si no está configurado, por WhatsApp con CallMeBot. Datos en secretos/claves.json. Si faltan, no hace nada.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CENTRO = "https://centro-informacion.vercel.app/#agentes"


def configuracion():
    try:
        return json.loads((RAIZ / "secretos" / "claves.json").read_text(encoding="utf-8")).get("whatsapp") or {}
    except Exception:  # noqa: BLE001
        return {}


def telegram(texto):
    try:
        todo = json.loads((RAIZ / "secretos" / "claves.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    t = todo.get("telegram") or {}
    token, chat = str(t.get("token") or "").strip(), str(t.get("chat_id") or "").strip()
    if not token:
        return None
    base = f"https://api.telegram.org/bot{token}/"
    if not chat:  # el chat se descubre solo: es quien le escribió al bot
        with urllib.request.urlopen(base + "getUpdates", timeout=30) as r:
            upd = json.loads(r.read().decode())
        chats = [u.get("message", {}).get("chat", {}).get("id") for u in upd.get("result", []) if u.get("message")]
        if not chats:
            return "falta que le escribas al bot"
        chat = str(chats[-1])
    datos = urllib.parse.urlencode({"chat_id": chat, "text": texto[:4000], "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(urllib.request.Request(base + "sendMessage", data=datos), timeout=30) as r:
        return f"enviado por Telegram ({r.status})"


def mandar(texto):
    tg = telegram(texto)
    if tg:
        return tg
    c = configuracion()
    tel, key = str(c.get("telefono") or "").strip(), str(c.get("apikey") or "").strip()
    if not tel or not key:
        return "sin configurar"
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode({"phone": tel, "text": texto[:1500], "apikey": key})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "CentroInformacion"}), timeout=30) as r:
        return f"enviado ({r.status})"


def resumen(d):
    menu = d.get("menu") or []
    borr = [b for b in menu if b.get("cuerpo_html")]
    lineas = [f"Diario Federal · Redacción automática", f"{len(menu)} temas · {len(borr)} borradores listos", ""]
    for b in menu[:12]:
        marca = "✅" if b.get("cuerpo_html") else "•"
        lineas.append(f"{marca} {((b.get('titulos') or [b.get('titulo_tema')])[0] or '')[:110]}")
    ag = d.get("agenda") or []
    if ag:
        lineas += ["", "Agenda del día"] + [f"• {x['titulo'][:100]}" for x in ag[:5]]
    seg = d.get("seguimiento") or []
    if seg:
        lineas += ["", "Seguimiento"] + [f"• {x['tema'][:90]} (+{x['nuevas']})" for x in seg[:4]]
    lineas += ["", CENTRO]
    return "\n".join(lineas)
