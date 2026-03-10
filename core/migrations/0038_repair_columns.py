"""
Migrazione di riparazione emergenziale.
Ricrea la colonna riceve_notifiche_messaggi che risulta mancante nel DB
di produzione (Render) pur essendo segnata come applicata nella tabella
django_migrations. Usa atomic=False per garantire che il RunSQL venga
eseguito anche se il migration tracker è in stato inconsistente.
"""
from django.db import migrations


class Migration(migrations.Migration):

    # atomic=False: ogni RunSQL viene committato indipendentemente
    atomic = False

    dependencies = [
        ('core', '0037_remove_riceve_notifiche'),
    ]

    operations = [
        # Ricrea colonna riceve_notifiche_messaggi se non esiste
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS riceve_notifiche_messaggi boolean NOT NULL DEFAULT false;",
            reverse_sql="ALTER TABLE core_dipendente DROP COLUMN IF EXISTS riceve_notifiche_messaggi;",
        ),
        # Assicura che le colonne foto esistano
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_profilo_url varchar(500) NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Assicura che core_titolare esista
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS core_titolare (
                    id bigserial PRIMARY KEY,
                    nome varchar(100) NOT NULL,
                    telegram_chat_id varchar(50) NOT NULL DEFAULT '',
                    notifiche_attive boolean NOT NULL DEFAULT true,
                    dipendente_id bigint UNIQUE REFERENCES core_dipendente(id) ON DELETE SET NULL,
                    user_id integer NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE
                );
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
