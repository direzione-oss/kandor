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
    today = timezone.now().date()
    end_date = today + timedelta(days=days)
    
    count = 0
    programmazioni = ProgrammazioneRicorrente.objects.filter(squadra_abituale__isnull=False)

    # Programmazioni che hanno già uno storico nel passato non devono rigenerare nuovi turni nel passato
    progs_with_past = set(
        AssegnazioneTurno.objects.filter(
            programmazione_feriale__in=programmazioni,
            turno__data__lt=today
        ).values_list('programmazione_feriale_id', flat=True).distinct()
    )

    # Trova la data piu' remota tra i contratti attivi (senza storico già consolidato) e oggi
    min_start = today
    for prog in programmazioni:
        if prog.pk not in progs_with_past and prog.data_inizio_contratto and prog.data_inizio_contratto < min_start:
            min_start = prog.data_inizio_contratto

    start_date = min_start
    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.weekday()
        day_of_month = current_date.day
        
        match_giornalieri = programmazioni.filter(tipo_ripetizione='GIORNALIERO')
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
        
        matches = list(match_giornalieri) + list(match_settimanali) + list(match_mensili) + match_bisettimanali
        
        for prog in matches:
            # Controllo periodo contrattuale
            if prog.data_inizio_contratto and current_date < prog.data_inizio_contratto:
                continue  # Non ancora iniziato
            if prog.data_fine_contratto and current_date > prog.data_fine_contratto:
                continue  # Contratto scaduto
            
            if current_date < today and prog.pk in progs_with_past:
                continue

            squadra = prog.squadra_abituale

            # Evita duplicati (controlla sulla data per non duplicare se la squadra è cambiata)
            exists = AssegnazioneTurno.objects.filter(
                turno__data=current_date,
                programmazione_feriale=prog
            ).exists()
            
            if not exists:
                # Crea/Recupera Turno
                turno = Turno.objects.filter(data=current_date, squadra=squadra).first()
                if not turno:
                    turno = Turno.objects.create(
                        data=current_date,
                        squadra=squadra,
                        mezzo=prog.mezzo_abituale
                    )

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
                
                assign = AssegnazioneTurno.objects.create(
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

def _is_qualifica_compatibile(qualifica_richiesta, dip_qualifiche_nomi):
    """Verifica se le qualifiche del dipendente sono compatibili con la qualifica richiesta (anche per affinità, es. PULIZIA / ADD PULIZIE)."""
    if not qualifica_richiesta:
        return True
    req_nome = (getattr(qualifica_richiesta, 'nome', str(qualifica_richiesta)) or '').upper().strip()
    if not req_nome:
        return True
    dip_upper = [q.upper().strip() for q in dip_qualifiche_nomi]
    if req_nome in dip_upper:
        return True
    # Gruppi di affinità semantica presenti in anagrafica
    radici = ['PULIZI', 'PORTIN', 'RECEPTION', 'IMPIEG', 'MAGAZZIN', 'GIARDIN', 'MANUTEN']
    for rad in radici:
        if rad in req_nome and any(rad in dq for dq in dip_upper):
            return True
    return False


def trova_sostituti(cliente, data, ora_inizio, ora_fine, escludi_dipendenti_ids=None, qualifica_richiesta=None, escludi_richiesta_id=None):
    """
    Trova l'elenco dei dipendenti pronti a sostituire (is_sostituto=True, stato='ATTIVO')
    e LIBERI nella data e fascia oraria indicate.
    Filtri:
    1. Stato ATTIVO e is_sostituto=True
    2. Non in Ferie/Malattia/Permesso (non rifiutata) sovrapposta in quella data/orario
    3. Non già impegnati in un altro Turno coincidente (come caposquadra o componente attivo non escluso)
    4. Non già impegnati come sostituto in un'altra RichiestaSostituzione coincidente

    Ranking:
    1. Compatibilità qualifica (se specificata)
    2. Distanza geografica casa-cliente (crescente)
    3. Ordine alfabetico (cognome, nome)
    """
    from .models import Assenza, RichiestaSostituzione

    # 1. Filtro Dipendenti Attivi e Pronti a Sostituire (Jolly/Sostituti)
    candidati = Dipendente.objects.filter(stato='ATTIVO', is_sostituto=True).prefetch_related('qualifiche')

    escludi_set = set(escludi_dipendenti_ids or [])

    # 2. Escludi Assenze (non rifiutate) che coprono la data e l'orario del turno
    data_check = data.date() if isinstance(data, datetime) else data

    assenze_giorno = Assenza.objects.filter(
        data_inizio__lte=data_check,
        data_fine__gte=data_check
    ).exclude(stato_approvazione='RIFIUTATA')

    for ass in assenze_giorno:
        # Se l'assenza ha orario specifico (es. permesso orario), verifica sovrapposizione col turno
        if ass.ora_inizio and ass.ora_fine and ora_inizio and ora_fine:
            if ass.ora_fine <= ora_inizio or ass.ora_inizio >= ora_fine:
                continue  # Il permesso non si sovrappone all'orario del turno
        escludi_set.add(ass.dipendente_id)

    # 3. Escludi chi è già occupato in un turno sovrapposto (come Caposquadra o Componente non escluso)
    assegnazioni_concomitanti = AssegnazioneTurno.objects.filter(
        turno__data=data_check
    ).select_related('turno__squadra').prefetch_related('turno__squadra__componenti', 'dipendenti_esclusi')

    if ora_inizio and ora_fine:
        assegnazioni_concomitanti = assegnazioni_concomitanti.filter(
            orario_inizio_previsto__lt=ora_fine,
            orario_fine_previsto__gt=ora_inizio
        )

    for a_conc in assegnazioni_concomitanti:
        sq = a_conc.turno.squadra if a_conc.turno else None
        if not sq:
            continue
        esclusi_turno_ids = {d.id for d in a_conc.dipendenti_esclusi.all()}
        if sq.caposquadra_id and sq.caposquadra_id not in esclusi_turno_ids:
            escludi_set.add(sq.caposquadra_id)
        for comp in sq.componenti.all():
            if comp.id not in esclusi_turno_ids:
                escludi_set.add(comp.id)

    # 4. Escludi chi è già assegnato come sostituto in un'altra sostituzione sovrapposta nello stesso giorno
    sost_concomitanti = RichiestaSostituzione.objects.filter(
        assegnazione_originale__turno__data=data_check,
        stato__in=['INVIATA', 'ACCETTATA', 'COMPLETATA'],
        sostituto__isnull=False
    )
    if escludi_richiesta_id:
        sost_concomitanti = sost_concomitanti.exclude(pk=escludi_richiesta_id)
    if ora_inizio and ora_fine:
        sost_concomitanti = sost_concomitanti.filter(
            assegnazione_originale__orario_inizio_previsto__lt=ora_fine,
            assegnazione_originale__orario_fine_previsto__gt=ora_inizio
        )
    for sc in sost_concomitanti:
        escludi_set.add(sc.sostituto_id)

    if escludi_set:
        candidati = candidati.exclude(id__in=escludi_set)

    # 5. Calcolo Distanza, Compatibilità Qualifica e Ranking
    risultati = []
    coord_cliente = (cliente.latitudine, cliente.longitudine) if cliente else (None, None)
    has_client_coords = coord_cliente[0] is not None and coord_cliente[1] is not None

    for dip in candidati:
        distanza = float('inf')
        coord_dip = (dip.latitudine, dip.longitudine)

        if has_client_coords and coord_dip[0] is not None and coord_dip[1] is not None:
            try:
                distanza = geodesic(coord_dip, coord_cliente).km
            except Exception:
                distanza = float('inf')

        skills = [q.nome for q in dip.qualifiche.all()]
        compatibile = _is_qualifica_compatibile(qualifica_richiesta, skills)

        risultati.append({
            'dipendente': dip,
            'distanza_km': distanza,
            'skills': skills,
            'qualifica_compatibile': compatibile,
        })

    # Ordina: prima chi ha qualifica compatibile, poi per distanza crescente, infine per cognome/nome
    risultati.sort(key=lambda x: (
        0 if x['qualifica_compatibile'] else 1,
        x['distanza_km'],
        (x['dipendente'].cognome or '').upper(),
        (x['dipendente'].nome or '').upper()
    ))

    return risultati


# Manteniamo compatibilità con il vecchio nome
trova_jolly = trova_sostituti


def crea_richiesta_sostituzione(assegnazione, dipendente_assente, motivo, note='', auto_invia=False):
    """
    Crea una richiesta di sostituzione:
    1. Calcola lista sostituti pronti a sostituire (is_sostituto=True) e liberi nel turno
    2. Crea RichiestaSostituzione con stato APERTA (così l'Amministrazione può scegliere
       chi assegnare o a chi inviare la notifica)
    3. Se presente un Responsabile Area con Telegram, gli invia notifica informativa.
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

    # Escludi i componenti attivi di questo stesso turno e il dipendente assente
    esclusi_turno_ids = set(assegnazione.dipendenti_esclusi.values_list('id', flat=True))
    componenti_ids = [dipendente_assente.id]
    if squadra:
        for cid in squadra.componenti.values_list('id', flat=True):
            if cid not in esclusi_turno_ids and cid not in componenti_ids:
                componenti_ids.append(cid)
        if squadra.caposquadra_id and squadra.caposquadra_id not in esclusi_turno_ids and squadra.caposquadra_id not in componenti_ids:
            componenti_ids.append(squadra.caposquadra_id)

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

    # Crea la richiesta in stato APERTA (pronta per la selezione da parte dell'Amministrazione)
    richiesta = RichiestaSostituzione.objects.create(
        assegnazione_originale=assegnazione,
        dipendente_assente=dipendente_assente,
        motivo_assenza=motivo,
        responsabile_area=ra,
        stato='APERTA',
        sostituti_candidati=sostituti_ids,
        note=note,
    )

    # Notifica Responsabile Area via Telegram se configurato
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
                f"Candidati liberi disponibili: {len(sostituti)}"
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
    elif auto_invia:
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
    """Notifica via Telegram SOLO i Responsabili (Titolari, Responsabili Area) e il Gestionale su PC (Admin).
    I dipendenti comuni NON ricevono i messaggi inviati da altri dipendenti.
    """
    import requests
    from django.conf import settings
    from .models import Dipendente, Titolare, ResponsabileArea

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return

    # Ignora comandi automatici del bot
    if testo and testo.startswith('/'):
        return

    anteprima = (testo or '📷 Foto')[:120]
    if testo and len(testo) > 120:
        anteprima += '…'

    msg = (
        f"💬 <b>Nuovo messaggio da {dipendente}</b>\n"
        f"{anteprima}\n\n"
        f"🔗 <a href='https://kandor.onrender.com/chat-simulator/'>Rispondi nel Centro Messaggi</a>"
    )

    chat_ids = set()

    # 1. Admin Telegram (Gestionale PC)
    admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
    if admin_chat_id:
        chat_ids.add(str(admin_chat_id))

    # 2. Titolari con notifiche attive
    try:
        for titolare in Titolare.objects.filter(notifiche_attive=True):
            cid = titolare.get_chat_id()
            if cid:
                chat_ids.add(str(cid))
    except Exception:
        pass

    # 3. Responsabili Area con Telegram collegato
    try:
        for ra in ResponsabileArea.objects.select_related('dipendente').filter(
            dipendente__telegram_chat_id__isnull=False
        ).exclude(dipendente__telegram_chat_id=''):
            if ra.dipendente and ra.dipendente.pk != dipendente.pk:
                chat_ids.add(str(ra.dipendente.telegram_chat_id))
    except Exception:
        pass

    # 4. Dipendenti con flag riceve_notifiche_messaggi SOLO se ricoprono un ruolo da responsabile o titolare
    try:
        for ref in Dipendente.objects.filter(
            riceve_notifiche_messaggi=True,
            telegram_chat_id__isnull=False
        ).exclude(telegram_chat_id='').exclude(pk=dipendente.pk):
            is_responsabile = hasattr(ref, 'ruolo_responsabile') or hasattr(ref, 'titolare_profilo')
            if is_responsabile:
                chat_ids.add(str(ref.telegram_chat_id))
    except Exception:
        pass

    for chat_id in chat_ids:
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
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


def get_richieste_sostituzione_per_assenza(assenza):
    """Restituisce tutte le RichiestaSostituzione attive collegate al dipendente e al periodo dell'assenza."""
    from .models import RichiestaSostituzione
    qs = RichiestaSostituzione.objects.filter(
        dipendente_assente=assenza.dipendente,
        assegnazione_originale__turno__data__gte=assenza.data_inizio,
        assegnazione_originale__turno__data__lte=assenza.data_fine,
        stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA', 'ACCETTATA', 'COMPLETATA']
    ).select_related('assegnazione_originale__cliente', 'assegnazione_originale__turno', 'sostituto').order_by('assegnazione_originale__turno__data', 'assegnazione_originale__orario_inizio_previsto')
    return list(qs)


def avvia_sostituzione_per_assenza(assenza):
    """
    Esegue la procedura di sostituzione per un'assenza già AVVALATA dall'amministrazione.
    Trova i turni scoperti nel periodo dell'assenza e crea una RichiestaSostituzione (in stato APERTA)
    per ciascun turno non ancora coperto.
    """
    if assenza.stato_approvazione != 'APPROVATA':
        return 0

    from .models import Assenza, AssegnazioneTurno, Squadra, RichiestaSostituzione
    from django.db.models import Q
    import datetime

    # Evita ricorsione via signal usando update() atomico
    if not assenza.is_processed:
        Assenza.objects.filter(pk=assenza.pk).update(is_processed=True)
        assenza.is_processed = True

    dip = assenza.dipendente
    squadre = Squadra.objects.filter(Q(componenti=dip) | Q(caposquadra=dip)).distinct()

    if not squadre.exists():
        return 0

    totale_create = 0
    data = assenza.data_inizio
    while data <= assenza.data_fine:
        assegnazioni = AssegnazioneTurno.objects.filter(
            turno__data=data,
            turno__squadra__in=squadre
        ).select_related('turno', 'turno__squadra', 'cliente').prefetch_related('dipendenti_esclusi')

        for a in assegnazioni:
            # Se il dipendente era già escluso da questo turno, non serve sostituirlo
            if any(d.id == dip.id for d in a.dipendenti_esclusi.all()):
                continue

            # Se è un permesso ad ore, verifica eventuale sovrapposizione oraria
            if assenza.ora_inizio and assenza.ora_fine and a.orario_inizio_previsto and a.orario_fine_previsto:
                if a.orario_fine_previsto <= assenza.ora_inizio or a.orario_inizio_previsto >= assenza.ora_fine:
                    continue  # Il permesso non copre l'orario del turno

            gia_pres = RichiestaSostituzione.objects.filter(
                assegnazione_originale=a,
                dipendente_assente=dip,
                stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA', 'ACCETTATA', 'COMPLETATA']
            ).exists()

            if not gia_pres:
                try:
                    orario_str = f" ({assenza.get_orario_display()})" if assenza.ora_inizio else ""
                    crea_richiesta_sostituzione(
                        a, dip, assenza.tipo,
                        f"Avvallata da Amministrazione — {assenza.tipo}{orario_str}",
                        auto_invia=False
                    )
                    totale_create += 1
                except Exception as e:
                    print(f"[Avvallo Assenza] Errore sostituzione per {a.pk}: {e}")

        data += datetime.timedelta(days=1)

    return totale_create


def assegna_sostituto_da_ufficio(richiesta_id, sostituto_id=None, applica_a_periodo=False):
    """
    Permette all'Amministrazione di confermare direttamente dall'ufficio il sostituto
    (sia scegliendo un candidato libero dalla lista, sia confermando il sostituto già in attesa
    se il dipendente non riesce a rispondere su Telegram).
    Se applica_a_periodo=True, assegna lo stesso sostituto anche agli altri turni scoperti
    della stessa assenza.
    """
    from .models import RichiestaSostituzione, Dipendente, Assenza
    import requests
    from django.conf import settings

    try:
        richiesta = RichiestaSostituzione.objects.select_related(
            'assegnazione_originale__cliente',
            'assegnazione_originale__turno__squadra',
            'dipendente_assente',
            'sostituto'
        ).get(pk=richiesta_id)
    except RichiestaSostituzione.DoesNotExist:
        return {'ok': False, 'error': 'Richiesta di sostituzione non trovata'}

    if sostituto_id:
        try:
            sostituto = Dipendente.objects.get(pk=sostituto_id)
        except Dipendente.DoesNotExist:
            return {'ok': False, 'error': 'Sostituto selezionato non trovato'}
    elif richiesta.sostituto:
        sostituto = richiesta.sostituto
    else:
        return {'ok': False, 'error': 'Seleziona il sostituto da confermare'}

    # Elenco delle richieste da completare
    richieste_target = [richiesta]
    if applica_a_periodo:
        data_turno = richiesta.assegnazione_originale.turno.data
        assenza_collegata = Assenza.objects.filter(
            dipendente=richiesta.dipendente_assente,
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).exclude(stato_approvazione='RIFIUTATA').first()
        if assenza_collegata:
            altre = RichiestaSostituzione.objects.filter(
                dipendente_assente=richiesta.dipendente_assente,
                assegnazione_originale__turno__data__gte=assenza_collegata.data_inizio,
                assegnazione_originale__turno__data__lte=assenza_collegata.data_fine,
                stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA']
            ).exclude(pk=richiesta.pk).select_related(
                'assegnazione_originale__cliente',
                'assegnazione_originale__turno__squadra'
            )
            richieste_target.extend(list(altre))

    now = timezone.now()
    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    confermate_count = 0

    for req in richieste_target:
        req.sostituto = sostituto
        req.stato = 'COMPLETATA'
        if not req.approvata_ra_il:
            req.approvata_ra_il = now
        if not req.inviata_sostituto_il:
            req.inviata_sostituto_il = now
        req.risposta_sostituto_il = now

        assegn = req.assegnazione_originale
        cliente = assegn.cliente
        if sostituto.latitudine and sostituto.longitudine and cliente.latitudine and cliente.longitudine:
            try:
                req.distanza_km = geodesic(
                    (sostituto.latitudine, sostituto.longitudine),
                    (cliente.latitudine, cliente.longitudine)
                ).km
            except Exception:
                pass

        nota_uff = f"Confermata dall'Ufficio: {sostituto.cognome} {sostituto.nome}"
        if nota_uff not in (req.note or ''):
            req.note = f"{req.note}\n{nota_uff}".strip()
        req.save()
        confermate_count += 1

        # Invia promemoria su Telegram al sostituto (se ha Telegram) e notifica completamento
        if bot_token and sostituto.telegram_chat_id:
            try:
                orario_str = f"{assegn.orario_inizio_previsto.strftime('%H:%M')}-{assegn.orario_fine_previsto.strftime('%H:%M')}" if (assegn.orario_inizio_previsto and assegn.orario_fine_previsto) else "N/D"
                msg_sost = (
                    f"✅ SOSTITUZIONE CONFERMATA DALL'UFFICIO\n\n"
                    f"📍 Cliente: {cliente.ragione_sociale}\n"
                    f"📫 Indirizzo: {cliente.indirizzo_sede or 'N/D'}\n"
                    f"📅 Data: {assegn.turno.data.strftime('%d/%m/%Y')}\n"
                    f"🕐 Orario: {orario_str}\n"
                    f"👤 In sostituzione di: {req.dipendente_assente}\n\n"
                    f"L'Amministrazione ha registrato la tua assegnazione per questo turno. Buon lavoro! 👍"
                )
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": sostituto.telegram_chat_id, "text": msg_sost},
                    timeout=5
                )
            except Exception:
                pass

        try:
            _notifica_completamento(req)
        except Exception:
            pass

    return {
        'ok': True,
        'richiesta': richiesta,
        'sostituto_nome': f"{sostituto.cognome} {sostituto.nome}",
        'confermate_count': confermate_count,
    }


