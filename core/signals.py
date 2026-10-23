"""
Signals per sincronizzare il calendario turni con le Programmazioni Ricorrenti,
le Squadre e lo stato dei Dipendenti (licenziamento / eliminazione).

REGOLA FONDAMENTALE STORICO CEDOLINI E ORE:
- Eliminando o modificando una Squadra, una ProgrammazioneRicorrente o licenziando/eliminando
  un Dipendente, vengono cancellati/aggiornati SOLO i turni dalla data di eliminazione/modifica
  (o data_licenziamento) in poi.
- Tutti i turni del passato (data < cutoff_date), le relative assegnazioni e le ore registrate
  (TimeTracking / ModificaCedolino / Assenze passate) vengono SEMPRE preservati.
"""
from django.db.models.signals import pre_save, post_save, pre_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, date, datetime


def _consolida_turni_passati_dipendenti(squadra, dipendente_ids, cutoff_date=None, save_squadra_tag=False):
    """
    Preserva la presenza storica dei dipendenti (dipendente_ids) nei turni passati
    (data < cutoff_date) della squadra indicata prima che i componenti vengano rimossi
    dalla squadra o che la squadra venga eliminata.
    Non sovrascrive mai i TimeTracking già esistenti.
    """
    from core.models import AssegnazioneTurno, TimeTracking, Dipendente, Assenza

    if not squadra or not squadra.pk:
        return 0

    if cutoff_date is None:
        cutoff_date = timezone.now().date()

    dip_ids = [int(pk) for pk in dipendente_ids if pk]
    if not dip_ids and not save_squadra_tag:
        return 0

    past_assigns = list(
        AssegnazioneTurno.objects.filter(
            turno__squadra=squadra,
            turno__data__lt=cutoff_date
        ).select_related('turno').prefetch_related('dipendenti_esclusi')
    )
    if not past_assigns:
        return 0

    if save_squadra_tag:
        tag = f"[Squadra: {squadra.nome}]"
        for assign in past_assigns:
            mansione = assign.mansione_svolta or ''
            if '[Squadra:' not in mansione:
                assign.mansione_svolta = f"{tag} {mansione}".strip()
                assign.save(update_fields=['mansione_svolta'])

    if not dip_ids:
        return 0

    dipendenti_map = {
        d.pk: d for d in Dipendente.objects.filter(pk__in=dip_ids)
    }
    if not dipendenti_map:
        return 0

    assign_ids = [a.pk for a in past_assigns]
    existing_tt_pairs = set(
        TimeTracking.objects.filter(
            assegnazione_id__in=assign_ids,
            dipendente_id__in=dipendenti_map.keys()
        ).values_list('assegnazione_id', 'dipendente_id')
    )

    min_date = min(a.turno.data for a in past_assigns)
    max_date = max(a.turno.data for a in past_assigns)
    assenze_qs = Assenza.objects.filter(
        dipendente_id__in=dipendenti_map.keys(),
        data_inizio__lte=max_date,
        data_fine__gte=min_date
    ).exclude(stato_approvazione='RIFIUTATA')

    assenze_list = list(assenze_qs)

    def _is_assente(dip_id, d):
        for ass in assenze_list:
            if ass.dipendente_id == dip_id and ass.data_inizio <= d <= ass.data_fine:
                return True
        return False

    to_create = []
    for assign in past_assigns:
        d_turno = assign.turno.data
        esclusi_ids = {d.pk for d in assign.dipendenti_esclusi.all()}
        for dip_id, dip in dipendenti_map.items():
            if (assign.pk, dip_id) in existing_tt_pairs:
                continue
            if dip_id in esclusi_ids:
                continue
            if dip.data_assunzione and d_turno < dip.data_assunzione:
                continue
            if dip.data_licenziamento and d_turno >= dip.data_licenziamento:
                continue
            if _is_assente(dip_id, d_turno):
                continue
            to_create.append(
                TimeTracking(
                    dipendente=dip,
                    assegnazione=assign,
                    ore_dichiarate=None,
                    is_validated=False,
                    source='MANUAL',
                    note=f"Storico turno ({squadra.nome})"
                )
            )
            existing_tt_pairs.add((assign.pk, dip_id))

    if to_create:
        TimeTracking.objects.bulk_create(to_create)

    return len(to_create)


