from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0058_dipendente_pin_accesso'),
    ]

    operations = [
        migrations.AlterField(
            model_name='richiestasostituzione',
            name='stato',
            field=models.CharField(
                choices=[
                    ('APERTA', 'Aperta'),
                    ('APPROVATA_RA', 'Approvata dal Responsabile'),
                    ('INVIATA', 'Inviata al Sostituto'),
                    ('ACCETTATA', 'Accettata'),
                    ('RIFIUTATA', 'Rifiutata'),
                    ('SCADUTA', 'Scaduta (timeout 1h)'),
                    ('COMPLETATA', 'Completata'),
                    ('ANNULLATA', 'Annullata'),
                    ('NON_SOSTITUITO', 'Non Sostituito (Salto Turno)'),
                ],
                default='APERTA',
                max_length=20,
            ),
        ),
    ]
