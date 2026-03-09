from datetime import datetime, date, timedelta
from django.db.models import Q
from geopy.distance import geodesic
from django.utils import timezone
from .models import Dipendente, AssegnazioneTurno, ProgrammazioneRicorrente, RichiestaStraordinaria, Turno, Squadra

def genera_turni_automatici(days=365):
    """
    Genera i turni per i prossimi 'days' giorni (default 12 mesi = 365)
    basandosi sulla ProgrammazioneRicorrente.
    Rispetta le date di inizio/fine contratto.
    Ritorna il numero di assegnazioni create.
    """
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=days)
    
    count = 0
    programmazioni = ProgrammazioneRicorrente.objects.filter(squadra_abituale__isnull=False)

    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.weekday()
        day_of_month = current_date.day
        
        match_settimanali = programmazioni.filter(tipo_ripetizione='SETTIMANALE', giorno_settimana=weekday)
        match_mensili = programmazioni.filter(tipo_ripetizione='MENSILE', giorno_mese=day_of_month)
        
        # Bisettimanale: stesso giorno della settimana, ma solo nelle settimane "attive"
        match_bisettimanali_candidates = programmazioni.filter(tipo_ripetizione='BISETTIMANALE', giorno_settimana=weekday)
        match_bisettimanali = []
        for prog in match_bisettimanali_candidates:
            if prog.data_inizio_contratto:
                # Calcola quante settimane sono passate dalla data_inizio_contratto
                delta_days = (current_date - prog.data_inizio_contratto).days
                settimane_passate = delta_days // 7
                # Settimana attiva se il numero di settimane passate è pari (0, 2, 4...)
                if delta_days >= 0 and settimane_passate % 2 == 0:
                    match_bisettimanali.append(prog)
        
        matches = list(match_settimanali) + list(match_mensili) + match_bisettimanali
        
        for prog in matches:
            # Controllo periodo contrattuale
            if prog.data_inizio_contratto and current_date < prog.data_inizio_contratto:
                continue  # Non ancora iniziato
            if prog.data_fine_contratto and current_date > prog.data_fine_contratto:
                continue  # Contratto scaduto
            
            squadra = prog.squadra_abituale
            
            # Crea/Recupera Turno
            turno, created = Turno.objects.get_or_create(
                data=current_date,
                squadra=squadra,
                defaults={'mezzo': prog.mezzo_abituale}
            )
            
            # Evita duplicati
            exists = AssegnazioneTurno.objects.filter(
                turno=turno,
                programmazione_feriale=prog
            ).exists()
            
            if not exists:
                orario_inizio = prog.ora_inizio
                
                if prog.durata:
                        dummy_date = date.today()
                        dt_start = datetime.combine(dummy_date, orario_inizio)
                        hours = int(prog.durata)
                        minutes = int((prog.durata - hours) * 60)
                        dt_end = dt_start + timedelta(hours=hours, minutes=minutes)
                        orario_fine = dt_end.time()
                else:
                        orario_fine = orario_inizio # Should not happen ideally
                
                AssegnazioneTurno.objects.create(
                    turno=turno,
                    cliente=prog.cliente,
                    programmazione_feriale=prog,
                    orario_inizio_previsto=orario_inizio,
                    orario_fine_previsto=orario_fine,
                    mansione_svolta=f"Generato autom. (Qualifica: {prog.qualifica_richiesta})"
                )
                count += 1
        
        current_date += timedelta(days=1)
    
    return count

