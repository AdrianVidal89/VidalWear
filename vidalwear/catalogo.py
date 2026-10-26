"""Las categorías de ropa y los filtros de los conjuntos.

Todo lo que es «vocabulario» de la app vive aquí: qué categorías se ofrecen a
un hombre y a una mujer, en qué orden las recorre la guía de alta, qué papel
juega cada una en un conjunto (arriba, abajo, calzado…) y qué filtros hay.

La «capa» es lo que permite montar un conjunto con sentido y pintarlo
ordenado: primero lo de abrigo, luego arriba, abajo, calzado y accesorios.
"""

from datetime import date

# Orden en que se pintan las prendas dentro de un conjunto.
CAPAS = ["exterior", "cuerpo", "arriba", "abajo", "calzado", "accesorio"]

# clave: (nombre, «tus …» para la guía, icono, capa, consejo para la foto)
CATEGORIAS = {
    "camisetas": ("Camisetas", "tus camisetas", "👕", "arriba",
                  "Extiéndelas sobre la cama, de una en una, bien estiradas."),
    "tops": ("Camisetas y tops", "tus camisetas y tops", "👚", "arriba",
             "Extiéndelos sobre la cama, de uno en uno."),
    "polos": ("Polos", "tus polos", "👕", "arriba",
              "Abotonados y estirados sobre la cama."),
    "camisas": ("Camisas", "tus camisas", "👔", "arriba",
                "Mejor en percha y colgadas de una puerta lisa: se ve el cuello."),
    "blusas": ("Blusas y camisas", "tus blusas y camisas", "👚", "arriba",
               "En percha, colgadas de una puerta lisa."),
    "jerseis": ("Jerséis y sudaderas", "tus jerséis y sudaderas", "🧶", "arriba",
                "Doblados por la mitad o extendidos, que se vea el cuello."),
    "punto": ("Jerséis y cárdigans", "tus jerséis y cárdigans", "🧶", "arriba",
              "Extendidos sobre la cama, que se vea el cuello."),
    "chaquetas": ("Chaquetas y abrigos", "tus chaquetas y abrigos", "🧥", "exterior",
                  "En percha, colgados de una puerta. Cerrados, si se puede."),
    "americanas": ("Americanas y trajes", "tus americanas y trajes", "🤵", "exterior",
                   "En percha. Si es un traje, la chaqueta y el pantalón juntos."),
    "blazers": ("Americanas y blazers", "tus americanas y blazers", "🧥", "exterior",
                "En percha, colgadas de una puerta lisa."),
    "vestidos": ("Vestidos", "tus vestidos", "👗", "cuerpo",
                 "En percha y colgados: que se vea el largo entero."),
    "monos": ("Monos", "tus monos", "👗", "cuerpo",
              "En percha, que se vea el largo entero."),
    "faldas": ("Faldas", "tus faldas", "👗", "abajo",
               "Extendidas sobre la cama, que se vea el vuelo."),
    "pantalones": ("Pantalones", "tus pantalones", "👖", "abajo",
                   "Doblados por la mitad a lo largo, sobre la cama."),
    "vaqueros": ("Vaqueros", "tus vaqueros", "👖", "abajo",
                 "Doblados por la mitad a lo largo: así se distingue el lavado."),
    "cortos": ("Pantalones cortos", "tus pantalones cortos", "🩳", "abajo",
               "Extendidos sobre la cama."),
    "zapatos": ("Zapatos y zapatillas", "tus zapatos y zapatillas", "👟", "calzado",
                "El par junto, de lado, sobre el suelo."),
    "bolsos": ("Bolsos", "tus bolsos", "👜", "accesorio",
               "De frente, sobre una mesa o el suelo."),
    "cinturones": ("Cinturones", "tus cinturones", "➰", "accesorio",
                   "Enrollados o estirados, que se vea la hebilla."),
    "relojes": ("Relojes", "tus relojes", "⌚", "accesorio",
                "De frente, sobre una superficie lisa. Que se vea la esfera."),
    "joyas": ("Joyería y bisutería", "tus joyas", "💍", "accesorio",
              "Sobre un fondo liso. Los pendientes, por parejas."),
    "corbatas": ("Corbatas y pajaritas", "tus corbatas", "👔", "accesorio",
                 "Estiradas sobre la cama."),
    "panuelos": ("Bufandas y pañuelos", "tus bufandas y pañuelos", "🧣", "accesorio",
                 "Extendidos o doblados, que se vea el dibujo."),
    "fulares": ("Pañuelos y fulares", "tus pañuelos y fulares", "🧣", "accesorio",
                "Extendidos, que se vea el dibujo."),
    "gorras": ("Gorras y sombreros", "tus gorras y sombreros", "🧢", "accesorio",
               "De frente, sobre una mesa."),
    "gafas": ("Gafas de sol", "tus gafas de sol", "🕶️", "accesorio",
              "Abiertas, de frente."),
    "otros": ("Otros", "lo que falte", "✚", "accesorio",
              "Lo que no encaje arriba. Ponle nombre para saber qué es."),
}

