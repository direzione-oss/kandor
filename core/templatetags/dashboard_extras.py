from django import template
from django.utils import timezone
from datetime import timedelta
from core.models import Mezzo
from django.db.models import Q

register = template.Library()

@register.filter
def multiply_80(value):
    """Moltiplica il valore per 80 (pixel per ora nel calendario)."""
    try:
        return int(value) * 80
    except (TypeError, ValueError):
        return 0

@register.simple_tag
def unread_chat_count():
    from core.models import MessaggioChat
    return MessaggioChat.objects.filter(direzione='IN', letto=False).count()

@register.simple_tag
def unread_chat_badge():
    from core.models import MessaggioChat
    from django.utils.safestring import mark_safe
    count = MessaggioChat.objects.filter(direzione='IN', letto=False).count()
    if not count:
        return ''
    return mark_safe(
        f'<span style="position:absolute;top:8px;right:8px;background:#e74c3c;color:white;'
        f'border-radius:50%;min-width:20px;height:20px;font-size:12px;font-weight:bold;'
        f'display:inline-flex;align-items:center;justify-content:center;padding:0 5px">'
        f'{count}</span>'
    )

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
    # Ordina per scadenza più vicina
    processed_vehicles.sort(key=lambda v: min(a['date'] for a in v['alerts']))
    # Flag: ci sono scadenze nei prossimi 7 giorni o già scadute?
    threshold_7 = today + timedelta(days=7)
    has_urgent_7days = any(
        any(a['date'] <= threshold_7 for a in v['alerts'])
        for v in processed_vehicles
    )
    return {'vehicles': processed_vehicles, 'has_urgent_7days': has_urgent_7days}

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
            try:
                next_bday = bday.replace(year=today.year)
            except ValueError:
                next_bday = bday.replace(year=today.year, month=2, day=28)
            
            # If passed this year, check next year
            if next_bday < today:
                try:
                    next_bday = bday.replace(year=today.year + 1)
                except ValueError:
                    next_bday = bday.replace(year=today.year + 1, month=2, day=28)
                
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
    
    # Flag: ci sono compleanni nei prossimi 7 giorni?
    has_urgent_7days = any(
        b['days_until'] <= 7 for b in employees_birthdays + clients_birthdays
    )
    return {
        'employees_birthdays': employees_birthdays,
        'clients_birthdays': clients_birthdays,
        'has_birthdays': bool(employees_birthdays or clients_birthdays),
        'has_urgent_7days': has_urgent_7days,
    }



