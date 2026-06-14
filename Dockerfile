# Yaride backend: бот + Mini App API (+ админка через start_prod.py).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY admin/ admin/
COPY webapp_api/ webapp_api/
COPY main.py .
COPY scripts/start_prod.py scripts/start_prod.py

RUN mkdir -p /data

ENV DB_PATH=/data/yaride.db

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + (__import__('os').getenv('PORT') or __import__('os').getenv('WEBAPP_PORT') or '8080') + '/health', timeout=3)"

CMD ["python", "scripts/start_prod.py"]
