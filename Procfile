web: python manage.py migrate --no-input && gunicorn cleanup_erp.wsgi --workers 1 --threads 1 --max-requests 100 --max-requests-jitter 10 --timeout 120 --bind 0.0.0.0:$PORT
