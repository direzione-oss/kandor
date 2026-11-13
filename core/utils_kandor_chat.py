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
        
        assegnazioni = list(
            AssegnazioneTurno.objects.filter(
                turno__data=data_calendario
            ).filter(
                Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
            ).select_related('cliente', 'turno', 'turno__squadra').distinct().order_by('orario_inizio_previsto')
        )
        
        testo = f"📅 Calendario del {data_calendario.strftime('%d/%m/%Y')}\n\n"
        
        if not assegnazioni:
            testo += "Nessun turno assegnato per questa giornata.\n"
        else:
            tt_map = {
                t.assegnazione_id: t
                for t in TimeTracking.objects.filter(
                    dipendente=dipendente,
                    assegnazione_id__in=[a.id for a in assegnazioni],
                )
            }
            for a in assegnazioni:
                inizio = a.orario_inizio_previsto.strftime('%H:%M') if a.orario_inizio_previsto else '?'
                fine = a.orario_fine_previsto.strftime('%H:%M') if a.orario_fine_previsto else '?'
                cliente_nome = a.cliente.ragione_sociale if a.cliente else 'Cliente'
                squadra_nome = a.turno.squadra.nome if (a.turno and a.turno.squadra) else 'Squadra'
                
                testo += f"🏢 *{cliente_nome}*\n"
                testo += f"🕒 {inizio} - {fine} (Squadra: {squadra_nome})\n"
                
                # Note/mansioni del turno (inserite dall'app)
                if a.mansione_svolta:
                    testo += f"📋 Mansione: {a.mansione_svolta}\n"
                
                # Usa TimeTracking pre-caricato in batch
                tt = tt_map.get(a.id)
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
        return {'text': f'Errore calendario: {str(e)}', 'reply_markup': get_main_menu(dipendente)}


def get_main_menu(dipendente=None):
    """Ritorna il menu principale con bottoni inline."""
    keyboard = [
        [{'text': '⏱ Registra Ore', 'callback_data': 'menu_ore'}],
        [{'text': '📅 Calendario', 'callback_data': 'menu_calendario'}],
        [{'text': '📋 Turni da compilare', 'callback_data': 'menu_turni_mancanti'}],
        [{'text': 'Malattia', 'callback_data': 'menu_malattia'},
         {'text': 'Ferie', 'callback_data': 'menu_ferie'}],
    ]
    if dipendente and getattr(dipendente, 'usufruisce_104', False):
        keyboard.append([{'text': 'Permesso', 'callback_data': 'menu_permesso'},
                         {'text': 'Legge 104', 'callback_data': 'menu_104'}])
        keyboard.append([{'text': '🧴 Richiedi Materiali', 'callback_data': 'menu_materiali'},
                         {'text': '🚨 Segnalazione', 'callback_data': 'menu_segnalazione'}])
    else:
        keyboard.append([{'text': 'Permesso', 'callback_data': 'menu_permesso'},
                         {'text': '🚨 Segnalazione', 'callback_data': 'menu_segnalazione'}])
        keyboard.append([{'text': '🧴 Richiedi Materiali Cantiere', 'callback_data': 'menu_materiali'}])
    
    keyboard.extend([
        [{'text': '📄 Buste Paga', 'callback_data': 'menu_buste_paga'},
         {'text': '📸 Foto Profilo', 'callback_data': 'menu_foto_profilo'}],
        [{'text': '📖 Guida', 'url': 'https://kandor.187.126.30.207.sslip.io/manuale-dipendente/'}],
    ])
    return {'inline_keyboard': keyboard}

def get_turni_oggi_keyboard(dipendente):
    """Ritorna tastiera inline con i turni di OGGI del dipendente."""
    try:
        today = timezone.now().date()
        assegnazioni = list(
            AssegnazioneTurno.objects.filter(
                turno__data=today
            ).filter(
                Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
            ).select_related('cliente', 'turno').distinct()
        )
        compilati_ids = set(
            TimeTracking.objects.filter(
                dipendente=dipendente,
                assegnazione_id__in=[a.id for a in assegnazioni],
            ).values_list('assegnazione_id', flat=True)
        ) if assegnazioni else set()
        
        keyboard = []
        for a in assegnazioni:
            inizio = a.orario_inizio_previsto.strftime('%H:%M') if a.orario_inizio_previsto else '?'
            fine = a.orario_fine_previsto.strftime('%H:%M') if a.orario_fine_previsto else '?'
            cliente_nome = a.cliente.ragione_sociale[:20] if a.cliente else 'N/D'
            label = f"{cliente_nome} ({inizio}-{fine})"
            if a.id in compilati_ids:
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
    """Ritorna tastiera con turni passati senza ore compilate (ultimi 31 giorni)."""
    try:
        from datetime import timedelta as td
        today = timezone.now().date()
        trentuno_giorni_fa = today - td(days=31)
        
        assegnazioni = list(
            AssegnazioneTurno.objects.filter(
                turno__data__gte=trentuno_giorni_fa,
                turno__data__lte=today,
            ).filter(
                Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
            ).exclude(
                dipendenti_esclusi=dipendente
            ).select_related('cliente', 'turno').order_by('-turno__data').distinct()
        )
        compilati_ids = set(
            TimeTracking.objects.filter(
                dipendente=dipendente,
                assegnazione_id__in=[a.id for a in assegnazioni],
            ).values_list('assegnazione_id', flat=True)
        ) if assegnazioni else set()
        
        keyboard = []
        for a in assegnazioni:
            if a.id not in compilati_ids:
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


# ==============================================================================
# STATO CONVERSAZIONALE TELEGRAM PERSISTENTE (MULTI-WORKER & DB-BACKED)
# ==============================================================================

TELEGRAM_STATE_TTL_SECONDS = 86400  # 24 ore di validità massima per uno stato conversazionale aperto


