from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_remove_assegnazioneturno_core_assign_turno_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='assenza',
                    name='ora_inizio',
                    field=models.TimeField(blank=True, null=True, verbose_name='Ora Inizio'),
                ),
                migrations.AddField(
                    model_name='assenza',
                    name='ora_fine',
                    field=models.TimeField(blank=True, null=True, verbose_name='Ora Fine'),
                ),
            ],
            database_operations=[]
        ),
        migrations.AddField(
            model_name='assenza',
            name='stato_approvazione',
            field=models.CharField(
                choices=[
                    ('IN_ATTESA', 'In Attesa Avvallo Amministrazione'),
                    ('APPROVATA', 'Approvata (Avvallata)'),
                    ('RIFIUTATA', "Rifiutata dall'Amministrazione")
                ],
                default='IN_ATTESA',
                max_length=20,
                verbose_name='Stato Avvallo Amministrazione'
            ),
        ),
        migrations.AddField(
            model_name='assenza',
            name='approvata_da_admin_il',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Avvallata il'),
        ),
    ]
