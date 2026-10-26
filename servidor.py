#!/usr/bin/env python3
"""Arranca VidalWear.

    python servidor.py                       # con lo que digan las variables de entorno
    python servidor.py --datos ./datos --puerto 8085 --depurar
"""

import argparse
import os

from vidalwear import Ajustes, crear_app


def principal():
    p = argparse.ArgumentParser(description="VidalWear — el armario en el móvil")
    p.add_argument("--datos", help="carpeta de datos (base de datos y fotos)")
    p.add_argument("--puerto", type=int, help="puerto (por defecto 8085)")
    p.add_argument("--depurar", action="store_true")
    args = p.parse_args()
    if args.datos:
        os.environ["VIDALWEAR_DATOS"] = args.datos
    if args.puerto:
        os.environ["VIDALWEAR_PUERTO"] = str(args.puerto)

    ajustes = Ajustes()
    app = crear_app(ajustes)
    print(f"VidalWear en http://0.0.0.0:{ajustes.puerto}/  (datos: {ajustes.datos})", flush=True)
    if args.depurar:
        app.run(host="0.0.0.0", port=ajustes.puerto, debug=True)
        return
    from waitress import serve
    # Pocos hilos: es una app de casa y cada hilo cuesta memoria en el NAS.
    serve(app, host="0.0.0.0", port=ajustes.puerto, threads=ajustes.hilos,
          channel_timeout=60, max_request_body_size=30 * 1024 * 1024)


if __name__ == "__main__":
    principal()
