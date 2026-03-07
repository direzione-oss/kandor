from django import template
from django.utils import timezone
from datetime import timedelta
from core.models import Mezzo
from django.db.models import Q

register = template.Library()

@register.inclusion_tag('admin/widgets/expiring_vehicles_widget.html')
def expiring_vehicles_widget():
    today = timezone.now().date()
    threshold = today + timedelta(days=45)
    
    # Filtriamo mezzi con scadenze nel range o già scadute (e non nulle)
    # Scadute: data < today
    # In scadenza: today <= data <= threshold
    
    # Polizza
    expiring_polizza = Q(scadenza_polizza__isnull=False) & Q(scadenza_polizza__lte=threshold)
    # Bollo
    expiring_bollo = Q(scadenza_bollo__isnull=False) & Q(scadenza_bollo__lte=threshold)
    
    veicoli = Mezzo.objects.filter(expiring_polizza | expiring_bollo).distinct()
    
    processed_vehicles = []
    for mezzo in veicoli:
        alerts = []
        # Check Polizza
        if mezzo.scadenza_polizza:
            if mezzo.scadenza_polizza < today:
                alerts.append({'type': 'Polizza', 'date': mezzo.scadenza_polizza, 'status': 'SCADUTA', 'color': 'red'})
            elif mezzo.scadenza_polizza <= threshold:
                days = (mezzo.scadenza_polizza - today).days
                alerts.append({'type': 'Polizza', 'date': mezzo.scadenza_polizza, 'status': f'Scade tra {days} gg', 'color': 'orange'})
                
        # Check Bollo
        if mezzo.scadenza_bollo:
            if mezzo.scadenza_bollo < today:
                alerts.append({'type': 'Bollo', 'date': mezzo.scadenza_bollo, 'status': 'SCADUTO', 'color': 'red'})
            elif mezzo.scadenza_bollo <= threshold:
                days = (mezzo.scadenza_bollo - today).days
                alerts.append({'type': 'Bollo', 'date': mezzo.scadenza_bollo, 'status': f'Scade tra {days} gg', 'color': 'orange'})
        
        # Filtra solo quelli rilevanti (potrebbe averne una ok e una scaduta, mostriamo solo alerts)
        relevant_alerts = [a for a in alerts if a['date'] <= threshold]
        
        if relevant_alerts:
            processed_vehicles.append({
                'obj': mezzo,
                'alerts': relevant_alerts
            })
    return {'vehicles': processed_vehicles}

@register.inclusion_tag('admin/widgets/upcoming_birthdays_widget.html')
def upcoming_birthdays_widget():
    from core.models import Dipendente, Cliente
    today = timezone.now().date()
    threshold = today + timedelta(days=20)
    
    def get_upcoming(objects, date_field):
        upcoming_list = []
        for obj in objects:
            bday = getattr(obj, date_field)
            if not bday: continue
            
            # Next birthday for this year
            next_bday = bday.replace(year=today.year)
            
            # If passed this year, check next year
            if next_bday < today:
                next_bday = bday.replace(year=today.year + 1)
                
            if today <= next_bday <= threshold:
                days_until = (next_bday - today).days
                upcoming_list.append({
                    'obj': obj,
                    'date': next_bday,
                    'days_until': days_until,
                    'is_today': days_until == 0
                })
        return upcoming_list

    # Employees
    dipendenti = Dipendente.objects.filter(stato='ATTIVO', data_nascita__isnull=False)
    employees_birthdays = get_upcoming(dipendenti, 'data_nascita')
    employees_birthdays.sort(key=lambda x: x['days_until'])
    
    # Clients
    clienti = Cliente.objects.filter(referente_data_nascita__isnull=False)
    clients_birthdays = get_upcoming(clienti, 'referente_data_nascita')
    clients_birthdays.sort(key=lambda x: x['days_until'])
    
    return {
        'employees_birthdays': employees_birthdays,
        'clients_birthdays': clients_birthdays,
        'has_birthdays': bool(employees_birthdays or clients_birthdays)
    }



