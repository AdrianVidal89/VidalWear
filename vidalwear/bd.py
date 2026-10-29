"""La base de datos: un SQLite en la carpeta de datos.

Tres cosas: personas, prendas y conjuntos. Las fotos van aparte, en disco;
aquí solo se guarda qué prenda es cada foto.

Ciclo de una prenda:
  bandeja  → recién subida desde el móvil, con la foto tal cual.
  armario  → ya procesada en el portátil: con su recorte sin fondo y su ficha.
Cuando alguien se desprende de una prenda se borra de verdad (fila y fotos),
y con ella los conjuntos que la usaban: un conjunto cojo no sirve.
"""

import json
import sqlite3

from flask import current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    genero TEXT NOT NULL CHECK (genero IN ('hombre', 'mujer')),
    bienvenida_hecha INTEGER NOT NULL DEFAULT 0,
    creado TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS prendas (
    -- AUTOINCREMENT: un número de prenda no se reutiliza nunca, ni tras
    -- borrarla. El taller y el inventario del vault se fían de ese número.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    categoria TEXT NOT NULL,
    nombre TEXT NOT NULL DEFAULT '',
    estado TEXT NOT NULL DEFAULT 'bandeja' CHECK (estado IN ('bandeja', 'armario')),
    foto TEXT NOT NULL,              -- nombre base de los ficheros en disco
    recorte INTEGER NOT NULL DEFAULT 0,
    ficha TEXT NOT NULL DEFAULT '{}', -- lo que anota el taller: color, formalidad…
    creado TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    procesado TEXT
);
CREATE INDEX IF NOT EXISTS prendas_por_usuario ON prendas(usuario_id, estado);

CREATE TABLE IF NOT EXISTS conjuntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo TEXT NOT NULL,
    explicacion TEXT NOT NULL DEFAULT '',
    ocasiones TEXT NOT NULL DEFAULT '[]',
    momentos TEXT NOT NULL DEFAULT '[]',
    temporadas TEXT NOT NULL DEFAULT '[]',
    puntuacion INTEGER NOT NULL DEFAULT 50,   -- lo bien que lo ve el estilista (0-100)
    valoracion INTEGER NOT NULL DEFAULT 0,    -- lo que dice la persona: -1, 0, 1
    creado TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS conjunto_prendas (
    conjunto_id INTEGER NOT NULL REFERENCES conjuntos(id) ON DELETE CASCADE,
    prenda_id INTEGER NOT NULL REFERENCES prendas(id) ON DELETE CASCADE,
    orden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (conjunto_id, prenda_id)
);

-- Lo que la persona corrige en la ficha de una prenda («esto no es un
-- jersey, es un…»). La estilista lo lee en el taller y lo respeta: un campo
-- corregido por la persona no lo vuelve a pisar el taller.
CREATE TABLE IF NOT EXISTS correcciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prenda_id INTEGER NOT NULL REFERENCES prendas(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    campo TEXT NOT NULL,
    antes TEXT,                       -- JSON
    despues TEXT,                     -- JSON
    creado TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atendida TEXT                     -- cuándo la vio la estilista (NULL = pendiente)
);
CREATE INDEX IF NOT EXISTS correcciones_por_prenda ON correcciones(prenda_id);