def segna_non_sostituito_da_ufficio(richiesta_id, applica_a_periodo=False):
    """
    Permette all'Amministrazione di segnare un turno scoperto come NON SOSTITUITO (Salto Turno).
    Pulisce/elimina eventuali TimeTracking per il dipendente assente e l'eventuale sostituto
    affinché non vengano contabilizzate ore né al cliente né al dipendente.
    """
    from .models import RichiestaSostituzione, TimeTracking, Assenza

    try:
        richiesta = RichiestaSostituzione.objects.select_related(
            'assegnazione_originale__cliente',
            'assegnazione_originale__turno__squadra',
            'dipendente_assente',
            'sostituto'
        ).get(pk=richiesta_id)
    except RichiestaSostituzione.DoesNotExist:
        return {'ok': False, 'error': 'Richiesta di sostituzione non trovata'}

    richieste_target = [richiesta]
    if applica_a_periodo:
        data_turno = richiesta.assegnazione_originale.turno.data
        assenza_collegata = Assenza.objects.filter(
            dipendente=richiesta.dipendente_assente,
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).exclude(stato_approvazione='RIFIUTATA').first()
        if assenza_collegata:
            altre = RichiestaSostituzione.objects.filter(
                dipendente_assente=richiesta.dipendente_assente,
                assegnazione_originale__turno__data__gte=assenza_collegata.data_inizio,
                assegnazione_originale__turno__data__lte=assenza_collegata.data_fine,
                stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA', 'NON_SOSTITUITO', 'RIFIUTATA', 'SCADUTA']
            ).exclude(pk=richiesta.pk).select_related(
                'assegnazione_originale__cliente',
                'assegnazione_originale__turno__squadra'
            )
            richieste_target.extend(list(altre))

    processed_count = 0
    for req in richieste_target:
        prev_sostituto = req.sostituto
        req.sostituto = None
        req.stato = 'NON_SOSTITUITO'
        nota_str = "Segnato dall'Ufficio come Non Sostituito (Salto Turno - 0 ore)"
        if nota_str not in (req.note or ''):
            req.note = f"{req.note}\n{nota_str}".strip()
        req.save()

        # Cancella TimeTracking per dipendente assente ed eventuale vecchio sostituto
        assegn = req.assegnazione_originale
        if req.dipendente_assente:
            TimeTracking.objects.filter(assegnazione=assegn, dipendente=req.dipendente_assente).delete()
            assegn.dipendenti_esclusi.add(req.dipendente_assente)
        if prev_sostituto:
            TimeTracking.objects.filter(assegnazione=assegn, dipendente=prev_sostituto).delete()

        processed_count += 1

    return {
        'ok': True,
        'richiesta': richiesta,
        'processed_count': processed_count,
        'message': f"Segnato come Non Sostituito (Salto Turno) per {processed_count} turno/i. Ore non contabilizzate."
    }


