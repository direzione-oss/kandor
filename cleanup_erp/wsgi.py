"""
WSGI config for cleanup_erp project.
Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')
django.setup()

# Sincronizzazione automatica del DB prima dell'inizializzazione del gestore WSGI
from django.core.management import call_command
from django.db import connection, connections, DEFAULT_DB_ALIAS

try:
    print("==> Tentativo migrazione su DB principale...")
    call_command('migrate', interactive=False)
except Exception as main_db_err:
    print(f"⚠️ Impossibile completare le migrazioni sul DB principale ({main_db_err}). Switching automatico a SQLite locale...")
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': settings.BASE_DIR / 'db_local.sqlite3',
        'OPTIONS': {
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
            'timeout': 30,
        },
        'CONN_MAX_AGE': 0,
    }
    connections[DEFAULT_DB_ALIAS].close()
    try:
        call_command('migrate', interactive=False)
        print("   ✅ Migrazione SQLite locale completata con successo!")
    except Exception as sqlite_err:
        print(f"❌ Errore migrazione SQLite: {sqlite_err}")

try:
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@kandor.it', 'Kandor2024!')
        print("   ✅ Superuser 'admin' creato con successo!")
    else:
        u = User.objects.get(username='admin')
        u.set_password('Kandor2024!')
        u.save()
        print("   ✅ Password 'admin' sincronizzata con successo!")
except Exception as user_err:
    print(f"⚠️ Errore creazione superuser: {user_err}")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
