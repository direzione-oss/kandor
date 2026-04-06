from django.db import migrations


def forward(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'riceve_notifiche_messaggi' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente "
                    "ADD COLUMN riceve_notifiche_messaggi integer NOT NULL DEFAULT 0;"
                )
            if 'foto' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto varchar(100) NULL;"
                )
            if 'foto_profilo_url' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto_profilo_url varchar(500) NULL;"
                )
            if 'foto_url' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto_url varchar(500) NULL;"
                )
        else:
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS riceve_notifiche_messaggi boolean NOT NULL DEFAULT false;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS foto_profilo_url varchar(500) NULL;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;"
            )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_dipendente_foto_fields'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
