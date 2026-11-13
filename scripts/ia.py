"""
IA gratuita para los agentes de redacción. No usa el plan de Claude.

Prueba en orden:
  1. Gemini (Google), si existe la clave GEMINI_API_KEY.
  2. Groq, si existe la clave GROQ_API_KEY.
Las dos se sacan gratis (aistudio.google.com y console.groq.com) y se guardan como
"secrets" del repositorio en GitHub (Settings → Secrets and variables → Actions).
"""

import json
import os
import re
import time
import urllib.error
import urllib.request


class SinClave(Exception):
    pass


class IA:
    def __init__(self, conf):
        self.gemini = os.environ.get("GEMINI_API_KEY", "").strip()
        self.groq = os.environ.get("GROQ_API_KEY", "").strip()
        self.gemini_modelos = conf.get("gemini_modelos") or ["gemini-flash-latest"]
        self.groq_modelos = conf.get("groq_modelos") or ["llama-3.3-70b-versatile"]
        self.pausa = float(conf.get("pausa_segundos", 5))
        self.llamadas = 0
        self.usado = None  # "Gemini · modelo" que respondió la última vez
        self._ultima = 0.0

    @property
    def disponible(self):
        return bool(self.gemini or self.groq)

    def _post(self, url, cuerpo, cabeceras):
        espera = self.pausa - (time.time() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={"Content-Type": "application/json", **cabeceras})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        finally:
            self._ultima = time.time()
            self.llamadas += 1

    def _gemini(self, modelo, prompt):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        d = self._post(url, {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
        }, {"x-goog-api-key": self.gemini})
        partes = d["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in partes)

    def _groq(self, modelo, prompt):
        d = self._post("https://api.groq.com/openai/v1/chat/completions", {
            "model": modelo, "temperature": 0.4,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }, {"Authorization": f"Bearer {self.groq}"})
        return d["choices"][0]["message"]["content"]

    def json(self, prompt):
        """Manda el pedido y devuelve el JSON de la respuesta. Si un proveedor falla, prueba el siguiente."""
        if not self.disponible:
            raise SinClave("Falta la clave GEMINI_API_KEY o GROQ_API_KEY")
        intentos = []
        if self.gemini:
            intentos += [("Gemini", m, self._gemini) for m in self.gemini_modelos]
        if self.groq:
            intentos += [("Groq", m, self._groq) for m in self.groq_modelos]
        errores = []
        for prov, modelo, fn in intentos:
            for vuelta in range(2):
                try:
                    texto = fn(modelo, prompt)
                    self.usado = f"{prov} · {modelo}"
                    return leer_json(texto)
                except urllib.error.HTTPError as e:
                    errores.append(f"{prov} {modelo}: HTTP {e.code}")
                    if e.code == 429 and vuelta == 0:
                        time.sleep(30)  # límite por minuto: esperar y reintentar una vez
                        continue
                    break  # 404 (modelo que no existe), 400, 403: probar el siguiente
                except Exception as e:  # noqa: BLE001
                    errores.append(f"{prov} {modelo}: {str(e)[:80]}")
                    break
        raise RuntimeError("; ".join(errores[-4:]))


def leer_json(texto):
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            return json.loads(m.group(0))
        raise
