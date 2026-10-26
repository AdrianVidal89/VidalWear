"""Las pantallas que ve la persona en el móvil."""

from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, get_flashed_messages, jsonify,
                   redirect, render_template, request, send_file, session, url_for)

from . import __version__, bd, catalogo, imagenes

web = Blueprint("web", __name__)


def ajustes():
    return current_app.config["AJUSTES"]


@web.before_app_request
def cargar_usuario():
    g.usuario = bd.usuario(session.get("uid"))
    if g.usuario is None:
        session.pop("uid", None)


@web.app_context_processor
def contexto():
    return {
        "app": ajustes().titulo,
        "version": __version__,
        "usuario": g.get("usuario"),
        "mensajes": get_flashed_messages(with_categories=True),
        "cat": catalogo.categoria,
        "catalogo": catalogo,
    }


def con_usuario(vista):
    """Pantallas que necesitan saber quién mira: sin perfil, al selector."""
    @wraps(vista)
    def envuelta(*a, **k):
        if g.usuario is None:
            return redirect(url_for("web.perfiles"))
        return vista(*a, **k)
    return envuelta


def prenda_mia(pid):
    p = bd.prenda(pid)
    if p is None or p["usuario_id"] != g.usuario["id"]:
        abort(404)
    return p


def entrar(uid):
    session.permanent = True
    session["uid"] = uid


# ------------------------------------------------------------------ PERFILES
@web.route("/")
def inicio():
    if g.usuario is None:
        return redirect(url_for("web.perfiles"))
    if not g.usuario["bienvenida_hecha"]:
        return redirect(url_for("web.bienvenida"))
    return redirect(url_for("web.armario"))


@web.route("/perfiles")
def perfiles():
    lista = bd.usuarios()
    if not lista:
        return redirect(url_for("web.nuevo"))
    return render_template("perfiles.html", perfiles=lista, seccion="perfil")


@web.post("/perfiles/<int:uid>/entrar")
def entrar_perfil(uid):
    if bd.usuario(uid) is None:
        abort(404)
    entrar(uid)
    return redirect(url_for("web.inicio"))


@web.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()[:40]
        genero = request.form.get("genero")
        if not nombre or genero not in catalogo.GENEROS:
            flash("Pon un nombre y elige hombre o mujer.", "error")
            return render_template("nuevo.html", nombre=nombre, seccion="perfil")
        entrar(bd.crear_usuario(nombre, genero))
        return redirect(url_for("web.bienvenida"))
    return render_template("nuevo.html", nombre="", seccion="perfil")


@web.route("/perfil", methods=["GET", "POST"])
@con_usuario
def perfil():
    if request.method == "POST":
        nombre = (request.form.get("nombre") or "").strip()[:40]
        genero = request.form.get("genero")
        if nombre and genero in catalogo.GENEROS:
            bd.actualizar_usuario(g.usuario["id"], nombre=nombre, genero=genero)
            flash("Guardado.", "ok")
        return redirect(url_for("web.perfil"))
    return render_template("perfil.html", seccion="perfil",
                           n_prendas=len(bd.prendas(g.usuario["id"])),
                           n_bandeja=bd.contar_bandeja(g.usuario["id"]))


@web.post("/perfil/salir")
def salir():
    session.pop("uid", None)
    return redirect(url_for("web.perfiles"))


@web.post("/perfil/borrar")
@con_usuario
def borrar_perfil():
    if request.form.get("confirmar") != g.usuario["nombre"]:
        flash("Para borrar el perfil escribe su nombre tal cual.", "error")
        return redirect(url_for("web.perfil"))
    for base in bd.borrar_usuario(g.usuario["id"]):
        imagenes.borrar(ajustes().fotos, base)
    session.pop("uid", None)
    flash("Perfil borrado, con todas sus prendas y conjuntos.", "ok")
    return redirect(url_for("web.perfiles"))


# ------------------------------------------------------------ GUÍA DE ALTA
@web.route("/bienvenida")
@con_usuario
def bienvenida():
    pasos = catalogo.categorias_de(g.usuario["genero"])
    return render_template("bienvenida.html", pasos=pasos, seccion="anadir")