GUIA = {
    "hombre": ["camisetas", "polos", "camisas", "jerseis", "chaquetas", "americanas",
               "pantalones", "vaqueros", "cortos", "zapatos", "cinturones", "relojes",
               "corbatas", "panuelos", "gorras", "gafas", "otros"],
    "mujer": ["tops", "blusas", "punto", "chaquetas", "blazers", "vestidos", "monos",
              "faldas", "pantalones", "vaqueros", "cortos", "zapatos", "bolsos",
              "joyas", "relojes", "fulares", "cinturones", "gafas", "otros"],
}

GENEROS = {"hombre": "Hombre", "mujer": "Mujer"}


def categoria(clave):
    """Datos de una categoría. Una desconocida se trata como «otros»."""
    nombre, tus, icono, capa, consejo = CATEGORIAS.get(clave, CATEGORIAS["otros"])
    return {"clave": clave if clave in CATEGORIAS else "otros", "nombre": nombre,
            "tus": tus, "icono": icono, "capa": capa, "consejo": consejo}


def categorias_de(genero):
    return [categoria(c) for c in GUIA.get(genero, GUIA["hombre"])]


# ------------------------------------------------------------------ FILTROS
# Cada grupo es de elección única: se pulsa una pastilla y se vuelve a pulsar
# para quitarla. Las claves sin tildes: van en la URL y en la base de datos.
FILTROS = {
    "ocasion": ("Ocasión", [("casual", "Casual"), ("smart", "Arreglado informal"),
                            ("formal", "Formal"), ("fiesta", "Fiesta"),
                            ("deporte", "Deporte")]),
    "momento": ("Momento", [("dia", "Día"), ("noche", "Noche")]),
    "temporada": ("Temporada", [("primavera", "Primavera"), ("verano", "Verano"),
                                ("otono", "Otoño"), ("invierno", "Invierno")]),
}

# Nombre de la columna en la tabla de conjuntos para cada grupo de filtros.
COLUMNA_FILTRO = {"ocasion": "ocasiones", "momento": "momentos", "temporada": "temporadas"}


def temporada_actual(hoy=None):
    """La estación de Sevilla, no la del calendario: el verano empieza en junio
    y se alarga a septiembre, el otoño son dos meses."""
    m = (hoy or date.today()).month
    if m in (12, 1, 2):
        return "invierno"
    if m in (3, 4, 5):
        return "primavera"
    if m in (6, 7, 8, 9):
        return "verano"
    return "otono"


def etiqueta_filtro(grupo, clave):
    for k, nombre in FILTROS[grupo][1]:
        if k == clave:
            return nombre
    return clave


FORMALIDAD = {1: "Deportivo", 2: "Casual", 3: "Arreglado informal",
              4: "De oficina", 5: "Formal"}
