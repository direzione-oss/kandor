"""Script di build per Render - esegue collectstatic, migrate e crea superuser."""
import subprocess
import sys

commands = [
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    [sys.executable, "manage.py", "collectstatic", "--no-input"],
    [sys.executable, "manage.py", "migrate", "--no-input"],
]

for cmd in commands:
    print(f"\n==> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"❌ ERRORE: comando '{' '.join(cmd)}' fallito con codice {result.returncode}")
        sys.exit(result.returncode)

# Crea superuser admin se non esiste
print("\n==> Creazione superuser admin...")
try:
    import os, django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')
    django.setup()
    from django.contrib.auth.models import User
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@kandor.it', 'Kandor2024!')
        print("   ✅ Superuser 'admin' creato con successo!")
    else:
        u = User.objects.get(username='admin')
        u.set_password('Kandor2024!')
        u.save()
        print("   ✅ Password del superuser 'admin' aggiornata con successo!")
except Exception as e:
    print(f"   ⚠️ Nota durante aggiornamento superuser: {e}")

print("\n==> Build completato con successo!")
sys.exit(0)