@web.route("/bienvenida/fin")
@con_usuario
def bienvenida_fin():
    bd.actualizar_usuario(g.usuario["id"], bienvenida_hecha=1)
    return render_template("fin.html", seccion="anadir",
                           n_bandeja=bd.contar_bandeja(g.usuario["id"]))


# ------------------------------------------------------------------- AÑADIR
@web.route("/anadir")
@con_usuario
def anadir():
    return render_template("anadir.html", seccion="anadir",
                           categorias=catalogo.categorias_de(g.usuario["genero"]))


@web.route("/anadir/<clave>")
@con_usuario
def subir(clave):
    if clave not in catalogo.CATEGORIAS:
        abort(404)
    guiado = request.args.get("guiado") == "1"
    pasos = catalogo.categorias_de(g.usuario["genero"])
    claves = [p["clave"] for p in pasos]
    paso = claves.index(clave) + 1 if clave in claves else None
    siguiente = None
    if guiado and paso is not None:
        siguiente = pasos[paso] if paso < len(pasos) else None
    ya = [p for p in bd.prendas(g.usuario["id"]) if p["categoria"] == clave]
    return render_template("subir.html", seccion="anadir", c=catalogo.categoria(clave),
                           guiado=guiado, paso=paso, total=len(pasos),
                           siguiente=siguiente, ya=ya)


@web.post("/api/prendas")
@con_usuario
def api_subir():
    clave = request.form.get("categoria", "otros")
    if clave not in catalogo.CATEGORIAS:
        clave = "otros"
    nombre = (request.form.get("nombre") or "").strip()[:80]
    foto = request.files.get("foto")
    if foto is None:
        return jsonify(error="No ha llegado ninguna foto."), 400
    try:
        base = imagenes.guardar_original(ajustes().fotos, foto.stream)
    except imagenes.FotoNoValida as e:
        return jsonify(error=str(e)), 415
    pid = bd.crear_prenda(g.usuario["id"], clave, nombre, base)
    return jsonify(id=pid, mini=url_for("web.foto", pid=pid, tipo="mini"))


@web.post("/api/prendas/<int:pid>/nombre")
@con_usuario
def api_nombre(pid):
    prenda_mia(pid)
    datos = request.get_json(silent=True) or {}
    bd.actualizar_prenda(pid, nombre=(datos.get("nombre") or "").strip()[:80])
    return jsonify(ok=True)


# ------------------------------------------------------------------ ARMARIO
@web.route("/armario")
@con_usuario
def armario():
    todas = bd.prendas(g.usuario["id"])
    filtro = request.args.get("c")
    grupos = {}
    for p in todas:
        grupos.setdefault(p["categoria"], []).append(p)
    # Las categorías en el orden de la guía; las que no estén en ella, al final.
    orden = [c["clave"] for c in catalogo.categorias_de(g.usuario["genero"])]
    claves = sorted(grupos, key=lambda k: orden.index(k) if k in orden else 99)
    visibles = [k for k in claves if not filtro or k == filtro]
    return render_template("armario.html", seccion="armario", grupos=grupos, claves=claves,
                           visibles=visibles, filtro=filtro, total=len(todas),
                           n_bandeja=sum(1 for p in todas if p["estado"] == "bandeja"))


@web.route("/prenda/<int:pid>", methods=["GET", "POST"])
@con_usuario
def prenda(pid):
    p = prenda_mia(pid)
    if request.method == "POST":
        clave = request.form.get("categoria")
        cambios = {"nombre": (request.form.get("nombre") or "").strip()[:80]}
        if clave in catalogo.CATEGORIAS:
            cambios["categoria"] = clave
        bd.actualizar_prenda(pid, **cambios)
        flash("Guardado.", "ok")
        return redirect(url_for("web.prenda", pid=pid))
    n_conjuntos = sum(1 for c in bd.conjuntos(g.usuario["id"])
                      if any(x["id"] == pid for x in c["prendas"]))
    return render_template("prenda.html", seccion="armario", p=p, n_conjuntos=n_conjuntos,
                           categorias=catalogo.categorias_de(g.usuario["genero"]))