def avvalla_assenza_da_amministrazione(assenza_id, note_admin=''):
    """
    Procedura di avvallo dell'amministrazione:
    1. Imposta lo stato a APPROVATA
    2. Avvia la procedura di sostituzione creando le RichiestaSostituzione per i turni scoperti
    3. Notifica il dipendente via Telegram
    """
    from .models import Assenza
    import requests
    from django.conf import settings

    try:
        assenza = Assenza.objects.get(pk=assenza_id)
    except Assenza.DoesNotExist:
        return {'ok': False, 'error': 'Assenza non trovata'}

    assenza.stato_approvazione = 'APPROVATA'
    assenza.is_processed = True
    assenza.approvata_da_admin_il = timezone.now()
    if note_admin:
        assenza.note = f"{assenza.note}\nNote Admin: {note_admin}".strip()
    assenza.save()

    avvia_sostituzione_per_assenza(assenza)
    richieste_attive = get_richieste_sostituzione_per_assenza(assenza)
    num_sostituzioni = len(richieste_attive)
    richieste_ids = [r.id for r in richieste_attive]

    # Notifica Telegram al Dipendente
    dip = assenza.dipendente
    if dip.telegram_chat_id:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if bot_token:
            if assenza.data_inizio == assenza.data_fine:
                periodo_str = assenza.data_inizio.strftime('%d/%m/%Y')
            else:
                periodo_str = f"{assenza.data_inizio.strftime('%d/%m/%Y')} - {assenza.data_fine.strftime('%d/%m/%Y')}"

            orario_str = f" ({assenza.get_orario_display()})" if assenza.ora_inizio else ""

            msg_dip = (
                f"✅ AVVALLO AMMINISTRAZIONE\n\n"
                f"La tua comunicazione di {assenza.tipo} per il periodo {periodo_str}{orario_str} "
                f"è stata AVVALATA E APPROVATA dall'Amministrazione.\n\n"
            )
            if num_sostituzioni > 0:
                msg_dip += f"🔄 In gestione la sostituzione per {num_sostituzioni} turno/i nel periodo."
            else:
                msg_dip += f"ℹ️ Nessun turno da sostituire nel periodo."

            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={'chat_id': dip.telegram_chat_id, 'text': msg_dip},
                    timeout=5
                )
            except Exception:
                pass

    return {
        'ok': True,
        'assenza': assenza,
        'num_sostituzioni': num_sostituzioni,
        'richieste_ids': richieste_ids,
        'prima_richiesta_id': richieste_ids[0] if richieste_ids else None,
    }


