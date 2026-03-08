import re
from datetime import datetime, time, date, timedelta
from django.utils import timezone
from .models import Dipendente, Cliente, TimeTracking, AssegnazioneTurno, Turno, Squadra, Mezzo
from django.db.models import Q

def normalize_text(text):
    """Rimuove caratteri speciali e normalizza spazi"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip().lower())

def fuzzy_find_cliente(query_name):
    """Cerca il cliente che meglio matcha il nome fornito."""
    query = normalize_text(query_name)
    candidates = Cliente.objects.all()
    best_match = None
    best_score = 0
    
    for c in candidates:
        c_name = normalize_text(c.ragione_sociale)
        if query == c_name:
            return c
        if query in c_name:
            score = len(query) / len(c_name)
            if score > best_score:
                best_score = score
                best_match = c
    
    return best_match

def parse_message(text):
    """Estrae (nome_cliente, ore) dal testo."""
    match = re.search(r'^(.*?)(\d+[.,:]?\d*)$', text.strip())
    
    if match:
        client_part = match.group(1).strip()
        time_part = match.group(2).strip().replace(',', '.')
        
        hours = 0.0
        if ':' in time_part:
            h, m = time_part.split(':')
            hours = int(h) + int(m)/60
        else:
            hours = float(time_part)
            
        return client_part, round(hours, 2)
    
    return None, None


# ========== MENU INTERATTIVO ==========

def get_main_menu():
    """Ritorna il menu principale con bottoni inline."""
    return {
        'inline_keyboard': [
            [{'text': '⏱ Registra Ore', 'callback_data': 'menu_ore'}],
            [{'text': '📋 Turni da compilare', 'callback_data': 'menu_turni_mancanti'}],
            [{'text': 'Malattia', 'callback_data': 'menu_malattia'},
             {'text': 'Ferie', 'callback_data': 'menu_ferie'}],
            [{'text': 'Permesso', 'callback_data': 'menu_permesso'},
             {'text': 'Segnalazione', 'callback_data': 'menu_segnalazione'}],
        ]
    }

def get_turni_oggi_keyboard(dipendente):
    """Ritorna tastiera inline con i turni di OGGI del dipendente."""
    today = timezone.now().date()
    assegnazioni = AssegnazioneTurno.objects.filter(
        turno__data=today
    ).filter(
        Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
    ).select_related('cliente', 'turno').distinct()
    
    keyboard = []
    for a in assegnazioni:
        inizio = a.orario_inizio_previsto.strftime('%H:%M')
        fine = a.orario_fine_previsto.strftime('%H:%M')
        label = f"{a.cliente.ragione_sociale[:20]} ({inizio}-{fine})"
        # Controlla se già compilato
        has_tt = TimeTracking.objects.filter(assegnazione=a, dipendente=dipendente).exists()
        if has_tt:
            label = f"✅ {label}"
        keyboard.append([{'text': label, 'callback_data': f'ore_turno_{a.pk}'}])
    
    if not keyboard:
        keyboard.append([{'text': '— Nessun turno oggi —', 'callback_data': 'menu_start'}])
    keyboard.append([{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}])
    return {'inline_keyboard': keyboard}

def get_turni_non_compilati_keyboard(dipendente):
    """Ritorna tastiera con turni passati senza ore compilate (ultimi 7 giorni)."""
    from datetime import timedelta as td
    today = timezone.now().date()
    sette_giorni_fa = today - td(days=7)
    
    assegnazioni = AssegnazioneTurno.objects.filter(
        turno__data__gte=sette_giorni_fa,
        turno__data__lte=today,
    ).filter(
        Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
    ).select_related('cliente', 'turno').order_by('-turno__data').distinct()
    
    keyboard = []
    for a in assegnazioni:
        has_tt = TimeTracking.objects.filter(assegnazione=a, dipendente=dipendente).exists()
        if not has_tt:
            data_str = a.turno.data.strftime('%d/%m')
            inizio = a.orario_inizio_previsto.strftime('%H:%M')
            fine = a.orario_fine_previsto.strftime('%H:%M')
            label = f"🔴 {data_str} {a.cliente.ragione_sociale[:18]} ({inizio}-{fine})"
            keyboard.append([{'text': label, 'callback_data': f'ore_turno_{a.pk}'}])
    
    if not keyboard:
        keyboard.append([{'text': '✅ Tutto compilato!', 'callback_data': 'menu_start'}])
    keyboard.append([{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}])
    return {'inline_keyboard': keyboard}


# Stato conversazione multi-step (in memoria)
_TELEGRAM_STATE = {}


def handle_telegram_message(telegram_chat_id, text, sender_name="Utente"):
    """
    Logica principale con supporto comandi e menu interattivo.
    Ritorna stringa o dict con text + reply_markup.
    """
    dipendenti = Dipendente.objects.filter(telegram_chat_id=telegram_chat_id, stato='ATTIVO')
    
    if not dipendenti.exists():
        return f"Non ti conosco! Il tuo ID Telegram e': {telegram_chat_id}\nInvialo all'amministratore per farti abilitare."
    
    dipendente = dipendenti.first()
    clean_text = normalize_text(text)
    
    # COMANDI /start e /menu
    if clean_text in ('/start', '/menu', 'menu', 'start'):
        return {
            'text': f"Ciao {dipendente.nome}! Cosa vuoi fare?",
            'reply_markup': get_main_menu()
        }
    
    # COMANDO /ore
    if clean_text == '/ore':
        return {
            'text': "Seleziona il turno di oggi per cui registrare le ore:",
            'reply_markup': get_turni_oggi_keyboard(dipendente)
        }
    
    # COMANDO /malattia
    if clean_text in ('/malattia', 'malattia'):
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente, tipo='MALATTIA',
            data_inizio=today, data_fine=today,
            note=f"Via Telegram: {text}", source='TELEGRAM'
        )
        return {
            'text': f"Registrata MALATTIA per oggi ({today.strftime('%d/%m')}). Riposati {dipendente.nome}!",
            'reply_markup': get_main_menu()
        }

    # COMANDO /ferie
    if clean_text in ('/ferie', 'ferie'):
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente, tipo='FERIE',
            data_inizio=today, data_fine=today,
            note=f"Via Telegram: {text}", source='TELEGRAM'
        )
        return {
            'text': f"Ferie registrate per oggi ({today.strftime('%d/%m')}). Buon relax {dipendente.nome}!",
            'reply_markup': get_main_menu()
        }

    # COMANDO /permesso
    if clean_text in ('/permesso', 'permesso'):
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente, tipo='PERMESSO',
            data_inizio=today, data_fine=today,
            note=f"Via Telegram: {text}", source='TELEGRAM'
        )
        return {
            'text': f"Permesso registrato per oggi ({today.strftime('%d/%m')}).",
            'reply_markup': get_main_menu()
        }

    # SEGNALAZIONE
    if clean_text.startswith('/segnalazione') or clean_text.startswith('segnalazione'):
        from .models import Segnalazione
        contenuto = text.lower().replace('/segnalazione', '').replace('segnalazione', '').strip()
        if not contenuto:
            _TELEGRAM_STATE[telegram_chat_id] = {'action': 'segnalazione'}
            return "Scrivi il testo della segnalazione:"
        Segnalazione.objects.create(dipendente=dipendente, testo=contenuto)
        return {
            'text': f"Segnalazione registrata: '{contenuto}'",
            'reply_markup': get_main_menu()
        }
    
    # Controlla stato conversazione (attesa input)
    state = _TELEGRAM_STATE.get(telegram_chat_id)
    if state:
        action = state.get('action')
        
        # Attesa ore per un turno specifico
        if action == 'attesa_ore':
            assegnazione_id = state.get('assegnazione_id')
            del _TELEGRAM_STATE[telegram_chat_id]
            
            try:
                hours = float(clean_text.replace(',', '.').replace(':', '.'))
            except ValueError:
                return "Formato ore non valido. Scrivi un numero (es: 8 o 7.5)"
            
            try:
                assegnazione = AssegnazioneTurno.objects.select_related('cliente').get(pk=assegnazione_id)
            except AssegnazioneTurno.DoesNotExist:
                return "Turno non trovato."
            
            return _salva_ore_turno(dipendente, assegnazione, hours, text)
        
        # Attesa testo segnalazione
        if action == 'segnalazione':
            del _TELEGRAM_STATE[telegram_chat_id]
            from .models import Segnalazione
            Segnalazione.objects.create(dipendente=dipendente, testo=text.strip())
            return {
                'text': f"Segnalazione registrata: '{text.strip()}'",
                'reply_markup': get_main_menu()
            }
    
    # Nessun comando riconosciuto: mostra menu
    return {
        'text': f"Ciao {dipendente.nome}! Usa i bottoni per navigare il menu.\nPuoi anche scrivere:\n- /ore — registra ore\n- /malattia, /ferie, /permesso\n- /segnalazione testo",
        'reply_markup': get_main_menu()
    }


def handle_telegram_callback(telegram_chat_id, callback_data, sender_name="Utente"):
    """Gestisce i bottoni inline premuti dall'utente."""
    dipendenti = Dipendente.objects.filter(telegram_chat_id=telegram_chat_id, stato='ATTIVO')
    
    if not dipendenti.exists():
        return {'text': f"Non ti conosco! ID: {telegram_chat_id}"}
    
    dipendente = dipendenti.first()
    
    # Menu principale
    if callback_data == 'menu_start':
        return {
            'text': f"Ciao {dipendente.nome}! Cosa vuoi fare?",
            'reply_markup': get_main_menu()
        }
    
    # Registra Ore -> mostra lista clienti
    if callback_data == 'menu_ore':
        return {
            'text': "Seleziona il turno di oggi per cui registrare le ore:",
            'reply_markup': get_turni_oggi_keyboard(dipendente)
        }
    
    # Turni da compilare
    if callback_data == 'menu_turni_mancanti':
        return {
            'text': "Turni senza ore (ultimi 7 giorni):\nSeleziona per inserire le ore.",
            'reply_markup': get_turni_non_compilati_keyboard(dipendente)
        }
    
    # Malattia
    if callback_data == 'menu_malattia':
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente, tipo='MALATTIA',
            data_inizio=today, data_fine=today,
            note="Via bottone Telegram", source='TELEGRAM'
        )
        return {
            'text': f"Registrata MALATTIA per oggi ({today.strftime('%d/%m')}). Riposati!",
            'reply_markup': get_main_menu()
        }
    
    # Ferie
    if callback_data == 'menu_ferie':
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente, tipo='FERIE',
            data_inizio=today, data_fine=today,
            note="Via bottone Telegram", source='TELEGRAM'
        )
        return {
            'text': f"Ferie registrate per oggi ({today.strftime('%d/%m')}). Buon relax!",
            'reply_markup': get_main_menu()
        }
    
    # Permesso
    if callback_data == 'menu_permesso':
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente, tipo='PERMESSO',
            data_inizio=today, data_fine=today,
            note="Via bottone Telegram", source='TELEGRAM'
        )
        return {
            'text': f"Permesso registrato per oggi ({today.strftime('%d/%m')}).",
            'reply_markup': get_main_menu()
        }
    
    # Segnalazione -> chiedi testo
    if callback_data == 'menu_segnalazione':
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'segnalazione'}
        return {'text': "Scrivi il testo della segnalazione:"}
    
    # Turno selezionato per ore
    if callback_data.startswith('ore_turno_'):
        assegnazione_id = callback_data.replace('ore_turno_', '')
        try:
            assegnazione = AssegnazioneTurno.objects.select_related('cliente', 'turno').get(pk=assegnazione_id)
        except AssegnazioneTurno.DoesNotExist:
            return {'text': "Turno non trovato."}
        
        data_str = assegnazione.turno.data.strftime('%d/%m')
        inizio = assegnazione.orario_inizio_previsto.strftime('%H:%M')
        fine = assegnazione.orario_fine_previsto.strftime('%H:%M')
        
        _TELEGRAM_STATE[telegram_chat_id] = {
            'action': 'attesa_ore',
            'assegnazione_id': int(assegnazione_id)
        }
        return {'text': f"Turno: {assegnazione.cliente.ragione_sociale}\n"
                       f"Data: {data_str} ({inizio}-{fine})\n\n"
                       f"Quante ore hai lavorato?\n(Scrivi il numero, es: 8 o 7.5)"}
    
    return {'text': "Comando non riconosciuto.", 'reply_markup': get_main_menu()}