def gestisci_eliminazione_squadra(squadra, cutoff_date=None):
    """
    Gestisce l'eliminazione di una Squadra:
    1. Consolida tutti i turni del passato (data < cutoff_date) salvando il nome squadra
       e preservando i componenti storici, scollegando il FK squadra=None per evitare cascade.
    2. Elimina SOLO i turni dalla data di eliminazione in poi (data >= cutoff_date).
    """
    from core.models import Turno, ProgrammazioneRicorrente

    if not squadra or not squadra.pk:
        return {'past_preserved': 0, 'future_deleted': 0}

    if cutoff_date is None:
        cutoff_date = timezone.now().date()

    member_ids = set(squadra.componenti.values_list('pk', flat=True))
    if squadra.caposquadra_id:
        member_ids.add(squadra.caposquadra_id)

    # 1. Consolida i turni passati (data < cutoff_date)
    _consolida_turni_passati_dipendenti(
        squadra,
        member_ids,
        cutoff_date=cutoff_date,
        save_squadra_tag=True
    )

    # Scollega i turni passati dalla squadra in modo che NON vengano eliminati
    past_turni_qs = Turno.objects.filter(squadra=squadra, data__lt=cutoff_date)
    past_preserved = past_turni_qs.count()
    past_turni_qs.update(squadra=None)

    # 2. Cancella SOLO i turni futuri/odierni (data >= cutoff_date)
    future_turni_qs = Turno.objects.filter(squadra=squadra, data__gte=cutoff_date)
    future_deleted = future_turni_qs.count()
    future_turni_qs.delete()

    # Scollega programmazioni ricorrenti
    ProgrammazioneRicorrente.objects.filter(squadra_abituale=squadra).update(squadra_abituale=None)

    return {'past_preserved': past_preserved, 'future_deleted': future_deleted}


def _gestisci_rimozione_membri_squadra(squadra, removed_ids, cutoff_date=None):
    """
    Quando uno o più dipendenti vengono rimossi da una Squadra:
    - Mantiene intatti tutti i turni e le ore del passato (data < cutoff_date).
    - Rimuove i dipendenti dai turni futuri (data >= cutoff_date) della squadra.
    """
    from core.models import TimeTracking, RichiestaSostituzione, AssegnazioneTurno

    if not squadra or not squadra.pk or not removed_ids:
        return

    if cutoff_date is None:
        cutoff_date = timezone.now().date()

    # Filtra chi è effettivamente uscito (non è più né caposquadra né componente)
    current_comp_ids = set(squadra.componenti.values_list('pk', flat=True))
    if squadra.caposquadra_id:
        current_comp_ids.add(squadra.caposquadra_id)

    effective_removed = [pk for pk in removed_ids if pk and pk not in current_comp_ids]
    if not effective_removed:
        return

    # 1. Preserva la presenza nei turni passati (data < cutoff_date)
    _consolida_turni_passati_dipendenti(squadra, effective_removed, cutoff_date=cutoff_date)

    # 2. Pulisci TimeTracking futuri (data >= cutoff_date) per questi dipendenti nella squadra
    TimeTracking.objects.filter(
        assegnazione__turno__squadra=squadra,
        assegnazione__turno__data__gte=cutoff_date,
        dipendente_id__in=effective_removed
    ).delete()

    # 3. Cancella richieste di sostituzione future aperte per questi dipendenti nella squadra
    RichiestaSostituzione.objects.filter(
        assegnazione_originale__turno__squadra=squadra,
        assegnazione_originale__turno__data__gte=cutoff_date,
        dipendente_assente_id__in=effective_removed
    ).delete()


def _gestisci_aggiunta_membri_squadra(squadra, added_ids, cutoff_date=None):
    """
    Quando uno o più dipendenti vengono aggiunti a una Squadra:
    - Esclude i nuovi membri dai turni passati (data < cutoff_date) in cui non avevano
      TimeTracking, così la modifica ha effetto SOLO da cutoff_date in avanti.
    - Riabilita i nuovi membri nei turni futuri (data >= cutoff_date) rimuovendoli da dipendenti_esclusi.
    """
    from core.models import AssegnazioneTurno, TimeTracking, Dipendente

    if not squadra or not squadra.pk or not added_ids:
        return

    if cutoff_date is None:
        cutoff_date = timezone.now().date()

    added_ids = [int(pk) for pk in added_ids if pk]
    if not added_ids:
        return

    past_assigns = list(
        AssegnazioneTurno.objects.filter(
            turno__squadra=squadra,
            turno__data__lt=cutoff_date
        )
    )
    if past_assigns:
        past_assign_ids = [a.pk for a in past_assigns]
        tt_pairs = set(
            TimeTracking.objects.filter(
                assegnazione_id__in=past_assign_ids,
                dipendente_id__in=added_ids
            ).values_list('assegnazione_id', 'dipendente_id')
        )
        for assign in past_assigns:
            to_exclude = [dip_id for dip_id in added_ids if (assign.pk, dip_id) not in tt_pairs]
            if to_exclude:
                assign.dipendenti_esclusi.add(*to_exclude)

    # Nei turni futuri (data >= cutoff_date), rimuovi da dipendenti_esclusi i nuovi membri attivi
    active_added_ids = list(
        Dipendente.objects.filter(pk__in=added_ids).exclude(stato='INATTIVO').values_list('pk', flat=True)
    )
    if active_added_ids:
        future_assigns = AssegnazioneTurno.objects.filter(
            turno__squadra=squadra,
            turno__data__gte=cutoff_date
        )
        for assign in future_assigns:
            assign.dipendenti_esclusi.remove(*active_added_ids)


