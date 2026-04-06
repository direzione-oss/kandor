"""
Fast importer v2: usa bulk_create con FK come _id per evitare
l'errore "Cannot assign int: must be instance".
"""
import os, sys, json

sys.path.insert(0, r'C:\Users\serra\.gemini\antigravity\playground\phantom-ionosphere')
os.environ['DJANGO_SETTINGS_MODULE'] = 'cleanup_erp.settings'
os.environ['PYTHONUTF8'] = '1'
os.environ['SUPABASE_DB_PORT'] = '5432'
os.environ['SKIP_GEOCODING'] = '1'
os.environ.pop('LOCAL_DEV', None)

import django
django.setup()

from django.db import connection
assert connection.vendor == 'postgresql', f"ERRORE: connesso a {connection.vendor}!"
print(f"✅ Connesso a: PostgreSQL (Supabase)")

fixture_path = r'C:\Users\serra\.gemini\antigravity\playground\phantom-ionosphere\db_push_clean.json'
with open(fixture_path, encoding='utf-8') as f:
    fixtures = json.load(f)
print(f"📦 Oggetti nel file: {len(fixtures)}")

from collections import defaultdict
from django.apps import apps

by_model = defaultdict(list)
for obj in fixtures:
    by_model[obj['model']].append(obj)

MODEL_ORDER = [
    'core.qualifica',
    'core.mezzo',
    'core.dipendente',
    'core.squadra',
    'core.cliente',
    'core.programmazionericorrente',
    'core.richiestastraordinaria',
    'core.turno',
    'core.assegnazioneturno',
    'core.assenza',
    'core.timetracking',
    'core.responsabilearea',
    'core.richiestasostituzione',
    'core.messaggiochat',
    'core.segnalazione',
    'core.proximitylog',
    'core.titolare',
    'core.messaggioprogrammato',
]

def get_fk_fields(ModelClass):
    """Restituisce un set di nomi di campi FK."""
    fk_fields = set()
    m2m_fields = set()
    for field in ModelClass._meta.get_fields():
        if hasattr(field, 'many_to_many') and field.many_to_many:
            m2m_fields.add(field.name)
        elif hasattr(field, 'column') and hasattr(field, 'related_model') and field.related_model:
            # È un FK
            fk_fields.add(field.name)
    return fk_fields, m2m_fields

total = 0
errors = []

for model_label in MODEL_ORDER:
    records = by_model.get(model_label, [])
    if not records:
        continue

    try:
        ModelClass = apps.get_model(*model_label.split('.'))
        fk_names, m2m_names = get_fk_fields(ModelClass)

        instances = []
        all_m2m = []

        for rec in records:
            fields = rec['fields']
            kwargs = {'pk': rec['pk']}
            rec_m2m = {}

            for k, v in fields.items():
                if k in m2m_names:
                    rec_m2m[k] = v
                elif k in fk_names and v is not None:
                    # FK: usa _id per passare il PK direttamente
                    kwargs[f'{k}_id'] = v
                else:
                    kwargs[k] = v

            instances.append((ModelClass(**kwargs), rec_m2m))

        objs = [i[0] for i in instances]
        created = ModelClass.objects.bulk_create(objs, ignore_conflicts=True)
        count_ok = len(created)
        print(f"  ✅ {model_label}: {count_ok}/{len(objs)} inseriti")
        total += count_ok

        # Gestisci M2M (dopo l'inserimento)
        for obj, m2m_data in instances:
            for field_name, pks in m2m_data.items():
                if pks:
                    try:
                        getattr(obj, field_name).set(pks)
                    except Exception:
                        pass

    except Exception as e:
        print(f"  ❌ {model_label}: {e}")
        errors.append((model_label, str(e)))

# Modelli non coperti
for model_label in by_model:
    if model_label not in MODEL_ORDER:
        print(f"  ⚠️  {model_label}: {len(by_model[model_label])} record saltati (non in lista)")

print(f"\n{'='*50}")
print(f"✅ Totale inseriti: {total}")
if errors:
    print(f"❌ Errori: {len(errors)}")
    for m, e in errors:
        print(f"   {m}: {e[:120]}")

# Reset sequenze PostgreSQL
print("\n📍 Reset sequenze PostgreSQL...")
tables = [
    'core_turno', 'core_assegnazioneturno', 'core_dipendente', 'core_cliente',
    'core_squadra', 'core_qualifica', 'core_mezzo', 'core_programmazionericorrente',
    'core_assenza', 'core_timetracking', 'core_responsabilearea', 'core_messaggioprogrammato',
]
with connection.cursor() as c:
    for table in tables:
        try:
            c.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1), true
                );
            """)
        except Exception as e:
            print(f"  ⚠️  {table}: {e}")
print("✅ Sequenze aggiornate.")
print("\n🎉 Import completato!")
