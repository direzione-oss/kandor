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
    """
    Cerca il cliente che meglio matcha il nome fornito.
    Ritorna (Cliente, score) o (None, 0).
    Semplice implementazione: 'contains' case insensitive
    """
    query = normalize_text(query_name)
    candidates = Cliente.objects.all()
    best_match = None
    best_score = 0
    
    for c in candidates:
        c_name = normalize_text(c.ragione_sociale)
        if query == c_name: # Exact
            return c
        if query in c_name: # Contains
            score = len(query) / len(c_name)
            if score > best_score:
                best_score = score
                best_match = c
    
    return best_match

def parse_message(text):
    """
    Estrae (nome_cliente, ore) dal testo.
    Supporta formati: "Hotel Roma 4", "Roma 4.5", "Hotel Roma 4:30"
    """
    # Regex per trovare numeri alla fine (es. 4, 4.5, 4,5, 4:30)
    # Group 1: Nome Cliente, Group 2: Ore
    match = re.search(r'^(.*?)(\d+[.,:]?\d*)$', text.strip())
    
    if match:
        client_part = match.group(1).strip()
        time_part = match.group(2).strip().replace(',', '.')
        
        hours = 0.0
        if ':' in time_part: # Format HH:MM
            h, m = time_part.split(':')
            hours = int(h) + int(m)/60
        else:
            hours = float(time_part)
            
        return client_part, round(hours, 2)
    
    return None, None

def handle_telegram_message(telegram_chat_id, text, sender_name="Utente"):
    """
    Logica principale:
    1. Identifica Dipendente
    2. Identifica Cliente e Ore
    3. Registra TimeTracking
    """
    # 1. Identifica Dipendente
    # Cerchiamo per ID esatto
    dipendenti = Dipendente.objects.filter(telegram_chat_id=telegram_chat_id, stato='ATTIVO')
    
    if not dipendenti.exists():
        return f"🚫 Ciao {sender_name}, non ti conosco! Il tuo ID Telegram è: {telegram_chat_id}\nInvialo all'amministratore per farti abilitare."
    
    dipendente = dipendenti.first()

    # --- NUOVI COMANDI ---
    clean_text = normalize_text(text)
    
    # MALATTIA
    if 'malattia' in clean_text:
        # Registra malattia per oggi
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente,
            tipo='MALATTIA',
            data_inizio=today,
            data_fine=today,
            note=f"Segnalata via Telegram: {text}",
            source='TELEGRAM'
        )
        return f"d'oh! 🤒 Mi dispiace che stai male {dipendente.nome}. Ho registrato la MALATTIA per oggi ({today.strftime('%d/%m')}). Riposati!"

    # FERIE
    if 'ferie' in clean_text:
        today = timezone.now().date()
        from .models import Assenza
        # Logica semplice: Ferie per oggi. In futuro parsing date.
        Assenza.objects.create(
            dipendente=dipendente,
            tipo='FERIE',
            data_inizio=today,
            data_fine=today,
            note=f"Richiesta via Telegram: {text}",
            source='TELEGRAM'
        )
        return f"🏖️ Ferie registrate per oggi ({today.strftime('%d/%m')}). Goditi il relax {dipendente.nome}!"

    # PERMESSO
    if 'permesso' in clean_text:
        today = timezone.now().date()
        from .models import Assenza
        Assenza.objects.create(
            dipendente=dipendente,
            tipo='PERMESSO',
            data_inizio=today,
            data_fine=today,
            note=f"Richiesta via Telegram: {text}",
            source='TELEGRAM'
        )
        return f"ok, {dipendente.nome}. Ho segnato un PERMESSO per oggi."

    # SEGNALAZIONE
    if clean_text.startswith('segnalazione'):
        from .models import Segnalazione
        # Rimuovi la parola chiave
        contenuto = text.lower().replace('segnalazione', '', 1).strip()
        if not contenuto:
            contenuto = "Generica"
            
        Segnalazione.objects.create(
            dipendente=dipendente,
            testo=contenuto
        )
        return f"📝 Grazie {dipendente.nome}, ho preso nota della tua segnalazione: '{contenuto}'. L'amministrazione verificherà."
        
    # --- FINE NUOVI COMANDI ---
        
    client_name, hours = parse_message(text)
    
    if not client_name or not hours:
        return f"👋 Ciao {dipendente.nome}!\nPuoi scrivermi:\n- 'NomeCliente Ore' (es: 'Hotel Roma 8')\n- 'Malattia', 'Ferie', 'Permesso'\n- 'Segnalazione: testo...'"
        
    cliente = fuzzy_find_cliente(client_name)
    
    if not cliente:
        return f"❌ Non ho trovato nessun cliente simile a '{client_name}'. Riprova."
        
    # -- Logica di Salvataggio --
    # Cerchiamo se esiste già un'assegnazione/turno per OGGI per questo dipendente/cliente
    today = timezone.now().date()
    # Per semplicità nel MVP, creiamo un TimeTracking 'volante' collegato a un Turno Fittizio o esistente?
    # Modello attuale: TimeTracking -> AssegnazioneTurno -> Turno
    # Dobbiamo trovare o creare un Turno e un'AssegnazioneTurno.
    
    # Cerchiamo Assegnazione esistente
    assegnazione = AssegnazioneTurno.objects.filter(
        turno__data=today,
        turno__squadra__componenti=dipendente,
        cliente=cliente
    ).first()
    
    if not assegnazione:
        # Fallback: Creiamo un'assegnazione 'recuperata'?
        # Questo è complesso per il MVP. Per ora cerchiamo Assegnazione generica su quel cliente,
        # o creiamo turno ad-hoc?
        # Semplificazione MVP: Se non c'è turno pianificato, ERRORE o SALVATAGGIO su Turno 'Jolly/Recupero'.
        
        # PROVIAMO A CREARE REGOLE PIU' LASCHE: Cerchiamo un turno qualsiasi di oggi dove il dipendente è presente
        # Se non c'è, creiamo Turno 'Smart' (Squadra automatica o fittizia?)
        # Creiamo una 'Squadra Personale' se non esiste?
        
        # Meglio: Troviamo un turno di oggi qualsiasi del dipendente.
        user_turni = Turno.objects.filter(data=today, squadra__componenti=dipendente)
        
        if user_turni.exists():
            turno = user_turni.first()
        else:
            # Creiamo Turno ad-hoc per 'Segnalazioni Telegram'
            # Serve una Squadra... usiamo una squadra fittizia o cerchiamo la squadra abituale del dipendente
            squadra = dipendente.squadre_appartenenza.first()
            if not squadra:
                 return "❌ Non appartieni a nessuna squadra, impossibile creare il turno."
                 
            turno = Turno.objects.create(data=today, squadra=squadra)
            
        # Creiamo Assegnazione su questo Turno per questo Cliente
        # Orari stimati (es. ora attuale - ore lavorate -> ora attuale)
        end_dt = timezone.now()
        start_dt = end_dt - timedelta(hours=hours)
        
        assegnazione = AssegnazioneTurno.objects.create(
            turno=turno,
            cliente=cliente,
            orario_inizio_previsto=start_dt.time(),
            orario_fine_previsto=end_dt.time(),
            mansione_svolta="Segnalazione via Telegram"
        )
        msg_extra = " (Turno creato automaticamente)"
    else:
        # Assegnazione esistente trovata
        # Aggiorniamo orari reali? O creiamo TimeTracking separato?
        # Creiamo TimeTracking
        # Stimiamo orari check-in/out basati su 'hours' e ora attuale come fine
        end_dt = timezone.now()
        start_dt = end_dt - timedelta(hours=hours)
        msg_extra = ""

    TimeTracking.objects.create(
        dipendente=dipendente,
        assegnazione=assegnazione,
        check_in=check_in_time,
        check_out=check_out_time,
        source='TELEGRAM',
        note=f"Messaggio originale: {text}"
    )
    
    return f"✅ Salvato! {hours}h per {cliente.ragione_sociale}.{msg_extra}"

