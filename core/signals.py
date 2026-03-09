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
    end_date = today + timedelta(days=days)
    count = 0
    
    current_date = today
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
def on_programmazione_save(sender, instance, **kwargs):
    """Quando modificata: cancella e rigenera SOLO i turni di questa programmazione."""
    deleted = _cleanup_future_assignments(instance)
    created = _genera_turni_singola_programmazione(instance)
    print(f"[SYNC] Aggiornata prog. '{instance.cliente}': {deleted} rimossi, {created} creati.")


@receiver(post_save, sender='core.Assenza')
def on_assenza_save(sender, instance, created, **kwargs):
    """
    Quando viene creata un'assenza (soprattutto programmata/futura):
    - Verifica tutti i turni nel range data_inizio → data_fine
    - Per ogni turno scoperto, avvia automaticamente la procedura di sostituzione
    - Skippa le assenze Telegram same-day (già gestite dall'handler Telegram)
    """
    if not created:
        return  # Solo nuove assenze, non aggiornamenti
    
    today = timezone.now().date()
    
    # Se l'assenza è Telegram e copre solo oggi, la sostituzione
    # è già stata gestita da _gestisci_assenza_con_sostituzione()
    if instance.source == 'TELEGRAM' and instance.data_inizio == today and instance.data_fine == today:
        return
    
    from core.models import AssegnazioneTurno, Squadra, RichiestaSostituzione
    from django.db.models import Q
    
    dipendente = instance.dipendente
    
    # Trova le squadre del dipendente
    squadre = Squadra.objects.filter(
        Q(componenti=dipendente) | Q(caposquadra=dipendente)
    ).distinct()
    
    if not squadre.exists():
        return
    
    # Trova tutti i turni nel range dell'assenza
    assegnazioni = AssegnazioneTurno.objects.filter(
        turno__data__gte=instance.data_inizio,
        turno__data__lte=instance.data_fine,
        turno__squadra__in=squadre
    ).select_related('turno', 'turno__squadra', 'cliente')
    
    turni_scoperti = list(assegnazioni)
    if not turni_scoperti:
        return
    
    # Mappa tipo assenza → motivo sostituzione
    motivo_map = {
        'MALATTIA': 'MALATTIA', 'FERIE': 'FERIE',
        'PERMESSO': 'PERMESSO', '104': '104', 'ALTRO': 'ALTRO',
    }
    motivo = motivo_map.get(instance.tipo, 'ALTRO')
    
    richieste_create = 0
    for assegnazione in turni_scoperti:
        # Verifica che non esista già una richiesta per questa assegnazione/dipendente
        gia_esistente = RichiestaSostituzione.objects.filter(
            assegnazione_originale=assegnazione,
            dipendente_assente=dipendente,
            stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA', 'ACCETTATA', 'COMPLETATA']
        ).exists()
        
        if gia_esistente:
            continue
        
        try:
            from core.services import crea_richiesta_sostituzione
            crea_richiesta_sostituzione(
                assegnazione, dipendente, motivo,
                f"Assenza programmata {instance.tipo}: {instance.data_inizio.strftime('%d/%m')}→{instance.data_fine.strftime('%d/%m')}"
            )
            richieste_create += 1
        except Exception as e:
            print(f"[Assenza Signal] Errore sostituzione assegnazione {assegnazione.pk}: {e}")
    
    if richieste_create > 0:
        print(f"[Assenza Signal] {dipendente}: {richieste_create} richieste sostituzione create ({instance.data_inizio}→{instance.data_fine})")
        
        # Notifica admin
        try:
            from django.conf import settings
            admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
            if admin_chat_id:
                token = settings.TELEGRAM_BOT_TOKEN
                alert_msg = (
                    f"📋 ASSENZA PROGRAMMATA\n\n"
                    f"👤 {dipendente.cognome} {dipendente.nome}\n"
                    f"📅 {instance.data_inizio.strftime('%d/%m/%Y')} → {instance.data_fine.strftime('%d/%m/%Y')}\n"
                    f"📝 Motivo: {instance.tipo}\n"
                    f"⚠️ Turni scoperti: {len(turni_scoperti)}\n"
                    f"🔄 Richieste sostituzione create: {richieste_create}\n"
                )
                for a in turni_scoperti:
                    alert_msg += f"  • {a.turno.data.strftime('%d/%m')} — {a.cliente.ragione_sociale} ({a.orario_inizio_previsto.strftime('%H:%M')}-{a.orario_fine_previsto.strftime('%H:%M')})\n"
                
                import requests as req
                req.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={'chat_id': admin_chat_id, 'text': alert_msg}
                )
        except Exception:
            pass


@receiver(post_save, sender='core.Dipendente')
def upload_foto_supabase(sender, instance, **kwargs):
    """
    Quando viene salvato un dipendente con una nuova foto,
    carica il file su Supabase Storage e salva l'URL pubblico in foto_url.
    """
    if not instance.foto:
        return
    # Salta se foto_url è già popolato per la stessa foto
    expected_filename = f"dipendenti/{instance.pk}_{instance.foto.name.split('/')[-1]}"
    if instance.foto_url and expected_filename.split('_', 1)[-1] in instance.foto_url:
        return
    try:
        from django.conf import settings
        import requests as req
        supabase_url = getattr(settings, 'SUPABASE_URL', '')
        service_key = getattr(settings, 'SUPABASE_SERVICE_KEY', '')
        bucket = getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'kandor-media')
        if not supabase_url or not service_key:
            return
        # Leggi il file
        instance.foto.open('rb')
        file_data = instance.foto.read()
        instance.foto.close()
        # Nome file univoco
        ext = instance.foto.name.split('.')[-1].lower()
        remote_path = f"dipendenti/{instance.pk}.{ext}"
        # Upload su Supabase Storage (upsert)
        upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{remote_path}"
        headers = {
            'Authorization': f'Bearer {service_key}',
            'Content-Type': f'image/{ext}',
            'x-upsert': 'true',
        }
        resp = req.put(upload_url, headers=headers, data=file_data, timeout=15)
        if resp.status_code in (200, 201):
            public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{remote_path}"
            # Salva foto_url senza ritriggerare questo signal
            sender.objects.filter(pk=instance.pk).update(foto_url=public_url)
    except Exception:
        pass
