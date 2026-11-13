from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_cinque_migliorie_erp'),
    ]

    operations = [
        migrations.CreateModel(
            name='TelegramConversationState',
            fields=[
                ('chat_id', models.CharField(max_length=64, primary_key=True, serialize=False, verbose_name='Telegram Chat ID')),
                ('state_data', models.JSONField(blank=True, default=dict, verbose_name='Dati Stato Conversazione')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ultimo Aggiornamento')),
            ],
            options={
                'verbose_name': 'Stato Conversazione Telegram',
                'verbose_name_plural': 'Stati Conversazione Telegram',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SchedulerExecutionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_name', models.CharField(max_length=100, verbose_name='Nome Job Schedulato')),
                ('execution_date', models.DateField(verbose_name='Data Esecuzione')),
                ('executed_at', models.DateTimeField(auto_now_add=True, verbose_name='Timestamp Esecuzione')),
                ('worker_pid', models.IntegerField(blank=True, null=True, verbose_name='PID Worker')),
                ('details', models.JSONField(blank=True, default=dict, verbose_name='Esito / Dettagli')),
            ],
            options={
                'verbose_name': 'Log Esecuzione Scheduler',
                'verbose_name_plural': 'Log Esecuzioni Scheduler',
                'ordering': ['-execution_date', '-executed_at'],
                'unique_together': {('job_name', 'execution_date')},
            },
        ),
    ]
