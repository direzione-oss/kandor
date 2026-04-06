import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_titolare_table(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == 'sqlite':
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


def reverse_titolare(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS core_titolare;")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_dipendente_foto_profilo_url'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # AlterModelOptions sono sempre sicuri (solo metadati)
        migrations.AlterModelOptions(
            name='cliente',
            options={'ordering': ['ragione_sociale'], 'verbose_name': 'Cliente',
                     'verbose_name_plural': 'Clienti'},
        ),
        migrations.AlterModelOptions(
            name='dipendente',
            options={'ordering': ['cognome', 'nome'], 'verbose_name_plural': 'Dipendenti'},
        ),
        migrations.AlterModelOptions(
            name='mezzo',
            options={'ordering': ['modello', 'targa'], 'verbose_name_plural': 'Mezzi Aziendali'},
        ),
        migrations.AlterModelOptions(
            name='responsabilearea',
            options={'ordering': ['nome_area'], 'verbose_name': 'Responsabile Area',
                     'verbose_name_plural': 'Responsabili Area'},
        ),
        migrations.AlterModelOptions(
            name='richiestastraordinaria',
            options={'ordering': ['-data_inizio', 'ora_inizio'],
                     'verbose_name_plural': 'Richieste Straordinarie'},
        ),
        migrations.AlterModelOptions(
            name='squadra',
            options={'ordering': ['nome'], 'verbose_name_plural': 'Squadre'},
        ),
        # Crea tabella Titolare (SQLite e PostgreSQL compatibile)
        migrations.RunPython(create_titolare_table, reverse_titolare),
    ]
