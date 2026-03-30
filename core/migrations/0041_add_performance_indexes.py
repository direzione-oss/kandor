from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Aggiunge indici DB sulle colonne più usate nelle query critiche:
    - Turno.data       → filtraggio per settimana nel calendario
    - TimeTracking.*   → feed telegram e verifica ore
    - Assenza.*        → feed telegram e reports
    - Segnalazione.*   → feed telegram
    """

    dependencies = [
        ('core', '0040_assegnazioneturno_dipendenti_esclusi'),
    ]

    operations = [
        # Turno.data — interrogato su ogni caricamento del calendario
        migrations.AddIndex(
            model_name='turno',
            index=models.Index(fields=['data'], name='core_turno_data_idx'),
        ),
        # Turno.(data, squadra) — filtro combinato frequente
        migrations.AddIndex(
            model_name='turno',
            index=models.Index(fields=['data', 'squadra'], name='core_turno_data_squadra_idx'),
        ),
        # TimeTracking.source — filtraggio TELEGRAM nel feed
        migrations.AddIndex(
            model_name='timetracking',
            index=models.Index(fields=['source'], name='core_tt_source_idx'),
        ),
        # TimeTracking.check_out — ordinamento nel feed
        migrations.AddIndex(
            model_name='timetracking',
            index=models.Index(fields=['-check_out'], name='core_tt_checkout_idx'),
        ),
        # TimeTracking.is_validated — filtraggio validazioni
        migrations.AddIndex(
            model_name='timetracking',
            index=models.Index(fields=['is_validated'], name='core_tt_validated_idx'),
        ),
        # Assenza.source + created_at — feed telegram
        migrations.AddIndex(
            model_name='assenza',
            index=models.Index(fields=['source', '-created_at'], name='core_assenza_source_idx'),
        ),
        # Segnalazione.data_inserimento — ordinamento feed
        migrations.AddIndex(
            model_name='segnalazione',
            index=models.Index(fields=['-data_inserimento'], name='core_segn_data_idx'),
        ),
        # AssegnazioneTurno.turno — lookup per turno_data
        migrations.AddIndex(
            model_name='assegnazioneturno',
            index=models.Index(fields=['turno'], name='core_assign_turno_idx'),
        ),
    ]