def trova_sostituti(cliente, data, ora_inizio, ora_fine, escludi_dipendenti_ids=None, qualifica_richiesta=None):
    """
    Trova un elenco compatibile di dipendenti sostituti per una copertura improvvisa.
    Filtri:
    1. Stato ATTIVO e is_sostituto=True
    2. Non in Ferie/Malattia/Permesso in quella data
    3. Non già impegnati in un Turno coincidente
    4. Qualifica compatibile (se specificata)
    
    Ranking: Distanza geografica casa-cliente (crescente)
    """
    
    # 1. Filtro Dipendenti Attivi e Sostituti
    candidati = Dipendente.objects.filter(stato='ATTIVO', is_sostituto=True)

    # Filtro opzionale per Qualifica
    if qualifica_richiesta:
        candidati = candidati.filter(qualifiche=qualifica_richiesta)
    
    if escludi_dipendenti_ids:
        candidati = candidati.exclude(id__in=escludi_dipendenti_ids)

    # 2. Escludi Assenze
    data_check = data
    if isinstance(data, datetime):
        data_check = data.date()
        
    from .models import Assenza
    dipendenti_assenti = Assenza.objects.filter(
        data_inizio__lte=data_check,
        data_fine__gte=data_check
    ).values_list('dipendente_id', flat=True)
    
    candidati = candidati.exclude(id__in=dipendenti_assenti)

    # 3. Escludi chi è già occupato in un altro turno
    assegnazioni_concomitanti = AssegnazioneTurno.objects.filter(
        turno__data=data,
        orario_inizio_previsto__lt=ora_fine,
        orario_fine_previsto__gt=ora_inizio
    )
    
    squadre_impegnate_ids = assegnazioni_concomitanti.values_list('turno__squadra_id', flat=True)
    candidati = candidati.exclude(squadre_appartenenza__id__in=squadre_impegnate_ids)

    # 4. Calcolo Distanza e Ranking
    risultati = []
    coord_cliente = (cliente.latitudine, cliente.longitudine)
    has_client_coords = coord_cliente[0] is not None and coord_cliente[1] is not None

    for dip in candidati:
        distanza = float('inf')
        coord_dip = (dip.latitudine, dip.longitudine)
        
        if has_client_coords and coord_dip[0] is not None and coord_dip[1] is not None:
             distanza = geodesic(coord_dip, coord_cliente).km
        
        risultati.append({
            'dipendente': dip,
            'distanza_km': distanza,
            'skills': [q.nome for q in dip.qualifiche.all()]
        })

    # Ordina per distanza crescente
    risultati.sort(key=lambda x: x['distanza_km'])
    
    return risultati


# Manteniamo compatibilità con il vecchio nome
trova_jolly = trova_sostituti


def crea_richiesta_sostituzione(assegnazione, dipendente_assente, motivo, note=''):
    """
    Crea una richiesta di sostituzione:
    1. Trova il Responsabile Area della squadra
    2. Calcola lista sostituti ordinata per distanza
    3. Crea RichiestaSostituzione con stato APERTA
    4. Invia notifica Telegram al Responsabile Area per approvazione
    """
    from .models import ResponsabileArea, RichiestaSostituzione
    import requests
    from django.conf import settings
    
    cliente = assegnazione.cliente
    turno = assegnazione.turno
    squadra = turno.squadra
    
    # Trova qualifica richiesta (se esiste programmazione collegata)
    qualifica = None
    if assegnazione.programmazione_feriale and assegnazione.programmazione_feriale.qualifica_richiesta:
        qualifica = assegnazione.programmazione_feriale.qualifica_richiesta
    
    # Trova sostituti disponibili
    componenti_ids = list(squadra.componenti.values_list('id', flat=True))
    if squadra.caposquadra:
        componenti_ids.append(squadra.caposquadra.id)
    
    sostituti = trova_sostituti(
        cliente=cliente,
        data=turno.data,
        ora_inizio=assegnazione.orario_inizio_previsto,
        ora_fine=assegnazione.orario_fine_previsto,
        escludi_dipendenti_ids=componenti_ids,
        qualifica_richiesta=qualifica
    )
    
    sostituti_ids = [s['dipendente'].id for s in sostituti]
    
    # Trova Responsabile Area
    ra = None
    try:
        ra = ResponsabileArea.objects.filter(squadre=squadra).first()
    except Exception:
        pass
    
    # Crea la richiesta
    richiesta = RichiestaSostituzione.objects.create(
        assegnazione_originale=assegnazione,
        dipendente_assente=dipendente_assente,
        motivo_assenza=motivo,
        responsabile_area=ra,
        stato='APERTA',
        sostituti_candidati=sostituti_ids,
        note=note,
    )
    
    # Notifica Responsabile Area via Telegram
    if ra and ra.dipendente.telegram_chat_id:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if bot_token:
            primo_sost = sostituti[0] if sostituti else None
            sost_info = ''
            if primo_sost:
                dist = f"{primo_sost['distanza_km']:.1f} km" if primo_sost['distanza_km'] != float('inf') else "N/D"
                sost_info = f"\nPrimo sostituto proposto: {primo_sost['dipendente']} ({dist})"
            
            msg = (
                f"⚠️ RICHIESTA SOSTITUZIONE\n"
                f"Dipendente: {dipendente_assente} ({motivo})\n"
                f"Turno: {turno.data.strftime('%d/%m/%Y')} - "
                f"{assegnazione.orario_inizio_previsto.strftime('%H:%M')}-"
                f"{assegnazione.orario_fine_previsto.strftime('%H:%M')}\n"
                f"Cliente: {cliente.ragione_sociale}\n"
                f"Squadra: {squadra.nome}"
                f"{sost_info}\n\n"
                f"Candidati disponibili: {len(sostituti)}"
            )
            
            keyboard = {
                "inline_keyboard": [[
                    {"text": "✅ Approva", "callback_data": f"approva_sost_{richiesta.pk}"},
                    {"text": "❌ Rifiuta", "callback_data": f"rifiuta_sost_ra_{richiesta.pk}"}
                ]]
            }
            
            try:
                import json
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": ra.dipendente.telegram_chat_id,
                        "text": msg,
                        "reply_markup": json.dumps(keyboard)
                    },
                    timeout=10
                )
            except Exception:
                pass
    else:
        # Se non c'è RA, approva automaticamente
        richiesta.stato = 'APPROVATA_RA'
        richiesta.approvata_ra_il = timezone.now()
        richiesta.save()
        approva_e_invia_sostituto(richiesta.pk)
    
    return richiesta