def gestisci_licenziamento_dipendente(dipendente, cutoff_date=None):
    """
    Gestisce il licenziamento (stato='INATTIVO' o data_licenziamento) di un Dipendente:
    1. Mantiene TUTTI i turni, le assegnazioni, i TimeTracking, le Assenze e le ModificaCedolino
       del passato (data < cutoff_date).
    2. Cancella/esclude il dipendente SOLO dai turni a partire da cutoff_date (data >= cutoff_date).
    3. Se cutoff_date <= oggi, rimuove il dipendente dalle squadre attive per il futuro.
    """
    from core.models import (
        Squadra, Turno, AssegnazioneTurno, TimeTracking,
        Assenza, RichiestaSostituzione
    )

    if not dipendente or not dipendente.pk:
        return {'future_shifts_cleaned': 0, 'future_tt_deleted': 0}

    today = timezone.now().date()
    if cutoff_date is None:
        cutoff_date = dipendente.data_licenziamento or today

    # Trova tutte le squadre in cui il dipendente è caposquadra o componente
    squadre = list(
        Squadra.objects.filter(
            Q(caposquadra=dipendente) | Q(componenti=dipendente)
        ).distinct()
    )

    # 1. Preserva i turni passati (data < cutoff_date) prima di rimuoverlo dalle squadre
    for sq in squadre:
        _consolida_turni_passati_dipendenti(sq, [dipendente.pk], cutoff_date=cutoff_date)

    # 2. Elimina TimeTracking futuri (data >= cutoff_date)
    future_tt_qs = TimeTracking.objects.filter(
        dipendente=dipendente,
        assegnazione__turno__data__gte=cutoff_date
    )
    future_tt_deleted = future_tt_qs.count()
    future_tt_qs.delete()

    # 3. Gestisci Assenze future (data >= cutoff_date)
    Assenza.objects.filter(
        dipendente=dipendente,
        data_inizio__gte=cutoff_date
    ).delete()
    Assenza.objects.filter(
        dipendente=dipendente,
        data_inizio__lt=cutoff_date,
        data_fine__gte=cutoff_date
    ).update(data_fine=cutoff_date - timedelta(days=1))

    # 4. Gestisci Richieste di Sostituzione future (data >= cutoff_date)
    RichiestaSostituzione.objects.filter(
        dipendente_assente=dipendente,
        assegnazione_originale__turno__data__gte=cutoff_date
    ).delete()
    RichiestaSostituzione.objects.filter(
        sostituto=dipendente,
        assegnazione_originale__turno__data__gte=cutoff_date
    ).update(sostituto=None, stato='APERTA')

    # 5. Escludi il dipendente da tutte le assegnazioni turno da cutoff_date in poi
    future_assigns = list(
        AssegnazioneTurno.objects.filter(
            turno__squadra__in=squadre,
            turno__data__gte=cutoff_date
        )
    )
    for assign in future_assigns:
        assign.dipendenti_esclusi.add(dipendente)

    # 6. Se il licenziamento è già efficace (cutoff_date <= today), rimuovi dalle squadre attive
    if cutoff_date <= today:
        for sq in squadre:
            if sq.componenti.filter(pk=dipendente.pk).exists():
                sq.componenti.remove(dipendente)
            if sq.caposquadra_id == dipendente.pk:
                sq.caposquadra = None
                sq.save(update_fields=['caposquadra'])

            # Se la squadra è rimasta completamente priva di membri attivi,
            # elimina i turni futuri (data >= cutoff_date) di quella squadra vuota
            has_active_members = (
                (sq.caposquadra and sq.caposquadra.stato != 'INATTIVO') or
                sq.componenti.exclude(stato='INATTIVO').exists()
            )
            if not has_active_members:
                Turno.objects.filter(squadra=sq, data__gte=cutoff_date).delete()

    return {
        'future_shifts_cleaned': len(future_assigns),
        'future_tt_deleted': future_tt_deleted,
    }


