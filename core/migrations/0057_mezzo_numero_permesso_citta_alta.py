# Safe migration for adding numero_permesso_citta_alta to Mezzo

from django.db import migrations, models


def apply_safely(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_mezzo);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'numero_permesso_citta_alta' not in cols:
                cursor.execute("ALTER TABLE core_mezzo ADD COLUMN numero_permesso_citta_alta varchar(50) NULL;")
        else:
            cursor.execute("ALTER TABLE core_mezzo ADD COLUMN IF NOT EXISTS numero_permesso_citta_alta varchar(50) NULL;")


def reverse_safely(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0056_messaggiochat_allegato_nome_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(apply_safely, reverse_safely),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='mezzo',
                    name='numero_permesso_citta_alta',
                    field=models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        verbose_name='Numero Permesso Città Alta (Bergamo)'
                    ),
                ),
            ]
        )
    ]