def _salva_ore_turno(dipendente, assegnazione, hours, original_text):
    """Salva le ore lavorate per una specifica assegnazione turno."""
    # Aggiorna se esiste già un TimeTracking, altrimenti crea
    tt, created = TimeTracking.objects.update_or_create(
        dipendente=dipendente,
        assegnazione=assegnazione,
        defaults={
            'ore_dichiarate': hours,
            'source': 'TELEGRAM',
            'note': f"Messaggio: {original_text}",
            'is_validated': False,
        }
    )
    
    data_str = assegnazione.turno.data.strftime('%d/%m')
    action = "Salvato" if created else "Aggiornato"
    return {
        'text': f"{action}! {hours}h per {assegnazione.cliente.ragione_sociale} ({data_str}).",
        'reply_markup': get_main_menu()
    }


def send_telegram_message(chat_id, text):
    """Invia un messaggio proattivo a una specifica chat_id."""
    from django.conf import settings
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
    
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={'chat_id': chat_id, 'text': text})
        return r.status_code == 200
    except Exception:
        return False


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcola la distanza tra due punti GPS usando Haversine. Ritorna metri."""
    import math
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def check_proximity(dipendente, lat, lon):
    """Controlla la prossimita del dipendente a tutti i clienti."""
    from .models import ProximityLog
    clienti = Cliente.objects.exclude(latitudine__isnull=True).exclude(longitudine__isnull=True)
    events = []
    
    for cliente in clienti:
        dist = calculate_distance(lat, lon, float(cliente.latitudine), float(cliente.longitudine))
        raggio = float(cliente.raggio_prossimita) if cliente.raggio_prossimita else 100
        is_inside = dist <= raggio
        
        last_log = ProximityLog.objects.filter(
            dipendente=dipendente, cliente=cliente
        ).order_by('-timestamp').first()
        
        was_inside = last_log.inside if last_log else False
        
        if is_inside != was_inside:
            ProximityLog.objects.create(
                dipendente=dipendente,
                cliente=cliente,
                latitudine=lat,
                longitudine=lon,
                distanza=dist,
                inside=is_inside
            )
            if is_inside:
                events.append(('enter', cliente, dist))
            else:
                events.append(('exit', cliente, dist))
    
    return events
