# Generated for Kandor Employee Web App

import random
from django.db import migrations, models


def populate_pin_accesso(apps, schema_editor):
    Dipendente = apps.get_model('core', 'Dipendente')
    for dip in Dipendente.objects.all():
        if not dip.pin_accesso or len(dip.pin_accesso.strip()) != 4:
            dip.pin_accesso = f"{random.randint(1000, 9999)}"
            dip.save(update_fields=['pin_accesso'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_mezzo_numero_permesso_citta_alta'),
    ]

    operations = [
        migrations.AddField(
            model_name='dipendente',
            name='pin_accesso',
            field=models.CharField(
                blank=True,
                default='',
                help_text="PIN numerico di 4 cifre per l'accesso alla Web App Dipendenti (generato in automatico se lasciato vuoto)",
                max_length=4,
                verbose_name='PIN Accesso App (4 cifre)',
            ),
        ),
        migrations.AlterField(
            model_name='timetracking',
            name='source',
            field=models.CharField(
                choices=[
                    ('MANUAL', 'Manuale'),
                    ('TELEGRAM', 'Telegram'),
                    ('WHATSAPP', 'WhatsApp'),
                    ('WEBAPP', 'Web App'),
                ],
                default='MANUAL',
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_pin_accesso, migrations.RunPython.noop),
    ]
