# Generated for Kandor — Corsi di Formazione e Alert Scadenza 20 gg

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_CORSI = [
    (1, "Corso sicurezza generale"),
    (2, "Corso Specifico Basso Rischio"),
    (3, "Corso Movimentazione manuale carichi"),
    (4, "Corso DPI 3 lavori in quota"),
    (5, "Corso RLS"),
    (6, "Corso preposto"),
    (7, "Corso primo soccorso"),
    (8, "Corso piattaforme mobili con o senza stabilizzatori"),
    (9, "Corso HACCP"),
    (10, "Corso antincendio livello 2"),
]


def seed_default_corsi(apps, schema_editor):
    CorsoFormazione = apps.get_model('core', 'CorsoFormazione')
    CorsoDipendente = apps.get_model('core', 'CorsoDipendente')
    Dipendente = apps.get_model('core', 'Dipendente')

    corsi_objs = []
    for ordine, nome in DEFAULT_CORSI:
        corso, _ = CorsoFormazione.objects.get_or_create(
            nome=nome,
            defaults={'ordine': ordine, 'attivo': True}
        )
        corsi_objs.append(corso)

    for dip in Dipendente.objects.all():
        for corso in corsi_objs:
            CorsoDipendente.objects.get_or_create(
                dipendente=dip,
                corso=corso,
                defaults={'stato': 'NON_PREVISTO'}
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_remove_assegnazioneturno_core_assign_turno_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorsoFormazione',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200, unique=True, verbose_name='Nome Corso')),
                ('descrizione', models.TextField(blank=True, verbose_name='Descrizione / Note')),
                ('ordine', models.PositiveIntegerField(default=100, verbose_name='Ordine')),
                ('attivo', models.BooleanField(default=True, verbose_name='Attivo')),
            ],
            options={
                'verbose_name': 'Corso di Formazione',
                'verbose_name_plural': 'Corsi di Formazione',
                'ordering': ['ordine', 'nome'],
            },
        ),
        migrations.CreateModel(
            name='CorsoDipendente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stato', models.CharField(choices=[('NON_PREVISTO', '— Seleziona (Fatto / Deve essere fatto) —'), ('DA_FARE', '⏳ Deve essere fatto'), ('FATTO', '✅ Fatto')], default='NON_PREVISTO', max_length=20, verbose_name='Stato (Fatto / Deve essere fatto)')),
                ('data_scadenza', models.DateField(blank=True, null=True, verbose_name='Data di Scadenza')),
                ('note', models.CharField(blank=True, max_length=255, verbose_name='Note')),
                ('dipendente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='corsi_formazione', to='core.dipendente', verbose_name='Dipendente')),
                ('corso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dipendenti_iscritti', to='core.corsoformazione', verbose_name='Corso di Formazione')),
            ],
            options={
                'verbose_name': 'Corso di Formazione',
                'verbose_name_plural': '🎓 Corsi di Formazione',
                'ordering': ['corso__ordine', 'corso__nome'],
                'unique_together': {('dipendente', 'corso')},
            },
        ),
        migrations.RunPython(seed_default_corsi, migrations.RunPython.noop),
    ]
