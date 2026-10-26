# VidalWear para el NAS: Python pequeño, sin nada más. El trabajo pesado
# (quitar el fondo de las fotos) lo hace el portátil, no el NAS.
FROM python:3.12-slim-bookworm

ENV MALLOC_ARENA_MAX=2 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY vidalwear/ ./vidalwear/
COPY servidor.py LEEME.md ./

ENV VIDALWEAR_DATOS=/datos \
    VIDALWEAR_PUERTO=8085

EXPOSE 8085
CMD ["python", "servidor.py"]