-- Lo que la persona pide desde la app («rehacer conjuntos»). Una pendiente
-- como mucho por persona y tipo; al pedir otra vez se actualiza el comentario.
CREATE TABLE IF NOT EXISTS peticiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL DEFAULT 'rehacer_conjuntos',
    comentario TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    atendida TEXT,
    nota TEXT NOT NULL DEFAULT ''     -- lo que contesta la estilista al atenderla
);
"""


def abrir(ruta):
    con = sqlite3.connect(ruta, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def iniciar(ruta):
    con = abrir(ruta)
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(ESQUEMA)
    con.commit()
    con.close()


def bd():
    """La conexión de esta petición (una por petición, se cierra sola)."""
    if "bd" not in g:
        g.bd = abrir(current_app.config["AJUSTES"].bd)
    return g.bd


def cerrar(_=None):
    con = g.pop("bd", None)
    if con is not None:
        con.close()


# ------------------------------------------------------------------ USUARIOS
def usuarios():
    return bd().execute(
        "SELECT u.*, (SELECT COUNT(*) FROM prendas p WHERE p.usuario_id = u.id) AS n_prendas "
        "FROM usuarios u ORDER BY u.nombre COLLATE NOCASE").fetchall()


def usuario(uid):
    if uid is None:
        return None
    return bd().execute("SELECT * FROM usuarios WHERE id = ?", (uid,)).fetchone()


def crear_usuario(nombre, genero):
    cur = bd().execute("INSERT INTO usuarios (nombre, genero) VALUES (?, ?)", (nombre, genero))
    bd().commit()
    return cur.lastrowid


def actualizar_usuario(uid, **campos):
    permitidos = {k: v for k, v in campos.items() if k in ("nombre", "genero", "bienvenida_hecha")}
    if not permitidos:
        return
    sets = ", ".join(f"{k} = ?" for k in permitidos)
    bd().execute(f"UPDATE usuarios SET {sets} WHERE id = ?", (*permitidos.values(), uid))
    bd().commit()


def borrar_usuario(uid):
    """Devuelve los nombres de foto de sus prendas para borrarlas del disco."""
    fotos = [r["foto"] for r in bd().execute("SELECT foto FROM prendas WHERE usuario_id = ?", (uid,))]
    bd().execute("DELETE FROM usuarios WHERE id = ?", (uid,))
    bd().commit()
    return fotos


# ------------------------------------------------------------------- PRENDAS
def _prenda(fila):
    if fila is None:
        return None
    p = dict(fila)
    try:
        p["ficha"] = json.loads(p.get("ficha") or "{}")
    except ValueError:
        p["ficha"] = {}
    return p


def crear_prenda(uid, categoria, nombre, foto):
    cur = bd().execute(
        "INSERT INTO prendas (usuario_id, categoria, nombre, foto) VALUES (?, ?, ?, ?)",
        (uid, categoria, nombre, foto))
    bd().commit()
    return cur.lastrowid


def prenda(pid):
    return _prenda(bd().execute("SELECT * FROM prendas WHERE id = ?", (pid,)).fetchone())


def prendas(uid=None, estado=None):
    sql, args = "SELECT * FROM prendas WHERE 1 = 1", []
    if uid is not None:
        sql += " AND usuario_id = ?"
        args.append(uid)
    if estado:
        sql += " AND estado = ?"
        args.append(estado)
    sql += " ORDER BY categoria, nombre COLLATE NOCASE, id"
    return [_prenda(f) for f in bd().execute(sql, args)]


def contar_bandeja(uid=None):
    sql, args = "SELECT COUNT(*) FROM prendas WHERE estado = 'bandeja'", []
    if uid is not None:
        sql += " AND usuario_id = ?"
        args.append(uid)
    return bd().execute(sql, args).fetchone()[0]


def actualizar_prenda(pid, **campos):
    permitidos = {}
    for k, v in campos.items():
        if k == "ficha":
            v = json.dumps(v, ensure_ascii=False)
        if k in ("nombre", "categoria", "estado", "recorte", "ficha", "procesado"):
            permitidos[k] = v
    if not permitidos:
        return
    sets = ", ".join(f"{k} = ?" for k in permitidos)
    bd().execute(f"UPDATE prendas SET {sets} WHERE id = ?", (*permitidos.values(), pid))
    bd().commit()


def borrar_prenda(pid):
    """Borra la prenda y los conjuntos en los que salía."""
    bd().execute(
        "DELETE FROM conjuntos WHERE id IN "
        "(SELECT conjunto_id FROM conjunto_prendas WHERE prenda_id = ?)", (pid,))
    bd().execute("DELETE FROM prendas WHERE id = ?", (pid,))
    bd().commit()


# ----------------------------------------------------------------- CONJUNTOS
def _conjunto(fila):
    c = dict(fila)
    for k in ("ocasiones", "momentos", "temporadas"):
        try:
            c[k] = json.loads(c[k] or "[]")
        except ValueError:
            c[k] = []
    c["prendas"] = [_prenda(f) for f in bd().execute(
        "SELECT p.* FROM conjunto_prendas cp JOIN prendas p ON p.id = cp.prenda_id "
        "WHERE cp.conjunto_id = ? ORDER BY cp.orden", (c["id"],))]
    return c


def conjuntos(uid):
    filas = bd().execute(
        "SELECT * FROM conjuntos WHERE usuario_id = ? ORDER BY puntuacion DESC, id DESC", (uid,))
    return [_conjunto(f) for f in filas]


def conjuntos_con_prenda(pid):
    """Los conjuntos en los que sale una prenda: primero los que gustan y los
    que mejor ve el estilista; los descartados («no me lo pondría»), al final."""
    filas = bd().execute(
        "SELECT c.* FROM conjuntos c JOIN conjunto_prendas cp ON cp.conjunto_id = c.id "
        "WHERE cp.prenda_id = ? ORDER BY (c.valoracion < 0), c.valoracion DESC, "
        "c.puntuacion DESC, c.id DESC", (pid,))
    return [_conjunto(f) for f in filas]


def conjunto(cid):
    f = bd().execute("SELECT * FROM conjuntos WHERE id = ?", (cid,)).fetchone()
    return _conjunto(f) if f else None


def valorar_conjunto(cid, valor):
    bd().execute("UPDATE conjuntos SET valoracion = ? WHERE id = ?", (valor, cid))
    bd().commit()


def guardar_conjuntos(uid, lista, reemplazar):
    """Carga conjuntos del estilista. Con «reemplazar» se quitan antes los que
    había, salvo los que la persona marcó con un «me gusta»: esos se respetan."""
    con = bd()
    if reemplazar:
        con.execute("DELETE FROM conjuntos WHERE usuario_id = ? AND valoracion <= 0", (uid,))
    creados = 0
    for c in lista:
        cur = con.execute(
            "INSERT INTO conjuntos (usuario_id, titulo, explicacion, ocasiones, momentos, "
            "temporadas, puntuacion) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, c["titulo"], c.get("explicacion", ""),
             json.dumps(c.get("ocasiones", [])), json.dumps(c.get("momentos", [])),
             json.dumps(c.get("temporadas", [])), int(c.get("puntuacion", 50))))
        for orden, pid in enumerate(c["prendas"]):
            con.execute("INSERT OR IGNORE INTO conjunto_prendas VALUES (?, ?, ?)",
                        (cur.lastrowid, pid, orden))
        creados += 1
    con.commit()
    return creados


# -------------------------------------------------------------- CORRECCIONES
def corregir(pid, uid, campo, antes, despues):
    bd().execute(
        "INSERT INTO correcciones (prenda_id, usuario_id, campo, antes, despues) "
        "VALUES (?, ?, ?, ?, ?)",
        (pid, uid, campo, json.dumps(antes, ensure_ascii=False),
         json.dumps(despues, ensure_ascii=False)))
    bd().commit()


def campos_corregidos(pid):
    """Los campos de una prenda que ha corregido la persona alguna vez."""
    return {f["campo"] for f in bd().execute(
        "SELECT DISTINCT campo FROM correcciones WHERE prenda_id = ?", (pid,))}


def _correccion(f):
    c = dict(f)
    for k in ("antes", "despues"):
        try:
            c[k] = json.loads(c[k]) if c[k] is not None else None
        except ValueError:
            pass
    return c


def correcciones(pendientes=True, uid=None):
    sql = ("SELECT c.*, p.nombre AS prenda_nombre, p.categoria AS prenda_categoria, "
           "u.nombre AS persona FROM correcciones c JOIN prendas p ON p.id = c.prenda_id "
           "JOIN usuarios u ON u.id = c.usuario_id WHERE 1 = 1")
    args = []
    if pendientes:
        sql += " AND c.atendida IS NULL"
    if uid is not None:
        sql += " AND c.usuario_id = ?"
        args.append(uid)
    return [_correccion(f) for f in bd().execute(sql + " ORDER BY c.id", args)]


# ---------------------------------------------------------------- PETICIONES
def peticion_pendiente(uid, tipo="rehacer_conjuntos"):
    f = bd().execute("SELECT * FROM peticiones WHERE usuario_id = ? AND tipo = ? "
                     "AND atendida IS NULL ORDER BY id DESC LIMIT 1", (uid, tipo)).fetchone()
    return dict(f) if f else None


def ultima_atendida(uid, tipo="rehacer_conjuntos"):
    f = bd().execute("SELECT * FROM peticiones WHERE usuario_id = ? AND tipo = ? "
                     "AND atendida IS NOT NULL ORDER BY atendida DESC LIMIT 1",
                     (uid, tipo)).fetchone()
    return dict(f) if f else None


def pedir(uid, comentario, tipo="rehacer_conjuntos"):
    ya = peticion_pendiente(uid, tipo)
    if ya:
        bd().execute("UPDATE peticiones SET comentario = ? WHERE id = ?", (comentario, ya["id"]))
    else:
        bd().execute("INSERT INTO peticiones (usuario_id, tipo, comentario) VALUES (?, ?, ?)",
                     (uid, tipo, comentario))
    bd().commit()


def anular_peticion(uid, tipo="rehacer_conjuntos"):
    """Solo se anula la pendiente; las atendidas se quedan como historial."""
    bd().execute("DELETE FROM peticiones WHERE usuario_id = ? AND tipo = ? AND atendida IS NULL",
                 (uid, tipo))
    bd().commit()


def peticiones(pendientes=True):
    sql = ("SELECT pe.*, u.nombre AS persona FROM peticiones pe "
           "JOIN usuarios u ON u.id = pe.usuario_id")
    if pendientes:
        sql += " WHERE pe.atendida IS NULL"
    return [dict(f) for f in bd().execute(sql + " ORDER BY pe.id")]


def atender(peticiones_ids=(), correcciones_ids=(), nota=""):
    ahora = "datetime('now', 'localtime')"
    con = bd()
    n_p = n_c = 0
    for i in peticiones_ids:
        n_p += con.execute(f"UPDATE peticiones SET atendida = {ahora}, nota = ? "
                           "WHERE id = ? AND atendida IS NULL", (nota, int(i))).rowcount
    for i in correcciones_ids:
        n_c += con.execute(f"UPDATE correcciones SET atendida = {ahora} "
                           "WHERE id = ? AND atendida IS NULL", (int(i),)).rowcount
    con.commit()
    return n_p, n_c


def contar_avisos():
    con = bd()
    return (con.execute("SELECT COUNT(*) FROM peticiones WHERE atendida IS NULL").fetchone()[0],
            con.execute("SELECT COUNT(*) FROM correcciones WHERE atendida IS NULL").fetchone()[0])
