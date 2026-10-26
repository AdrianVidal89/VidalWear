#!/bin/sh
# ==============================================================================
# deploy.sh — construir, levantar y vigilar VidalWear en el NAS
# ==============================================================================
#   sh deploy.sh            construir y levantar (lo normal)
#   sh deploy.sh estado     ver si está en marcha
#   sh deploy.sh logs [n]   últimas n líneas del registro
#   sh deploy.sh parar      pararlo
#   sh deploy.sh reiniciar  reiniciarlo sin reconstruir
# ==============================================================================
set -e

PATH="/share/CACHEDEV1_DATA/.qpkg/container-station/bin:$PATH"
export PATH
DOCKER_CONFIG=/tmp/dockercfg
export DOCKER_CONFIG

CARPETA=$(cd "$(dirname "$0")" && pwd)
cd "$CARPETA"

aviso() { echo "[$(date '+%H:%M:%S')] $1"; }

PUERTO=""
[ -f .env ] && PUERTO=$(grep '^PUERTO=' .env | cut -d= -f2 | tr -d ' ' || true)
[ -n "$PUERTO" ] || PUERTO=8085

case "${1:-desplegar}" in
  estado)
    docker compose ps
    curl -fsS "http://localhost:$PUERTO/estado" 2>/dev/null || echo "No responde en el $PUERTO"
    echo
    exit 0 ;;
  logs)
    docker compose logs --tail "${2:-60}"
    exit 0 ;;
  parar)
    docker compose down
    aviso "Parado."
    exit 0 ;;
  reiniciar)
    docker compose restart
    aviso "Reiniciado."
    exit 0 ;;
esac

[ -f .env ] || { echo "ERROR: falta el fichero .env (cópialo de .env.example)"; exit 1; }

# Las carpetas de datos se crean a mano: si las crea Docker, son de root y el
# contenedor (que corre como adrian) no podría escribir en ellas.
mkdir -p datos/fotos datos/copias

# --- Copia de la base de datos ------------------------------------------------
# Las fotos están en disco; qué prenda es cada una, sus fichas y los conjuntos
# viven en vidalwear.db. Copia antes de cada despliegue, se guardan las diez
# últimas. Con la app en marcha se usa la copia en caliente de SQLite.
if [ -f datos/vidalwear.db ]; then
    COPIA="copias/vidalwear-$(date '+%Y%m%d-%H%M%S').db"
    if docker ps --format '{{.Names}}' | grep -qx vidalwear; then
        docker exec vidalwear python -c "import sqlite3; s=sqlite3.connect('/datos/vidalwear.db'); d=sqlite3.connect('/datos/$COPIA'); s.backup(d); d.close()"
    else
        cp datos/vidalwear.db "datos/$COPIA"
    fi
    aviso "Copia de la base de datos en datos/$COPIA"
    ls -1t datos/copias/vidalwear-*.db 2>/dev/null | tail -n +11 | while read -r V; do rm -f "$V"; done
fi

aviso "Construyendo la imagen…"
docker compose build

aviso "Levantando…"
docker compose up -d

aviso "Esperando a que responda…"
INTENTO=0
while [ "$INTENTO" -lt 30 ]; do
    if curl -fsS "http://localhost:$PUERTO/estado" >/dev/null 2>&1; then
        aviso "Listo: http://localhost:$PUERTO/"
        curl -fsS "http://localhost:$PUERTO/estado"
        echo
        exit 0
    fi
    INTENTO=$((INTENTO + 1))
    sleep 2
done

echo "ERROR: no responde en el puerto $PUERTO. Mira el registro:"
docker compose logs --tail 40
exit 1
