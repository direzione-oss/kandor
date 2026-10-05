from django.db import migrations, models


def apply_safely(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_assenza);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'ora_inizio' not in cols:
                cursor.execute("ALTER TABLE core_assenza ADD COLUMN ora_inizio time NULL;")
            if 'ora_fine' not in cols:
                cursor.execute("ALTER TABLE core_assenza ADD COLUMN ora_fine time NULL;")
        else:
            cursor.execute("ALTER TABLE core_assenza ADD COLUMN IF NOT EXISTS ora_inizio time NULL;")
            cursor.execute("ALTER TABLE core_assenza ADD COLUMN IF NOT EXISTS ora_fine time NULL;")


def reverse_safely(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0044_add_part_time_visita_medica'),
    ]

    operations = [
        migrations.RunPython(apply_safely, reverse_safely),
    ]
