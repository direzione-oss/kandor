# Generated for Kandor — Preserve past shifts when a Squadra is deleted

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_modificacedolino_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='turno',
            name='squadra',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.squadra', verbose_name='Squadra Assegnata'),
        ),
    ]
