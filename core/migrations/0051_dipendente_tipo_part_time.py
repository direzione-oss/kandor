# Generated for Kandor — Synchronize state and add tipo_part_time to Dipendente

from django.db import migrations, models


def apply_safely(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'tipo_part_time' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN tipo_part_time varchar(1) NULL;")
            if 'is_part_time' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN is_part_time integer NOT NULL DEFAULT 0;")
            if 'ore_settimanali_part_time' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN ore_settimanali_part_time numeric(4, 1) NULL;")
            if 'data_ultima_visita_medica' not in cols:
                cursor.execute("ALTER TABLE core_dipendente ADD COLUMN data_ultima_visita_medica date NULL;")
            cursor.execute("PRAGMA table_info(core_mezzo);")
            m_cols = [r[1] for r in cursor.fetchall()]
            if 'scadenza_revisione' not in m_cols:
                cursor.execute("ALTER TABLE core_mezzo ADD COLUMN scadenza_revisione date NULL;")
        else:
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS tipo_part_time varchar(1) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS is_part_time boolean NOT NULL DEFAULT false;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS ore_settimanali_part_time numeric(4, 1) NULL;")
            cursor.execute("ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS data_ultima_visita_medica date NULL;")
            cursor.execute("ALTER TABLE core_mezzo ADD COLUMN IF NOT EXISTS scadenza_revisione date NULL;")


def reverse_safely(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0050_remove_assegnazioneturno_core_assign_turno_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(apply_safely, reverse_safely),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='dipendente',
                    name='is_part_time',
                    field=models.BooleanField(default=False, verbose_name='Contratto Part-Time'),
                ),
                migrations.AddField(
                    model_name='dipendente',
                    name='ore_settimanali_part_time',
                    field=models.DecimalField(
                        blank=True, decimal_places=1, help_text='Facoltativo', max_digits=4, null=True, verbose_name='Ore Settimanali (Part-Time)'
                    ),
                ),
                migrations.AddField(
                    model_name='dipendente',
                    name='tipo_part_time',
                    field=models.CharField(
                        blank=True,
                        choices=[('M', 'M - Misto'), ('V', 'V - Verticale'), ('O', 'O - Orizzontale')],
                        help_text='Selezionare M (Misto), V (Verticale) o O (Orizzontale)',
                        max_length=1,
                        null=True,
                        verbose_name='Tipo Part-Time'
                    ),
                ),
                migrations.AddField(
                    model_name='dipendente',
                    name='data_ultima_visita_medica',
                    field=models.DateField(blank=True, null=True, verbose_name='Prossima scadenza visita medica'),
                ),
                migrations.AddField(
                    model_name='mezzo',
                    name='scadenza_revisione',
                    field=models.DateField(blank=True, null=True, verbose_name='Scadenza Revisione'),
                ),
            ]
        ),
    ]