def send_telegram_message(chat_id, text):
    """
    Invia un messaggio proattivo a una specifica chat_id.
    Ritorna True se successo, False altrimenti.
    """
    import requests
    from django.conf import settings
    
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        response = requests.post(
            url,
            json={'chat_id': chat_id, 'text': text},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending telegram message: {e}")
        return False

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calcola la distanza tra due punti GPS usando la formula di Haversine.
    Ritorna la distanza in metri.
    """
    from math import radians, cos, sin, asin, sqrt
    
    # Raggio della Terra in metri
    R = 6371000
    
    # Converti in radianti
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Formula di Haversine
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    distance = R * c
    
    return distance

def check_proximity(dipendente, lat, lon):
    """
    Controlla la prossimità del dipendente a tutti i clienti.
    Aggiorna ProximityLog e ritorna eventi di entrata/uscita.
    """
    from core.models import Cliente, ProximityLog
    from django.utils import timezone
    
    PROXIMITY_THRESHOLD = 1000  # 1km in metri
    events = []
    
    # Ottieni tutti i clienti con coordinate
    clienti = Cliente.objects.filter(latitudine__isnull=False, longitudine__isnull=False)
    
    for cliente in clienti:
        distance = calculate_distance(lat, lon, cliente.latitudine, cliente.longitudine)
        
        # Ottieni o crea il log di prossimità
        log, created = ProximityLog.objects.get_or_create(
            dipendente=dipendente,
            cliente=cliente,
            defaults={'is_near': False}
        )
        
        # Controllo entrata (< 1km e non era vicino)
        if distance < PROXIMITY_THRESHOLD and not log.is_near:
            log.is_near = True
            log.entered_at = timezone.now()
            log.save()
            events.append({
                'type': 'entry',
                'dipendente': dipendente,
                'cliente': cliente,
                'distance': distance,
                'timestamp': log.entered_at
            })
        
        # Controllo uscita (>= 1km e era vicino)
        elif distance >= PROXIMITY_THRESHOLD and log.is_near:
            log.is_near = False
            log.exited_at = timezone.now()
            log.save()
            events.append({
                'type': 'exit',
                'dipendente': dipendente,
                'cliente': cliente,
                'distance': distance,
                'timestamp': log.exited_at
            })
    
    return events

