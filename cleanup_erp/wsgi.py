"""
WSGI config for cleanup_erp project.
Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')
django.setup()

# Sincronizzazione automatica del DB prima dell'inizializzazione del gestore WSGI
try:
    from django.core.management import call_command
    from django.db import connection, connections, DEFAULT_DB_ALIAS
    
    # Verificazione e fallback automatico se la connessione al DB primario fallisce
    try:
        connection.ensure_connection()
    except Exception as db_err:
        print(f"⚠️ Impossibile connettersi al DB primario ({db_err}), fallback a SQLite locale...")
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

    print("==> Esecuzione migrazioni database su WSGI...")
    call_command('migrate', interactive=False)
    
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@kandor.it', 'Kandor2024!')
        print("   ✅ Superuser 'admin' creato con successo!")
    else:
        u = User.objects.get(username='admin')
        u.set_password('Kandor2024!')
        u.save()
        print("   ✅ Password 'admin' sincronizzata con successo!")
except Exception as e:
    print(f"❌ Errore durante sincronizzazione DB su WSGI: {e}")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
