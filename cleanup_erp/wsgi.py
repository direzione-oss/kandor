"""
WSGI config for cleanup_erp project.
Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')
django.setup()

# Sincronizzazione atomica del DB prima dell'inizializzazione del gestore WSGI
try:
    from django.core.management import call_command
    from django.db import connection
    
    tables = connection.introspection.table_names()
    if 'django_session' not in tables:
        print("==> Esecuzione migrazioni essenziali prima di abilitare le richieste HTTP...")
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
    print(f"⚠️ Errore durante sincronizzazione DB su WSGI: {e}")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
