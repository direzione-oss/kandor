"""
Stub migration: questa migrazione era stata applicata su Render ma il file
era stato eliminato per errore. Reinserita come stub vuoto per mantenere
la compatibilità della catena migrazioni.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_riceve_notifiche_messaggi'),
    ]

    operations = [
        # Stub: operazioni già applicate manualmente o tramite RunSQL in 0033
    ]