@register.inclusion_tag('admin/widgets/weekly_schedule_widget.html', takes_context=True)
def weekly_schedule_widget(context):
    request = context.get('request')
    try:
        week_offset = int(request.GET.get('week', 0))
    except (ValueError, TypeError):
        week_offset = 0
    
    # Filtro squadra
    squadra_filter = request.GET.get('squadra', '')
        
    from core.models import Turno, Squadra, AssegnazioneTurno
    today = timezone.now().date()
    
    # Lista squadre per il dropdown (con attributo selected pre-calcolato)
    squadre_raw = Squadra.objects.all().order_by('nome')
    squadre = []
    for sq in squadre_raw:
        squadre.append({
            'id': sq.id,
            'nome': sq.nome,
            'selected': 'selected' if str(sq.id) == squadra_filter else '',
        })
    
    # Calculate start of the week (Monday)
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    
    # Generate 7 days from Monday
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    DAYS_MAP = {
        0: 'LUNEDÌ', 1: 'MARTEDÌ', 2: 'MERCOLEDÌ', 3: 'GIOVEDÌ', 4: 'VENERDÌ', 5: 'SABATO', 6: 'DOMENICA'
    }
    MONTHS_MAP = {
        1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu', 7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'
    }

    # Colori per squadre
    COLORS = ['#0277bd', '#2e7d32', '#c62828', '#f57c00', '#6a1b9a', '#00838f', '#ad1457', '#4e342e']
    squadra_colors = {}
    color_idx = 0

    # GENERAZIONE AUTOMATICA: genera sempre i turni mancanti per la settimana
    end_of_week = dates[-1]
    if end_of_week >= today:  # Solo settimane presenti/future
        try:
            from core.services import genera_turni_automatici
            genera_turni_automatici(days=(end_of_week - today).days + 1)
        except Exception:
            pass  # Non bloccare la visualizzazione se la generazione fallisce
    
    # RILEVAMENTO SOVRAPPOSIZIONI: stessa squadra, stesso giorno, orari sovrapposti
    overlaps = []
    for d in dates:
        assegnazioni_giorno = AssegnazioneTurno.objects.filter(
            turno__data=d
        ).select_related('turno__squadra', 'cliente')
        
        # Raggruppa per squadra
        from collections import defaultdict
        per_squadra = defaultdict(list)
        for a in assegnazioni_giorno:
            per_squadra[a.turno.squadra.id].append(a)
        
        for sq_id, assigns in per_squadra.items():
            for i in range(len(assigns)):
                for j in range(i + 1, len(assigns)):
                    a1, a2 = assigns[i], assigns[j]
                    # Sovrapposizione: stessa squadra, orari sovrapposti
                    if a1.orario_inizio_previsto < a2.orario_fine_previsto and a2.orario_inizio_previsto < a1.orario_fine_previsto:
                        overlaps.append({
                            'data': d.strftime('%d/%m'),
                            'squadra': a1.turno.squadra.nome,
                            'c1': str(a1.cliente),
                            'c2': str(a2.cliente),
                            'orario': f"{a1.orario_inizio_previsto.strftime('%H:%M')}-{a1.orario_fine_previsto.strftime('%H:%M')} vs {a2.orario_inizio_previsto.strftime('%H:%M')}-{a2.orario_fine_previsto.strftime('%H:%M')}"
                        })

    schedule = []
    for d in dates:
        shifts_qs = Turno.objects.filter(data=d).select_related('squadra', 'mezzo').prefetch_related('assegnazioni__cliente')
        
        # Filtra per squadra se selezionata
        if squadra_filter:
            shifts_qs = shifts_qs.filter(squadra_id=squadra_filter)
        
        day_data = {
            'date_obj': d,
            'day_name': DAYS_MAP[d.weekday()], 
            'day_date': f"{d.day:02d} {MONTHS_MAP[d.month]}", 
            'iso_date': d.isoformat(),
            'is_today': d == today,
            'shifts': [],
            'events': []
        }
        
        for shift in shifts_qs:
            # Assegna colore alla squadra
            sq_id = shift.squadra.id
            if sq_id not in squadra_colors:
                squadra_colors[sq_id] = COLORS[color_idx % len(COLORS)]
                color_idx += 1

            assignments_data = []
            for assign in shift.assegnazioni.all().order_by('orario_inizio_previsto'):
                start = assign.orario_inizio_previsto.strftime('%H:%M')
                end = assign.orario_fine_previsto.strftime('%H:%M')
                assignments_data.append({
                    'cliente': assign.cliente,
                    'time_range': f"{start} - {end}"
                })
                
                # Calcola posizione evento nella griglia
                sh = assign.orario_inizio_previsto.hour
                sm = assign.orario_inizio_previsto.minute
                eh = assign.orario_fine_previsto.hour
                em = assign.orario_fine_previsto.minute
                
                duration_min = (eh * 60 + em) - (sh * 60 + sm)
                if duration_min <= 0:
                    duration_min = 60
                
                height = max(int(duration_min * 40 / 60), 18)
                top_offset = int(sm * 40 / 60)
                
                day_data['events'].append({
                    'assign_id': assign.id,
                    'turno_id': shift.id,
                    'cliente_nome': assign.cliente.ragione_sociale[:25],
                    'cliente_id': assign.cliente.id,
                    'squadra_nome': shift.squadra.nome,
                    'squadra_id': shift.squadra.id,
                    'start_hour': sh,
                    'height': height,
                    'top_offset': top_offset,
                    'color': squadra_colors[sq_id],
                    'time_range': f"{start}-{end}",
                    'ora_inizio': start,
                    'ora_fine': end,
                    'note': assign.mansione_svolta or ''
                })

            day_data['shifts'].append({
                'squadra': shift.squadra.nome,
                'squadra_id': shift.squadra.id,
                'mezzo': shift.mezzo.targa if shift.mezzo else 'N/D',
                'caposquadra': shift.squadra.caposquadra.cognome if shift.squadra.caposquadra else '?',
                'assignments': assignments_data
            })
            
        schedule.append(day_data)
    
    # Range ore da visualizzare (05:00 - 22:00)
    hours_range = list(range(5, 23))
        
    return {
        'schedule': schedule,
        'hours_range': hours_range,
        'overlaps': overlaps,
        'squadre': squadre,
        'squadra_filter': squadra_filter,
        'current_week_offset': week_offset,
        'prev_week_offset': week_offset - 1,
        'next_week_offset': week_offset + 1,
        'week_start': start_of_week,
        'week_end': dates[-1],
        'week_range': f"{start_of_week.day:02d} {MONTHS_MAP[start_of_week.month]} - {dates[-1].day:02d} {MONTHS_MAP[dates[-1].month]}"
    }

