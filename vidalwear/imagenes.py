"""Las fotos en disco.

Cada prenda tiene un nombre base (al azar) y hasta cuatro ficheros:

  originales/<base>.jpg       la foto del móvil, a 1600 px como mucho
  originales/<base>.mini.jpg  miniatura de 480 px para las rejillas
  recortes/<base>.webp        la prenda sin fondo (la hace el taller)
  recortes/<base>.mini.webp   su miniatura

El móvil ya manda la foto comprimida, pero aquí se vuelve a pasar por Pillow
siempre: endereza la foto según el EXIF, le quita los datos de ubicación y no
se fía de lo que llegue.
"""

import secrets
from pathlib import Path

from PIL import Image, ImageOps

LADO_ORIGINAL = 1600
LADO_MINI = 480
LADO_RECORTE = 1000
LADO_MINI_RECORTE = 420

# Una foto de móvil enorme (50 Mpx) cabe; algo más es sospechoso.
Image.MAX_IMAGE_PIXELS = 80_000_000


class FotoNoValida(ValueError):
    pass


def _carpetas(raiz):
    o, r = Path(raiz) / "originales", Path(raiz) / "recortes"
    o.mkdir(parents=True, exist_ok=True)
    r.mkdir(parents=True, exist_ok=True)
    return o, r


def guardar_original(raiz, flujo):
    """Guarda la foto que llega del móvil. Devuelve su nombre base."""
    originales, _ = _carpetas(raiz)
    base = secrets.token_hex(8)
    try:
        with Image.open(flujo) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as e:  # Pillow lanza de todo con un fichero raro
        raise FotoNoValida("No se ha podido leer la foto. Prueba a hacerla otra vez.") from e
    grande = im.copy()
    grande.thumbnail((LADO_ORIGINAL, LADO_ORIGINAL), Image.LANCZOS)
    grande.save(originales / f"{base}.jpg", "JPEG", quality=82, optimize=True, progressive=True)
    im.thumbnail((LADO_MINI, LADO_MINI), Image.LANCZOS)
    im.save(originales / f"{base}.mini.jpg", "JPEG", quality=78, optimize=True)
    return base


def guardar_recorte(raiz, base, flujo):
    """Guarda la prenda sin fondo que manda el taller (con transparencia)."""
    _, recortes = _carpetas(raiz)
    try:
        with Image.open(flujo) as im:
            im = im.convert("RGBA")
    except Exception as e:
        raise FotoNoValida("El recorte no es una imagen válida.") from e
    im.thumbnail((LADO_RECORTE, LADO_RECORTE), Image.LANCZOS)
    im.save(recortes / f"{base}.webp", "WEBP", quality=86, method=5)
    im.thumbnail((LADO_MINI_RECORTE, LADO_MINI_RECORTE), Image.LANCZOS)
    im.save(recortes / f"{base}.mini.webp", "WEBP", quality=82, method=5)


def ruta(raiz, base, tipo):
    """tipo: original, mini, recorte o recorte-mini."""
    o, r = Path(raiz) / "originales", Path(raiz) / "recortes"
    return {
        "original": o / f"{base}.jpg",
        "mini": o / f"{base}.mini.jpg",
        "recorte": r / f"{base}.webp",
        "recorte-mini": r / f"{base}.mini.webp",
    }[tipo]


def borrar(raiz, base):
    for tipo in ("original", "mini", "recorte", "recorte-mini"):
        ruta(raiz, base, tipo).unlink(missing_ok=True)
