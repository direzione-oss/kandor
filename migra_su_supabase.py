# -*- coding: utf-8 -*-
"""
migra_su_supabase.py — Migrazione dati KANDOR da SQLite a Supabase (PostgreSQL)
Da eseguire UNA SOLA VOLTA dopo aver:
  1. Configurato .env con le credenziali Supabase
  2. Eseguito: python manage.py migrate (per creare le tabelle su Supabase)

ESECUZIONE:
   python migra_su_supabase.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import sqlite3
import django
from pathlib import Path
from datetime import datetime, time as dt_time

# Setup Django
BASE_DIR = Path(__file__).parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cleanup_erp.settings')

# Per la migrazione, usiamo SQLite come sorgente, NON le impostazioni di settings.py
# Quindi carichiamo Django ma poi lavoriamo direttamente con i DB

# Carica .env manualmente
from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')

django.setup()

# Ora importiamo i modelli Django
from django.db import connection
from core.models import (
    Qualifica, Dipendente, Cliente, ProgrammazioneRicorrente,
    RichiestaStraordinaria, Mezzo, Squadra, Turno, AssegnazioneTurno,
    TimeTracking, Assenza, Segnalazione, MessaggioProgrammato, ProximityLog
)
from django.contrib.auth.models import User

SQLITE_DB = BASE_DIR / 'db.sqlite3'

# -------------------------------------------------------
# Funzioni Helper
# -------------------------------------------------------
def get_sqlite_connection():
    """Apre connessione al database SQLite locale."""
    if not SQLITE_DB.exists():
        print(f"ERRORE: Database SQLite non trovato: {SQLITE_DB}")
        sys.exit(1)
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row
    return conn

def get_sqlite_rows(conn, table_name):
    """Recupera tutte le righe da una tabella SQLite."""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table_name}")
        return [dict(row) for row in cur.fetchall()]
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  Tabella '{table_name}' non trovata: {e}")
        return []

def norm_val(v):
    """Normalizza valori per PostgreSQL."""
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == '':
        return None
    return v

def parse_time(v):
    """Converte una stringa orario SQLite in datetime.time."""
    if v is None:
        return None
    if isinstance(v, dt_time):
        return v
    if isinstance(v, str):
        v = v.strip()
        if not v:
            return None
        for fmt in ('%H:%M:%S', '%H:%M', '%H:%M:%S.%f'):
            try:
                return datetime.strptime(v, fmt).time()
            except ValueError:
                continue
    return None

# -------------------------------------------------------
# Migrazione Tabelle Semplici (senza FK)
# -------------------------------------------------------
def migra_qualifiche(conn):
    rows = get_sqlite_rows(conn, 'core_qualifica')
    count = 0
    for row in rows:
        obj, created = Qualifica.objects.update_or_create(
            id=row['id'],
            defaults={'nome': row['nome'], 'descrizione': row.get('descrizione', '')}
        )
        if created:
            count += 1
    print(f"   ✅ Qualifiche: {count} create, {len(rows)} totali")
    return count

def migra_mezzi(conn):
    rows = get_sqlite_rows(conn, 'core_mezzo')
    count = 0
    for row in rows:
        obj, created = Mezzo.objects.update_or_create(
            id=row['id'],
            defaults={
                'modello': row.get('modello', ''),
                'targa': row.get('targa', ''),
                'stato': row.get('stato', 'DISPONIBILE'),
                'km_attuali': row.get('km_attuali', 0),
                'scadenza_polizza': norm_val(row.get('scadenza_polizza')),
                'scadenza_bollo': norm_val(row.get('scadenza_bollo')),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Mezzi: {count} creati, {len(rows)} totali")
    return count

def migra_dipendenti(conn):
    rows = get_sqlite_rows(conn, 'core_dipendente')
    count = 0
    for row in rows:
        obj, created = Dipendente.objects.update_or_create(
            id=row['id'],
            defaults={
                'nome': row.get('nome', ''),
                'cognome': row.get('cognome', ''),
                'codice_fiscale': row.get('codice_fiscale', ''),
                'data_nascita': norm_val(row.get('data_nascita')),
                'indirizzo_residenza': row.get('indirizzo_residenza', ''),
                'email': row.get('email', ''),
                'telefono': row.get('telefono', ''),
                'latitudine': norm_val(row.get('latitudine')),
                'longitudine': norm_val(row.get('longitudine')),
                'categoria_protetta': bool(row.get('categoria_protetta', 0)),
                'stato': row.get('stato', 'ATTIVO'),
                'telegram_chat_id': row.get('telegram_chat_id', ''),
            }
        )
        if created:
            count += 1
    
    # Migra relazione M2M: dipendente_qualifiche
    m2m_rows = get_sqlite_rows(conn, 'core_dipendente_qualifiche')
    m2m_count = 0
    for row in m2m_rows:
        try:
            dip = Dipendente.objects.get(id=row['dipendente_id'])
            qual = Qualifica.objects.get(id=row['qualifica_id'])
            dip.qualifiche.add(qual)
            m2m_count += 1
        except Exception as e:
            print(f"      ⚠️  M2M Dip-Qual: {e}")
    
    print(f"   ✅ Dipendenti: {count} creati, {len(rows)} totali ({m2m_count} qualifiche associate)")
    return count

def migra_clienti(conn):
    rows = get_sqlite_rows(conn, 'core_cliente')
    count = 0
    for row in rows:
        obj, created = Cliente.objects.update_or_create(
            id=row['id'],
            defaults={
                'ragione_sociale': row.get('ragione_sociale', ''),
                'partita_iva': norm_val(row.get('partita_iva')),
                'codice_fiscale': norm_val(row.get('codice_fiscale')),
                'indirizzo_sede': row.get('indirizzo_sede', ''),
                'latitudine': norm_val(row.get('latitudine')),
                'longitudine': norm_val(row.get('longitudine')),
                'referente_nome': row.get('referente_nome', ''),
                'referente_ruolo': row.get('referente_ruolo', ''),
                'referente_data_nascita': norm_val(row.get('referente_data_nascita')),
                'ore_mensili_contratto': row.get('ore_mensili_contratto', 0),
                'note_mansioni': row.get('note_mansioni', ''),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Clienti: {count} creati, {len(rows)} totali")
    return count

def migra_squadre(conn):
    rows = get_sqlite_rows(conn, 'core_squadra')
    count = 0
    for row in rows:
        obj, created = Squadra.objects.update_or_create(
            id=row['id'],
            defaults={
                'nome': row.get('nome', ''),
                'caposquadra_id': norm_val(row.get('caposquadra_id')),
            }
        )
        if created:
            count += 1
    
    # Migra relazione M2M: squadra_componenti
    m2m_rows = get_sqlite_rows(conn, 'core_squadra_componenti')
    m2m_count = 0
    for row in m2m_rows:
        try:
            sq = Squadra.objects.get(id=row['squadra_id'])
            dip = Dipendente.objects.get(id=row['dipendente_id'])
            sq.componenti.add(dip)
            m2m_count += 1
        except Exception as e:
            print(f"      ⚠️  M2M Squadra-Comp: {e}")
    
    print(f"   ✅ Squadre: {count} create, {len(rows)} totali ({m2m_count} componenti associati)")
    return count

# -------------------------------------------------------
# Migrazione Tabelle con FK
# -------------------------------------------------------
def migra_programmazioni(conn):
    rows = get_sqlite_rows(conn, 'core_programmazionericorrente')
    count = 0
    for row in rows:
        obj, created = ProgrammazioneRicorrente.objects.update_or_create(
            id=row['id'],
            defaults={
                'cliente_id': row['cliente_id'],
                'tipo_ripetizione': row.get('tipo_ripetizione', 'SETTIMANALE'),
                'giorno_settimana': norm_val(row.get('giorno_settimana')),
                'giorno_mese': norm_val(row.get('giorno_mese')),
                'ora_inizio': parse_time(row.get('ora_inizio')),
                'durata': row.get('durata', 1.0),
                'ora_fine': parse_time(row.get('ora_fine')),
                'orario_flessibile': bool(row.get('orario_flessibile', 0)),
                'qualifica_richiesta_id': norm_val(row.get('qualifica_richiesta_id')),
                'squadra_abituale_id': norm_val(row.get('squadra_abituale_id')),
                'mezzo_abituale_id': norm_val(row.get('mezzo_abituale_id')),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Programmazioni Ricorrenti: {count} create, {len(rows)} totali")
    return count

def migra_straordinari(conn):
    rows = get_sqlite_rows(conn, 'core_richiestastraordinaria')
    count = 0
    for row in rows:
        obj, created = RichiestaStraordinaria.objects.update_or_create(
            id=row['id'],
            defaults={
                'cliente_id': row['cliente_id'],
                'data_inizio': row['data_inizio'],
                'data_fine': norm_val(row.get('data_fine')),
                'ora_inizio': parse_time(row['ora_inizio']),
                'ora_fine': parse_time(row['ora_fine']),
                'descrizione': row.get('descrizione', ''),
                'completata': bool(row.get('completata', 0)),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Richieste Straordinarie: {count} create, {len(rows)} totali")
    return count

def migra_turni(conn):
    rows = get_sqlite_rows(conn, 'core_turno')
    count = 0
    for row in rows:
        obj, created = Turno.objects.update_or_create(
            id=row['id'],
            defaults={
                'data': row['data'],
                'squadra_id': row['squadra_id'],
                'mezzo_id': norm_val(row.get('mezzo_id')),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Turni: {count} creati, {len(rows)} totali")
    return count

def migra_assegnazioni(conn):
    rows = get_sqlite_rows(conn, 'core_assegnazioneturno')
    count = 0
    for row in rows:
        obj, created = AssegnazioneTurno.objects.update_or_create(
            id=row['id'],
            defaults={
                'turno_id': row['turno_id'],
                'cliente_id': row['cliente_id'],
                'programmazione_feriale_id': norm_val(row.get('programmazione_feriale_id')),
                'richiesta_straordinaria_id': norm_val(row.get('richiesta_straordinaria_id')),
                'orario_inizio_previsto': parse_time(row['orario_inizio_previsto']),
                'orario_fine_previsto': parse_time(row['orario_fine_previsto']),
                'mansione_svolta': row.get('mansione_svolta', ''),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Assegnazioni Turno: {count} create, {len(rows)} totali")
    return count

def migra_timetracking(conn):
    rows = get_sqlite_rows(conn, 'core_timetracking')
    count = 0
    for row in rows:
        obj, created = TimeTracking.objects.update_or_create(
            id=row['id'],
            defaults={
                'dipendente_id': row['dipendente_id'],
                'assegnazione_id': row['assegnazione_id'],
                'check_in': norm_val(row.get('check_in')),
                'check_out': norm_val(row.get('check_out')),
                'note': row.get('note', ''),
                'source': row.get('source', 'MANUAL'),
                'is_validated': bool(row.get('is_validated', 0)),
            }
        )
        if created:
            count += 1
    print(f"   ✅ TimeTracking: {count} creati, {len(rows)} totali")
    return count

def migra_assenze(conn):
    rows = get_sqlite_rows(conn, 'core_assenza')
    count = 0
    for row in rows:
        obj, created = Assenza.objects.update_or_create(
            id=row['id'],
            defaults={
                'dipendente_id': row['dipendente_id'],
                'tipo': row['tipo'],
                'data_inizio': row['data_inizio'],
                'data_fine': row['data_fine'],
                'note': row.get('note', ''),
                'source': row.get('source', 'MANUAL'),
                'is_processed': bool(row.get('is_processed', 0)),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Assenze: {count} create, {len(rows)} totali")
    return count

def migra_segnalazioni(conn):
    rows = get_sqlite_rows(conn, 'core_segnalazione')
    count = 0
    for row in rows:
        obj, created = Segnalazione.objects.update_or_create(
            id=row['id'],
            defaults={
                'dipendente_id': row['dipendente_id'],
                'testo': row.get('testo', ''),
                'risolto': bool(row.get('risolto', 0)),
                'note_amministrazione': row.get('note_amministrazione', ''),
            }
        )
        if created:
            count += 1
    print(f"   ✅ Segnalazioni: {count} create, {len(rows)} totali")
    return count

def migra_messaggi_programmati(conn):
    rows = get_sqlite_rows(conn, 'core_messaggioprogrammato')
    count = 0
    for row in rows:
        obj, created = MessaggioProgrammato.objects.update_or_create(
            id=row['id'],
            defaults={
                'titolo': row.get('titolo', ''),
                'testo': row.get('testo', ''),
                'data_programmata': row['data_programmata'],
                'invia_a_tutti': bool(row.get('invia_a_tutti', 0)),
                'inviato': bool(row.get('inviato', 0)),
            }
        )
        if created:
            count += 1
    
    # Migra relazione M2M: messaggio_destinatari
    m2m_rows = get_sqlite_rows(conn, 'core_messaggioprogrammato_destinatari')
    m2m_count = 0
    for row in m2m_rows:
        try:
            msg = MessaggioProgrammato.objects.get(id=row['messaggioprogrammato_id'])
            dip = Dipendente.objects.get(id=row['dipendente_id'])
            msg.destinatari.add(dip)
            m2m_count += 1
        except Exception as e:
            print(f"      ⚠️  M2M Msg-Dest: {e}")
    
    print(f"   ✅ Messaggi Programmati: {count} creati, {len(rows)} totali ({m2m_count} destinatari)")
    return count

def migra_proximity_logs(conn):
    rows = get_sqlite_rows(conn, 'core_proximitylog')
    count = 0
    for row in rows:
        obj, created = ProximityLog.objects.update_or_create(
            id=row['id'],
            defaults={
                'dipendente_id': row['dipendente_id'],
                'cliente_id': row['cliente_id'],
                'is_near': bool(row.get('is_near', 0)),
                'entered_at': norm_val(row.get('entered_at')),
                'exited_at': norm_val(row.get('exited_at')),
            }
        )
        if created:
            count += 1
    print(f"   ✅ ProximityLog: {count} creati, {len(rows)} totali")
    return count

def migra_utenti_django(conn):
    """Migra la tabella auth_user (admin di Django)."""
    rows = get_sqlite_rows(conn, 'auth_user')
    count = 0
    for row in rows:
        if not User.objects.filter(username=row['username']).exists():
            user = User(
                id=row['id'],
                username=row['username'],
                email=row.get('email', ''),
                is_staff=bool(row.get('is_staff', 0)),
                is_superuser=bool(row.get('is_superuser', 0)),
                is_active=bool(row.get('is_active', 1)),
                first_name=row.get('first_name', ''),
                last_name=row.get('last_name', ''),
            )
            user.password = row['password']  # Hash già calcolato
            user.save()
            count += 1
    print(f"   ✅ Utenti Django: {count} creati, {len(rows)} totali")
    return count

# -------------------------------------------------------
# Resetta sequenze PostgreSQL
# -------------------------------------------------------
def reset_sequences():
    """Resetta le sequenze auto-increment di PostgreSQL dopo l'import."""
    tables = [
        'core_qualifica', 'core_mezzo', 'core_dipendente', 'core_cliente',
        'core_squadra', 'core_programmazionericorrente', 'core_richiestastraordinaria',
        'core_turno', 'core_assegnazioneturno', 'core_timetracking',
        'core_assenza', 'core_segnalazione', 'core_messaggioprogrammato',
        'core_proximitylog', 'auth_user',
    ]
    with connection.cursor() as cursor:
        for table in tables:
            try:
                cursor.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                                  COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)
                """)
            except Exception as e:
                print(f"   ⚠️  Sequenza {table}: {e}")
    print("   ✅ Sequenze PostgreSQL resettate")

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
def main():
    print("\n" + "=" * 55)
    print("  KANDOR — Migrazione da SQLite a Supabase")
    print("=" * 55)

    # Verifica connessione a Supabase (PostgreSQL)
    print("\n📡 Verifica connessione a Supabase...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("   ✅ Connessione a Supabase OK!")
    except Exception as e:
        print(f"   ❌ ERRORE connessione: {e}")
        print("\n   Verifica che:")
        print("   1. Il file .env contenga le credenziali corrette")
        print("   2. La password del database sia quella di Supabase")
        print("   3. python manage.py migrate sia stato eseguito")
        sys.exit(1)

    # Connessione SQLite
    print("\n📂 Connessione a SQLite locale...")
    conn = get_sqlite_connection()
    print("   ✅ Connessione SQLite OK!")

    # Migrazione in ordine (prima le tabelle senza FK, poi quelle con FK)
    print("\n" + "-" * 55)
    print("  FASE 1: Tabelle Base")
    print("-" * 55)
    migra_utenti_django(conn)
    migra_qualifiche(conn)
    migra_mezzi(conn)
    migra_dipendenti(conn)
    migra_clienti(conn)
    migra_squadre(conn)

    print("\n" + "-" * 55)
    print("  FASE 2: Tabelle con Relazioni")
    print("-" * 55)
    migra_programmazioni(conn)
    migra_straordinari(conn)
    migra_turni(conn)
    migra_assegnazioni(conn)
    migra_timetracking(conn)
    migra_assenze(conn)
    migra_segnalazioni(conn)
    migra_messaggi_programmati(conn)
    migra_proximity_logs(conn)

    print("\n" + "-" * 55)
    print("  FASE 3: Aggiornamento Sequenze")
    print("-" * 55)
    reset_sequences()

    conn.close()

    print("\n" + "=" * 55)
    print("  ✅ MIGRAZIONE COMPLETATA CON SUCCESSO!")
    print("=" * 55)
    print("\n  Prossimi passi:")
    print("  1. Verifica i dati su Supabase Dashboard → Table Editor")
    print("  2. Avvia l'app: python manage.py runserver")
    print("  3. Accedi a /admin/ per verificare i dati\n")
    input("Premi INVIO per chiudere...")

if __name__ == "__main__":
    main()