@register.filter
def is_operational_model(model_name):
    return model_name in ['AssegnazioneTurno', 'Assenza', 'TimeTracking', 'Turno']

@register.filter
def is_resource_model(model_name):
    return model_name in ['Cliente', 'Dipendente', 'Mezzo', 'Qualifica', 'Squadra', 'MessaggioProgrammato']

@register.inclusion_tag('admin/widgets/telegram_feed_widget.html')
def telegram_feed_widget():
    from core.models import TimeTracking, Assenza, Segnalazione
    
    # Ultime 10 Ore Lavorate da Telegram
    latest_hours = TimeTracking.objects.filter(source='TELEGRAM').order_by('-check_out')[:10]
    
    # Ultime 10 Assenze da Telegram
    latest_absences = Assenza.objects.filter(source='TELEGRAM').order_by('-created_at')[:10]
    
    # Ultime 10 Segnalazioni
    latest_reports = Segnalazione.objects.all().order_by('-data_inserimento')[:10]
    
    return {
        'latest_hours': latest_hours,
        'latest_absences': latest_absences,
        'latest_reports': latest_reports
    }

@register.inclusion_tag('admin/widgets/expiring_contracts_widget.html')
def expiring_contracts_widget():
    from core.models import ProgrammazioneRicorrente
    today = timezone.now().date()
    threshold = today + timedelta(days=30)
    
    # Programmazioni con data_fine_contratto entro 30 giorni o già scadute (ma non troppo vecchie)
    past_limit = today - timedelta(days=7)  # Mostra scadute fino a 7 giorni fa
    expiring = ProgrammazioneRicorrente.objects.filter(
        data_fine_contratto__isnull=False,
        data_fine_contratto__gte=past_limit,
        data_fine_contratto__lte=threshold
    ).select_related('cliente', 'squadra_abituale').order_by('data_fine_contratto')
    
    contracts = []
    for prog in expiring:
        days_left = (prog.data_fine_contratto - today).days
        contracts.append({
            'prog': prog,
            'cliente': prog.cliente.ragione_sociale,
            'tipo': prog.get_tipo_ripetizione_display(),
            'giorno': prog.get_giorno_settimana_display() if prog.giorno_settimana is not None else f"Giorno {prog.giorno_mese}",
            'data_fine': prog.data_fine_contratto,
            'days_left': days_left,
            'is_expired': days_left < 0,
            'is_urgent': 0 <= days_left <= 7,
            'prog_id': prog.pk,
        })
    
    return {
        'contracts': contracts,
        'has_expiring': bool(contracts),
    }
