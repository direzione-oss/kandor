"""
Migrazione di riparazione emergenziale.
Ricrea la colonna riceve_notifiche_messaggi che risulta mancante nel DB
di produzione (Render) pur essendo segnata come applicata nella tabella
django_migrations. Usa atomic=False per garantire che il RunSQL venga
eseguito anche se il migration tracker è in stato inconsistente.
Versione 2: compatibile con SQLite (sviluppo locale) e PostgreSQL (produzione).
"""
from django.db import migrations, connection


def add_column_if_missing(table, column, col_type_pg, col_type_sqlite, apps, schema_editor):
    """Aggiunge una colonna solo se non esiste già (compatibile PG e SQLite)."""
    db = schema_editor.connection.vendor  # 'postgresql' o 'sqlite'
    with connection.cursor() as cursor:
        if db == 'sqlite':
            # SQLite: leggi il PRAGMA per vedere le colonne esistenti
            cursor.execute(f"PRAGMA table_info({table});")
            cols = [row[1] for row in cursor.fetchall()]
            if column not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type_sqlite};")
        else:
            # PostgreSQL: usa IF NOT EXISTS
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type_pg};"
            )


def repair_forward(apps, schema_editor):
    db = schema_editor.connection.vendor
    with connection.cursor() as cursor:
        # --- riceve_notifiche_messaggi ---
        if db == 'sqlite':
            cursor.execute("PRAGMA table_info(core_dipendente);")
            cols = [r[1] for r in cursor.fetchall()]
            if 'riceve_notifiche_messaggi' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente "
                    "ADD COLUMN riceve_notifiche_messaggi integer NOT NULL DEFAULT 0;"
                )
            if 'foto' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto varchar(100) NULL;"
                )
            if 'foto_url' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto_url varchar(500) NULL;"
                )
            if 'foto_profilo_url' not in cols:
                cursor.execute(
                    "ALTER TABLE core_dipendente ADD COLUMN foto_profilo_url varchar(500) NULL;"
                )
            # core_titolare su SQLite
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS core_titolare (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome varchar(100) NOT NULL,
                    telegram_chat_id varchar(50) NOT NULL DEFAULT '',
                    notifiche_attive integer NOT NULL DEFAULT 1,
                    dipendente_id integer UNIQUE REFERENCES core_dipendente(id) ON DELETE SET NULL,
                    user_id integer NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE
                );
            """)
        else:
            # PostgreSQL — SQL originale
            cursor.execute(
                "ALTER TABLE core_dipendente "
                "ADD COLUMN IF NOT EXISTS riceve_notifiche_messaggi boolean NOT NULL DEFAULT false;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto varchar(100) NULL;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_url varchar(500) NULL;"
            )
            cursor.execute(
                "ALTER TABLE core_dipendente ADD COLUMN IF NOT EXISTS foto_profilo_url varchar(500) NULL;"
            )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS core_titolare (
                    id bigserial PRIMARY KEY,
                    nome varchar(100) NOT NULL,
                    telegram_chat_id varchar(50) NOT NULL DEFAULT '',
                    notifiche_attive boolean NOT NULL DEFAULT true,
                    dipendente_id bigint UNIQUE REFERENCES core_dipendente(id) ON DELETE SET NULL,
                    user_id integer NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE
                );
            """)


def repair_reverse(apps, schema_editor):
    pass  # rollback non necessario


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('core', '0037_remove_riceve_notifiche'),
    ]

    operations = [
        migrations.RunPython(repair_forward, repair_reverse),
    ]
