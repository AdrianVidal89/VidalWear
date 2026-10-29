"""La API del taller: lo que usa el portátil para procesar la bandeja y cargar
los conjuntos. Todo en JSON bajo /api/taller/.

  GET  /api/taller/estado                 cuántas prendas hay en la bandeja
  GET  /api/taller/usuarios               las personas
  GET  /api/taller/bandeja                prendas pendientes de procesar
  GET  /api/taller/prendas?usuario=N      el armario completo (con fichas)
  POST /api/taller/prendas/<id>           recorte + ficha → la prenda pasa al armario
  GET  /api/taller/conjuntos?usuario=N    los conjuntos y lo que opinó la persona
  POST /api/taller/conjuntos              cargar conjuntos nuevos
  GET  /api/taller/avisos[?todo=1]        peticiones y correcciones de las personas
  POST /api/taller/avisos/atender         marcarlas como atendidas

Lo que la persona corrige en la ficha manda: «procesar» no pisa nunca un
campo que la persona haya corregido (lo dice «corregido» en cada prenda).
"""

import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, url_for

from . import bd, catalogo, imagenes

api = Blueprint("api", __name__, url_prefix="/api/taller")


def _prenda_json(p):
    v = (p.get("procesado") or p["creado"]).replace(" ", "T")
    return {
        "id": p["id"], "usuario_id": p["usuario_id"], "categoria": p["categoria"],
        "capa": catalogo.categoria(p["categoria"])["capa"], "nombre": p["nombre"],
        "estado": p["estado"], "ficha": p["ficha"], "creado": p["creado"],
        "procesado": p["procesado"],
        "corregido": sorted(bd.campos_corregidos(p["id"])),
        "foto": url_for("web.foto", pid=p["id"], tipo="original", _external=True),
        "recorte": (url_for("web.foto", pid=p["id"], tipo="recorte", _external=True, v=v)
                    if p["recorte"] else None),
    }


@api.get("/estado")
def estado():
    peticiones, correcciones = bd.contar_avisos()
    return jsonify(bandeja=bd.contar_bandeja(), personas=len(bd.usuarios()),
                   peticiones=peticiones, correcciones=correcciones)


@api.get("/categorias")
def categorias():
    return jsonify({k: catalogo.categoria(k) for k in catalogo.CATEGORIAS})


@api.get("/usuarios")
def usuarios():
    return jsonify([{"id": u["id"], "nombre": u["nombre"], "genero": u["genero"],
                     "prendas": u["n_prendas"]} for u in bd.usuarios()])


@api.get("/bandeja")
def bandeja():
    return jsonify([_prenda_json(p) for p in bd.prendas(estado="bandeja")])


@api.get("/prendas")
def prendas():
    uid = request.args.get("usuario", type=int)
    return jsonify([_prenda_json(p) for p in bd.prendas(uid)])


