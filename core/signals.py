"""
Signals per sincronizzare il calendario turni con le Programmazioni Ricorrenti.
Quando una ProgrammazioneRicorrente viene modificata o eliminata, 
i turni futuri collegati vengono cancellati e rigenerati.

OTTIMIZZATO: rigenera solo i turni della specifica programmazione modificata,
non tutti i 365 giorni di tutte le programmazioni.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta, date, datetime


def _cleanup_future_assignments(instance):
    """Rimuove le assegnazioni future collegate a una programmazione specifica."""
    from core.models import AssegnazioneTurno, Turno
    
    today = timezone.now().date()
    
    future_assignments = AssegnazioneTurno.objects.filter(
        programmazione_feriale=instance,
        turno__data__gte=today
    )
    
    turno_ids = list(future_assignments.values_list('turno_id', flat=True))
    deleted_count = future_assignments.count()
    future_assignments.delete()
    
    # Elimina turni rimasti vuoti
    Turno.objects.filter(pk__in=turno_ids).exclude(assegnazioni__isnull=False).delete()
    
    return deleted_count


def _genera_turni_singola_programmazione(prog, days=365):
    """
    Genera turni per UNA SOLA programmazione ricorrente.
    Molto più veloce di genera_turni_automatici() che scorre TUTTE.
    """
    from core.models import Turno, AssegnazioneTurno
    
    if not prog.squadra_abituale:
        return 0
    
    today = timezone.now().date()
    # Se la data di inizio contratto e' nel passato, la generazione inizia da quella data
    if prog.data_inizio_contratto and prog.data_inizio_contratto < today:
        start_date = prog.data_inizio_contratto
    else:
        start_date = today

    end_date = today + timedelta(days=days)
    count = 0
    
    current_date = start_date
    while current_date <= end_date:
        # Controllo periodo contrattuale
        if prog.data_inizio_contratto and current_date < prog.data_inizio_contratto:
            current_date += timedelta(days=1)
            continue
        if prog.data_fine_contratto and current_date > prog.data_fine_contratto:
            break  # Oltre la fine contratto, stop
        
        match = False
        weekday = current_date.weekday()
        
        if prog.tipo_ripetizione == 'SETTIMANALE' and prog.giorno_settimana == weekday:
            match = True
        elif prog.tipo_ripetizione == 'MENSILE' and prog.giorno_mese == current_date.day:
            match = True
        elif prog.tipo_ripetizione == 'BISETTIMANALE' and prog.giorno_settimana == weekday:
            if prog.data_inizio_contratto:
                delta_days = (current_date - prog.data_inizio_contratto).days
                settimane = delta_days // 7
                if delta_days >= 0 and settimane % 2 == 0:
                    match = True
        
        if match:
            turno, _ = Turno.objects.get_or_create(
                data=current_date,
                squadra=prog.squadra_abituale,
                defaults={'mezzo': prog.mezzo_abituale}
            )
            
            exists = AssegnazioneTurno.objects.filter(
                turno=turno,
                programmazione_feriale=prog
            ).exists()
            
            if not exists:
                orario_inizio = prog.ora_inizio
                if prog.durata:
                    dt_start = datetime.combine(date.today(), orario_inizio)
                    hours = int(prog.durata)
                    minutes = int((prog.durata - hours) * 60)
                    dt_end = dt_start + timedelta(hours=hours, minutes=minutes)
                    orario_fine = dt_end.time()
                else:
                    orario_fine = orario_inizio
                
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


@receiver(pre_delete, sender='core.ProgrammazioneRicorrente')
def on_programmazione_delete(sender, instance, **kwargs):
    """Quando eliminata: cancella solo le assegnazioni future di questa programmazione."""
    deleted = _cleanup_future_assignments(instance)
    print(f"[SYNC] Eliminata prog. '{instance.cliente}': {deleted} assegnazioni rimosse.")


@receiver(post_save, sender='core.ProgrammazioneRicorrente')
def on_programmazione_save(sender, instance, raw=False, **kwargs):
    """Quando modificata: cancella e rigenera SOLO i turni di questa programmazione.
    raw=True durante loaddata/fixtures: salta per evitare errori di FK mancanti."""
    if raw:
        return
    deleted = _cleanup_future_assignments(instance)
    created = _genera_turni_singola_programmazione(instance)
    print(f"[SYNC] Aggiornata prog. '{instance.cliente}': {deleted} rimossi, {created} creati.")


@receiver(post_save, sender='core.Assenza')
def on_assenza_save(sender, instance, created, raw=False, **kwargs):
    """
    Quando un'assenza viene salvata ed è AVVALATA dall'Amministrazione (stato_approvazione == 'APPROVATA'):
    Avvia la procedura automatica di sostituzione per i turni scoperti.
    """
    if raw or instance.is_processed:
        return
    
    # REQUISITO FONDAMENTALE: La sostituzione parte SOLO DOPO l'avvallo dell'amministrazione
    if instance.stato_approvazione != 'APPROVATA':
        return
    
    from core.services import avvia_sostituzione_per_assenza
    richieste_create = avvia_sostituzione_per_assenza(instance)
    if richieste_create > 0:
        print(f"[Assenza Signal] Assenza ID {instance.pk} avvallata per {instance.dipendente}: {richieste_create} sostituzioni create.")



