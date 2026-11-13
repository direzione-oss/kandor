from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_telegram_state_and_scheduler_lock'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='turno',
            index=models.Index(fields=['data', 'squadra'], name='core_turno_data_sq_idx'),
        ),
        migrations.AddIndex(
            model_name='assegnazioneturno',
            index=models.Index(fields=['turno', 'cliente'], name='core_assign_turno_cli_idx'),
        ),
        migrations.AddIndex(
            model_name='timetracking',
            index=models.Index(fields=['dipendente', 'assegnazione'], name='core_tt_dip_assign_idx'),
        ),
        migrations.AddIndex(
            model_name='timetracking',
            index=models.Index(fields=['assegnazione', 'is_validated'], name='core_tt_assign_val_idx'),
        ),
    ]
