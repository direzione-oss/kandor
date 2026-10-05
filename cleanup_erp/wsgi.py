"""
WSGI config for cleanup_erp project.
Exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')

application = get_wsgi_application()

# Auto-esecuzione migrazioni database e reset admin all'avvio del server (essenziale su Render epimero)
try:
    from django.core.management import call_command
    print("==> Esecuzione automatica migrazioni database all'avvio WSGI...")
    call_command('migrate', interactive=False)
    
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@kandor.it', 'Kandor2024!')
        print("   ✅ Superuser 'admin' creato con successo!")
    else:
        u = User.objects.get(username='admin')
        u.set_password('Kandor2024!')
        u.save()
        print("   ✅ Password 'admin' resettata con successo!")
except Exception as e:
    print(f"⚠️ Avviso durante migrazione WSGI: {e}")
