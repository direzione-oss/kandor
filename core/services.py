from datetime import datetime, date, timedelta
from django.db.models import Q
from geopy.distance import geodesic
from django.utils import timezone
from .models import Dipendente, AssegnazioneTurno, ProgrammazioneRicorrente, RichiestaStraordinaria, Turno, Squadra

def genera_turni_automatici(days=7):
    """
    Genera i turni per i prossimi 'days' giorni basandosi sulla ProgrammazioneRicorrente.
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
        
        matches = list(match_settimanali) + list(match_mensili)
        
        for prog in matches:
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

def trova_jolly(cliente, data, ora_inizio, ora_fine, escludi_dipendenti_ids=None, qualifica_richiesta=None):
    """
    Trova un elenco compatibile di dipendenti per una copertura improvvisa (Jolly).
    Filtri:
    1. Stato ATTIVO
    2. Non in Ferie/Malattia/Permesso in quella data
    3. Non già impegnati in un Turno coincidente (controllo sovrapposizione oraria)
    
    Ranking:
    - Distanza geografica casa-lavoro (se coordinate disponibili)
    """
    
    # 1. Filtro Dipendenti Attivi
    candidati = Dipendente.objects.filter(stato='ATTIVO')

    # Filtro opzionale per Qualifica
    if qualifica_richiesta:
        candidati = candidati.filter(qualifiche=qualifica_richiesta)
    
    if escludi_dipendenti_ids:
        candidati = candidati.exclude(id__in=escludi_dipendenti_ids)

    # 2. Escludi Assenze
    # Converti datetime in date se necessario
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