def _cleanup_future_assignments(instance):
    """Rimuove SOLO le assegnazioni future (data >= oggi) collegate a una programmazione specifica."""
    from core.models import AssegnazioneTurno, Turno
    
    today = timezone.now().date()
    
    future_assignments = AssegnazioneTurno.objects.filter(
        programmazione_feriale=instance,
        turno__data__gte=today
    )
    
    turno_ids = list(future_assignments.values_list('turno_id', flat=True))
    deleted_count = future_assignments.count()
    future_assignments.delete()
    
    # Elimina turni futuri rimasti vuoti (MAI toccare turni del passato data < today)
    Turno.objects.filter(pk__in=turno_ids, data__gte=today).exclude(assegnazioni__isnull=False).delete()
    
    return deleted_count


def _genera_turni_singola_programmazione(prog, days=365, only_future=False):
    """
    Genera turni per UNA SOLA programmazione ricorrente.
    Se la programmazione esisteva già e ha già turni nel passato (o only_future=True),
    genera i turni SOLO da oggi in avanti, lasciando intatto lo storico passato.
    """
    from core.models import Turno, AssegnazioneTurno
    
    if not prog.squadra_abituale:
        return 0
    
    today = timezone.now().date()
    has_past_assignments = AssegnazioneTurno.objects.filter(
        programmazione_feriale=prog,
        turno__data__lt=today
    ).exists()

    if only_future or has_past_assignments:
        start_date = max(today, prog.data_inizio_contratto) if prog.data_inizio_contratto else today
    elif prog.data_inizio_contratto and prog.data_inizio_contratto < today:
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
        
        if prog.tipo_ripetizione == 'GIORNALIERO':
            match = True
        elif prog.tipo_ripetizione == 'SETTIMANALE' and prog.giorno_settimana == weekday:
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
            # Verifica se esiste già un'assegnazione per questa programmazione nella data corrente
            exists = AssegnazioneTurno.objects.filter(
                turno__data=current_date,
                programmazione_feriale=prog
            ).exists()
            
            if not exists:
                turno, _ = Turno.objects.get_or_create(
                    data=current_date,
                    squadra=prog.squadra_abituale,
                    defaults={'mezzo': prog.mezzo_abituale}
                )
                orario_inizio = prog.ora_inizio
                if prog.durata:
                    dt_start = datetime.combine(date.today(), orario_inizio)
                    hours = int(prog.durata)
                    minutes = int((prog.durata - hours) * 60)
                    dt_end = dt_start + timedelta(hours=hours, minutes=minutes)
                    orario_fine = dt_end.time()
                else:
                    orario_fine = orario_inizio
                
                assign = AssegnazioneTurno.objects.create(
                    turno=turno,
                    cliente=prog.cliente,
                    programmazione_feriale=prog,
                    orario_inizio_previsto=orario_inizio,
                    orario_fine_previsto=orario_fine,
                    mansione_svolta=f"Generato autom. (Qualifica: {prog.qualifica_richiesta})"
                )
                # Escludi eventuali componenti della squadra già licenziati a questa data
                squadra = prog.squadra_abituale
                esclusi_licenziati = []
                if squadra.caposquadra and (
                    squadra.caposquadra.stato == 'INATTIVO' or
                    (squadra.caposquadra.data_licenziamento and current_date >= squadra.caposquadra.data_licenziamento)
                ):
                    esclusi_licenziati.append(squadra.caposquadra.pk)
                for comp in squadra.componenti.all():
                    if comp.stato == 'INATTIVO' or (comp.data_licenziamento and current_date >= comp.data_licenziamento):
                        esclusi_licenziati.append(comp.pk)
                if esclusi_licenziati:
                    assign.dipendenti_esclusi.add(*esclusi_licenziati)
                count += 1
        
        current_date += timedelta(days=1)
    
    return count


@receiver(pre_delete, sender='core.ProgrammazioneRicorrente')
def on_programmazione_delete(sender, instance, **kwargs):
    """Quando eliminata: cancella solo le assegnazioni future di questa programmazione."""
    deleted = _cleanup_future_assignments(instance)
    print(f"[SYNC] Eliminata prog. '{instance.cliente}': {deleted} assegnazioni future rimosse.")