class PersistentTelegramStateStore:
    """
    Dizionario persistente per lo stato conversazionale multi-step del bot Telegram.
    Salva e legge da `TelegramConversationState` su database (con fallback in memoria/cache),
    normalizzando sempre le chiavi `chat_id` a stringa (`str(chat_id).strip()`).
    """
    def __init__(self):
        self._fallback = {}

    @staticmethod
    def _norm(key):
        return str(key).strip() if key is not None else ''

    def get(self, key, default=None):
        k = self._norm(key)
        if not k:
            return default
        try:
            from .models import TelegramConversationState
            obj = TelegramConversationState.objects.filter(pk=k).first()
            if obj is not None:
                # Scadenza automatica dopo 24 ore per evitare stati appesi
                if obj.updated_at and (timezone.now() - obj.updated_at).total_seconds() > TELEGRAM_STATE_TTL_SECONDS:
                    obj.delete()
                    self._fallback.pop(k, None)
                    return default
                return dict(obj.state_data) if isinstance(obj.state_data, dict) else obj.state_data
            return default
        except Exception:
            return self._fallback.get(k, default)

    def __getitem__(self, key):
        val = self.get(key, default=None)
        if val is None:
            raise KeyError(self._norm(key))
        return val

    def __setitem__(self, key, value):
        k = self._norm(key)
        if not k:
            return
        clean_val = dict(value) if isinstance(value, dict) else value
        self._fallback[k] = clean_val
        try:
            from django.core.cache import cache
            cache.set(f"tg_conv_state_{k}", clean_val, TELEGRAM_STATE_TTL_SECONDS)
        except Exception:
            pass
        try:
            from .models import TelegramConversationState
            TelegramConversationState.objects.update_or_create(
                chat_id=k,
                defaults={'state_data': clean_val},
            )
        except Exception:
            pass

    def pop(self, key, default=None):
        k = self._norm(key)
        if not k:
            return default
        val = self.get(k, default=default)
        self._fallback.pop(k, None)
        try:
            from django.core.cache import cache
            cache.delete(f"tg_conv_state_{k}")
        except Exception:
            pass
        try:
            from .models import TelegramConversationState
            TelegramConversationState.objects.filter(pk=k).delete()
        except Exception:
            pass
        return val

    def __delitem__(self, key):
        self.pop(key, default=None)

    def __contains__(self, key):
        return self.get(key, default=None) is not None

    def clear(self):
        self._fallback.clear()
        try:
            from .models import TelegramConversationState
            TelegramConversationState.objects.all().delete()
        except Exception:
            pass


_TELEGRAM_STATE = PersistentTelegramStateStore()


def get_telegram_state(chat_id, default=None):
    return _TELEGRAM_STATE.get(chat_id, default=default)


def set_telegram_state(chat_id, state_dict):
    _TELEGRAM_STATE[chat_id] = state_dict


def clear_telegram_state(chat_id):
    return _TELEGRAM_STATE.pop(chat_id, None)


def _gestisci_accreditamento_telegram(telegram_chat_id, text, sender_name="Utente"):
    """
    Gestisce l'accreditamento sicuro di un nuovo account Telegram tramite Codice Fiscale + PIN a 4 cifre.
    Impedisce:
    - duplicazione di telegram_chat_id su più dipendenti
    - sovrascrittura di un dipendente che ha GIÀ un altro telegram_chat_id collegato (blocco secondo telefono)
    - tentativi ripetuti (rate-limit 5 tentativi / 15 min)
    """
    from django.core.cache import cache

    chat_id_str = str(telegram_chat_id).strip()

    # Se il chat_id appartiene a un dipendente INATTIVO, blocca subito
    if Dipendente.objects.filter(telegram_chat_id=chat_id_str, stato='INATTIVO').exists():
        return "⛔ Il tuo profilo dipendente risulta non attivo. Contatta l'Amministrazione."

    fail_key = f"tg_auth_fail_{chat_id_str}"
    pending_cf_key = f"tg_auth_cf_{chat_id_str}"
    fail_count = cache.get(fail_key, 0)
    if fail_count >= 5:
        return (
            f"⛔ Troppi tentativi errati di accreditamento. Per sicurezza riprova tra 15 minuti "
            f"oppure comunica il tuo ID Telegram ({chat_id_str}) direttamente all'Amministrazione."
        )

    raw = (text or '').strip()
    upper_raw = raw.upper()

    # Cerca Codice Fiscale (16 caratteri alfanumerici) e/o PIN (4 cifre) nel messaggio
    cf_match = re.search(r'\b([A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])\b', upper_raw)
    pin_match = re.search(r'\b(\d{4})\b', upper_raw)

    st = _TELEGRAM_STATE.get(chat_id_str, {})
    saved_cf = cache.get(pending_cf_key) or (st.get('auth_cf') if st.get('action') == 'attesa_pin_accreditamento' else None)

    cf_val = cf_match.group(1) if cf_match else None
    pin_val = pin_match.group(1) if pin_match else None

    # Caso 1: L'utente ha inviato solo il Codice Fiscale -> chiedi il PIN di 4 cifre
    if cf_val and not pin_val:
        cache.set(pending_cf_key, cf_val, 600)
        _TELEGRAM_STATE[chat_id_str] = {'action': 'attesa_pin_accreditamento', 'auth_cf': cf_val}
        return (
            f"🔐 Codice Fiscale ricevuto ({cf_val}).\n"
            f"Ora rispondi scrivendo il tuo PIN personale di 4 cifre per completare l'accreditamento:"
        )

    # Caso 2: L'utente aveva già inviato il CF e ora invia il PIN di 4 cifre
    if not cf_val and saved_cf and pin_val and len(raw.replace(' ', '')) == 4:
        cf_val = saved_cf

    # Caso 3: Abbiamo sia Codice Fiscale sia PIN -> verifica e accredita
    if cf_val and pin_val:
        cache.delete(pending_cf_key)
        _TELEGRAM_STATE.pop(chat_id_str, None)

        cand = Dipendente.objects.filter(codice_fiscale__iexact=cf_val).first()
        cand_pin = (cand.pin_accesso or '').strip() if cand else ''

        if not cand or not cand_pin or cand_pin != pin_val:
            new_fails = fail_count + 1
            cache.set(fail_key, new_fails, 900)
            return (
                f"❌ Codice Fiscale o PIN non corretti (tentativo {new_fails}/5).\n"
                f"Verifica i dati e riprova (scrivendo CODICE FISCALE e PIN, es: RSSMRA80A01H501U 1234) "
                f"oppure invia il tuo ID Telegram ({chat_id_str}) all'Amministrazione."
            )

        if cand.stato != 'ATTIVO':
            return "⛔ Questo profilo dipendente risulta non attivo. Contatta l'Amministrazione."

        existing_tg = (cand.telegram_chat_id or '').strip()
        if existing_tg and existing_tg != chat_id_str:
            # Blocco furto identità / secondo telefono non autorizzato (senza inviare messaggi allarmanti al dipendente)
            return (
                f"⛔ Blocco di sicurezza: il profilo di {cand.cognome} {cand.nome} è GIÀ collegato a un account Telegram.\n"
                f"Per impedire che qualcuno entri a nome di un collega, non è consentito collegare un secondo telefono in autonomia.\n"
                f"Se hai cambiato telefono, contatta l'Amministrazione comunicando il tuo ID: {chat_id_str}"
            )

        # Verifica che questo chat_id non sia associato a nessun altro record
        altro = Dipendente.objects.filter(telegram_chat_id=chat_id_str).exclude(pk=cand.pk).first()
        if altro:
            return (
                f"⛔ Questo account Telegram (ID: {chat_id_str}) risulta già collegato a un altro dipendente. "
                f"Contatta l'Amministrazione."
            )

        cand.telegram_chat_id = chat_id_str
        cand.save(update_fields=['telegram_chat_id'])
        cache.delete(fail_key)

        return {
            'text': (
                f"✅ Accreditamento completato in sicurezza!\n"
                f"Benvenuto/a {cand.nome} {cand.cognome}, il tuo account Telegram (ID: {chat_id_str}) "
                f"è ora collegato in modo esclusivo al tuo profilo.\n\nCosa vuoi fare?"
            ),
            'reply_markup': get_main_menu(cand)
        }

    # Messaggio predefinito per utente non ancora accreditato
    return (
        f"Non ti conosco! Il tuo ID Telegram e': {chat_id_str}\n\n"
        f"🔐 Per abilitarti subito in sicurezza, rispondi scrivendo il tuo CODICE FISCALE seguito dal tuo PIN di 4 cifre "
        f"(esempio: RSSMRA80A01H501U 1234), oppure invia questo ID all'amministratore per farti abilitare."
    )