def approva_e_invia_sostituto(richiesta_id):
    """
    Dopo approvazione del RA, invia la richiesta al sostituto corrente nella coda.
    Include: cliente, turno, orari, compagni di squadra con contatti.
    """
    from .models import RichiestaSostituzione, Dipendente
    import requests, json
    from django.conf import settings
    
    try:
        richiesta = RichiestaSostituzione.objects.get(pk=richiesta_id)
    except RichiestaSostituzione.DoesNotExist:
        return None
    
    candidati = richiesta.sostituti_candidati
    idx = richiesta.sostituto_corrente_idx
    
    if idx >= len(candidati):
        richiesta.stato = 'ANNULLATA'
        richiesta.note += '\nNessun sostituto disponibile ha accettato.'
        richiesta.save()
        return None
    
    sostituto_id = candidati[idx]
    try:
        sostituto = Dipendente.objects.get(pk=sostituto_id)
    except Dipendente.DoesNotExist:
        # Passa al successivo
        richiesta.sostituto_corrente_idx = idx + 1
        richiesta.save()
        return approva_e_invia_sostituto(richiesta_id)
    
    richiesta.sostituto = sostituto
    richiesta.stato = 'INVIATA'
    richiesta.inviata_sostituto_il = timezone.now()
    
    # Calcola distanza
    assegnazione = richiesta.assegnazione_originale
    cliente = assegnazione.cliente
    if sostituto.latitudine and sostituto.longitudine and cliente.latitudine and cliente.longitudine:
        richiesta.distanza_km = geodesic(
            (sostituto.latitudine, sostituto.longitudine),
            (cliente.latitudine, cliente.longitudine)
        ).km
    
    richiesta.save()
    
    # Prepara info compagni di squadra
    squadra = assegnazione.turno.squadra
    compagni = []
    if squadra:
        for comp in squadra.componenti.exclude(id=richiesta.dipendente_assente.id):
            tel = comp.telefono or 'N/D'
            compagni.append(f"  • {comp.nome} {comp.cognome} (tel: {tel})")
        if squadra.caposquadra and squadra.caposquadra.id != richiesta.dipendente_assente.id:
            tel = squadra.caposquadra.telefono or 'N/D'
            compagni.append(f"  • {squadra.caposquadra.nome} {squadra.caposquadra.cognome} (Caposquadra, tel: {tel})")
    
    compagni_str = '\n'.join(compagni) if compagni else '  Nessun compagno'
    dist_str = f"{richiesta.distanza_km:.1f} km" if richiesta.distanza_km else "N/D"
    
    msg = (
        f"🔔 RICHIESTA DI SOSTITUZIONE\n\n"
        f"📍 Cliente: {cliente.ragione_sociale}\n"
        f"📫 Indirizzo: {cliente.indirizzo_sede}\n"
        f"📅 Data: {assegnazione.turno.data.strftime('%d/%m/%Y')}\n"
        f"🕐 Orario: {assegnazione.orario_inizio_previsto.strftime('%H:%M')}-"
        f"{assegnazione.orario_fine_previsto.strftime('%H:%M')}\n"
        f"📏 Distanza da casa tua: {dist_str}\n\n"
        f"👥 Squadra: {squadra.nome if squadra else 'N/D'}\n"
        f"Compagni:\n{compagni_str}\n\n"
        f"⏰ Hai 1 ora per rispondere."
    )
    
    # Invia via Telegram
    if sostituto.telegram_chat_id:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if bot_token:
            keyboard = {
                "inline_keyboard": [[
                    {"text": "✅ Accetto", "callback_data": f"accetta_sost_{richiesta.pk}"},
                    {"text": "❌ Rifiuto", "callback_data": f"rifiuta_sost_{richiesta.pk}"}
                ]]
            }
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": sostituto.telegram_chat_id,
                        "text": msg,
                        "reply_markup": json.dumps(keyboard)
                    },
                    timeout=10
                )
            except Exception:
                pass
    
    return richiesta


