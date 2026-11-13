from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_performance_indexes_n1_cleanup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assegnazioneturno',
            name='ore_previste_contratto',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Ore contrattuali previste per questo turno. Possono differire dalla durata orario inizio-fine.',
                max_digits=6,
                null=True,
                verbose_name='Ore previste (contratto)',
            ),
        ),
        migrations.AlterField(
            model_name='modificacedolino',
            name='ore_lavorate_override',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=6,
                null=True,
                verbose_name='Ore Totali Rettificate',
            ),
        ),
        migrations.AlterField(
            model_name='modificacedolino',
            name='ore_validate_override',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=6,
                null=True,
                verbose_name='Ore Validate Rettificate',
            ),
        ),
        migrations.CreateModel(
            name='StoricoContrattoCliente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valido_dal', models.DateField(verbose_name='Valido Dal')),
                ('valido_al', models.DateField(blank=True, help_text='Lasciare vuoto se è il contratto attualmente in vigore', null=True, verbose_name='Valido Fino Al')),
                ('ore_mensili_contratto', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Ore Mensili Contratto')),
                ('importo_mensile_contratto', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Importo Mensile Contratto (€)')),
                ('note_variazione', models.CharField(blank=True, default='', max_length=255, verbose_name='Note Variazione / Adeguamento')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='storico_contratti', to='core.cliente', verbose_name='Cliente')),
            ],
            options={
                'verbose_name': 'Storico Contratto Cliente',
                'verbose_name_plural': 'Storico Contratti Clienti',
                'ordering': ['-valido_dal', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='storicocontrattocliente',
            index=models.Index(fields=['cliente', 'valido_dal', 'valido_al'], name='core_storicocontr_cli_dt_idx'),
        ),
    ]