@register.inclusion_tag('admin/widgets/weekly_schedule_widget.html', takes_context=True)
def weekly_schedule_widget(context):
    request = context.get('request')
    try:
        week_offset = int(request.GET.get('week', 0)) if request else 0
    except (ValueError, TypeError, AttributeError):
        week_offset = 0
    
    # Filtro squadra
    squadra_filter = request.GET.get('squadra', '') if request else ''
        
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

    # GENERAZIONE AUTOMATICA: genera turni mancanti solo per i 7 giorni visibili
    end_of_week = dates[-1]
    if end_of_week >= today:
        try:
            from core.models import ProgrammazioneRicorrente
            from datetime import datetime as _dt
            progs = ProgrammazioneRicorrente.objects.filter(squadra_abituale__isnull=False).select_related('cliente', 'squadra_abituale', 'mezzo_abituale')
            for d in dates:
                if d < today:
                    continue
                wd = d.weekday()
                for p in progs:
                    if p.data_inizio_contratto and d < p.data_inizio_contratto:
                        continue
                    if p.data_fine_contratto and d > p.data_fine_contratto:
                        continue
                    match = False
                    if p.tipo_ripetizione == 'SETTIMANALE' and p.giorno_settimana == wd:
                        match = True
                    elif p.tipo_ripetizione == 'MENSILE' and p.giorno_mese == d.day:
                        match = True
                    elif p.tipo_ripetizione == 'BISETTIMANALE' and p.giorno_settimana == wd:
                        if p.data_inizio_contratto:
                            delta = (d - p.data_inizio_contratto).days
                            if delta >= 0 and (delta // 7) % 2 == 0:
                                match = True
                    if match:
                        try:
                            turno = Turno.objects.filter(data=d, squadra=p.squadra_abituale).first()
                            if not turno:
                                turno = Turno.objects.create(data=d, squadra=p.squadra_abituale, mezzo=p.mezzo_abituale)
                            
                            if not AssegnazioneTurno.objects.filter(turno=turno, programmazione_feriale=p).exists():
                                oi = p.ora_inizio
                                if p.durata:
                                    dt_s = _dt.combine(d, oi)
                                    h = int(p.durata); m = int((p.durata - h) * 60)
                                    of = (dt_s + timedelta(hours=h, minutes=m)).time()
                                else:
                                    of = oi
                                AssegnazioneTurno.objects.create(
                                    turno=turno, cliente=p.cliente, programmazione_feriale=p,
                                    orario_inizio_previsto=oi, orario_fine_previsto=of,
                                    mansione_svolta=f"Generato autom. ({p.qualifica_richiesta})"
                                )
                        except Exception as e:
                            print(f"[WeeklySchedule] Errore generazione turno automatico: {e}")
        except Exception as e:
            print(f"[WeeklySchedule] Errore generale in generazione turni: {e}")
    
    # RILEVAMENTO SOVRAPPOSIZIONI: stessa squadra, stesso giorno, orari sovrapposti
    overlaps = []
    # Carica TUTTE le assegnazioni della settimana in una sola query
    all_assigns = list(AssegnazioneTurno.objects.filter(
        turno__data__in=dates,
        orario_inizio_previsto__isnull=False,
        orario_fine_previsto__isnull=False
    ).select_related('turno__squadra', 'cliente'))
    
    # Raggruppa per (data, squadra)
    from collections import defaultdict
    per_day_squadra = defaultdict(list)
    for a in all_assigns:
        if a.turno and a.turno.squadra:
            per_day_squadra[(a.turno.data, a.turno.squadra.id)].append(a)
    
    for key, assigns in per_day_squadra.items():
        for i in range(len(assigns)):
            for j in range(i + 1, len(assigns)):
                a1, a2 = assigns[i], assigns[j]
                if a1.orario_inizio_previsto and a1.orario_fine_previsto and a2.orario_inizio_previsto and a2.orario_fine_previsto:
                    if a1.orario_inizio_previsto < a2.orario_fine_previsto and a2.orario_inizio_previsto < a1.orario_fine_previsto:
                        overlaps.append({
                            'data': key[0].strftime('%d/%m'),
                            'squadra': a1.turno.squadra.nome,
                            'c1': str(a1.cliente),
                            'c2': str(a2.cliente),
                            'orario': f"{a1.orario_inizio_previsto.strftime('%H:%M')}-{a1.orario_fine_previsto.strftime('%H:%M')} vs {a2.orario_inizio_previsto.strftime('%H:%M')}-{a2.orario_fine_previsto.strftime('%H:%M')}"
                        })

    # Pre-carica tutti i TimeTracking per la settimana per efficienza
    from core.models import TimeTracking
    all_tt = TimeTracking.objects.filter(
        assegnazione__turno__data__in=dates
    ).select_related('assegnazione')
    
    # Mappa assegnazione_id -> TimeTracking
    tt_map = {}
    for tt in all_tt:
        tt_map[tt.assegnazione_id] = tt

    # OTTIMIZZAZIONE: una query unica per tutti i turni della settimana
    # invece di 7 query separate (una per giorno)
    shifts_qs_all = Turno.objects.filter(
        data__in=dates
    ).select_related(
        'squadra', 'squadra__caposquadra', 'mezzo'
    ).prefetch_related(
        'assegnazioni__cliente',
        'assegnazioni__dipendenti_esclusi',
    ).order_by('data', 'squadra__nome')

    if squadra_filter:
        shifts_qs_all = shifts_qs_all.filter(squadra_id=squadra_filter)

    # Raggruppa turni per data
    turni_per_data = defaultdict(list)
    for shift in shifts_qs_all:
        turni_per_data[shift.data].append(shift)

    schedule = []
    for d in dates:
        day_data = {
            'date_obj': d,
            'day_name': DAYS_MAP[d.weekday()],
            'day_date': f"{d.day:02d} {MONTHS_MAP[d.month]}",
            'iso_date': d.isoformat(),
            'is_today': d == today,
            'shifts': [],
            'events': []
        }

        for shift in turni_per_data.get(d, []):
            sq_id = shift.squadra.id
            if sq_id not in squadra_colors:
                squadra_colors[sq_id] = COLORS[color_idx % len(COLORS)]
                color_idx += 1

            assignments_data = []
            STATO_COLORS = {
                'green': '#27ae60', 'yellow': '#f39c12',
                'red': '#e74c3c',   'white':  '#bdc3c7',
            }
            HOUR_PX = 80
            grid_start_min = 4 * 60

            # Filtra solo assegnazioni con orari previsti non nulli
            valid_assigns = [
                a for a in shift.assegnazioni.all()
                if a.orario_inizio_previsto is not None and a.orario_fine_previsto is not None
            ]
            for assign in sorted(valid_assigns, key=lambda a: a.orario_inizio_previsto):
                start = assign.orario_inizio_previsto.strftime('%H:%M')
                end   = assign.orario_fine_previsto.strftime('%H:%M')

                tt = tt_map.get(assign.id)
                def _fmt_ore(ore_float):
                    """Converte 7.5 → '7h30'' | 7.0 → '7h' | 0.5 → '30'"""
                    if ore_float is None:
                        return '—'
                    try:
                        h = int(ore_float)
                        m = int(round((ore_float - h) * 60))
                        if h and m:
                            return f"{h}h{m:02d}'"
                        elif h:
                            return f"{h}h"
                        else:
                            return f"{m}'"
                    except (TypeError, ValueError):
                        return '—'

                if tt and tt.is_validated:
                    ore_stato = 'green';  ore_label = _fmt_ore(tt.durata_ore) + ' ✓'
                elif tt and (tt.ore_dichiarate or tt.check_out):
                    ore_stato = 'yellow'; ore_label = _fmt_ore(tt.durata_ore)
                elif d < today:
                    ore_stato = 'red';    ore_label = "!"
                else:
                    ore_stato = 'white'
                    sh_m = assign.orario_inizio_previsto.hour * 60 + assign.orario_inizio_previsto.minute
                    eh_m = assign.orario_fine_previsto.hour * 60 + assign.orario_fine_previsto.minute
                    dur_min = max(eh_m - sh_m, 0)
                    ore_label = _fmt_ore(dur_min / 60) if dur_min else '—'

                badge_bg = STATO_COLORS.get(ore_stato, '#bdc3c7')
                badge_fg = '#fff' if ore_stato != 'white' else '#666'
                ore_badge_html = (
                    f'<span style="position:absolute;top:1px;right:1px;background:{badge_bg};color:{badge_fg};'
                    f'border-radius:8px;padding:0 4px;font-size:9px;font-weight:bold;line-height:16px;'
                    f'min-width:16px;text-align:center;z-index:3">{ore_label}</span>'
                )

                assignments_data.append({'cliente': assign.cliente, 'time_range': f"{start} - {end}"})

                sh = assign.orario_inizio_previsto.hour
                sm = assign.orario_inizio_previsto.minute
                eh = assign.orario_fine_previsto.hour
                em = assign.orario_fine_previsto.minute
                duration_min = max((eh * 60 + em) - (sh * 60 + sm), 1)

                start_total_min = sh * 60 + sm
                top_abs = int((start_total_min - grid_start_min) * HOUR_PX / 60)
                height  = max(int(duration_min * HOUR_PX / 60), 20)

                day_data['events'].append({
                    'assign_id':    assign.id,
                    'turno_id':     shift.id,
                    'cliente_nome': assign.cliente.ragione_sociale[:25],
                    'cliente_id':   assign.cliente.id,
                    'squadra_nome': shift.squadra.nome,
                    'squadra_id':   sq_id,
                    'start_hour':   sh,
                    'height':       height,
                    'top_abs':      top_abs,
                    'color':        squadra_colors[sq_id],
                    'time_range':   f"{start}-{end}",
                    'ora_inizio':   start,
                    'ora_fine':     end,
                    'ore_previste': assign.ore_previste_contratto or '',
                    'note':         assign.mansione_svolta or '',
                    'ore_stato':    ore_stato,
                    'ore_label':    ore_label,
                    'ore_badge_html': ore_badge_html,
                    'is_ricorrente': assign.programmazione_feriale_id is not None,
                })

            capo = shift.squadra.caposquadra
            day_data['shifts'].append({
                'squadra':     shift.squadra.nome,
                'squadra_id':  sq_id,
                'mezzo':       shift.mezzo.targa if shift.mezzo else 'N/D',
                'caposquadra': capo.cognome if capo else '?',
                'assignments': assignments_data,
            })

        schedule.append(day_data)
    
    # Range ore da visualizzare (04:00 - 23:00)
    grid_start = 4
    grid_end = 23
    hours_range = list(range(grid_start, grid_end))
    # Pre-calcola il top in pixel per ogni ora (evita filtri custom nel template)
    hours_with_top = [{'hour': h, 'top_px': (h - grid_start) * 80} for h in hours_range]
    total_height = (grid_end - grid_start) * 80
        
    return {
        'schedule': schedule,
        'hours_range': hours_range,
        'hours_with_top': hours_with_top,
        'grid_start': grid_start,
        'total_height': total_height,
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
    latest_hours = TimeTracking.objects.filter(
        source='TELEGRAM'
    ).select_related(
        'dipendente', 'assegnazione__cliente', 'assegnazione__turno__squadra'
    ).order_by('-check_out')[:10]

    # Ultime 10 Assenze da Telegram
    latest_absences = Assenza.objects.filter(
        source='TELEGRAM'
    ).select_related('dipendente').order_by('-created_at')[:10]

    # Ultime 10 Segnalazioni
    latest_reports = Segnalazione.objects.select_related(
        'dipendente'
    ).order_by('-data_inserimento')[:10]

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