@web.post("/prenda/<int:pid>/borrar")
@con_usuario
def borrar_prenda(pid):
    p = prenda_mia(pid)
    bd.borrar_prenda(pid)
    imagenes.borrar(ajustes().fotos, p["foto"])
    flash("Fuera del armario. Los conjuntos en los que salía se han quitado.", "ok")
    return redirect(url_for("web.armario"))


@web.route("/foto/<int:pid>/<tipo>")
def foto(pid, tipo):
    """Sirve una foto. «vista» y «vista-mini» dan el recorte si ya existe y la
    foto original si no, que es lo que quiere casi siempre la interfaz."""
    p = bd.prenda(pid)
    if p is None:
        abort(404)
    if tipo in ("vista", "vista-mini"):
        mini = tipo == "vista-mini"
        tipo = ("recorte-mini" if mini else "recorte") if p["recorte"] else ("mini" if mini else "original")
    if tipo not in ("original", "mini", "recorte", "recorte-mini"):
        abort(404)
    ruta = imagenes.ruta(ajustes().fotos, p["foto"], tipo)
    if not ruta.exists():
        abort(404)
    # Las URLs llevan ?v=<fecha de procesado>: se pueden cachear sin miedo.
    return send_file(ruta, max_age=60 * 60 * 24 * 30)


# ---------------------------------------------------------------- CONJUNTOS
@web.route("/conjuntos")
@con_usuario
def conjuntos():
    # Sin filtros en la URL, se arranca con la temporada de hoy marcada.
    if not request.args:
        return redirect(url_for("web.conjuntos", temporada=catalogo.temporada_actual()))
    elegidos = {k: request.args.get(k) for k in catalogo.FILTROS if request.args.get(k)}
    todos = bd.conjuntos(g.usuario["id"])

    def aciertos(c):
        return sum(1 for k, v in elegidos.items() if v in c[catalogo.COLUMNA_FILTRO[k]])

    def orden(c):
        return (-aciertos(c), -c["valoracion"], -c["puntuacion"], -c["id"])

    utiles = [c for c in todos if c["valoracion"] >= 0]
    exactos = sorted([c for c in utiles if aciertos(c) == len(elegidos)], key=orden)
    parecidos = sorted([c for c in utiles if 0 < aciertos(c) < len(elegidos)], key=orden)
    descartados = [c for c in todos if c["valoracion"] < 0]
    return render_template("conjuntos.html", seccion="conjuntos", elegidos=elegidos,
                           exactos=exactos, parecidos=parecidos[:6],
                           descartados=descartados, hay_alguno=bool(todos),
                           n_armario=len(bd.prendas(g.usuario["id"], "armario")))


@web.post("/api/conjuntos/<int:cid>/valorar")
@con_usuario
def valorar(cid):
    c = bd.conjunto(cid)
    if c is None or c["usuario_id"] != g.usuario["id"]:
        abort(404)
    valor = (request.get_json(silent=True) or {}).get("valor", 0)
    if valor not in (-1, 0, 1):
        valor = 0
    bd.valorar_conjunto(cid, valor)
    return jsonify(ok=True, valor=valor)


# -------------------------------------------------------------------- OTROS
@web.route("/estado")
def estado():
    return jsonify(app="VidalWear", version=__version__, ok=True,
                   personas=len(bd.usuarios()), bandeja=bd.contar_bandeja())


@web.route("/manifest.webmanifest")
def manifiesto():
    return jsonify({
        "name": ajustes().titulo, "short_name": ajustes().titulo,
        "start_url": "/", "display": "standalone",
        "background_color": "#111315", "theme_color": "#111315",
        "icons": [{"src": url_for("static", filename="icono.png"),
                   "sizes": "512x512", "type": "image/png"}],
    }), 200, {"Content-Type": "application/manifest+json"}
