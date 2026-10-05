web: python manage.py migrate --no-input && python build_render.py && gunicorn cleanup_erp.wsgi --workers 1 --threads 2 --timeout 60 --bind 0.0.0.0:$PORT
