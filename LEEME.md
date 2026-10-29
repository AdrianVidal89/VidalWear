# VidalWear

El armario en el móvil. Cada persona de casa fotografía su ropa y accesorios con
el móvil; el **taller** (el portátil, con Claude Code) les quita el fondo, las
ficha y monta conjuntos que luego se filtran por ocasión, momento y temporada.

## Piezas

| Dónde | Qué |
|---|---|
| NAS (`vidalwear/`, puerto 8085) | La app: perfiles, subida de muchas fotos de golpe con compresión en el propio móvil, armario, corrección de fichas, bajas, conjuntos y peticiones de «rehacer conjuntos». Flask + SQLite + Pillow. |
| Portátil (`taller/vidalwear.py`) | Baja la bandeja, recorta el fondo con `rembg` (modelo `isnet-general-use`), sube recortes y fichas, rehace el inventario `.md` del vault y carga los conjuntos. |

## Ciclo de una prenda

1. Se sube desde el móvil → queda en la **bandeja** (se ve ya en el armario con ⏳).
2. `vidalwear bajar` + `vidalwear recortar` en el portátil.
3. Claude mira las hojas de contacto y escribe la ficha (color, tejido, formalidad 1-5, temporadas).
4. `vidalwear subir fichas.json` → pasa al **armario** con su recorte sin fondo.
5. «Ya no la tengo» en la app → se borra (fila, fotos y los conjuntos en los que salía).

## Desplegar en el NAS

```sh
cd /share/homes/adrian/apps/vidalwear
cp .env.example .env
sh deploy.sh            # construir y levantar
sh deploy.sh estado
```

Actualizar después: `sh /share/homes/adrian/scripts/actualizar-vidalwear.sh` (copia de
`extras/actualizar.sh`), o el botón del Actualizador (puerto 8091).

## Taller en el portátil

```sh
python3 -m venv taller/.venv
taller/.venv/bin/pip install "rembg[cpu]" pillow
taller/.venv/bin/python taller/vidalwear.py estado
```

Variables: `VIDALWEAR_URL` (por defecto `http://100.92.242.23:8085`), `VIDALWEAR_TRABAJO`
(`~/.cache/vidalwear`), `VIDALWEAR_VAULT` (carpeta de los inventarios).

## Formato de los conjuntos (`vidalwear cargar`)

```json
{"usuario": 1, "reemplazar": true, "conjuntos": [
  {"titulo": "Marino y arena", "explicacion": "Por qué funciona…",
   "ocasiones": ["casual", "smart"], "momentos": ["dia"],
   "temporadas": ["primavera", "verano", "otono"],
   "puntuacion": 82, "prendas": [1, 2, 3]}]}
```

Valores: ocasión `casual|smart|formal|fiesta|deporte`, momento `dia|noche`, temporada
`primavera|verano|otono|invierno`. Con `reemplazar` se quitan los anteriores salvo los
que tengan «me gusta». Se valida todo antes de escribir: o entra todo o nada.
