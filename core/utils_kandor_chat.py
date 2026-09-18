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


def _gestisci_assenza_con_sostituzione(dipendente, tipo_assenza, msg_conferma, msg_aggiuntivo):
    """
    Registra l'assenza e verifica se il dipendente aveva turni oggi.
    Se sì, avvia automaticamente la procedura di sostituzione per ogni turno.
    """
    today = timezone.now().date()
    from .models import Assenza, AssegnazioneTurno, Squadra
    from django.db.models import Q
    
    # 1. Registra l'assenza
    Assenza.objects.create(
        dipendente=dipendente, tipo=tipo_assenza,
        data_inizio=today, data_fine=today,
        note="Via bottone Telegram", source='TELEGRAM'
    )
    
    # 2. Cerca turni di oggi dove il dipendente è coinvolto (come componente o caposquadra)
    squadre_dipendente = Squadra.objects.filter(
        Q(componenti=dipendente) | Q(caposquadra=dipendente)
    ).distinct()
    
    assegnazioni_oggi = AssegnazioneTurno.objects.filter(
        turno__data=today,
        turno__squadra__in=squadre_dipendente
    ).select_related('turno', 'turno__squadra', 'cliente')
    
    turni_scoperti = list(assegnazioni_oggi)
    
    # 3. Componi messaggio base
    testo = f"{msg_conferma} per oggi ({today.strftime('%d/%m')})."
    if msg_aggiuntivo:
        testo += f" {msg_aggiuntivo}"
    
    # 4. Se ci sono turni, avvia la sostituzione automatica
    if turni_scoperti:
        testo += f"\n\n⚠️ ATTENZIONE: Hai {len(turni_scoperti)} turno/i oggi!\n"
        
        richieste_create = 0
        for assegnazione in turni_scoperti:
            testo += f"  • {assegnazione.cliente.ragione_sociale} ({assegnazione.orario_inizio_previsto.strftime('%H:%M')}-{assegnazione.orario_fine_previsto.strftime('%H:%M')})\n"
            
            try:
                from .services import crea_richiesta_sostituzione
                motivo_map = {
                    'MALATTIA': 'MALATTIA',
                    'FERIE': 'FERIE',
                    'PERMESSO': 'PERMESSO',
                }
                crea_richiesta_sostituzione(
                    assegnazione, 
                    dipendente, 
                    motivo_map.get(tipo_assenza, 'ALTRO'),
                    f"Comunicato via Telegram"
                )
                richieste_create += 1
            except Exception as e:
                print(f"[Sostituzione Auto] Errore per assegnazione {assegnazione.pk}: {e}")
        
        if richieste_create > 0:
            testo += f"\n🔄 Procedura sostituzione avviata per {richieste_create} turno/i."
            testo += "\nIl Responsabile Area è stato notificato."
        
        # Notifica anche l'admin via Telegram (se configurato)
        try:
            from django.conf import settings
            admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
            if admin_chat_id:
                token = settings.TELEGRAM_BOT_TOKEN
                alert_msg = (
                    f"🚨 ALERT ASSENZA\n\n"
                    f"👤 {dipendente.cognome} {dipendente.nome} ha comunicato {tipo_assenza}\n"
                    f"📅 Data: {today.strftime('%d/%m/%Y')}\n"
                    f"⚠️ Turni scoperti: {len(turni_scoperti)}\n"
                )
                for a in turni_scoperti:
                    alert_msg += f"  • {a.cliente.ragione_sociale} ({a.orario_inizio_previsto.strftime('%H:%M')}-{a.orario_fine_previsto.strftime('%H:%M')}) — Squadra: {a.turno.squadra.nome}\n"
                alert_msg += "\n🔄 Procedura sostituzione avviata automaticamente."
                
                import requests as req
                req.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={'chat_id': admin_chat_id, 'text': alert_msg}
                )
        except Exception:
            pass
    
    return {
        'text': testo,
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
        return _gestisci_assenza_con_sostituzione(dipendente, 'MALATTIA', 'Registrata MALATTIA', 'Riposati!')
    
    # Ferie
    if callback_data == 'menu_ferie':
        return _gestisci_assenza_con_sostituzione(dipendente, 'FERIE', 'Ferie registrate', 'Buon relax!')
    
    # Permesso
    if callback_data == 'menu_permesso':
        return _gestisci_assenza_con_sostituzione(dipendente, 'PERMESSO', 'Permesso registrato', '')
    
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
            ).filter(
                Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
            ).select_related('cliente', 'turno').distinct().first()
            if not assegnazione:
                return {'text': "Turno non trovato o non appartiene alla tua squadra.", 'reply_markup': get_main_menu()}
        except Exception:
            return {'text': "Errore nel recupero del turno.", 'reply_markup': get_main_menu()}
        
        data_str = assegnazione.turno.data.strftime('%d/%m')
        inizio = assegnazione.orario_inizio_previsto.strftime('%H:%M')
        fine = assegnazione.orario_fine_previsto.strftime('%H:%M')
        
        _TELEGRAM_STATE[telegram_chat_id] = {
            'action': 'attesa_ore',
            'assegnazione_id': assegnazione.pk
        }
        return {'text': f"Turno: {assegnazione.cliente.ragione_sociale}\n"
                       f"Data: {data_str} ({inizio}-{fine})\n\n"
                       f"Quante ore hai lavorato?\n(Scrivi il numero, es: 8 o 7.5)"}
    
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
