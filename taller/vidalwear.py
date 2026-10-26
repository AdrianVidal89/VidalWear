#!/usr/bin/env python3
"""El taller de VidalWear: lo que se hace en el portátil, no en el NAS.

El NAS guarda y enseña; el trabajo pesado (quitar el fondo con un modelo de
IA) y el criterio (fichar la prenda, montar conjuntos) se hacen aquí, con
Claude Code. Flujo normal, cuando Adrian dice «procesa VidalWear»:

    vidalwear estado                 ¿qué hay en la bandeja?
    vidalwear bajar                  descarga las fotos pendientes
    vidalwear recortar               les quita el fondo y hace hojas de contacto
      (Claude mira las hojas y escribe fichas.json)
    vidalwear subir fichas.json      recortes + fichas al NAS → pasan al armario
    vidalwear inventario             rehace el .md del armario de cada persona en el vault
    vidalwear armario <id>           el armario en JSON, para montar conjuntos
    vidalwear conjuntos <id>         los conjuntos que hay y lo que opinó la persona
    vidalwear cargar conjuntos.json  sube conjuntos nuevos

Solo usa la biblioteca estándar más Pillow y rembg (en taller/.venv).
"""

import argparse
import io
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

URL = os.environ.get("VIDALWEAR_URL", "http://100.92.242.23:8085").rstrip("/")
TRABAJO = Path(os.environ.get("VIDALWEAR_TRABAJO", Path.home() / ".cache" / "vidalwear"))
VAULT = Path(os.environ.get(
    "VIDALWEAR_VAULT",
    Path.home() / "Documentos" / "Obsidian Vaults" / "MyNotebook" / "Notas" / "Moda" / "Armarios"))
PENDIENTES = TRABAJO / "pendientes"
HECHAS = TRABAJO / "hechas"
# isnet-general-use recorta bien cualquier objeto (ropa, zapatos, relojes).
# El de ropa (u2net_cloth_seg) solo sabe de prendas de cuerpo, no de un reloj.
MODELO = os.environ.get("VIDALWEAR_MODELO", "isnet-general-use")


# ------------------------------------------------------------------- red
def pedir(ruta, datos=None, metodo=None, cabeceras=None):
    req = urllib.request.Request(URL + ruta, data=datos, method=metodo,
                                 headers=cabeceras or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "replace")
        sys.exit(f"ERROR {e.code} en {ruta}: {cuerpo}")
    except urllib.error.URLError as e:
        sys.exit(f"No llego a VidalWear en {URL}: {e.reason}")


def enviar_json(ruta, obj):
    return pedir(ruta, json.dumps(obj).encode(), "POST", {"Content-Type": "application/json"})


def enviar_formulario(ruta, campos, ficheros):
    """multipart/form-data a mano, para no depender de requests."""
    limite = uuid.uuid4().hex
    cuerpo = io.BytesIO()
    for k, v in campos.items():
        cuerpo.write(f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode())
        cuerpo.write(v.encode() + b"\r\n")
    for k, (nombre, datos, tipo) in ficheros.items():
        cuerpo.write(f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"; "
                     f"filename=\"{nombre}\"\r\nContent-Type: {tipo}\r\n\r\n".encode())
        cuerpo.write(datos + b"\r\n")
    cuerpo.write(f"--{limite}--\r\n".encode())
    return pedir(ruta, cuerpo.getvalue(), "POST",
                 {"Content-Type": f"multipart/form-data; boundary={limite}"})


def descargar(url, destino):
    with urllib.request.urlopen(url, timeout=60) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)


def usuarios():
    return {u["id"]: u for u in pedir("/api/taller/usuarios")}


# --------------------------------------------------------------- órdenes
def estado(_):
    e = pedir("/api/taller/estado")
    print(f"VidalWear ({URL}): {e['personas']} persona(s), {e['bandeja']} prenda(s) en la bandeja.")
    locales = sorted(PENDIENTES.glob("*/prenda.json")) if PENDIENTES.exists() else []
    if locales:
        sin_recortar = [p for p in locales if not (p.parent / "recorte.png").exists()]
        print(f"En el portátil: {len(locales)} descargada(s), {len(sin_recortar)} sin recortar.")