@receiver(post_save, sender='core.ProgrammazioneRicorrente')
def on_programmazione_save(sender, instance, created=False, raw=False, **kwargs):
    """Quando modificata: cancella e rigenera SOLO i turni futuri di questa programmazione."""
    if raw:
        return
    deleted = _cleanup_future_assignments(instance)
    created_count = _genera_turni_singola_programmazione(instance, only_future=(not created))
    print(f"[SYNC] Aggiornata prog. '{instance.cliente}': {deleted} rimossi, {created_count} creati.")


@receiver(pre_delete, sender='core.Squadra')
def on_squadra_pre_delete(sender, instance, **kwargs):
    """
    Quando una Squadra viene eliminata:
    elimina SOLO i turni dalla data odierna in avanti e preserva tutti i turni passati.
    """
    res = gestisci_eliminazione_squadra(instance)
    print(
        f"[SYNC] Eliminazione Squadra '{instance.nome}': "
        f"{res['future_deleted']} turni futuri rimossi, {res['past_preserved']} turni passati preservati."
    )


@receiver(pre_save, sender='core.Squadra')
def on_squadra_pre_save(sender, instance, raw=False, **kwargs):
    """Traccia il cambio di caposquadra per preservare i turni passati e aggiornare solo i futuri."""
    if raw or not instance.pk:
        instance._old_caposquadra_id = None
        return
    from core.models import Squadra
    try:
        old = Squadra.objects.get(pk=instance.pk)
        instance._old_caposquadra_id = old.caposquadra_id
    except Squadra.DoesNotExist:
        instance._old_caposquadra_id = None


@receiver(post_save, sender='core.Squadra')
def on_squadra_post_save(sender, instance, created=False, raw=False, **kwargs):
    """Gestisce il cambio di caposquadra mantenendo intatto lo storico dei turni passati."""
    if raw or created:
        return
    old_capo_id = getattr(instance, '_old_caposquadra_id', None)
    new_capo_id = instance.caposquadra_id
    if old_capo_id != new_capo_id:
        if old_capo_id:
            _gestisci_rimozione_membri_squadra(instance, [old_capo_id])
        if new_capo_id:
            _gestisci_aggiunta_membri_squadra(instance, [new_capo_id])


@receiver(m2m_changed, sender='core.Squadra_componenti')
def on_squadra_componenti_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    Quando i componenti di una Squadra vengono modificati:
    - I membri rimossi vengono consolidati nei turni passati e rimossi solo dai turni futuri.
    - I membri aggiunti vengono esclusi dai turni passati (in cui non avevano lavorato)
      e inclusi solo nei turni da oggi in avanti.
    """
    if reverse:
        return
    if action == 'pre_remove' and pk_set:
        # Salva i membri rimossi per consolidarli prima che la relazione venga rimossa
        _consolida_turni_passati_dipendenti(instance, pk_set)
    elif action == 'post_remove' and pk_set:
        _gestisci_rimozione_membri_squadra(instance, pk_set)
    elif action == 'pre_clear':
        instance._cleared_comp_ids = list(instance.componenti.values_list('pk', flat=True))
        if instance._cleared_comp_ids:
            _consolida_turni_passati_dipendenti(instance, instance._cleared_comp_ids)
    elif action == 'post_clear':
        cleared = getattr(instance, '_cleared_comp_ids', [])
        if cleared:
            _gestisci_rimozione_membri_squadra(instance, cleared)
    elif action == 'post_add' and pk_set:
        _gestisci_aggiunta_membri_squadra(instance, pk_set)


@receiver(post_save, sender='core.Dipendente')
def on_dipendente_post_save(sender, instance, created=False, raw=False, **kwargs):
    """
    Quando un Dipendente viene licenziato (stato='INATTIVO' o data_licenziamento impostata),
    rimuove/esclude il dipendente SOLO dai turni a partire dalla data di licenziamento (o oggi),
    mantenendo tutti i turni del passato per non perdere i dati dei cedolini e le ore.
    """
    if raw:
        return
    if getattr(instance, '_processing_licenziamento', False):
        return
    if instance.stato == 'INATTIVO' or instance.data_licenziamento:
        instance._processing_licenziamento = True
        try:
            cutoff = instance.data_licenziamento or timezone.now().date()
            res = gestisci_licenziamento_dipendente(instance, cutoff_date=cutoff)
            print(
                f"[SYNC] Licenziamento/Fine rapporto {instance} (dal {cutoff}): "
                f"{res['future_shifts_cleaned']} turni futuri aggiornati, storico passato preservato."
            )
        finally:
            instance._processing_licenziamento = False


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
