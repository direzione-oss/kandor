from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_messaggiochat_foto_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='timetracking',
            name='ore_dichiarate',
            field=models.DecimalField(
                blank=True, decimal_places=1, help_text='Ore inserite dal dipendente',
                max_digits=4, null=True, verbose_name='Ore Dichiarate'
            ),
        ),
    ]
