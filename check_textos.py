import os
import sys
import time
import json
import urllib.request
import urllib.error

URL = "https://www.habbo.es/gamedata/external_flash_texts/1"
TXT_FILE = "external_flash_texts.txt"      # copia guardada en el repositorio
WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
MAX_MENSAJES = 15                          # tope de mensajes por ejecución


def descargar() -> str:
    req = urllib.request.Request(
        URL, headers={"User-Agent": "Mozilla/5.0 (compatible; HabboTextosBot/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def parse(texto: str) -> dict:
    datos = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave] = valor
    return datos


def trocear(lineas, limite=1850):
    bloque, largo = [], 0
    for l in lineas:
        if len(l) > limite:
            l = l[: limite - 3] + "..."
        if largo + len(l) + 1 > limite and bloque:
            yield "\n".join(bloque)
            bloque, largo = [], 0
        bloque.append(l)
        largo += len(l) + 1
    if bloque:
        yield "\n".join(bloque)


def enviar(contenido: str):
    data = json.dumps({"content": contenido}).encode("utf-8")
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

    añadidos = [f"{k}={v}" for k, v in nuevos.items() if k not in anteriores]
    modificados = [f"{k}={v}" for k, v in nuevos.items()
                   if k in anteriores and anteriores[k] != v]

    if not añadidos and not modificados:
        print("Sin cambios.")
        return

    mensajes = []
    if añadidos:
        mensajes.append(f"🆕 **{len(añadidos)} texto(s) nuevo(s):**")
        mensajes += [f"```\n{p}\n```" for p in trocear(añadidos)]
    if modificados:
        mensajes.append(f"✏️ **{len(modificados)} texto(s) modificado(s):**")
        mensajes += [f"```\n{p}\n```" for p in trocear(modificados)]

    if len(mensajes) > MAX_MENSAJES:
        omitidos = len(mensajes) - MAX_MENSAJES
        mensajes = mensajes[:MAX_MENSAJES] + [f"… y {omitidos} mensaje(s) más omitidos."]

    for m in mensajes:
        enviar(m)

    # Solo se guarda si el aviso salió bien
    with open(TXT_FILE, "w", encoding="utf-8") as f:
        f.write(nuevo_texto)
    print(f"Avisados {len(añadidos)} nuevos y {len(modificados)} modificados.")


if __name__ == "__main__":
    main()
