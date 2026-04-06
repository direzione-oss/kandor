"""
Resetta le sequenze PostgreSQL dopo un loaddata che inserisce PKs espliciti.
Necessario altrimenti i nuovi INSERT falliscono per duplicate key.
"""
import django, os, sys
sys.path.insert(0, r'C:\Users\serra\.gemini\antigravity\playground\phantom-ionosphere')
os.environ['DJANGO_SETTINGS_MODULE'] = 'cleanup_erp.settings'
os.environ['PYTHONUTF8'] = '1'
os.environ['SUPABASE_DB_PORT'] = '5432'
os.environ['PGOPTIONS'] = '-c statement_timeout=0'
django.setup()

from django.db import connection
from django.apps import apps

# Tabelle da controllare
tables = [
    'core_turno',
    'core_assegnazioneturno',
    'core_dipendente',
    'core_cliente',
    'core_squadra',
    'core_qualifica',
    'core_mezzo',
    'core_programmazionericorrente',
    'core_assenza',
    'core_timetracking',
    'core_responsabilearea',
    'core_richiestasostituzone',
    'core_messaggioprogrammato',
]

with connection.cursor() as c:
    for table in tables:
        try:
            # Trova la sequenza associata alla colonna id
            c.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                    false
                );
            """)
            c.execute(f"SELECT MAX(id) FROM {table}")
            max_id = c.fetchone()[0]
            print(f"✅ {table}: sequenza resettata (max id = {max_id})")
        except Exception as e:
            print(f"⚠️  {table}: {e}")

print("\nDone.")