def gestisci_risposta_sostituto(richiesta_id, accettato):
    """
    Gestisce la risposta del sostituto.
    Se accettato: assegna al turno, stato COMPLETATA.
    Se rifiutato/scaduto: passa al prossimo sostituto.
    """
    from .models import RichiestaSostituzione
    
    try:
        richiesta = RichiestaSostituzione.objects.get(pk=richiesta_id)
    except RichiestaSostituzione.DoesNotExist:
        return None
    
    richiesta.risposta_sostituto_il = timezone.now()
    
    if accettato:
        richiesta.stato = 'COMPLETATA'
        richiesta.save()
        
        # Notifica il RA e l'admin
        _notifica_completamento(richiesta)
        return richiesta
    else:
        richiesta.stato = 'RIFIUTATA'
        richiesta.sostituto_corrente_idx += 1
        richiesta.sostituto = None
        richiesta.save()
        
        # Prova il prossimo sostituto
        return approva_e_invia_sostituto(richiesta.pk)


def verifica_timeout_sostituzioni():
    """
    Da chiamare periodicamente (es. ogni 15 min via cron/management command).
    Verifica le richieste INVIATA con timeout > 1h e passa al sostituto successivo.
    """
    from .models import RichiestaSostituzione
    
    scadenza = timezone.now() - timedelta(hours=1)
    richieste_scadute = RichiestaSostituzione.objects.filter(
        stato='INVIATA',
        inviata_sostituto_il__lt=scadenza
    )
    
    for richiesta in richieste_scadute:
        richiesta.stato = 'SCADUTA'
        richiesta.sostituto_corrente_idx += 1
        richiesta.sostituto = None
        richiesta.save()
        approva_e_invia_sostituto(richiesta.pk)


def _notifica_completamento(richiesta):
    """Notifica il RA e l'admin che la sostituzione è stata accettata."""
    import requests, json
    from django.conf import settings
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return
    
    assegnazione = richiesta.assegnazione_originale
    msg = (
        f"✅ SOSTITUZIONE CONFERMATA\n\n"
        f"Sostituto: {richiesta.sostituto}\n"
        f"Cliente: {assegnazione.cliente.ragione_sociale}\n"
        f"Data: {assegnazione.turno.data.strftime('%d/%m/%Y')}\n"
        f"Orario: {assegnazione.orario_inizio_previsto.strftime('%H:%M')}-"
        f"{assegnazione.orario_fine_previsto.strftime('%H:%M')}\n"
        f"Sostituisce: {richiesta.dipendente_assente} ({richiesta.motivo_assenza})"
    )
    
    # Notifica RA
    if richiesta.responsabile_area and richiesta.responsabile_area.dipendente.telegram_chat_id:
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": richiesta.responsabile_area.dipendente.telegram_chat_id, "text": msg},
                timeout=10
            )
        except Exception:
            pass
    
    # Notifica Titolari
    notifica_titolari(f"✅ Sostituzione confermata: {richiesta.sostituto} copre {richiesta.dipendente_assente} "
                      f"({assegnazione.cliente.ragione_sociale} - {assegnazione.turno.data.strftime('%d/%m')})")


