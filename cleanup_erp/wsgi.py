"""
WSGI config for cleanup_erp project.
Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')
django.setup()

# Auto-esecuzione migrazioni database e reset admin all'avvio del server WSGI
from django.core.management import call_command

print("==> Esecuzione automatica migrazioni database all'avvio WSGI...")
try:
    call_command('migrate', interactive=False)
    print("   ✅ Migrazioni database completate con successo!")
except Exception as e:
    print(f"⚠️ Avviso durante migrazione WSGI: {e}")

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
except Exception as e:
    print(f"⚠️ Errore gestione superuser WSGI: {e}")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