def handle_telegram_message(telegram_chat_id, text, sender_name="Utente"):
    """
    Logica principale con supporto comandi e menu interattivo.
    Ritorna stringa o dict con text + reply_markup.
    """
    dipendenti = Dipendente.objects.filter(telegram_chat_id=telegram_chat_id, stato='ATTIVO')
    
    if not dipendenti.exists():
        return _gestisci_accreditamento_telegram(telegram_chat_id, text, sender_name=sender_name)
    
    dipendente = dipendenti.first()
    clean_text = normalize_text(text)
    
    # COMANDI /start e /menu
    if clean_text in ('/start', '/menu', 'menu', 'start'):
        _TELEGRAM_STATE.pop(telegram_chat_id, None)
        return {
            'text': f"Ciao {dipendente.nome}! Cosa vuoi fare?",
            'reply_markup': get_main_menu(dipendente)
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

    # COMANDO /104
    if clean_text in ('/104', '104'):
        if getattr(dipendente, 'usufruisce_104', False):
            _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_dati_104'}
            return {'text': 'Scrivi la data o il periodo per la Legge 104 (es: 15/10/2026, oppure 15/10/2026 - 18/10/2026):'}
        else:
            return {'text': 'La tua scheda dipendente non prevede la Legge 104.', 'reply_markup': get_main_menu(dipendente)}

    # SEGNALAZIONE
    if clean_text.startswith('/segnalazione') or clean_text.startswith('segnalazione'):
        contenuto = text.lower().replace('/segnalazione', '').replace('segnalazione', '').strip()
        if not contenuto:
            _TELEGRAM_STATE[telegram_chat_id] = {'action': 'segnalazione'}
            return "Scrivi il testo della segnalazione:"
        seg, triage = _crea_segnalazione_con_triage_ia(dipendente, contenuto)
        return {
            'text': (
                f"✅ Segnalazione registrata: '{contenuto}'\n"
                f"🤖 Triage IA: [{triage['urgenza']}] {triage['categoria']}\n"
                f"💡 {triage['azione_consigliata']}"
            ),
            'reply_markup': get_main_menu(dipendente)
        }
    
    # Controlla stato conversazione (attesa input)
    state = _TELEGRAM_STATE.get(telegram_chat_id)
    if state:
        action = state.get('action')

        # Attesa motivazione opzionale per ore diverse da quelle previste
        if action == 'attesa_motivo_ore':
            assegnazione_id = state.get('assegnazione_id')
            del _TELEGRAM_STATE[telegram_chat_id]
            _cmd_keywords = {
                'menu', 'start', '/start', 'turni', 'inserisci ore', 'ore',
                'malattia', 'ferie', 'permesso', 'segnalazione', 'chat', 'buste paga'
            }
            if clean_text in ('salta', 'no', '-', 'nessuno', 'ok'):
                return {"text": "👍 Perfetto, ore confermate senza motivazione aggiuntiva.", "reply_markup": get_main_menu(dipendente)}
            if clean_text not in _cmd_keywords and not any(clean_text.startswith(k) for k in ('📅', '⏱', '🤒', '🌴', '🕐', '🚨', '💬', '📄')):
                motivo_str = text.strip()
                base_note = f"Registrato da {dipendente.nome} {dipendente.cognome}"
                TimeTracking.objects.filter(assegnazione_id=assegnazione_id, dipendente=dipendente).update(
                    note=f"{motivo_str} ({base_note})"
                )
                TimeTracking.objects.filter(assegnazione_id=assegnazione_id).exclude(dipendente=dipendente).update(
                    note=f"{motivo_str} (Registrato dal collega {dipendente.nome} {dipendente.cognome})"
                )
                return {"text": f"📝 Motivazione registrata: \"{motivo_str}\"", "reply_markup": get_main_menu(dipendente)}
        
        # Attesa ore per un turno specifico
        if action == 'attesa_ore':
            assegnazione_id = state.get('assegnazione_id')
            del _TELEGRAM_STATE[telegram_chat_id]
            
            note_extra = ""
            match = re.match(r'^\s*(\d+(?:[.,]\d+)?)\s*(?:or[ae]|h)?(?:\s*[-:]?\s*(.*))?$', clean_text, re.IGNORECASE)
            if match:
                hours_str = match.group(1).replace(',', '.')
                note_extra = (match.group(2) or '').strip()
                try:
                    hours = float(hours_str)
                except ValueError:
                    return "Formato ore non valido. Scrivi un numero (es: 8 o 7.5)"
            else:
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
            
            return _salva_ore_turno(dipendente, assegnazione, hours, text, note_extra=note_extra)
        
        # Attesa testo segnalazione
        
        # Attesa date malattia o ferie
        if action in ['attesa_date_malattia', 'attesa_date_ferie']:
            del _TELEGRAM_STATE[telegram_chat_id]
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
                    dates.append(date(year, month, day))
                except ValueError:
                    return "Data non valida. Riprova."
            
            data_inizio = dates[0]
            data_fine = dates[-1]
            if data_fine < data_inizio:
                data_inizio, data_fine = data_fine, data_inizio
                
            return _gestisci_assenza_con_sostituzione(dipendente, tipo, f"Registrata {tipo}", "", data_inizio=data_inizio, data_fine=data_fine)
            
        # Attesa date 104
        if action == 'attesa_dati_104':
            del _TELEGRAM_STATE[telegram_chat_id]
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
                    dates.append(date(year, month, day))
                except ValueError:
                    return "Data non valida. Riprova."
            
            data_inizio = dates[0]
            data_fine = dates[-1]
            if data_fine < data_inizio:
                data_inizio, data_fine = data_fine, data_inizio
                
            return _gestisci_assenza_con_sostituzione(dipendente, '104', "Registrata assenza Legge 104", "", data_inizio=data_inizio, data_fine=data_fine)

        # Attesa dati permesso
        if action == 'attesa_dati_permesso':
            del _TELEGRAM_STATE[telegram_chat_id]
            
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
                    data_permesso = date(year, month, day)
                except ValueError:
                    return "Data non valida."
            
            if len(t_matches) < 2:
                return "Devi specificare sia l'ora di inizio che l'ora di fine (es. 09:00 - 11:00)."
                
            try:
                ora_inizio = time(int(t_matches[0][0]), int(t_matches[0][1]))
                ora_fine = time(int(t_matches[1][0]), int(t_matches[1][1]))
            except ValueError:
                return "Orari non validi."
                
            return _gestisci_assenza_con_sostituzione(dipendente, 'PERMESSO', "Permesso registrato", "", data_inizio=data_permesso, data_fine=data_permesso, ora_inizio=ora_inizio, ora_fine=ora_fine)

        if action == 'segnalazione':
            del _TELEGRAM_STATE[telegram_chat_id]
            seg, triage = _crea_segnalazione_con_triage_ia(dipendente, text.strip())
            return {
                'text': (
                    f"✅ Segnalazione registrata: '{text.strip()}'\n"
                    f"🤖 Triage IA: [{triage['urgenza']}] {triage['categoria']}\n"
                    f"💡 {triage['azione_consigliata']}"
                ),
                'reply_markup': get_main_menu(dipendente)
            }

        if action == 'attesa_testo_materiale':
            cliente_id = state.get('cliente_id')
            del _TELEGRAM_STATE[telegram_chat_id]
            from .models import ConsegnaRichiestaMateriale, ProdottoMagazzino
            from decimal import Decimal
            cli = Cliente.objects.filter(pk=cliente_id).first() if cliente_id else None
            if not cli:
                cli = Cliente.objects.first()
            testo_mat = text.strip()
            prod_match = None
            for p in ProdottoMagazzino.objects.filter(attivo=True):
                if p.nome.lower() in testo_mat.lower():
                    prod_match = p
                    break
            if cli:
                ConsegnaRichiestaMateriale.objects.create(
                    cliente=cli,
                    prodotto=prod_match,
                    descrizione_libera=prod_match.nome if prod_match else testo_mat[:200],
                    quantita=Decimal('1.0'),
                    costo_unitario_applicato=prod_match.costo_unitario if prod_match else Decimal('0.00'),
                    stato='RICHIESTA',
                    richiesto_da=dipendente,
                    data_richiesta=timezone.localdate(),
                    note=testo_mat[:300],
                )
            return {
                'text': (
                    f"🧴 *Richiesta Materiali Registrata!*\n"
                    f"📍 Cantiere: *{cli.ragione_sociale if cli else 'N/D'}*\n"
                    f"📦 Prodotti richiesti: _{testo_mat}_\n\n"
                    f"Il Magazzino / Caposquadra è stato avvisato per la consegna."
                ),
                'reply_markup': get_main_menu(dipendente),
                'parse_mode': 'Markdown',
            }

    # --- ASSISTENTE CONVERSAZIONALE IA (linguaggio naturale gratuito) ---
    try:
        from .ai_engine import interpreta_messaggio_libero
        parsed_ia = interpreta_messaggio_libero(dipendente, text)
    except Exception:
        parsed_ia = {'intent': 'SCONOSCIUTO'}

    if parsed_ia.get('intent') == 'REGISTRA_ORE' and parsed_ia.get('ore') and parsed_ia.get('assegnazione_id'):
        ass_id = parsed_ia['assegnazione_id']
        ore_val = parsed_ia['ore']
        cli_nome = parsed_ia.get('cliente_nome') or 'Cantiere'
        data_lbl = parsed_ia.get('data').strftime('%d/%m/%Y') if parsed_ia.get('data') else 'Oggi'
        return {
            'text': (
                f"🤖 *Assistente IA Kandor*\n"
                f"Ho capito che vuoi registrare *{ore_val:g} ore*:\n"
                f"📍 Cliente: *{cli_nome}*\n"
                f"📅 Data: *{data_lbl}*\n\n"
                f"Confermi la registrazione per la tua squadra?"
            ),
            'reply_markup': {
                "inline_keyboard": [
                    [
                        {"text": f"✅ Conferma {ore_val:g}h", "callback_data": f"ia_conf_ore_{ass_id}_{ore_val}"},
                        {"text": "❌ Annulla", "callback_data": "menu_principale"},
                    ]
                ]
            }
        }

    if parsed_ia.get('intent') == 'ASSENZA' and parsed_ia.get('tipo_assenza'):
        tipo_ass = parsed_ia['tipo_assenza']
        d_ini = parsed_ia.get('data_inizio') or timezone.now().date()
        d_fin = parsed_ia.get('data_fine') or d_ini
        periodo_str = d_ini.strftime('%d/%m/%Y') if d_ini == d_fin else f"{d_ini.strftime('%d/%m/%Y')} - {d_fin.strftime('%d/%m/%Y')}"
        return {
            'text': (
                f"🤖 *Assistente IA Kandor*\n"
                f"Ho capito che vuoi comunicare un'assenza:\n"
                f"🏷️ Tipo: *{tipo_ass}*\n"
                f"📅 Periodo: *{periodo_str}*\n\n"
                f"Vuoi inviare la richiesta all'Amministrazione?"
            ),
            'reply_markup': {
                "inline_keyboard": [
                    [
                        {"text": f"✅ Invia {tipo_ass}", "callback_data": f"ia_conf_ass_{tipo_ass}_{d_ini.isoformat()}_{d_fin.isoformat()}"},
                        {"text": "❌ Annulla", "callback_data": "menu_principale"},
                    ]
                ]
            }
        }

    if parsed_ia.get('intent') == 'SEGNALAZIONE':
        seg, triage = _crea_segnalazione_con_triage_ia(dipendente, text.strip())
        return {
            'text': (
                f"🤖 *Assistente IA Kandor*\n"
                f"Ho registrato automaticamente la tua segnalazione:\n"
                f"📝 \"{text.strip()}\"\n"
                f"🏷️ Triage: [{triage['urgenza']}] {triage['categoria']}\n"
                f"💡 {triage['azione_consigliata']}"
            ),
            'reply_markup': get_main_menu(dipendente)
        }
    
    # Nessun comando riconosciuto: mostra menu
    cmd_104 = ", /104" if getattr(dipendente, 'usufruisce_104', False) else ""
    return {
        'text': f"Ciao {dipendente.nome}! Usa i bottoni per navigare il menu o scrivi liberamente (es. 'oggi 4 ore da Condominio Verdi' oppure 'domani malattia').\nComandi rapidi:\n- /ore — registra ore\n- /malattia, /ferie, /permesso{cmd_104}\n- /segnalazione testo",
        'reply_markup': get_main_menu(dipendente)
    }


def _crea_segnalazione_con_triage_ia(dipendente, testo):
    """
    Crea una Segnalazione, esegue il Triage IA automatico (Categoria + Urgenza)
    e, se CRITICA o ALTA, invia un alert immediato a Titolare e Responsabile Area.
    """
    from .models import Segnalazione, Titolare, ResponsabileArea
    from .ai_engine import classifica_segnalazione
    triage = classifica_segnalazione(testo)
    nota_ia = f"[IA Triage: {triage['urgenza']} | {triage['categoria']}] {triage['azione_consigliata']}"
    seg = Segnalazione.objects.create(
        dipendente=dipendente,
        testo=testo,
        note_amministrazione=nota_ia,
    )
    # Se la segnalazione riguarda scorte/materiali, alimenta automaticamente anche la lista Magazzino & Consegne
    if triage.get('categoria') == 'MATERIALI_SCORTE':
        try:
            from .models import ConsegnaRichiestaMateriale
            from decimal import Decimal
            ultimo_turno = (
                AssegnazioneTurno.objects.filter(
                    Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente)
                )
                .select_related('cliente')
                .order_by('-turno__data')
                .first()
            )
            cli_target = ultimo_turno.cliente if ultimo_turno and ultimo_turno.cliente else Cliente.objects.first()
            if cli_target:
                ConsegnaRichiestaMateriale.objects.create(
                    cliente=cli_target,
                    descrizione_libera=testo[:200],
                    quantita=Decimal('1.0'),
                    stato='RICHIESTA',
                    richiesto_da=dipendente,
                    data_richiesta=timezone.localdate(),
                    note=f"Generata da Triage IA Segnalazione #{seg.id}",
                )
        except Exception:
            pass
    if triage['urgenza'] in ('CRITICA', 'ALTA'):
        emoji = "🚨" if triage['urgenza'] == 'CRITICA' else "⚠️"
        alert_msg = (
            f"{emoji} SEGNALAZIONE {triage['urgenza']} ({triage['categoria']})\n"
            f"👤 Da: {dipendente.nome} {dipendente.cognome}\n"
            f"📝 Testo: \"{testo}\"\n"
            f"💡 Azione IA: {triage['azione_consigliata']}"
        )
        chat_ids = set()
        for t in Titolare.objects.exclude(telegram_chat_id__isnull=True).exclude(telegram_chat_id=''):
            chat_ids.add(t.telegram_chat_id)
        for ra in ResponsabileArea.objects.select_related('dipendente').all():
            if ra.dipendente and ra.dipendente.telegram_chat_id:
                chat_ids.add(ra.dipendente.telegram_chat_id)
        for cid in chat_ids:
            try:
                send_telegram_message(cid, alert_msg)
            except Exception:
                pass
    return seg, triage


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

    return {'text': testo, 'reply_markup': get_main_menu(dipendente)}