def bajar(_):
    lista = pedir("/api/taller/bandeja")
    gente = usuarios()
    PENDIENTES.mkdir(parents=True, exist_ok=True)
    nuevas = 0
    for p in lista:
        carpeta = PENDIENTES / str(p["id"])
        if (carpeta / "original.jpg").exists():
            continue
        carpeta.mkdir(parents=True, exist_ok=True)
        descargar(p["foto"], carpeta / "original.jpg")
        p["persona"] = gente.get(p["usuario_id"], {}).get("nombre", "?")
        p["genero"] = gente.get(p["usuario_id"], {}).get("genero", "?")
        (carpeta / "prenda.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
        nuevas += 1
    print(f"{len(lista)} en la bandeja, {nuevas} descargada(s) ahora → {PENDIENTES}")


def _recortar_una(sesion, original, destino):
    from PIL import Image
    from rembg import remove
    with Image.open(original) as im:
        im = im.convert("RGB")
        sin_fondo = remove(im, session=sesion, post_process_mask=True)
    alfa = sin_fondo.getchannel("A")
    # Restos sueltos casi transparentes que agrandarían el recuadro: fuera.
    caja = alfa.point(lambda v: 255 if v > 24 else 0).getbbox()
    if caja:
        margen = int(max(caja[2] - caja[0], caja[3] - caja[1]) * 0.04)
        caja = (max(0, caja[0] - margen), max(0, caja[1] - margen),
                min(sin_fondo.width, caja[2] + margen), min(sin_fondo.height, caja[3] + margen))
        sin_fondo = sin_fondo.crop(caja)
    sin_fondo.save(destino, "PNG", optimize=True)
    return sin_fondo


def recortar(args):
    from PIL import Image, ImageDraw, ImageFont
    from rembg import new_session
    carpetas = sorted((p.parent for p in PENDIENTES.glob("*/prenda.json")), key=lambda c: int(c.name))
    if not carpetas:
        print("No hay nada descargado. Primero: vidalwear bajar")
        return
    sesion = None
    vistas = []
    for c in carpetas:
        recorte = c / "recorte.png"
        if not recorte.exists() or args.rehacer:
            if sesion is None:
                print(f"Cargando el modelo {MODELO} (la primera vez se descarga)…", flush=True)
                sesion = new_session(MODELO)
            print(f"  recortando {c.name}…", flush=True)
            _recortar_una(sesion, c / "original.jpg", recorte)
        vistas.append(c)

    # Hojas de contacto: original y recorte lado a lado, con el número de la
    # prenda. Es lo que mira Claude para fichar (12 por hoja, de un vistazo).
    for f in TRABAJO.glob("hoja-*.jpg"):
        f.unlink()
    CELDA, POR_HOJA, COLS = 300, 12, 3
    try:
        letra = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        letra = ImageFont.load_default()
    hojas = []
    for n in range(0, len(vistas), POR_HOJA):
        grupo = vistas[n:n + POR_HOJA]
        filas = (len(grupo) + COLS - 1) // COLS
        hoja = Image.new("RGB", (COLS * CELDA * 2, filas * (CELDA + 34)), (236, 236, 236))
        d = ImageDraw.Draw(hoja)
        for i, c in enumerate(grupo):
            x, y = (i % COLS) * CELDA * 2, (i // COLS) * (CELDA + 34)
            datos = json.loads((c / "prenda.json").read_text())
            with Image.open(c / "original.jpg") as o:
                o.thumbnail((CELDA - 8, CELDA - 8))
                hoja.paste(o, (x + 4, y + 34))
            with Image.open(c / "recorte.png") as r:
                r.thumbnail((CELDA - 8, CELDA - 8))
                fondo = Image.new("RGB", r.size, (250, 250, 250))
                fondo.paste(r, mask=r.getchannel("A"))
                hoja.paste(fondo, (x + CELDA + 4, y + 34))
            rotulo = f"#{c.name} {datos['categoria']} {datos.get('nombre') or ''}"[:34]
            d.text((x + 6, y + 6), rotulo, fill=(20, 20, 20), font=letra)
        destino = TRABAJO / f"hoja-{n // POR_HOJA + 1}.jpg"
        hoja.save(destino, "JPEG", quality=85)
        hojas.append(destino)
    print(f"{len(vistas)} prenda(s) recortadas. Hojas para revisar:")
    for h in hojas:
        print(f"  {h}")
    print(f"Recortes sueltos en {PENDIENTES}/<id>/recorte.png")


def subir(args):
    fichas = json.loads(Path(args.fichero).read_text())
    HECHAS.mkdir(parents=True, exist_ok=True)
    for pid, f in fichas.items():
        c = PENDIENTES / str(pid)
        ficheros = {}
        if (c / "recorte.png").exists() and not f.get("sin_recorte"):
            ficheros["recorte"] = ("recorte.png", (c / "recorte.png").read_bytes(), "image/png")
        datos = {k: f[k] for k in ("nombre", "categoria", "ficha") if k in f}
        r = enviar_formulario(f"/api/taller/prendas/{pid}", {"datos": json.dumps(datos)}, ficheros)
        print(f"  #{pid} → armario: {r['nombre']}")
        if c.exists():
            destino = HECHAS / str(pid)
            shutil.rmtree(destino, ignore_errors=True)
            shutil.move(str(c), destino)
    print(f"{len(fichas)} prenda(s) subidas. Ahora: vidalwear inventario")


def armario(args):
    datos = pedir(f"/api/taller/prendas?usuario={args.usuario}")
    compacto = [{"id": p["id"], "categoria": p["categoria"], "capa": p["capa"],
                 "nombre": p["nombre"], "estado": p["estado"], "ficha": p["ficha"]} for p in datos]
    texto = json.dumps(compacto, ensure_ascii=False, indent=1)
    if args.salida:
        Path(args.salida).write_text(texto)
        print(f"{len(compacto)} prendas → {args.salida}")
    else:
        print(texto)


def conjuntos(args):
    print(json.dumps(pedir(f"/api/taller/conjuntos?usuario={args.usuario}"),
                     ensure_ascii=False, indent=1))


def cargar(args):
    datos = json.loads(Path(args.fichero).read_text())
    r = enviar_json("/api/taller/conjuntos", datos)
    print(f"Cargados {r['cargados']} conjunto(s).")


# ------------------------------------------------------------ inventario
NOMBRES_TEMPORADA = {"primavera": "primavera", "verano": "verano", "otono": "otoño",
                     "invierno": "invierno"}
FORMALIDAD = {1: "deportivo", 2: "casual", 3: "arreglado informal", 4: "oficina", 5: "formal"}


def inventario(_):
    VAULT.mkdir(parents=True, exist_ok=True)
    cats = pedir("/api/taller/categorias")
    for uid, u in usuarios().items():
        prendas = pedir(f"/api/taller/prendas?usuario={uid}")
        conj = pedir(f"/api/taller/conjuntos?usuario={uid}")
        por_cat = {}
        for p in prendas:
            por_cat.setdefault(p["categoria"], []).append(p)
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
        en_bandeja = sum(1 for p in prendas if p["estado"] == "bandeja")
        l = [
            "---",
            f"persona: {u['nombre']}",
            f"armario: {u['genero']}",
            f"vidalwear_id: {uid}",
            f"prendas: {len(prendas)}",
            f"actualizado: {hoy}",
            "---",
            f"# 👕 Armario de {u['nombre']}",
            "",
            f"> [!info] Generado por el taller de VidalWear el {hoy}. **No lo edites a mano**: "
            "se rehace entero cada vez que se procesa la bandeja. Lo que se cambie aquí se pierde; "
            f"los cambios se hacen en la app ({URL}).",
            "",
            f"**{len(prendas)} prendas** · {en_bandeja} en la bandeja · {len(conj)} conjuntos "
            f"({sum(1 for c in conj if c['valoracion'] > 0)} con «me gusta», "
            f"{sum(1 for c in conj if c['valoracion'] < 0)} descartados).",
            "",
        ]
        for cat in sorted(por_cat):
            c = cats.get(cat, {"nombre": cat, "icono": ""})
            l.append(f"## {c['icono']} {c['nombre']} ({len(por_cat[cat])})")
            l.append("")
            l.append("| # | Prenda | Color | Tejido | Estilo | Temporada |")
            l.append("|---|---|---|---|---|---|")
            for p in por_cat[cat]:
                f = p["ficha"] or {}
                nombre = p["nombre"] or "(sin nombre)"
                if p["estado"] == "bandeja":
                    nombre += " ⏳"
                temps = ", ".join(NOMBRES_TEMPORADA.get(t, t) for t in f.get("temporadas", []))
                foto = p["recorte"] or p["foto"]
                l.append(f"| {p['id']} | [{nombre}]({foto}) | {f.get('color', '')} | "
                         f"{f.get('material', '')} | {FORMALIDAD.get(f.get('formalidad'), '')} | {temps} |")
            l.append("")
        if conj:
            l.append("## ✦ Conjuntos")
            l.append("")
            ids = {p["id"]: p["nombre"] or p["categoria"] for p in prendas}
            for c in conj:
                marca = {1: " 👍", -1: " 👎"}.get(c["valoracion"], "")
                piezas = " + ".join(ids.get(i, f"#{i}") for i in c["prendas"])
                l.append(f"- **{c['titulo']}**{marca} — {piezas}. "
                         f"_{', '.join(c['ocasiones'] + c['momentos'] + c['temporadas'])}_")
            l.append("")
        destino = VAULT / f"Armario de {u['nombre']}.md"
        destino.write_text("\n".join(l))
        print(f"  {destino}")


# ------------------------------------------------------------------ main
def principal():
    p = argparse.ArgumentParser(prog="vidalwear", description="El taller de VidalWear")
    s = p.add_subparsers(dest="orden", required=True)
    s.add_parser("estado").set_defaults(f=estado)
    s.add_parser("bajar").set_defaults(f=bajar)
    r = s.add_parser("recortar")
    r.add_argument("--rehacer", action="store_true", help="volver a recortar aunque ya esté")
    r.set_defaults(f=recortar)
    r = s.add_parser("subir")
    r.add_argument("fichero")
    r.set_defaults(f=subir)
    s.add_parser("inventario").set_defaults(f=inventario)
    r = s.add_parser("armario")
    r.add_argument("usuario", type=int)
    r.add_argument("-o", "--salida")
    r.set_defaults(f=armario)
    r = s.add_parser("conjuntos")
    r.add_argument("usuario", type=int)
    r.set_defaults(f=conjuntos)
    r = s.add_parser("cargar")
    r.add_argument("fichero")
    r.set_defaults(f=cargar)
    s.add_parser("personas").set_defaults(
        f=lambda _: print(json.dumps(list(usuarios().values()), ensure_ascii=False, indent=1)))
    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    principal()
