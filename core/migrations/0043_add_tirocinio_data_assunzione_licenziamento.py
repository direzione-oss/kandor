from django.db import migrations, models


def apply_safely(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'data_assunzione' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN data_assunzione date NULL;")
            if 'data_licenziamento' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN data_licenziamento date NULL;")
            if 'foto' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN foto varchar(100) NULL;")
            if 'foto_profilo_url' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN foto_profilo_url varchar(500) NULL;")
            if 'foto_url' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN foto_url varchar(500) NULL;")
        else:
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS data_assunzione date NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS data_licenziamento date NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_profilo_url varchar(500) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;")

        indexes = [
            'core_assign_turno_idx',
            'core_assenza_source_idx',
            'core_segn_data_idx',
            'core_tt_source_idx',
            'core_tt_checkout_idx',
            'core_tt_validated_idx',
            'core_turno_data_idx',
            'core_turno_data_squadra_idx',
        ]
        for idx in indexes:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {idx};")
            except Exception:
                pass


def reverse_safely(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0042_converti_turni_ricorrenti'),
    ]

    operations = [
        migrations.RunPython(apply_safely, reverse_safely),
        migrations.AlterField(
            model_name='dipendente',
            name='riceve_notifiche_messaggi',
            field=models.BooleanField(default=False, help_text='Se attivo, questo dipendente/referente riceve una notifica Telegram quando arriva un messaggio nel Centro Messaggi', verbose_name='Riceve notifiche messaggi'),
        ),
        migrations.AlterField(
            model_name='dipendente',
            name='stato',
            field=models.CharField(choices=[('ATTIVO', 'Attivo'), ('TIROCINIO', 'Tirocinio'), ('MALATTIA', 'In Malattia'), ('FERIE', 'In Ferie'), ('PERMESSO', 'In Permesso'), ('104', 'Legge 104'), ('INATTIVO', 'Licenziato/Inattivo')], default='ATTIVO', max_length=20),
        ),
    ]
