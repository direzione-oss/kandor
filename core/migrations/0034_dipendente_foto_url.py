from django.db import migrations


def forward(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'foto_url' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto_url varchar(500) NULL;"
                )
        else:
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;"
            )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_dipendente_foto'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
