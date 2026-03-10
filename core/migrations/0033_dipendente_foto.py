from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_swap_nome_cognome'),
    ]

    operations = [
        # Rimuovi riceve_notifiche_messaggi solo se esiste
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS riceve_notifiche_messaggi;",
            reverse_sql="ALTER TABLE core_dipendente ADD COLUMN riceve_notifiche_messaggi boolean NOT NULL DEFAULT true;",
        ),
        # Aggiungi foto solo se non esiste già (Render aveva già questa colonna da migrazione precedente)
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;",
            reverse_sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS foto;",
        ),
        # Nota: il modello Titolare viene gestito dalla migrazione 0036
    ]
