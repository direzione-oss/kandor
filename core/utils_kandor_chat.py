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

def get_calendario_giornaliero(dipendente, data_calendario):
    """Genera il testo e i bottoni per il calendario giornaliero."""
    try:
        from datetime import timedelta
        
        assegnazioni = AssegnazioneTurno.objects.filter(
            turno__data=data_calendario
        ).filter(
            Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
        ).select_related('cliente', 'turno').distinct().order_by('orario_inizio_previsto')
        
        testo = f"📅 Calendario del {data_calendario.strftime('%d/%m/%Y')}\n\n"
        
        if not assegnazioni.exists():
            testo += "Nessun turno assegnato per questa giornata.\n"
        else:
            for a in assegnazioni:
                inizio = a.orario_inizio_previsto.strftime('%H:%M') if a.orario_inizio_previsto else '?'
                fine = a.orario_fine_previsto.strftime('%H:%M') if a.orario_fine_previsto else '?'
                cliente_nome = a.cliente.ragione_sociale
                squadra_nome = a.turno.squadra.nome
                
                testo += f"🏢 *{cliente_nome}*\n"
                testo += f"🕒 {inizio} - {fine} (Squadra: {squadra_nome})\n"
                
                # Note/mansioni del turno (inserite dall'app)
                if a.mansione_svolta:
                    testo += f"📋 Mansione: {a.mansione_svolta}\n"
                
                # Cerca timetracking
                tt = TimeTracking.objects.filter(assegnazione=a, dipendente=dipendente).first()
                if tt:
                    ore = tt.ore_dichiarate if tt.ore_dichiarate else 'N/D'
                    note = tt.note if tt.note else 'Nessuna'
                    testo += f"✅ Ore registrate: {ore}h\n"
                    testo += f"📝 Note: {note}\n"
                else:
                    testo += f"⏳ Ore non ancora registrate.\n"
                testo += "\n"
        
        # Bottoni prev/next
        prev_data = data_calendario - timedelta(days=1)
        next_data = data_calendario + timedelta(days=1)
        
        keyboard = [
            [
                {'text': '⬅️ Precedente', 'callback_data': f'cal_prev_{prev_data.strftime("%Y-%m-%d")}'},
                {'text': 'Successivo ➡️', 'callback_data': f'cal_next_{next_data.strftime("%Y-%m-%d")}'}
            ],
            [{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}]
        ]
        
        # Parse_mode non e supportato da default, ma i telegram clients renderizzano Markdown se inviato dal bot 
        # se parse_mode e supportato dalla API call. Qui restituiamo il text raw, i caratteri speciali faranno da UI.
        
        return {'text': testo, 'reply_markup': {'inline_keyboard': keyboard}, 'parse_mode': 'Markdown'}
    except Exception as e:
        return {'text': f'Errore calendario: {str(e)}', 'reply_markup': get_main_menu()}


def get_main_menu():
    """Ritorna il menu principale con bottoni inline."""
    return {
        'inline_keyboard': [
            [{'text': '⏱ Registra Ore', 'callback_data': 'menu_ore'}],
            [{'text': '📅 Calendario', 'callback_data': 'menu_calendario'}],
            [{'text': '📋 Turni da compilare', 'callback_data': 'menu_turni_mancanti'}],
            [{'text': 'Malattia', 'callback_data': 'menu_malattia'},
             {'text': 'Ferie', 'callback_data': 'menu_ferie'}],
            [{'text': 'Permesso', 'callback_data': 'menu_permesso'},
             {'text': 'Segnalazione', 'callback_data': 'menu_segnalazione'}],
            [{'text': '📸 Foto Profilo', 'callback_data': 'menu_foto_profilo'}],
            [{'text': '📖 Guida', 'url': 'https://kandor.onrender.com/manuale-dipendente/'}],
        ]
    }

