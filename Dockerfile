FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/cotizador.db

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2,<27" "setuptools>=84.1,<85" \
    && python -m pip install --no-cache-dir -r requirements.txt
COPY . .

RUN groupadd --system --gid 10001 cotizador \
    && useradd --system --uid 10001 --gid 10001 --home-dir /home/cotizador --create-home cotizador \
    && mkdir -p /data \
    && chown -R 10001:10001 /data /home/cotizador

ENV HOME=/home/cotizador
USER 10001:10001

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
