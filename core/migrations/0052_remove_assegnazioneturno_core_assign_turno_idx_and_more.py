# Safe migration for Kandor database state sync

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
            if 'usufruisce_104' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN usufruisce_104 integer NOT NULL DEFAULT 0;")

            cursor.execute("PRAGMA table_info(core_modificacedolino);")
            m_cols = [r[1] for r in cursor.fetchall()]
            if 'giorni_104_override' not in m_cols:
                cursor.execute("ALTER TABLE core_modificacedolino ADD COLUMN giorni_104_override integer NULL;")
        else:
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS data_assunzione date NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS data_licenziamento date NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_profilo_url varchar(500) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS usufruisce_104 boolean NOT NULL DEFAULT false;")
            cursor.execute("ALTER TABLE core_modificacedolino ADD COLUMN IF NOT EXISTS giorni_104_override integer NULL;")


def reverse_safely(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0051_dipendente_tipo_part_time'),
    ]

    state_ops = [
        migrations.RemoveIndex(
            model_name='assegnazioneturno',
            name='core_assign_turno_idx',
        ),
        migrations.RemoveIndex(
            model_name='assenza',
            name='core_assenza_source_idx',
        ),
        migrations.RemoveIndex(
            model_name='segnalazione',
            name='core_segn_data_idx',
        ),
        migrations.RemoveIndex(
            model_name='timetracking',
            name='core_tt_source_idx',
        ),
        migrations.RemoveIndex(
            model_name='timetracking',
            name='core_tt_checkout_idx',
        ),
        migrations.RemoveIndex(
            model_name='timetracking',
            name='core_tt_validated_idx',
        ),
        migrations.RemoveIndex(
            model_name='turno',
            name='core_turno_data_idx',
        ),
        migrations.RemoveIndex(
            model_name='turno',
            name='core_turno_data_squadra_idx',
        ),
        migrations.RemoveField(
            model_name='mezzo',
            name='scadenza_bollo',
        ),
        migrations.AddField(
            model_name='dipendente',
            name='data_assunzione',
            field=models.DateField(blank=True, null=True, verbose_name='Data di Assunzione'),
        ),
        migrations.AddField(
            model_name='dipendente',
            name='data_licenziamento',
            field=models.DateField(blank=True, null=True, verbose_name='Data di Licenziamento'),
        ),
        migrations.AddField(
            model_name='dipendente',
            name='foto',
            field=models.ImageField(blank=True, null=True, upload_to='foto_dipendenti/', verbose_name='Foto Profilo'),
        ),
        migrations.AddField(
            model_name='dipendente',
            name='foto_profilo_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL Foto Profilo (Telegram/Supabase)'),
        ),
        migrations.AddField(
            model_name='dipendente',
            name='foto_url',
            field=models.URLField(blank=True, max_length=500, null=True, verbose_name='URL Foto (Supabase)'),
        ),
        migrations.AddField(
            model_name='dipendente',
            name='usufruisce_104',
            field=models.BooleanField(default=False, help_text='Se attivo, abilita la richiesta e il calcolo dei permessi Legge 104 per questo dipendente', verbose_name='Usufruisce della Legge 104'),
        ),
        migrations.AddField(
            model_name='modificacedolino',
            name='giorni_104_override',
            field=models.IntegerField(blank=True, null=True, verbose_name='Giorni 104 Rettificati'),
        ),
        migrations.AlterField(
            model_name='dipendente',
            name='riceve_notifiche_messaggi',
            field=models.BooleanField(default=False, help_text="Se attivo e l'utente ricopre un ruolo di Responsabile/Titolare, riceve una notifica Telegram quando un dipendente invia un messaggio.", verbose_name='Riceve notifiche messaggi (Solo Responsabili)'),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(apply_safely, reverse_safely),
            ],
            state_operations=state_ops
        )
    ]
