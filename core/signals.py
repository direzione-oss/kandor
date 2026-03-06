"""
Signals per sincronizzare il calendario turni con le Programmazioni Ricorrenti.
Quando una ProgrammazioneRicorrente viene modificata o eliminata, 
i turni futuri collegati vengono cancellati e rigenerati.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone


@receiver(pre_delete, sender='core.ProgrammazioneRicorrente')
def on_programmazione_delete(sender, instance, **kwargs):
    """
    Quando una programmazione viene ELIMINATA, cancella tutte
    le assegnazioni e i turni futuri collegati.
    """
    from core.models import AssegnazioneTurno, Turno
    
    today = timezone.now().date()
    
    # Cancella assegnazioni future collegate a questa programmazione
    future_assignments = AssegnazioneTurno.objects.filter(
        programmazione_feriale=instance,
        turno__data__gte=today
    )
    
    # Raccogli i turni coinvolti prima di cancellare le assegnazioni
    turno_ids = list(future_assignments.values_list('turno_id', flat=True))
    
    deleted_count = future_assignments.count()
    future_assignments.delete()
    
    # Elimina anche i turni rimasti vuoti (senza più assegnazioni)
    for turno_id in turno_ids:
        turno = Turno.objects.filter(pk=turno_id).first()
        if turno and not turno.assegnazioni.exists():
            turno.delete()
    
    print(f"[SYNC] Programmazione eliminata per '{instance.cliente}': "
          f"{deleted_count} assegnazioni future rimosse.")


@receiver(post_save, sender='core.ProgrammazioneRicorrente')
def on_programmazione_save(sender, instance, **kwargs):
    """
    Quando una programmazione viene MODIFICATA, cancella le assegnazioni
    future collegate e rigenera i turni per tener conto delle modifiche.
    """
    from core.models import AssegnazioneTurno, Turno
    from core.services import genera_turni_automatici
    
    today = timezone.now().date()
    
    # Cancella assegnazioni future collegate a questa programmazione
    future_assignments = AssegnazioneTurno.objects.filter(
        programmazione_feriale=instance,
        turno__data__gte=today
    )
    
    turno_ids = list(future_assignments.values_list('turno_id', flat=True))
    
    deleted_count = future_assignments.count()
    future_assignments.delete()
    
    # Elimina turni rimasti vuoti
    for turno_id in turno_ids:
        turno = Turno.objects.filter(pk=turno_id).first()
        if turno and not turno.assegnazioni.exists():
            turno.delete()
    
    # Rigenera i turni (il servizio creerà solo quelli mancanti)
    new_count = genera_turni_automatici()
    
    print(f"[SYNC] Programmazione aggiornata per '{instance.cliente}': "
          f"{deleted_count} vecchie assegnazioni rimosse, {new_count} turni rigenerati.")
