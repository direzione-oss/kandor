from django.db import migrations


def swap_nome_cognome(apps, schema_editor):
    """Inverte nome e cognome per tutti i dipendenti (fix import errato)."""
    Dipendente = apps.get_model('core', 'Dipendente')
    for dip in Dipendente.objects.all():
        dip.nome, dip.cognome = dip.cognome, dip.nome
        dip.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_riceve_notifiche_messaggi'),
    ]

    operations = [
        migrations.RunPython(swap_nome_cognome, migrations.RunPython.noop),
    ]
