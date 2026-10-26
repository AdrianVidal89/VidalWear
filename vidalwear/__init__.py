"""VidalWear — el armario en el móvil."""

import os
import secrets
from pathlib import Path

from flask import Flask

__version__ = "0.0.2"


class Ajustes:
    """Todo lo configurable sale de variables de entorno con prefijo
    VIDALWEAR_ (nada de nombres genéricos: se heredan a otros procesos)."""

    def __init__(self):
        self.datos = Path(os.environ.get("VIDALWEAR_DATOS", "./datos")).resolve()
        self.puerto = int(os.environ.get("VIDALWEAR_PUERTO", "8085"))
        self.titulo = os.environ.get("VIDALWEAR_TITULO", "VidalWear")
        self.hilos = int(os.environ.get("VIDALWEAR_HILOS", "4"))
        self.fotos = self.datos / "fotos"
        self.bd = self.datos / "vidalwear.db"


def _clave_secreta(datos):
    """La clave de las cookies firmadas, generada una vez y guardada en datos/."""
    f = datos / "clave-secreta"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


def crear_app(ajustes=None):
    ajustes = ajustes or Ajustes()
    ajustes.fotos.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder="estatico", template_folder="plantillas")
    app.config.update(
        AJUSTES=ajustes,
        SECRET_KEY=_clave_secreta(ajustes.datos),
        # Una foto ya comprimida en el móvil pesa 200-400 KB; el techo es para
        # cuando la compresión del navegador falla y llega la foto tal cual.
        MAX_CONTENT_LENGTH=30 * 1024 * 1024,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 365,
    )

    from . import bd
    bd.iniciar(ajustes.bd)
    app.teardown_appcontext(bd.cerrar)

    from .api import api
    from .web import web
    app.register_blueprint(web)
    app.register_blueprint(api)
    return app