def get_turni_oggi_keyboard(dipendente):
    """Ritorna tastiera inline con i turni di OGGI del dipendente."""
    try:
        today = timezone.now().date()
        assegnazioni = AssegnazioneTurno.objects.filter(
            turno__data=today
        ).filter(
            Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
        ).select_related('cliente', 'turno').distinct()
        
        keyboard = []
        for a in assegnazioni:
            inizio = a.orario_inizio_previsto.strftime('%H:%M') if a.orario_inizio_previsto else '?'
            fine = a.orario_fine_previsto.strftime('%H:%M') if a.orario_fine_previsto else '?'
            cliente_nome = a.cliente.ragione_sociale[:20] if a.cliente else 'N/D'
            label = f"{cliente_nome} ({inizio}-{fine})"
            # Controlla se già compilato
            has_tt = TimeTracking.objects.filter(assegnazione=a, dipendente=dipendente).exists()
            if has_tt:
                label = f"✅ {label}"
            keyboard.append([{'text': label, 'callback_data': f'ore_turno_{a.pk}'}])
        
        if not keyboard:
            keyboard.append([{'text': '— Nessun turno oggi —', 'callback_data': 'menu_start'}])
        keyboard.append([{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}])
        return {'inline_keyboard': keyboard}
    except Exception as e:
        return {'inline_keyboard': [
            [{'text': f'Errore: {str(e)[:40]}', 'callback_data': 'menu_start'}],
            [{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}]
        ]}

def get_turni_non_compilati_keyboard(dipendente):
    """Ritorna tastiera con turni passati senza ore compilate (ultimi 7 giorni)."""
    try:
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
                inizio = a.orario_inizio_previsto.strftime('%H:%M') if a.orario_inizio_previsto else '?'
                fine = a.orario_fine_previsto.strftime('%H:%M') if a.orario_fine_previsto else '?'
                cliente_nome = a.cliente.ragione_sociale[:18] if a.cliente else 'N/D'
                label = f"🔴 {data_str} {cliente_nome} ({inizio}-{fine})"
                keyboard.append([{'text': label, 'callback_data': f'ore_turno_{a.pk}'}])
        
        if not keyboard:
            keyboard.append([{'text': '✅ Tutto compilato!', 'callback_data': 'menu_start'}])
        keyboard.append([{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}])
        return {'inline_keyboard': keyboard}
    except Exception as e:
        return {'inline_keyboard': [
            [{'text': f'Errore: {str(e)[:40]}', 'callback_data': 'menu_start'}],
            [{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}]
        ]}


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
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_date_malattia'}
        return {'text': 'Scrivi la data o il periodo di Malattia (es: 15/10/2026, oppure 15/10/2026 - 18/10/2026):'}


    # COMANDO /ferie
    if clean_text in ('/ferie', 'ferie'):
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_date_ferie'}
        return {'text': 'Scrivi la data o il periodo di Ferie (es: 15/10/2026, oppure 15/10/2026 - 18/10/2026):'}


    # COMANDO /permesso
    if clean_text in ('/permesso', 'permesso'):
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_dati_permesso'}
        return {'text': 'Scrivi la data e gli orari del permesso (es: 15/10/2026 09:00 - 11:00):'}

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
                assegnazione = AssegnazioneTurno.objects.filter(
                    pk=assegnazione_id
                ).filter(
                    Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
                ).select_related('cliente', 'turno').distinct().first()
                if not assegnazione:
                    return {"text": "Turno non trovato o non appartiene alla tua squadra.", "reply_markup": get_main_menu()}
            except Exception:
                return {"text": "Errore nel recupero del turno.", "reply_markup": get_main_menu()}
            
            return _salva_ore_turno(dipendente, assegnazione, hours, text)
        
        # Attesa testo segnalazione
        
        # Attesa date malattia o ferie
        if action in ['attesa_date_malattia', 'attesa_date_ferie']:
            del _TELEGRAM_STATE[telegram_chat_id]
            import datetime
            tipo = 'MALATTIA' if action == 'attesa_date_malattia' else 'FERIE'
            # Parser data: DD/MM/YYYY (opzionale - DD/MM/YYYY)
            pattern = r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?'
            matches = re.findall(pattern, text)
            
            if not matches:
                return "Formato non riconosciuto. Riprova (es. 15/10/2026 oppure 15/10/2026 - 18/10/2026)."
            
            today = timezone.now().date()
            dates = []
            for m in matches:
                day, month = int(m[0]), int(m[1])
                year = int(m[2]) if m[2] else today.year
                if year < 100: year += 2000
                try:
                    dates.append(datetime.date(year, month, day))
                except ValueError:
                    return "Data non valida. Riprova."
            
            data_inizio = dates[0]
            data_fine = dates[-1]
            if data_fine < data_inizio:
                data_inizio, data_fine = data_fine, data_inizio
                
            return _gestisci_assenza_con_sostituzione(dipendente, tipo, f"Registrata {tipo}", "", data_inizio=data_inizio, data_fine=data_fine)
            
        # Attesa dati permesso
        if action == 'attesa_dati_permesso':
            del _TELEGRAM_STATE[telegram_chat_id]
            import datetime
            
            # Parser: 15/10/2026 09:00 - 11:00
            date_pattern = r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?'
            time_pattern = r'(\d{1,2}):(\d{2})'
            
            d_matches = re.findall(date_pattern, text)
            t_matches = re.findall(time_pattern, text)
            
            today = timezone.now().date()
            if not d_matches:
                data_permesso = today
            else:
                m = d_matches[0]
                day, month = int(m[0]), int(m[1])
                year = int(m[2]) if m[2] else today.year
                if year < 100: year += 2000
                try:
                    data_permesso = datetime.date(year, month, day)
                except ValueError:
                    return "Data non valida."
            
            if len(t_matches) < 2:
                return "Devi specificare sia l'ora di inizio che l'ora di fine (es. 09:00 - 11:00)."
                
            try:
                ora_inizio = datetime.time(int(t_matches[0][0]), int(t_matches[0][1]))
                ora_fine = datetime.time(int(t_matches[1][0]), int(t_matches[1][1]))
            except ValueError:
                return "Orari non validi."
                
            return _gestisci_assenza_con_sostituzione(dipendente, 'PERMESSO', "Permesso registrato", "", data_inizio=data_permesso, data_fine=data_permesso, ora_inizio=ora_inizio, ora_fine=ora_fine)

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


