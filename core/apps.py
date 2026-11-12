from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'
    verbose_name = 'Kandor App'

    def ready(self):
        import core.signals  # noqa: F401

        # Sincronizzazione automatica tabelle se mancanti all'avvio dell'applicazione
        import sys
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv and 'dumpdata' not in sys.argv and 'loaddata' not in sys.argv:
            try:
                from django.db import connection
                from django.core.management import call_command

                tables = connection.introspection.table_names()
                if 'django_session' not in tables or 'core_turno' not in tables or 'core_profiloaccessoportale' not in tables:
                    print("⚠️ Tabelle critiche o nuove assenti. Esecuzione migrazione automatica in ready()...")
                    call_command('migrate', interactive=False)
                    print("   ✅ Migrazione automatica in ready() completata!")

                from django.contrib.auth.models import User
                if not User.objects.filter(username='admin').exists():
                    User.objects.create_superuser('admin', 'admin@kandor.it', 'Kandor2024!')
                    print("   ✅ Superuser 'admin' creato con successo in ready()!")

                from .accessi_service import assicura_profili_accesso_portale
                assicura_profili_accesso_portale()
            except Exception as e:
                print(f"⚠️ Avviso durante verifica tabelle in ready(): {e}")

        # Avvia lo scheduler in background per il promemoria delle 17:00
        import os
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('SERVER_SOFTWARE'):
            try:
                from .scheduler import start_scheduler
                start_scheduler()
            except Exception as e:
                print(f"⚠️ Avviso avvio scheduler: {e}")
