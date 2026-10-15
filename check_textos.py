import os
import sys
import time
import json
import urllib.request
import urllib.error
from urllib.parse import quote

URL = "https://www.habbo.es/gamedata/external_flash_texts/1"
TXT_FILE = "external_flash_texts.txt"      # copia guardada en el repositorio
WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
MAX_MENSAJES = 40                          # tope de mensajes por ejecución

# Insignias: para claves "badge_name_CODIGO" se muestra esta imagen
PREFIJO_INSIGNIA = "badge_name_"
URL_INSIGNIA = "https://images.habbo.com/c_images/album1584/{codigo}.png"


def descargar() -> str:
    req = urllib.request.Request(
        URL, headers={"User-Agent": "Mozilla/5.0 (compatible; HabboTextosBot/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(texto: str) -> dict:
    datos = {}
    for linea in texto.splitlines():
        if "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave] = valor
    return datos


def limpiar(s: str) -> str:
    # Evita que el texto cierre por error el bloque de código de Discord
    return s.replace("```", "'''")


def piezas(linea: str, prefijo: str = "", limite: int = 1700):
    """Divide una línea larga en varias para que nunca se recorte el texto."""
    linea = limpiar(linea)
    n = limite - len(prefijo)
    if not linea:
        return [prefijo.rstrip()]
    return [prefijo + linea[i:i + n] for i in range(0, len(linea), n)]


def trocear(lineas, limite=1800):
    """Agrupa líneas en mensajes que no superen el límite de Discord."""
    bloque, largo = [], 0
    for l in lineas:
        if largo + len(l) + 1 > limite and bloque:
            yield "\n".join(bloque).strip("\n")
            bloque, largo = [], 0
        bloque.append(l)
        largo += len(l) + 1
    if bloque:
        yield "\n".join(bloque).strip("\n")


def embed_insignia(clave: str, valor: str, estado: str) -> dict:
    codigo = clave[len(PREFIJO_INSIGNIA):]
    return {
        "title": codigo[:256],
        "description": f"{estado}: {valor}"[:300],
        "image": {"url": URL_INSIGNIA.format(codigo=quote(codigo, safe=""))},
    }


def enviar(payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "HabboTextosBot/1.0"},
    )
    for _ in range(3):
        try:
            urllib.request.urlopen(req, timeout=30)
            time.sleep(1)
            return
        except urllib.error.HTTPError as e:
            if e.code == 429:  # límite de velocidad de Discord
                time.sleep(5)
                continue
            raise


def main():
    if not WEBHOOK:
        sys.exit("Falta la variable DISCORD_WEBHOOK")

    nuevo_texto = descargar()
    nuevos = parse(nuevo_texto)
    if not nuevos:
        sys.exit("La descarga no contiene textos; se cancela para no sobrescribir.")

    # Primera ejecución: solo se guarda la base, sin avisar
    if not os.path.exists(TXT_FILE):
        with open(TXT_FILE, "w", encoding="utf-8") as f:
            f.write(nuevo_texto)
        print(f"Base inicial guardada ({len(nuevos)} textos).")
        return

    with open(TXT_FILE, "r", encoding="utf-8") as f:
        anteriores = parse(f.read())

    lineas_nuevos, n_nuevos = [], 0
    lineas_mod, n_mod = [], 0
    embeds = []  # imágenes de insignias

    for k, v in nuevos.items():
        if k not in anteriores:
            n_nuevos += 1
            lineas_nuevos += piezas(f"{k}={v}")
            if k.startswith(PREFIJO_INSIGNIA):
                embeds.append(embed_insignia(k, v, "🆕 Nuevo"))
        elif anteriores[k] != v:
            n_mod += 1
            lineas_mod.append(f"@@ {limpiar(k)} @@")
            lineas_mod += piezas(anteriores[k], "- ")
            lineas_mod += piezas(v, "+ ")
            lineas_mod.append("")
            if k.startswith(PREFIJO_INSIGNIA):
                embeds.append(embed_insignia(k, v, "✏️ Modificado"))

    if not n_nuevos and not n_mod:
        print("Sin cambios.")
        return

    mensajes = []  # cada elemento es un payload de webhook
    if n_nuevos:
        mensajes.append({"content": f"🆕 **{n_nuevos} texto(s) nuevo(s):**"})
        mensajes += [{"content": f"```\n{p}\n```"} for p in trocear(lineas_nuevos) if p.strip()]
    if n_mod:
        mensajes.append({"content": f"✏️ **{n_mod} texto(s) modificado(s)** (antes `-` / después `+`):"})
        mensajes += [{"content": f"```diff\n{p}\n```"} for p in trocear(lineas_mod) if p.strip()]
    if embeds:
        mensajes.append({"content": f"🏅 **{len(embeds)} insignia(s):**"})
        # Discord permite hasta 10 embeds por mensaje
        for i in range(0, len(embeds), 10):
            mensajes.append({"embeds": embeds[i:i + 10]})

    if len(mensajes) > MAX_MENSAJES:
        omitidos = len(mensajes) - MAX_MENSAJES
        mensajes = mensajes[:MAX_MENSAJES] + [{"content": f"… y {omitidos} mensaje(s) más omitidos."}]

    for m in mensajes:
        enviar(m)

    # Solo se guarda si el aviso salió bien
    with open(TXT_FILE, "w", encoding="utf-8") as f:
        f.write(nuevo_texto)
    print(f"Avisados {n_nuevos} nuevos y {n_mod} modificados ({len(embeds)} insignias).")


if __name__ == "__main__":
    main()