def _gestisci_assenza_con_sostituzione(dipendente, tipo_assenza, msg_conferma, msg_aggiuntivo, data_inizio=None, data_fine=None, ora_inizio=None, ora_fine=None):
    """
    Registra l'assenza in stato 'IN_ATTESA' e notifica l'Amministrazione.
    La procedura automatica di sostituzione per ogni turno partirà SOLTANTO DOPO l'avvallo dell'Amministrazione.
    """
    today = timezone.now().date()
    if not data_inizio:
        data_inizio = today
    if not data_fine:
        data_fine = data_inizio

    from .models import Assenza, AssegnazioneTurno, Squadra, Titolare
    from django.db.models import Q
    from django.conf import settings
    import requests as req
    import json
    
    # 1. Registra l'assenza in attesa di avvallo amministrazione
    assenza = Assenza.objects.create(
        dipendente=dipendente, tipo=tipo_assenza,
        data_inizio=data_inizio, data_fine=data_fine,
        ora_inizio=ora_inizio, ora_fine=ora_fine,
        note="Via bot Telegram (in attesa di avvallo)",
        source='TELEGRAM',
        stato_approvazione='IN_ATTESA',
        is_processed=False
    )
    
    # 2. Cerca turni nel periodo dove il dipendente è coinvolto
    squadre_dipendente = Squadra.objects.filter(
        Q(componenti=dipendente) | Q(caposquadra=dipendente)
    ).distinct()
    
    assegnazioni_oggi = AssegnazioneTurno.objects.filter(
        turno__data__range=[data_inizio, data_fine],
        turno__squadra__in=squadre_dipendente
    ).select_related('turno', 'turno__squadra', 'cliente')
    
    turni_scoperti = list(assegnazioni_oggi)
    
    # 3. Componi messaggio per il dipendente
    if data_inizio == data_fine:
        periodo_str = data_inizio.strftime('%d/%m/%Y')
    else:
        periodo_str = f"{data_inizio.strftime('%d/%m/%Y')} - {data_fine.strftime('%d/%m/%Y')}"
        
    testo = f"📩 {msg_conferma} per il periodo: {periodo_str}."
    if ora_inizio and ora_fine:
        testo += f" Dalle {ora_inizio.strftime('%H:%M')} alle {ora_fine.strftime('%H:%M')}."
    if msg_aggiuntivo:
        testo += f" {msg_aggiuntivo}"
        
    testo += "\n\n⏳ **In attesa di avvallo dell'Amministrazione**"
    if turni_scoperti:
        testo += f"\nHai {len(turni_scoperti)} turno/i nel periodo indicato. La procedura di sostituzione si avvierà in automatico **non appena l'Amministrazione avrà avvallato** la tua richiesta."
    else:
        testo += "\nNessun turno previsto per te nel periodo indicato."

    # 4. Notifica l'AMMINISTRAZIONE con tasti interattivi di Avvallo / Rifiuto
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if token:
        admin_chat_ids = set()
        admin_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
        if admin_id:
            admin_chat_ids.add(str(admin_id))
            
        try:
            for titolare in Titolare.objects.filter(notifiche_attive=True):
                cid = titolare.get_chat_id()
                if cid:
                    admin_chat_ids.add(str(cid))
        except Exception:
            pass

        orario_info = f"🕒 Orario: {ora_inizio.strftime('%H:%M')} - {ora_fine.strftime('%H:%M')}\n" if (ora_inizio and ora_fine) else ""
        
        turni_detail = ""
        if turni_scoperti:
            turni_detail = f"\n🚨 **Turni scoperti interessati ({len(turni_scoperti)}):**\n"
            for a in turni_scoperti:
                turni_detail += f"  👉 {a.cliente.ragione_sociale} ({a.orario_inizio_previsto.strftime('%H:%M')}-{a.orario_fine_previsto.strftime('%H:%M')}) 👥 {a.turno.squadra.nome}\n"
        else:
            turni_detail = "\nℹ️ Nessun turno previsto nel periodo."

        alert_admin = (
            f"⚠️ **COMUNICAZIONE ASSENZA DA AVVALLARE**\n\n"
            f"👤 **Dipendente**: {dipendente.cognome} {dipendente.nome}\n"
            f"📋 **Tipo**: {tipo_assenza}\n"
            f"📅 **Periodo**: {periodo_str}\n"
            f"{orario_info}"
            f"{turni_detail}\n"
            f"Clicca su **Avvalla** per approvare l'assenza e far partire in automatico la procedura di sostituzione."
        )

        keyboard_admin = {
            "inline_keyboard": [[
                {"text": "✅ Avvalla e Avvia Sostituzione", "callback_data": f"avvalla_assenza_{assenza.pk}"},
                {"text": "❌ Rifiuta Assenza", "callback_data": f"rifiuta_assenza_{assenza.pk}"}
            ]]
        }

        for cid in admin_chat_ids:
            try:
                req.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        'chat_id': cid,
                        'text': alert_admin,
                        'reply_markup': json.dumps(keyboard_admin),
                        'parse_mode': 'Markdown'
                    },
                    timeout=5
                )
            except Exception as e:
                print(f"[Alert Admin Error] {e}")

    # 5. Notifica preventiva al Responsabile Area
    try:
        from .models import ResponsabileArea
        ras = ResponsabileArea.objects.filter(squadre__in=squadre_dipendente).distinct()
        for ra in ras:
            if ra.dipendente.telegram_chat_id and token:
                msg_ra = (
                    f"ℹ️ COMUNICAZIONE ASSENZA (IN ATTESA AVVALLO ADMIN)\n\n"
                    f"👤 {dipendente.nome} {dipendente.cognome} ha registrato: {tipo_assenza}\n"
                    f"📅 Periodo: {periodo_str}\n"
                    f"⏳ La procedura di sostituzione si avvierà non appena l'Amministrazione avvallerà la richiesta."
                )
                try:
                    req.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json={'chat_id': ra.dipendente.telegram_chat_id, 'text': msg_ra},
                        timeout=5
                    )
                except Exception:
                    pass
    except Exception as e:
        print(f"[Notify RA Error] {e}")

    return {'text': testo, 'reply_markup': get_main_menu()}



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
    # Calendario - Oggi
    if callback_data == 'menu_calendario':
        oggi = timezone.now().date()
        return get_calendario_giornaliero(dipendente, oggi)
    
    # Calendario - Navigazione
    if callback_data.startswith('cal_prev_') or callback_data.startswith('cal_next_'):
        try:
            from datetime import datetime
            date_str = callback_data.split('_')[2]
            data_cal = datetime.strptime(date_str, '%Y-%m-%d').date()
            return get_calendario_giornaliero(dipendente, data_cal)
        except Exception:
            return {'text': 'Errore navigazione data.', 'reply_markup': get_main_menu()}

    # Turni da compilare
    if callback_data == 'menu_turni_mancanti':
        return {
            'text': "Turni senza ore (ultimi 7 giorni):\nSeleziona per inserire le ore.",
            'reply_markup': get_turni_non_compilati_keyboard(dipendente)
        }
    
    # Malattia
    if callback_data == 'menu_malattia':
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_date_malattia'}
        return {'text': 'Scrivi la data o il periodo di Malattia (es: 15/10/2026, oppure 15/10/2026 - 18/10/2026):'}
    
    # Ferie
    if callback_data == 'menu_ferie':
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_date_ferie'}
        return {'text': 'Scrivi la data o il periodo di Ferie (es: 15/10/2026, oppure 15/10/2026 - 18/10/2026):'}
    
    # Permesso
    if callback_data == 'menu_permesso':
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_dati_permesso'}
        return {'text': 'Scrivi la data e gli orari del permesso (es: 15/10/2026 09:00 - 11:00):'}
    
    # Segnalazione -> chiedi testo
    if callback_data == 'menu_segnalazione':
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'segnalazione'}
        return {'text': "Scrivi il testo della segnalazione:"}

    # Foto Profilo -> metti in attesa foto
    if callback_data == 'menu_foto_profilo':
        from django.core.cache import cache
        cache.set(f'pending_foto_profilo_{telegram_chat_id}', True, 300)  # 5 minuti
        return {
            'text': (
                "📸 Perfetto! Ora scatta una foto (o scegline una dalla galleria) "
                "e inviamela qui in chat.\n\n"
                "Diventerà la tua foto profilo nell'app Kandor. ✅\n"
                "Hai 5 minuti per inviarla."
            )
        }
    
    # Turno selezionato per ore
    if callback_data.startswith('ore_turno_'):
        assegnazione_id = callback_data.replace('ore_turno_', '')
        try:
            assegnazione = AssegnazioneTurno.objects.filter(
                pk=assegnazione_id
            ).select_related('cliente', 'turno', 'turno__squadra').first()
            if not assegnazione:
                return {'text': "Turno non trovato.", 'reply_markup': get_main_menu()}
        except Exception:
            return {'text': "Errore nel recupero del turno.", 'reply_markup': get_main_menu()}
        
        data_str = assegnazione.turno.data.strftime('%d/%m') if assegnazione.turno else ''
        inizio = assegnazione.orario_inizio_previsto.strftime('%H:%M') if assegnazione.orario_inizio_previsto else '?'
        fine = assegnazione.orario_fine_previsto.strftime('%H:%M') if assegnazione.orario_fine_previsto else '?'
        
        # Calcola ore previste dall'orario
        _ore_previste = None
        try:
            from datetime import datetime as _dtt, date as _datec
            _dt_start = _dtt.combine(_datec.today(), assegnazione.orario_inizio_previsto)
            _dt_end = _dtt.combine(_datec.today(), assegnazione.orario_fine_previsto)
            _diff = (_dt_end - _dt_start).seconds / 3600
            _ore_previste = round(_diff, 2)
        except Exception:
            pass

        # Controlla se le ore per questo turno sono GIÀ state inserite da un altro collega della squadra
        tt_squadra = TimeTracking.objects.filter(assegnazione=assegnazione).exclude(dipendente=dipendente).first()
        if tt_squadra and tt_squadra.ore_dichiarate:
            return {
                'text': f"ℹ️ Le ore per il turno {assegnazione.cliente.ragione_sociale} ({data_str}) "
                        f"sono già state registrate dal tuo collega {tt_squadra.dipendente.nome} {tt_squadra.dipendente.cognome} ({tt_squadra.ore_dichiarate}h).\n\n"
                        f"Non occorre che le inserisci nuovamente! 👍",
                'reply_markup': get_main_menu()
            }

        # Controlla se esiste già un TimeTracking per pre-popolare
        _tt_esistente = TimeTracking.objects.filter(assegnazione=assegnazione, dipendente=dipendente).first()

        _TELEGRAM_STATE[telegram_chat_id] = {
            'action': 'attesa_ore',
            'assegnazione_id': assegnazione.pk
        }
        _prompt = f"Turno: {assegnazione.cliente.ragione_sociale}\nData: {data_str} ({inizio}-{fine})\n"
        if _ore_previste:
            _prompt += f"⏱ Ore previste: {_ore_previste}h\n"
        if _tt_esistente and _tt_esistente.ore_dichiarate:
            _prompt += f"✅ Ore già registrate: {_tt_esistente.ore_dichiarate}h\n"
        _prompt += "\nQuante ore hai lavorato?\n(Scrivi il numero, es: 8 o 7.5 - invio per confermare le ore previste)"
        return {'text': _prompt}

    # Callback per conferma squadra al completo
    if callback_data.startswith('conf_squadra_si_'):
        assign_id = callback_data.replace('conf_squadra_si_', '')
        try:
            assign = AssegnazioneTurno.objects.select_related('cliente').get(pk=assign_id)
            return {
                'text': f"✅ Perfetto, presenza confermata per tutti i componenti della squadra per il turno {assign.cliente.ragione_sociale}.\n\nLe ore sono state contabilizzate per l'intero gruppo.",
                'reply_markup': get_main_menu()
            }
        except Exception:
            return {'text': "Errore nella conferma della squadra.", 'reply_markup': get_main_menu()}

    # Callback per segnalazione componente assente
    if callback_data.startswith('conf_squadra_no_'):
        assign_id = callback_data.replace('conf_squadra_no_', '')
        try:
            assign = AssegnazioneTurno.objects.select_related('cliente', 'turno__squadra__caposquadra').get(pk=assign_id)
            squadra = (assign.turno.squadra if (assign.turno and assign.turno.squadra) else None)
            if not squadra:
                from .models import Squadra
                squadra = Squadra.objects.filter(Q(componenti=dipendente) | Q(caposquadra=dipendente)).first()

            esclusi_ids = set(assign.dipendenti_esclusi.values_list('pk', flat=True))
            altri_comp = []
            if squadra:
                if squadra.caposquadra and squadra.caposquadra != dipendente and squadra.caposquadra.pk not in esclusi_ids:
                    altri_comp.append(squadra.caposquadra)
                for c in squadra.componenti.exclude(pk=squadra.caposquadra.pk if squadra.caposquadra else None):
                    if c != dipendente and c.pk not in esclusi_ids and c not in altri_comp:
                        altri_comp.append(c)

            keyboard = []
            for c in altri_comp:
                keyboard.append([{'text': f"❌ {c.nome} {c.cognome} (Segnala assente)", 'callback_data': f'conf_escludi_{assign_id}_{c.pk}'}])
            keyboard.append([{'text': "✅ Fatto / Nessun altro assente", 'callback_data': 'menu_start'}])

            return {
                'text': f"Seleziona chi mancava per il turno {assign.cliente.ragione_sociale}:",
                'reply_markup': {'inline_keyboard': keyboard}
            }
        except Exception as e:
            return {'text': f"Errore nel recupero componenti: {e}", 'reply_markup': get_main_menu()}

    # Callback per escludere uno specifico dipendente assente
    if callback_data.startswith('conf_escludi_'):
        raw = callback_data.replace('conf_escludi_', '')
        parts = raw.split('_')
        if len(parts) >= 2:
            assign_id, dip_assente_id = parts[0], parts[1]
            try:
                assign = AssegnazioneTurno.objects.select_related('cliente', 'turno').get(pk=assign_id)
                dip_assente = Dipendente.objects.get(pk=dip_assente_id)
                assign.dipendenti_esclusi.add(dip_assente)
                TimeTracking.objects.filter(assegnazione=assign, dipendente=dip_assente).delete()
                
                # Invia avviso al dipendente contrassegnato assente se ha Telegram
                if dip_assente.telegram_chat_id:
                    data_str = assign.turno.data.strftime('%d/%m/%Y') if assign.turno else ''
                    send_telegram_message(
                        dip_assente.telegram_chat_id,
                        f"⚠️ Sei stato segnalato come ASSENTE per il turno {assign.cliente.ragione_sociale} del {data_str}.\n"
                        f"Se si tratta di un errore, contatta il tuo caposquadra o amministratore."
                    )

                return {
                    'text': f"🚫 {dip_assente.nome} {dip_assente.cognome} è stato segnato come ASSENTE per il turno {assign.cliente.ragione_sociale}.\n\nLe ore per gli altri componenti rimangono confermate.",
                    'reply_markup': get_main_menu()
                }
            except Exception as e:
                return {'text': f"Errore nell'esclusione: {e}", 'reply_markup': get_main_menu()}

    # ===== GESTIONE AVVALLO AMMINISTRAZIONE ASSENZE =====

    if callback_data.startswith('avvalla_assenza_'):
        assenza_id = callback_data.replace('avvalla_assenza_', '')
        try:
            from .services import avvalla_assenza_da_amministrazione
            res = avvalla_assenza_da_amministrazione(assenza_id)
            if res.get('ok'):
                return {
                    'text': f"✅ ASSENZA AVVALATA DALL'AMMINISTRAZIONE!\n\n"
                            f"Procedura automatica di sostituzione avviata.\n"
                            f"Richieste sostituzione create: {res.get('num_sostituzioni', 0)}"
                }
            return {'text': f"❌ Errore nell'avvallo dell'assenza: {res.get('error')}"}
        except Exception as e:
            return {'text': f"❌ Errore: {e}"}

    if callback_data.startswith('rifiuta_assenza_'):
        assenza_id = callback_data.replace('rifiuta_assenza_', '')
        try:
            from .services import rifiuta_assenza_da_amministrazione
            res = rifiuta_assenza_da_amministrazione(assenza_id)
            if res.get('ok'):
                return {'text': "❌ Comunicazione di assenza RIFIUTATA dall'Amministrazione.\nIl dipendente è stato notificato."}
            return {'text': f"❌ Errore nel rifiuto: {res.get('error')}"}
        except Exception as e:
            return {'text': f"❌ Errore: {e}"}

    # ===== GESTIONE SOSTITUTI =====
    
    # Responsabile Area approva la richiesta di sostituzione
    if callback_data.startswith('approva_sost_'):
        richiesta_id = callback_data.replace('approva_sost_', '')
        try:
            from .models import RichiestaSostituzione
            from .services import approva_e_invia_sostituto
            richiesta = RichiestaSostituzione.objects.get(pk=richiesta_id)
            richiesta.stato = 'APPROVATA_RA'
            richiesta.approvata_ra_il = timezone.now()
            richiesta.save()
            approva_e_invia_sostituto(richiesta.pk)
            return {
                'text': f"✅ Richiesta approvata!\n"
                        f"Sostituzione per {richiesta.dipendente_assente} inviata al primo sostituto disponibile.\n"
                        f"Candidati nella coda: {len(richiesta.sostituti_candidati)}"
            }
        except Exception as e:
            return {'text': f"❌ Errore nell'approvazione: {e}"}
    
    # Responsabile Area rifiuta la sostituzione
    if callback_data.startswith('rifiuta_sost_ra_'):
        richiesta_id = callback_data.replace('rifiuta_sost_ra_', '')
        try:
            from .models import RichiestaSostituzione
            richiesta = RichiestaSostituzione.objects.get(pk=richiesta_id)
            richiesta.stato = 'ANNULLATA'
            richiesta.note += '\nRifiutata dal Responsabile Area.'
            richiesta.save()
            return {'text': "❌ Richiesta di sostituzione annullata."}
        except Exception as e:
            return {'text': f"❌ Errore: {e}"}
    
    # Sostituto accetta la richiesta
    if callback_data.startswith('accetta_sost_'):
        richiesta_id = callback_data.replace('accetta_sost_', '')
        try:
            from .services import gestisci_risposta_sostituto
            risultato = gestisci_risposta_sostituto(int(richiesta_id), accettato=True)
            if risultato and risultato.stato == 'COMPLETATA':
                assegn = risultato.assegnazione_originale
                return {
                    'text': f"✅ Sostituzione CONFERMATA!\n\n"
                            f"📍 Cliente: {assegn.cliente.ragione_sociale}\n"
                            f"📅 Data: {assegn.turno.data.strftime('%d/%m/%Y')}\n"
                            f"🕐 Orario: {assegn.orario_inizio_previsto.strftime('%H:%M')}-"
                            f"{assegn.orario_fine_previsto.strftime('%H:%M')}\n\n"
                            f"Grazie per la disponibilità! 👍"
                }
            return {'text': "⚠️ Errore nel confermare la sostituzione."}
        except Exception as e:
            return {'text': f"❌ Errore: {e}"}
    
    # Sostituto rifiuta la richiesta
    if callback_data.startswith('rifiuta_sost_'):
        richiesta_id = callback_data.replace('rifiuta_sost_', '')
        try:
            from .services import gestisci_risposta_sostituto
            risultato = gestisci_risposta_sostituto(int(richiesta_id), accettato=False)
            if risultato:
                return {'text': "Ok, richiesta passata al prossimo sostituto disponibile."}
            else:
                return {'text': "Richiesta rifiutata. Nessun altro sostituto disponibile."}
        except Exception as e:
            return {'text': f"❌ Errore: {e}"}
    
    return {'text': "Comando non riconosciuto.", 'reply_markup': get_main_menu()}


