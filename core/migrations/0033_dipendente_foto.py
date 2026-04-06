from django.db import migrations


def forward(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            # DROP riceve_notifiche_messaggi se esiste
            if 'riceve_notifiche_messaggi' in cols:
                try:
                    cursor.execute(
                        "ALTER TABLE core_dipendente DROP COLUMN riceve_notifiche_messaggi;"
                    )
                except Exception:
                    pass  # SQLite < 3.35 non supporta DROP COLUMN, ignoriamo
            # ADD foto se non esiste
            if 'foto' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto varchar(100) NULL;"
                )
        else:
            # PostgreSQL
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "DROP COLUMN IF EXISTS riceve_notifiche_messaggi;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;"
            )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_swap_nome_cognome'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