def notifica_nuovo_messaggio(dipendente, testo=None, foto_url=None):
    """Notifica admin, RA della squadra e titolari quando arriva un messaggio da un dipendente."""
    import requests
    from django.conf import settings
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return
    
    # Ignora messaggi di comando automatici
    if testo and testo.startswith('/'):
        return
    
    # Tronca testo lungo
    anteprima = (testo or '📷 Foto')[:120]
    if testo and len(testo) > 120:
        anteprima += '…'
    
    squadra = None
    try:
        from django.utils import timezone as tz
        assegnazione_oggi = dipendente.assegnazioni.filter(
            turno__data=tz.now().date()
        ).select_related('turno__squadra').first()
        if assegnazione_oggi:
            squadra = assegnazione_oggi.turno.squadra
    except Exception:
        pass
    
    msg = (
        f"💬 <b>Nuovo messaggio da {dipendente}</b>\n"
        f"{anteprima}\n\n"
        f"🔗 <a href='https://kandor.onrender.com/centro-messaggi/'>Rispondi nel Centro Messaggi</a>"
    )
    
    destinatari = set()
    
    # Admin
    admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', '')
    if admin_chat_id:
        destinatari.add(admin_chat_id)
    
    # RA della squadra del dipendente
    if squadra:
        try:
            from .models import ResponsabileArea
            ra = ResponsabileArea.objects.filter(squadre=squadra).select_related('dipendente').first()
            if ra and ra.dipendente.telegram_chat_id:
                destinatari.add(ra.dipendente.telegram_chat_id)
        except Exception:
            pass
    
    # Titolari
    try:
        from .models import Titolare
        for titolare in Titolare.objects.filter(notifiche_attive=True):
            cid = titolare.get_chat_id()
            if cid:
                destinatari.add(cid)
    except Exception:
        pass
    
    for chat_id in destinatari:
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML",
                      "disable_notification": False},
                timeout=5
            )
        except Exception:
            pass


def notifica_titolari(messaggio, solo_attivi=True):
    """Invia un messaggio Telegram a tutti i titolari configurati."""
    import requests
    from django.conf import settings
    from .models import Titolare
    
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return
    
    qs = Titolare.objects.filter(notifiche_attive=True) if solo_attivi else Titolare.objects.all()
    
    for titolare in qs:
        chat_id = titolare.get_chat_id()
        if not chat_id:
            continue
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": messaggio, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception:
            pass


def notifica_titolari_sostituzione_fallita(richiesta):
    """Alert ai titolari quando tutti i sostituti disponibili hanno rifiutato."""
    assegnazione = richiesta.assegnazione_originale
    msg = (
        f"🚨 <b>ALERT: TURNO SCOPERTO</b>\n\n"
        f"Assente: {richiesta.dipendente_assente} ({richiesta.motivo_assenza})\n"
        f"Cliente: {assegnazione.cliente.ragione_sociale}\n"
        f"Data: {assegnazione.turno.data.strftime('%d/%m/%Y')}\n"
        f"Orario: {assegnazione.orario_inizio_previsto.strftime('%H:%M') if assegnazione.orario_inizio_previsto else '?'}"
        f"-{assegnazione.orario_fine_previsto.strftime('%H:%M') if assegnazione.orario_fine_previsto else '?'}\n\n"
        f"❌ Nessun sostituto disponibile. Intervento manuale richiesto."
    )
    notifica_titolari(msg)