def handle_telegram_callback(telegram_chat_id, callback_data, sender_name="Utente"):
    """Gestisce i bottoni inline premuti dall'utente."""
    dipendenti = Dipendente.objects.filter(telegram_chat_id=telegram_chat_id, stato='ATTIVO')
    
    if not dipendenti.exists():
        return {'text': f"Non ti conosco! ID: {telegram_chat_id}"}
    
    dipendente = dipendenti.first()
    
    # Menu principale
    if callback_data == 'menu_start':
        _TELEGRAM_STATE.pop(telegram_chat_id, None)
        return {
            'text': f"Ciao {dipendente.nome}! Cosa vuoi fare?",
            'reply_markup': get_main_menu(dipendente)
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
            return {'text': 'Errore navigazione data.', 'reply_markup': get_main_menu(dipendente)}

    # Turni da compilare
    if callback_data == 'menu_turni_mancanti':
        return {
            'text': "Turni senza ore (ultimi 31 giorni):\nSeleziona per inserire le ore.",
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

    # Legge 104
    if callback_data == 'menu_104':
        if getattr(dipendente, 'usufruisce_104', False):
            _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_dati_104'}
            return {'text': 'Scrivi la data o il periodo per la Legge 104 (es: 15/10/2026, oppure 15/10/2026 - 18/10/2026):'}
        else:
            return {'text': 'La tua scheda dipendente non prevede la Legge 104.', 'reply_markup': get_main_menu(dipendente)}
    
    # Segnalazione -> chiedi testo
    if callback_data == 'menu_segnalazione':
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'segnalazione'}
        return {'text': "Scrivi il testo della segnalazione:"}

    # Richiesta Materiali Cantiere -> scegli cantiere
    if callback_data == 'menu_materiali':
        today = timezone.now().date()
        assegnazioni = (
            AssegnazioneTurno.objects.filter(turno__data__gte=today - timedelta(days=14), turno__data__lte=today + timedelta(days=7))
            .filter(Q(turno__squadra__componenti=dipendente) | Q(turno__squadra__caposquadra=dipendente))
            .select_related('cliente')
        )
        seen_c = {}
        for a in assegnazioni:
            if a.cliente_id and a.cliente_id not in seen_c:
                seen_c[a.cliente_id] = a.cliente.ragione_sociale
        if not seen_c:
            for c in Cliente.objects.all().order_by('ragione_sociale')[:10]:
                seen_c[c.id] = c.ragione_sociale
        kb = [[{'text': f"🏢 {nome[:28]}", 'callback_data': f"mat_cli_{cid}"}] for cid, nome in list(seen_c.items())[:10]]
        kb.append([{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}])
        return {
            'text': "🧴 *Richiesta Materiali Cantiere*\nSeleziona il cantiere in cui stanno finendo i prodotti:",
            'reply_markup': {'inline_keyboard': kb},
            'parse_mode': 'Markdown',
        }

    if callback_data.startswith('mat_cli_'):
        cid = int(callback_data.replace('mat_cli_', ''))
        cli = Cliente.objects.filter(pk=cid).first()
        _TELEGRAM_STATE[telegram_chat_id] = {'action': 'attesa_testo_materiale', 'cliente_id': cid}
        return {
            'text': (
                f"🧴 Cantiere selezionato: *{cli.ragione_sociale if cli else 'Cantiere'}*\n\n"
                f"Scrivi ora quali materiali o detergenti servono (es. _'2 taniche detergente pavimenti e 5 rotoli sacchi neri'_):"
            ),
            'parse_mode': 'Markdown',
        }

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

    # Buste Paga -> elenco cedolini disponibili per il dipendente
    if callback_data == 'menu_buste_paga':
        from .models import CedolinoDipendente
        cedolini = list(
            CedolinoDipendente.objects.filter(
                Q(dipendente=dipendente) | Q(codice_fiscale__iexact=dipendente.codice_fiscale)
            ).select_related('lotto').order_by('-created_at')[:12]
        )
        if not cedolini:
            return {
                'text': "📄 Non ci sono ancora buste paga pubblicate nel tuo archivio digitale.",
                'reply_markup': get_main_menu(dipendente),
            }
        kb = []
        for ced in cedolini:
            per = ced.periodo or ced.lotto.periodo
            netto_lbl = f" ({ced.netto_mese})" if ced.netto_mese else ""
            kb.append([{
                'text': f"📥 {per}{netto_lbl}",
                'callback_data': f"scarica_bp_{ced.pk}",
            }])
        kb.append([{'text': '↩ Menu Principale', 'callback_data': 'menu_start'}])
        return {
            'text': "📄 Seleziona la busta paga che desideri ricevere in PDF qui in chat:",
            'reply_markup': {'inline_keyboard': kb},
        }

    if callback_data.startswith('scarica_bp_'):
        from .models import CedolinoDipendente
        from .buste_paga_service import invia_cedolino_telegram
        bp_id = callback_data.replace('scarica_bp_', '')
        ced = CedolinoDipendente.objects.filter(
            pk=bp_id
        ).filter(
            Q(dipendente=dipendente) | Q(codice_fiscale__iexact=dipendente.codice_fiscale)
        ).first()
        if not ced:
            return {'text': "Busta paga non trovata.", 'reply_markup': get_main_menu(dipendente)}
        res = invia_cedolino_telegram(ced, force_resend=True)
        if res.get('ok'):
            return {'text': f"✅ Busta paga di {ced.periodo or ced.lotto.periodo} inviata qui sopra in PDF!", 'reply_markup': get_main_menu(dipendente)}
        return {'text': f"⚠️ Errore nell'invio del PDF: {res.get('error', 'Riprova più tardi')}", 'reply_markup': get_main_menu(dipendente)}
    
    # Turno selezionato per ore
    if callback_data.startswith('ore_turno_'):
        assegnazione_id = callback_data.replace('ore_turno_', '')
        try:
            assegnazione = AssegnazioneTurno.objects.filter(
                pk=assegnazione_id
            ).select_related('cliente', 'turno', 'turno__squadra').first()
            if not assegnazione:
                return {'text': "Turno non trovato.", 'reply_markup': get_main_menu(dipendente)}
        except Exception:
            return {'text': "Errore nel recupero del turno.", 'reply_markup': get_main_menu(dipendente)}
        
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
                'reply_markup': get_main_menu(dipendente)
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
            st = _TELEGRAM_STATE.get(str(telegram_chat_id), {})
            if st.get('action') == 'attesa_motivo_ore':
                return {
                    'text': (
                        f"✅ Perfetto, presenza confermata per tutti i componenti della squadra per il turno {assign.cliente.ragione_sociale}.\n\n"
                        f"📝 Scrivi ora qui sotto il motivo delle ore diverse da quelle previste (oppure premi 'Salta', non è obbligatorio):"
                    ),
                    'reply_markup': {
                        'inline_keyboard': [
                            [{'text': '⏭ Salta (nessuna motivazione)', 'callback_data': f'salta_motivo_ore_{assign.pk}'}],
                            [{'text': '🏠 Menu Principale', 'callback_data': 'menu_start'}],
                        ]
                    },
                }
            return {
                'text': f"✅ Perfetto, presenza confermata per tutti i componenti della squadra per il turno {assign.cliente.ragione_sociale}.\n\nLe ore sono state contabilizzate per l'intero gruppo.",
                'reply_markup': get_main_menu(dipendente)
            }
        except Exception:
            return {'text': "Errore nella conferma della squadra.", 'reply_markup': get_main_menu(dipendente)}

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
            return {'text': f"Errore nel recupero componenti: {e}", 'reply_markup': get_main_menu(dipendente)}

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
                    'reply_markup': get_main_menu(dipendente)
                }
            except Exception as e:
                return {'text': f"Errore nell'esclusione: {e}", 'reply_markup': get_main_menu(dipendente)}

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

    # ===== GESTIONE AVVALLO PASSAGGI PROCEDURE =====
    if callback_data.startswith('avvalla_passo_'):
        avvallo_id_raw = callback_data.replace('avvalla_passo_', '').strip()
        try:
            from .services import conferma_avvallo_passo_procedura
            res = conferma_avvallo_passo_procedura(
                avvallo_id=int(avvallo_id_raw),
                source='TELEGRAM',
            )
            if res.get('ok'):
                pratica = res.get('pratica')
                passo = res.get('passo')
                if res.get('tutti_approvati'):
                    return {
                        'text': (
                            f"✅ AVVALLO CONFERMATO!\n\n"
                            f"📋 Procedura: {pratica.titolo}\n"
                            f"🔢 Passaggio #{passo.ordine}: {passo.titolo}\n\n"
                            f"Il flag del passaggio è stato spuntato automaticamente e il responsabile è stato notificato per procedere con gli altri punti! 👍"
                        ),
                        'reply_markup': get_main_menu(dipendente),
                    }
                else:
                    return {
                        'text': (
                            f"✅ Il tuo OK è stato registrato!\n\n"
                            f"📋 Procedura: {pratica.titolo}\n"
                            f"🔢 Passaggio #{passo.ordine}: {passo.titolo}\n"
                            f"⏳ Resta in attesa l'OK di: {res.get('nomi_mancanti', '')}"
                        ),
                        'reply_markup': get_main_menu(dipendente),
                    }
            return {'text': f"❌ Errore nell'avvallo del passaggio: {res.get('error')}"}
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

    # Conferma ore proposte dall'Assistente IA
    if callback_data.startswith('ia_conf_ore_'):
        try:
            parts = callback_data.replace('ia_conf_ore_', '').split('_')
            ass_id = int(parts[0])
            ore_val = float(parts[1])
            assegnazione = AssegnazioneTurno.objects.select_related('cliente', 'turno').filter(pk=ass_id).first()
            if not assegnazione:
                return {'text': "❌ Turno non trovato.", 'reply_markup': get_main_menu(dipendente)}
            return _salva_ore_turno(dipendente, assegnazione, ore_val, f"{ore_val} (IA)")
        except Exception as e:
            return {'text': f"❌ Errore salvataggio ore: {e}", 'reply_markup': get_main_menu(dipendente)}

    # Conferma assenza proposta dall'Assistente IA
    if callback_data.startswith('ia_conf_ass_'):
        try:
            import datetime as dt_mod
            parts = callback_data.replace('ia_conf_ass_', '').split('_')
            tipo_ass = parts[0]
            d_ini = dt_mod.date.fromisoformat(parts[1])
            d_fin = dt_mod.date.fromisoformat(parts[2])
            return _gestisci_assenza_con_sostituzione(
                dipendente,
                tipo_ass,
                f"Registrata {tipo_ass} via Assistente IA",
                "",
                data_inizio=d_ini,
                data_fine=d_fin,
            )
        except Exception as e:
            return {'text': f"❌ Errore invio assenza: {e}", 'reply_markup': get_main_menu(dipendente)}

    # Salta inserimento motivazione ore diverse da quelle previste (opzionale)
    if callback_data.startswith('salta_motivo_ore'):
        _TELEGRAM_STATE.pop(str(telegram_chat_id), None)
        return {
            'text': "👍 Perfetto, ore confermate senza motivazione aggiuntiva.",
            'reply_markup': get_main_menu(dipendente),
        }
    
    return {'text': "Comando non riconosciuto.", 'reply_markup': get_main_menu(dipendente)}