def rifiuta_assenza_da_amministrazione(assenza_id, note_admin=''):
    """
    Rifiuta l'assenza da parte dell'amministrazione.
    """
    from .models import Assenza
    import requests
    from django.conf import settings

    try:
        assenza = Assenza.objects.get(pk=assenza_id)
    except Assenza.DoesNotExist:
        return {'ok': False, 'error': 'Assenza non trovata'}

    assenza.stato_approvazione = 'RIFIUTATA'
    if note_admin:
        assenza.note = f"{assenza.note}\nNote Admin Rifiuto: {note_admin}".strip()
    assenza.save()

    # Notifica Telegram al Dipendente
    dip = assenza.dipendente
    if dip.telegram_chat_id:
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if bot_token:
            if assenza.data_inizio == assenza.data_fine:
                periodo_str = assenza.data_inizio.strftime('%d/%m/%Y')
            else:
                periodo_str = f"{assenza.data_inizio.strftime('%d/%m/%Y')} - {assenza.data_fine.strftime('%d/%m/%Y')}"

            msg_dip = (
                f"❌ COMUNICAZIONE NON AVVALATA\n\n"
                f"La tua comunicazione di {assenza.tipo} per il periodo {periodo_str} "
                f"NON è stata avvallata dall'Amministrazione.\n\n"
                f"Ti invitiamo a contattare la gestione per chiarimenti."
            )
            try:
                requests.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={'chat_id': dip.telegram_chat_id, 'text': msg_dip},
                    timeout=5
                )
            except Exception:
                pass

    return {'ok': True, 'assenza': assenza}


