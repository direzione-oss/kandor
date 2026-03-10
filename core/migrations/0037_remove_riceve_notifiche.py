from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_dipendente_foto_fields'),
    ]

    operations = [
        # Rimuovi riceve_notifiche_messaggi se esiste ancora (già rimossa in 0033 su prod, ma non su dev)
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS riceve_notifiche_messaggi;",
            reverse_sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS riceve_notifiche_messaggi boolean NOT NULL DEFAULT false;",
        ),
        # Aggiungi foto se non esiste già
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;",
            reverse_sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS foto;",
        ),
        # Aggiungi foto_profilo_url se non esiste già
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_profilo_url varchar(500) NULL;",
            reverse_sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS foto_profilo_url;",
        ),
        # Aggiungi foto_url se non esiste già
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;",
            reverse_sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS foto_url;",
        ),
    ]
