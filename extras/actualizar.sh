#!/bin/sh
# ==============================================================================
# actualizar.sh — pone VidalWear al día en el NAS desde GitHub
# ==============================================================================
#   sh /share/homes/adrian/scripts/actualizar-vidalwear.sh          (rama main)
#   sh /share/homes/adrian/scripts/actualizar-vidalwear.sh otra-rama
#
# En el shell del QNAP no hay git: se baja el paquete del repositorio y se
# cambia la carpeta de sitio. Se respetan SIEMPRE el .env y la carpeta datos/
# (base de datos y fotos). La versión anterior queda en vidalwear.anterior.
#
# Vive FUERA de la carpeta que reemplaza: si no, se borraría a sí mismo.
# ==============================================================================
set -e

REPO=https://github.com/AdrianVidal89/VidalWear
RAMA="${1:-main}"
APPS="${VIDALWEAR_APPS:-/share/homes/adrian/apps}"
DESTINO="$APPS/vidalwear"
NUEVO="$APPS/.vidalwear-nuevo"
ANTERIOR="$APPS/vidalwear.anterior"
PAQUETE="$APPS/.vidalwear.tgz"

PATH="/share/CACHEDEV1_DATA/.qpkg/container-station/bin:$PATH"
export PATH
DOCKER_CONFIG=/tmp/dockercfg
export DOCKER_CONFIG

aviso() { echo "[$(date '+%H:%M:%S')] $1"; }

[ -d "$DESTINO" ] || { echo "ERROR: no existe $DESTINO"; exit 1; }
[ -f "$DESTINO/.env" ] || { echo "ERROR: falta $DESTINO/.env"; exit 1; }

aviso "Descargando la rama $RAMA…"
rm -rf "$NUEVO" "$PAQUETE" "$APPS/VidalWear-$RAMA"
curl -fsSL "$REPO/archive/refs/heads/$RAMA.tar.gz" -o "$PAQUETE"
tar xzf "$PAQUETE" -C "$APPS"
rm -f "$PAQUETE"
mv "$APPS/VidalWear-$RAMA" "$NUEVO"

[ -f "$NUEVO/servidor.py" ] || { echo "ERROR: la descarga no es válida"; rm -rf "$NUEVO"; exit 1; }
[ -f "$NUEVO/docker-compose.yml" ] || { echo "ERROR: la descarga no es válida"; rm -rf "$NUEVO"; exit 1; }

aviso "Conservando la configuración y los datos…"
cp -p "$DESTINO/.env" "$NUEVO/.env"

aviso "Parando VidalWear…"
cd "$DESTINO"
docker compose down || true
if [ -d "$DESTINO/datos" ]; then
    mv "$DESTINO/datos" "$NUEVO/datos"
fi

aviso "Cambiando de versión…"
cd "$APPS"
rm -rf "$ANTERIOR"
mv "$DESTINO" "$ANTERIOR"
mv "$NUEVO" "$DESTINO"

aviso "Construyendo y levantando…"
cd "$DESTINO"
sh deploy.sh