@api.post("/prendas/<int:pid>")
def procesar(pid):
    """Recibe el recorte (fichero «recorte», opcional) y la ficha (campo
    «datos», JSON con nombre, categoria y ficha). Marca la prenda como
    procesada: sale de la bandeja y entra en el armario."""
    p = bd.prenda(pid)
    if p is None:
        return jsonify(error="no existe"), 404
    try:
        datos = json.loads(request.form.get("datos") or "{}")
    except ValueError:
        return jsonify(error="«datos» no es JSON"), 400
    if "recorte" in request.files:
        try:
            imagenes.guardar_recorte(current_app.config["AJUSTES"].fotos, p["foto"],
                                     request.files["recorte"].stream)
        except imagenes.FotoNoValida as e:
            return jsonify(error=str(e)), 415
    cambios = {"estado": "armario",
               "procesado": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    if "recorte" in request.files:
        cambios["recorte"] = 1
    corregidos = bd.campos_corregidos(pid)
    if datos.get("nombre") and "nombre" not in corregidos:
        cambios["nombre"] = str(datos["nombre"])[:80]
    if datos.get("categoria") in catalogo.CATEGORIAS and "categoria" not in corregidos:
        cambios["categoria"] = datos["categoria"]
    if isinstance(datos.get("ficha"), dict):
        ficha = dict(datos["ficha"])
        # Lo que corrigió la persona se queda como ella lo dejó.
        for campo in corregidos & set(catalogo.CAMPOS_FICHA):
            if campo in p["ficha"]:
                ficha[campo] = p["ficha"][campo]
                if campo == "color" and "colores" in p["ficha"]:
                    ficha["colores"] = p["ficha"]["colores"]
            else:
                ficha.pop(campo, None)
        cambios["ficha"] = ficha
    bd.actualizar_prenda(pid, **cambios)
    return jsonify(_prenda_json(bd.prenda(pid)))


@api.get("/conjuntos")
def conjuntos():
    uid = request.args.get("usuario", type=int)
    if uid is None:
        return jsonify(error="falta ?usuario="), 400
    return jsonify([{
        "id": c["id"], "titulo": c["titulo"], "explicacion": c["explicacion"],
        "ocasiones": c["ocasiones"], "momentos": c["momentos"], "temporadas": c["temporadas"],
        "puntuacion": c["puntuacion"], "valoracion": c["valoracion"],
        "prendas": [p["id"] for p in c["prendas"]],
    } for c in bd.conjuntos(uid)])


@api.post("/conjuntos")
def cargar_conjuntos():
    """JSON: {"usuario": N, "reemplazar": true, "conjuntos": [{"titulo",
    "explicacion", "ocasiones", "momentos", "temporadas", "puntuacion",
    "prendas": [ids]}]}. Se valida todo antes de escribir nada."""
    datos = request.get_json(silent=True) or {}
    uid = datos.get("usuario")
    if bd.usuario(uid) is None:
        return jsonify(error="usuario desconocido"), 400
    suyas = {p["id"] for p in bd.prendas(uid, "armario")}
    validos = {g: {k for k, _ in v[1]} for g, v in catalogo.FILTROS.items()}
    errores = []
    lista = datos.get("conjuntos") or []
    for i, c in enumerate(lista):
        if not c.get("titulo"):
            errores.append(f"#{i}: sin título")
        ajenas = [x for x in c.get("prendas", []) if x not in suyas]
        if ajenas:
            errores.append(f"#{i} «{c.get('titulo')}»: prendas que no están en su armario {ajenas}")
        if len(c.get("prendas", [])) < 2:
            errores.append(f"#{i}: un conjunto necesita al menos dos prendas")
        for grupo, campo in catalogo.COLUMNA_FILTRO.items():
            malos = [v for v in c.get(campo, []) if v not in validos[grupo]]
            if malos:
                errores.append(f"#{i}: valores no válidos en {campo}: {malos}")
    if errores:
        return jsonify(error="nada cargado", detalles=errores), 400
    n = bd.guardar_conjuntos(uid, lista, bool(datos.get("reemplazar")))
    return jsonify(ok=True, cargados=n)


@api.get("/avisos")
def avisos():
    """Lo que han pedido o corregido las personas desde la app. Por defecto
    solo lo pendiente; con ?todo=1 también lo ya atendido."""
    pendientes = not request.args.get("todo")
    return jsonify(
        peticiones=[{k: x[k] for k in ("id", "usuario_id", "persona", "tipo", "comentario",
                                       "creado", "atendida", "nota")}
                    for x in bd.peticiones(pendientes)],
        correcciones=[{"id": x["id"], "usuario_id": x["usuario_id"], "persona": x["persona"],
                       "prenda_id": x["prenda_id"], "prenda": x["prenda_nombre"],
                       "categoria_actual": x["prenda_categoria"], "campo": x["campo"],
                       "antes": x["antes"], "despues": x["despues"], "creado": x["creado"],
                       "atendida": x["atendida"]}
                      for x in bd.correcciones(pendientes)])


@api.post("/avisos/atender")
def atender():
    """JSON: {"peticiones": [ids], "correcciones": [ids], "nota": "…"}. La nota
    la ve la persona en la app («Última vez: …»)."""
    datos = request.get_json(silent=True) or {}
    try:
        pet = [int(i) for i in datos.get("peticiones") or []]
        cor = [int(i) for i in datos.get("correcciones") or []]
    except (TypeError, ValueError):
        return jsonify(error="los ids tienen que ser números"), 400
    n_p, n_c = bd.atender(pet, cor, str(datos.get("nota") or "")[:300])
    return jsonify(ok=True, peticiones=n_p, correcciones=n_c)