def _salva_ore_turno(dipendente, assegnazione, hours, original_text):
    """Salva le ore lavorate per una specifica assegnazione turno ed estende la registrazione a tutta la squadra con notifiche Telegram."""
    from decimal import Decimal
    from .models import Squadra
    decimal_hours = Decimal(str(hours))

    # 1. Salva le ore per il dipendente che le ha digitate
    tt, created = TimeTracking.objects.update_or_create(
        dipendente=dipendente,
        assegnazione=assegnazione,
        defaults={
            'ore_dichiarate': decimal_hours,
            'source': 'TELEGRAM',
            'note': f"Registrato da {dipendente.nome} {dipendente.cognome}",
            'is_validated': False,
        }
    )

    # 2. Recupera la squadra (dal turno o di appartenenza)
    squadra = (assegnazione.turno.squadra if (assegnazione.turno and assegnazione.turno.squadra) else None)
    if not squadra:
        squadra = Squadra.objects.filter(Q(componenti=dipendente) | Q(caposquadra=dipendente)).first()

    esclusi_ids = set(assegnazione.dipendenti_esclusi.values_list('pk', flat=True))

    altri_comp = []
    if squadra:
        if squadra.caposquadra and squadra.caposquadra != dipendente and squadra.caposquadra.pk not in esclusi_ids:
            altri_comp.append(squadra.caposquadra)
        for c in squadra.componenti.exclude(pk=squadra.caposquadra.pk if squadra.caposquadra else None):
            if c != dipendente and c.pk not in esclusi_ids and c not in altri_comp:
                altri_comp.append(c)

    # 3. Crea/aggiorna TimeTracking anche per gli altri componenti della squadra
    for alt_dip in altri_comp:
        TimeTracking.objects.update_or_create(
            dipendente=alt_dip,
            assegnazione=assegnazione,
            defaults={
                'ore_dichiarate': decimal_hours,
                'source': 'TELEGRAM',
                'note': f"Registrato dal collega {dipendente.nome} {dipendente.cognome}",
                'is_validated': False,
            }
        )

    data_str = assegnazione.turno.data.strftime('%d/%m/%Y') if (assegnazione.turno and assegnazione.turno.data) else ''
    action = "Salvato" if created else "Aggiornato"

    # 4. INVIA NOTIFICA TELEGRAM PROATTIVA A TUTTI GLI ALTRI COMPONENTI DELLA SQUADRA
    sq_nome = squadra.nome if squadra else 'Squadra'
    for alt_dip in altri_comp:
        if alt_dip.telegram_chat_id:
            msg_collega = (
                f"ℹ️ AGGIORNAMENTO SQUADRA ({sq_nome})\n\n"
                f"Il tuo collega {dipendente.nome} {dipendente.cognome} ha già registrato le ore "
                f"({hours}h) per il turno {assegnazione.cliente.ragione_sociale} del {data_str}.\n\n"
                f"Le tue ore sono state registrate automaticamente! 👍"
            )
            send_telegram_message(alt_dip.telegram_chat_id, msg_collega)

    # 5. SE CI SONO ALTRI COMPONENTI, CHIEDI LA VERIFICA PRESENZA SQUADRA A CHI HA SCRITTO
    if altri_comp:
        nomi_comp = "\n".join([f"• {c.nome} {c.cognome}" for c in altri_comp])
        prompt_text = (
            f"✅ {action}! {hours}h per {assegnazione.cliente.ragione_sociale} ({data_str}).\n\n"
            f"👥 Confermi la presenza anche degli altri componenti della squadra?\n"
            f"{nomi_comp}"
        )
        keyboard = {
            'inline_keyboard': [
                [{'text': '✅ Sì, squadra al completo', 'callback_data': f'conf_squadra_si_{assegnazione.pk}'}],
                [{'text': '⚠️ No, mancava qualcuno', 'callback_data': f'conf_squadra_no_{assegnazione.pk}'}],
                [{'text': '🏠 Menu Principale', 'callback_data': 'menu_start'}]
            ]
        }
        return {'text': prompt_text, 'reply_markup': keyboard}

    return {
        'text': f"✅ {action}! {hours}h per {assegnazione.cliente.ragione_sociale} ({data_str}).",
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
        # Utilizziamo un raggio fisso di 150 metri poiché il modello Cliente non ha raggio_prossimita
        raggio = 150.0
        is_inside = dist <= raggio
        
        last_log = ProximityLog.objects.filter(
            dipendente=dipendente, cliente=cliente
        ).first()
        
        was_inside = last_log.is_near if last_log else False
        
        if is_inside != was_inside:
            log_obj, created = ProximityLog.objects.get_or_create(
                dipendente=dipendente,
                cliente=cliente
            )
            log_obj.is_near = is_inside
            if is_inside:
                log_obj.entered_at = timezone.now()
            else:
                log_obj.exited_at = timezone.now()
            log_obj.save()
            
            if is_inside:
                events.append({'type': 'entry', 'cliente': cliente, 'distanza': dist})
            else:
                events.append({'type': 'exit', 'cliente': cliente, 'distanza': dist})
    
    return events