def _salva_ore_turno(dipendente, assegnazione, hours, original_text, note_extra=None):
    """Salva le ore lavorate per una specifica assegnazione turno ed estende la registrazione a tutta la squadra con notifiche Telegram."""
    from decimal import Decimal
    from .models import Squadra
    decimal_hours = Decimal(str(hours))

    base_note = f"Registrato da {dipendente.nome} {dipendente.cognome}"
    note_dip = f"{note_extra} ({base_note})" if note_extra else base_note
    note_team = f"{note_extra} (Registrato dal collega {dipendente.nome} {dipendente.cognome})" if note_extra else f"Registrato dal collega {dipendente.nome} {dipendente.cognome}"

    # 1. Salva le ore per il dipendente che le ha digitate
    tt, created = TimeTracking.objects.update_or_create(
        dipendente=dipendente,
        assegnazione=assegnazione,
        defaults={
            'ore_dichiarate': decimal_hours,
            'source': 'TELEGRAM',
            'note': note_dip,
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
                'note': note_team,
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

    # Calcola ore previste per verificare eventuale scostamento
    _ore_prev = None
    if assegnazione.ore_previste_contratto and assegnazione.ore_previste_contratto > 0:
        _ore_prev = round(float(assegnazione.ore_previste_contratto), 1)
    elif assegnazione.orario_inizio_previsto and assegnazione.orario_fine_previsto:
        try:
            _dt_s = datetime.combine(date.today(), assegnazione.orario_inizio_previsto)
            _dt_e = datetime.combine(date.today(), assegnazione.orario_fine_previsto)
            if _dt_e < _dt_s:
                _dt_e += timedelta(days=1)
            _ore_prev = round((_dt_e - _dt_s).total_seconds() / 3600.0, 1)
        except Exception:
            pass

    richiedi_motivo = bool(_ore_prev and abs(float(hours) - _ore_prev) >= 0.01 and not note_extra)
    if richiedi_motivo and dipendente.telegram_chat_id:
        _TELEGRAM_STATE[str(dipendente.telegram_chat_id)] = {
            'action': 'attesa_motivo_ore',
            'assegnazione_id': assegnazione.pk,
        }

    # 5. SE CI SONO ALTRI COMPONENTI, CHIEDI LA VERIFICA PRESENZA SQUADRA A CHI HA SCRITTO
    if altri_comp:
        nomi_comp = "\n".join([f"• {c.nome} {c.cognome}" for c in altri_comp])
        prompt_text = (
            f"✅ {action}! {hours}h per {assegnazione.cliente.ragione_sociale} ({data_str}).\n\n"
            f"👥 Confermi la presenza anche degli altri componenti della squadra?\n"
            f"{nomi_comp}"
        )
        if richiedi_motivo:
            prompt_text += (
                f"\n\n⚠️ Hai inserito {float(hours):g}h invece delle {_ore_prev:g}h previste.\n"
                f"📝 Se vuoi, scrivi qui sotto il motivo della variazione (non è obbligatorio):"
            )
        keyboard = {
            'inline_keyboard': [
                [{'text': '✅ Sì, squadra al completo', 'callback_data': f'conf_squadra_si_{assegnazione.pk}'}],
                [{'text': '⚠️ No, mancava qualcuno', 'callback_data': f'conf_squadra_no_{assegnazione.pk}'}],
                [{'text': '🏠 Menu Principale', 'callback_data': 'menu_start'}]
            ]
        }
        return {'text': prompt_text, 'reply_markup': keyboard}

    if richiedi_motivo:
        return {
            'text': (
                f"✅ {action}! {hours}h per {assegnazione.cliente.ragione_sociale} ({data_str}).\n\n"
                f"⚠️ Hai inserito {float(hours):g}h invece delle {_ore_prev:g}h previste.\n"
                f"📝 Scrivi qui sotto il motivo delle ore diverse da quelle previste (non obbligatorio, puoi anche premere 'Salta'):"
            ),
            'reply_markup': {
                'inline_keyboard': [
                    [{'text': '⏭ Salta (nessuna motivazione)', 'callback_data': f'salta_motivo_ore_{assegnazione.pk}'}],
                    [{'text': '🏠 Menu Principale', 'callback_data': 'menu_start'}],
                ]
            },
        }

    return {
        'text': f"✅ {action}! {hours}h per {assegnazione.cliente.ragione_sociale} ({data_str}).",
        'reply_markup': get_main_menu(dipendente)
    }


def send_telegram_message(chat_id, text, reply_markup=None, parse_mode='Markdown'):
    """Invia un messaggio proattivo a una specifica chat_id."""
    from django.conf import settings
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id or not text:
        return False
    
    import requests
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    if parse_mode:
        payload['parse_mode'] = parse_mode
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200 and parse_mode:
            payload.pop('parse_mode', None)
            r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram Error] Send message failed: {e}")
        return False


def _is_image_file(filename, content_type=None):
    import os
    ext = os.path.splitext(filename or '')[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
        return True
    if content_type and str(content_type).lower().startswith('image/'):
        return True
    return False


def send_telegram_file(chat_id, file_bytes, filename, caption='', content_type=None):
    """Invia un file (foto, PDF cedolino, documento, ecc.) via Telegram a chat_id."""
    from django.conf import settings
    import requests
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token or not chat_id or not file_bytes:
        return False

    safe_name = filename or 'allegato'
    mime = content_type or 'application/octet-stream'
    cap = (caption or '').strip()

    # Se il testo supera il limite caption di Telegram (1024 caratteri), invia prima il testo
    if len(cap) > 1024:
        send_telegram_message(chat_id, cap, parse_mode=None)
        cap = ''

    data = {'chat_id': str(chat_id)}
    if cap:
        data['caption'] = cap

    is_img = _is_image_file(safe_name, mime)
    try:
        if is_img:
            url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
            r = requests.post(
                url_photo,
                data=data,
                files={'photo': (safe_name, file_bytes, mime)},
                timeout=30,
            )
            if r.status_code == 200:
                return True
        # Invio come documento (per PDF cedolini, Word, Excel, o fallback immagini grandi)
        url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
        r = requests.post(
            url_doc,
            data=data,
            files={'document': (safe_name, file_bytes, mime)},
            timeout=30,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram Error] Send file failed ({safe_name}): {e}")
        return False


def _save_uploaded_attachment_storage(file_bytes, filename, content_type=None):
    """Salva l'allegato caricato dall'ufficio sul volume Media persistente VPS (/app/media) e restituisce l'URL."""
    import os
    import uuid
    import re

    ext = os.path.splitext(filename or '')[1].lower() or '.bin'
    base = re.sub(r'[^a-zA-Z0-9_\-]', '_', os.path.splitext(filename or 'file')[0])[:40]
    stored_name = f"chat_office_{base}_{uuid.uuid4().hex[:8]}{ext}"

    try:
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        saved_path = default_storage.save(f"chat_files/{stored_name}", ContentFile(file_bytes))
        return default_storage.url(saved_path)
    except Exception as e:
        print(f"[AttachmentUpload] Local storage error: {e}")
        return ''


def prepare_uploaded_attachments(uploaded_files):
    """Legge i file caricati da un form Django in memoria e li prepara per l'invio multiplo e lo storico chat."""
    import os
    import mimetypes
    prepared = []
    for f in (uploaded_files or []):
        if not f:
            continue
        try:
            f.seek(0)
        except Exception:
            pass
        file_bytes = f.read()
        if not file_bytes:
            continue
        raw_name = os.path.basename(getattr(f, 'name', 'allegato') or 'allegato')
        ctype = getattr(f, 'content_type', None) or mimetypes.guess_type(raw_name)[0] or 'application/octet-stream'
        is_img = _is_image_file(raw_name, ctype)
        url = _save_uploaded_attachment_storage(file_bytes, raw_name, ctype)
        prepared.append({
            'bytes': file_bytes,
            'name': raw_name,
            'content_type': ctype,
            'is_image': is_img,
            'url': url,
        })
    return prepared


def send_and_record_telegram_to_employee(dipendente, text='', attachments=None, save_chat=True):
    """
    Invia un messaggio di testo e/o uno o più file allegati a un Dipendente via Telegram
    e registra l'invio nello storico MessaggioChat.
    Restituisce True se almeno un invio via Telegram è andato a buon fine.
    """
    from .models import MessaggioChat
    msg = (text or '').strip()
    att_list = list(attachments or [])
    chat_id = getattr(dipendente, 'telegram_chat_id', '') if dipendente else ''

    if not msg and not att_list:
        return False

    any_sent = False
    if not att_list:
        if save_chat and dipendente and dipendente.pk:
            MessaggioChat.objects.create(dipendente=dipendente, testo=msg, direzione='OUT')
            any_sent = True
        if chat_id:
            any_sent = send_telegram_message(chat_id, msg) or any_sent
        return any_sent

    # Ci sono allegati: il primo allegato porta il testo come caption (o testo separato se lungo)
    for idx, att in enumerate(att_list):
        cap = msg if idx == 0 else ''
        label_testo = cap if cap else f"📎 Allegato: {att['name']}"
        if cap and f"📎 {att['name']}" not in cap:
            label_testo = f"{cap}\n📎 {att['name']}"
        if save_chat and dipendente and dipendente.pk:
            MessaggioChat.objects.create(
                dipendente=dipendente,
                testo=label_testo,
                foto_url=att['url'] if att.get('is_image') else '',
                allegato_url=att['url'] if not att.get('is_image') else '',
                allegato_nome=att['name'],
                direzione='OUT',
            )
            any_sent = True
        if chat_id:
            ok = send_telegram_file(
                chat_id,
                att['bytes'],
                att['name'],
                caption=cap,
                content_type=att.get('content_type'),
            )
            if ok:
                any_sent = True
    return any_sent


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

def invia_promemoria_ore_mancanti(only_check=False, test_chat_id=None):
    """
    Invia un avviso ai dipendenti tramite Telegram per ricordare di inserire le ore lavorate nelle ultime 24 ore.
    L'avviso viene inviato solo ai dipendenti che hanno turni assegnati senza ore registrate e senza assenze.
    """
    from datetime import datetime, date, timedelta
    from django.utils import timezone
    from django.db.models import Q
    from .models import Dipendente, AssegnazioneTurno, TimeTracking, Assenza, MessaggioChat

    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    current_time = now.time()

    query_emps = Dipendente.objects.filter(stato='ATTIVO', telegram_chat_id__isnull=False).exclude(telegram_chat_id='')
    if test_chat_id:
        query_emps = query_emps.filter(telegram_chat_id=test_chat_id)

    inviati = 0
    errori = 0
    dettagli = []

    emp_list = list(query_emps)
    emp_ids = [e.id for e in emp_list]
    if not emp_ids:
        return {'inviati': 0, 'errori': 0, 'dettagli': []}

    # Pre-carica assenze e timetracking della finestra (yesterday..today) per eliminare le query N+1
    assenze_attive = list(
        Assenza.objects.filter(
            dipendente_id__in=emp_ids,
            data_inizio__lte=today,
            data_fine__gte=yesterday,
        ).exclude(stato_approvazione='RIFIUTATA')
    )
    assenze_per_emp = {}
    for ass in assenze_attive:
        assenze_per_emp.setdefault(ass.dipendente_id, []).append(ass)

    tt_compilati = set()
    for tt_row in TimeTracking.objects.filter(
        dipendente_id__in=emp_ids,
        assegnazione__turno__data__gte=yesterday,
        assegnazione__turno__data__lte=today,
    ):
        if tt_row.ore_dichiarate is not None or tt_row.durata_ore:
            tt_compilati.add((tt_row.dipendente_id, tt_row.assegnazione_id))

    for emp in emp_list:
        assigns = AssegnazioneTurno.objects.filter(
            turno__data__gte=yesterday,
            turno__data__lte=today
        ).filter(
            Q(turno__squadra__componenti=emp) | Q(turno__squadra__caposquadra=emp)
        ).select_related('cliente', 'turno').distinct().order_by('turno__data', 'orario_inizio_previsto')

        emp_assenze = assenze_per_emp.get(emp.id, [])
        missing_assigns = []
        for a in assigns:
            if a.turno.data == today and a.orario_inizio_previsto and a.orario_inizio_previsto > current_time:
                continue

            has_assenza = any(
                ass.data_inizio <= a.turno.data <= ass.data_fine
                for ass in emp_assenze
            )
            if has_assenza:
                continue

            if (emp.id, a.id) not in tt_compilati:
                missing_assigns.append(a)

        if not missing_assigns:
            continue

        lines = [
            "🔔 *PROMEMORIA ORE LAVORATE*",
            "",
            "Ciao *" + str(emp.nome) + "*, ti ricordiamo di inserire le ore lavorate per i seguenti turni delle ultime 24 ore:",
            ""
        ]

        for ma in missing_assigns:
            data_fmt = ma.turno.data.strftime("%d/%m/%Y")
            ora_i = ma.orario_inizio_previsto.strftime("%H:%M") if ma.orario_inizio_previsto else "??"
            ora_f = ma.orario_fine_previsto.strftime("%H:%M") if ma.orario_fine_previsto else "??"
            lines.append("🏢 *" + str(ma.cliente.ragione_sociale) + "*")
            lines.append("📅 " + data_fmt + " | 🕒 " + ora_i + " - " + ora_f)
            lines.append("")

        lines.append("👇 *Premi il pulsante sotto per registrare subito le tue ore:*")
        testo = "\n".join(lines)

        keyboard = {
            'inline_keyboard': [
                [{'text': '⏱ Registra Ore', 'callback_data': 'menu_ore'}],
                [{'text': '📅 Calendario', 'callback_data': 'menu_calendario'}]
            ]
        }

        dettaglio_item = {
            'dipendente': f"{emp.cognome} {emp.nome}",
            'chat_id': emp.telegram_chat_id,
            'turni_mancanti': len(missing_assigns)
        }

        if only_check:
            dettagli.append(dettaglio_item)
            inviati += 1
        else:
            success = send_telegram_message(emp.telegram_chat_id, testo, reply_markup=keyboard)
            if success:
                inviati += 1
                dettaglio_item['stato'] = 'Inviato'
                try:
                    MessaggioChat.objects.create(
                        dipendente=emp,
                        testo="[PROMEMORIA ORE TELEGRAM]\n" + testo,
                        direzione='OUT'
                    )
                except Exception:
                    pass
            else:
                errori += 1
                dettaglio_item['stato'] = 'Errore Invio'
            dettagli.append(dettaglio_item)

    return {
        'inviati': inviati,
        'errori': errori,
        'dettagli': dettagli
    }
