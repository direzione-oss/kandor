FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VPS_PROD=1 \
    PORT=8000 \
    MEDIA_ROOT=/app/media \
    PUBLIC_BASE_URL=https://kandor.187.126.30.207.sslip.io \
    RENDER_EXTERNAL_URL=https://kandor.187.126.30.207.sslip.io \
    DB_SSLMODE=disable

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/media /app/staticfiles && \
    USE_POSTGRES=0 python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "mkdir -p /app/media && python manage.py migrate --noinput && python manage.py createcachetable && python manage.py set_telegram_webhook ${PUBLIC_BASE_URL} && exec gunicorn cleanup_erp.wsgi:application --workers ${GUNICORN_WORKERS:-3} --threads 4 --max-requests 500 --max-requests-jitter 50 --timeout 120 --bind 0.0.0.0:${PORT:-8000}"]
