from django.db import migrations, models


def apply_safely(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'data_ultima_visita_medica' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN data_ultima_visita_medica date NULL;")
            if 'is_part_time' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN is_part_time integer NOT NULL DEFAULT 0;")
            if 'ore_settimanali_part_time' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN ore_settimanali_part_time numeric(4, 1) NULL;")
        else:
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS data_ultima_visita_medica date NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS is_part_time boolean NOT NULL DEFAULT false;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS ore_settimanali_part_time numeric(4, 1) NULL;")


def reverse_safely(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0043_add_tirocinio_data_assunzione_licenziamento'),
    ]

    operations = [
        migrations.RunPython(apply_safely, reverse_safely),
    ]
