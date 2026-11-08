from collections import defaultdict
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
    # Revisione
    expiring_revisione = Q(scadenza_revisione__isnull=False) & Q(scadenza_revisione__lte=threshold)
    # Permesso Città Alta (Bergamo)
    expiring_permesso_ca = Q(scadenza_permesso_citta_alta__isnull=False) & Q(scadenza_permesso_citta_alta__lte=threshold)
    
    veicoli = Mezzo.objects.filter(expiring_polizza | expiring_revisione | expiring_permesso_ca).distinct()
    
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
                
        # Check Revisione
        if mezzo.scadenza_revisione:
            if mezzo.scadenza_revisione < today:
                alerts.append({'type': 'Revisione', 'date': mezzo.scadenza_revisione, 'status': 'SCADUTO', 'color': 'red'})
            elif mezzo.scadenza_revisione <= threshold:
                days = (mezzo.scadenza_revisione - today).days
                alerts.append({'type': 'Revisione', 'date': mezzo.scadenza_revisione, 'status': f'Scade tra {days} gg', 'color': 'orange'})

        # Check Permesso Città Alta (Bergamo)
        if mezzo.scadenza_permesso_citta_alta:
            if mezzo.scadenza_permesso_citta_alta < today:
                alerts.append({'type': 'Permesso Città Alta (BG)', 'date': mezzo.scadenza_permesso_citta_alta, 'status': 'SCADUTO', 'color': 'red'})
            elif mezzo.scadenza_permesso_citta_alta <= threshold:
                days = (mezzo.scadenza_permesso_citta_alta - today).days
                alerts.append({'type': 'Permesso Città Alta (BG)', 'date': mezzo.scadenza_permesso_citta_alta, 'status': f'Scade tra {days} gg', 'color': 'orange'})
        
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

@register.inclusion_tag('admin/widgets/expiring_medical_visits_widget.html')
def expiring_medical_visits_widget():
    from core.models import Dipendente
    today = timezone.now().date()
    threshold = today + timedelta(days=20)

    dipendenti = Dipendente.objects.exclude(stato='INATTIVO').filter(
        data_ultima_visita_medica__isnull=False,
        data_ultima_visita_medica__lte=threshold
    ).order_by('data_ultima_visita_medica', 'cognome', 'nome')

    medical_visits = []
    for dip in dipendenti:
        scadenza = dip.data_ultima_visita_medica
        if scadenza < today:
            status = 'SCADUTA'
            is_expired = True
        else:
            days = (scadenza - today).days
            status = 'Scade OGGI' if days == 0 else f'Scade tra {days} gg'
            is_expired = False

        medical_visits.append({
            'obj': dip,
            'date': scadenza,
            'status': status,
            'is_expired': is_expired,
        })

    return {
        'medical_visits': medical_visits,
        'has_urgent': bool(medical_visits),
    }

@register.inclusion_tag('admin/widgets/expiring_training_courses_widget.html')
def expiring_training_courses_widget():
    from core.models import CorsoDipendente
    today = timezone.now().date()
    threshold = today + timedelta(days=20)

    training_courses = []
    try:
        corsi_qs = CorsoDipendente.objects.exclude(
            dipendente__stato='INATTIVO'
        ).filter(
            data_scadenza__isnull=False,
            data_scadenza__lte=threshold
        ).select_related('dipendente', 'corso').order_by(
            'data_scadenza', 'dipendente__cognome', 'dipendente__nome', 'corso__ordine'
        )

        for item in corsi_qs:
            scadenza = item.data_scadenza
            if scadenza < today:
                status = 'SCADUTO'
                is_expired = True
            else:
                days = (scadenza - today).days
                status = 'Scade OGGI' if days == 0 else f'Scade tra {days} gg'
                is_expired = False

            training_courses.append({
                'obj': item,
                'dipendente': item.dipendente,
                'corso': item.corso,
                'stato': item.stato,
                'date': scadenza,
                'status': status,
                'is_expired': is_expired,
            })
    except Exception:
        training_courses = []

    return {
        'training_courses': training_courses,
        'has_urgent': bool(training_courses),
    }

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
    import calendar
    import json
    from datetime import date as _date, datetime as _dt
    from core.models import Turno, Squadra, AssegnazioneTurno

    request = context.get('request')
    today = timezone.now().date()
    current_monday = today - timedelta(days=today.weekday())

    week_offset = 0
    if request:
        week_date_str = (request.GET.get('week_date') or '').strip()
        if week_date_str:
            try:
                target_d = _dt.strptime(week_date_str, '%Y-%m-%d').date()
                target_monday = target_d - timedelta(days=target_d.weekday())
                week_offset = (target_monday - current_monday).days // 7
            except (ValueError, TypeError):
                week_offset = 0
        else:
            try:
                week_offset = int(request.GET.get('week', 0))
            except (ValueError, TypeError, AttributeError):
                week_offset = 0

    # Filtro squadra
    squadra_filter = request.GET.get('squadra', '') if request else ''

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
    start_of_week = current_monday + timedelta(weeks=week_offset)

    # Generate 7 days from Monday
    dates = [start_of_week + timedelta(days=i) for i in range(7)]

    DAYS_MAP = {
        0: 'LUNEDÌ', 1: 'MARTEDÌ', 2: 'MERCOLEDÌ', 3: 'GIOVEDÌ', 4: 'VENERDÌ', 5: 'SABATO', 6: 'DOMENICA'
    }
    MONTHS_MAP = {
        1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu', 7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'
    }
    MONTHS_FULL_MAP = {
        1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile', 5: 'Maggio', 6: 'Giugno',
        7: 'Luglio', 8: 'Agosto', 9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
    }

    # Determina il mese di riferimento attivo (da parametro ?cal_month=YYYY-MM oppure giovedì della settimana visualizzata)
    ref_thursday = start_of_week + timedelta(days=3)
    active_month_key = f"{ref_thursday.year:04d}-{ref_thursday.month:02d}"
    req_cal_month = (request.GET.get('cal_month') or '').strip() if request else ''
    if req_cal_month and len(req_cal_month) == 7 and req_cal_month[4] == '-':
        try:
            _y, _m = int(req_cal_month[:4]), int(req_cal_month[5:7])
            if 1 <= _m <= 12:
                # Verifica che la settimana corrente tocchi effettivamente questo mese, altrimenti usa ref_thursday
                _m_first = _date(_y, _m, 1)
                _m_last = _date(_y, _m, calendar.monthrange(_y, _m)[1])
                if start_of_week <= _m_last and dates[-1] >= _m_first:
                    active_month_key = f"{_y:04d}-{_m:02d}"
        except (ValueError, TypeError):
            pass

    min_year = min(today.year - 1, start_of_week.year)
    max_year = max(today.year + 1, start_of_week.year + 1)

    calendar_months = []
    active_month_weeks = []
    active_month_label = f"{MONTHS_FULL_MAP[ref_thursday.month]} {ref_thursday.year}"

    for y in range(min_year, max_year + 1):
        for m in range(1, 13):
            m_key = f"{y:04d}-{m:02d}"
            m_label = f"{MONTHS_FULL_MAP[m]} {y}"
            m_first = _date(y, m, 1)
            m_last = _date(y, m, calendar.monthrange(y, m)[1])

            w_mon = m_first - timedelta(days=m_first.weekday())
            m_weeks = []
            while w_mon <= m_last:
                w_sun = w_mon + timedelta(days=6)
                w_off = (w_mon - current_monday).days // 7
                w_lbl = f"{w_mon.day:02d} {MONTHS_MAP[w_mon.month]} - {w_sun.day:02d} {MONTHS_MAP[w_sun.month]}"
                if w_off == 0:
                    w_lbl += " (Oggi)"
                w_item = {
                    'week_offset': w_off,
                    'label': w_lbl,
                    'short_label': f"{w_mon.day:02d} {MONTHS_MAP[w_mon.month]} – {w_sun.day:02d} {MONTHS_MAP[w_sun.month]}",
                    'is_selected': w_off == week_offset,
                    'selected': 'selected' if w_off == week_offset else '',
                    'is_current': w_off == 0,
                    'days': [
                        {
                            'num': (w_mon + timedelta(days=di)).day,
                            'in_month': (w_mon + timedelta(days=di)).month == m,
                            'is_today': (w_mon + timedelta(days=di)) == today,
                        }
                        for di in range(7)
                    ],
                }
                m_weeks.append(w_item)
                w_mon += timedelta(days=7)

            is_sel_month = (m_key == active_month_key)
            if is_sel_month:
                active_month_weeks = m_weeks
                active_month_label = m_label

            calendar_months.append({
                'key': m_key,
                'year': y,
                'month': m,
                'label': m_label,
                'selected': 'selected' if is_sel_month else '',
                'is_selected': is_sel_month,
                'weeks': m_weeks,
            })

    calendar_months_json = json.dumps(calendar_months)

    # Colori per squadre
    COLORS = ['#0277bd', '#2e7d32', '#c62828', '#f57c00', '#6a1b9a', '#00838f', '#ad1457', '#4e342e']
    squadra_colors = {}
    color_idx = 0

    # OTTIMIZZAZIONE: Caricamento in 3 passaggi con prefetch per azzerare le N+1 query
    from core.models import Turno, AssegnazioneTurno, TimeTracking
    shifts_qs_all = list(Turno.objects.filter(
        data__in=dates
    ).select_related(
        'squadra', 'squadra__caposquadra', 'mezzo'
    ).prefetch_related(
        'squadra__componenti'
    ).order_by('data', 'squadra__nome'))

    if squadra_filter:
        shifts_qs_all = [s for s in shifts_qs_all if str(s.squadra_id) == squadra_filter]

    shift_ids = [s.id for s in shifts_qs_all]

    # Carica assegnazioni con query diretta per ID turno e prefetch di dipendenti_esclusi
    all_assigns = list(AssegnazioneTurno.objects.filter(
        turno_id__in=shift_ids
    ).select_related('cliente', 'turno__squadra').prefetch_related('dipendenti_esclusi'))

    # Mappa assegnazioni per turno
    assigns_per_shift = defaultdict(list)
    for a in all_assigns:
        assigns_per_shift[a.turno_id].append(a)

    # Cache membri squadra in memoria per evitare query N+1
    squadra_members_cache = {}
    for shift in shifts_qs_all:
        sq_id = shift.squadra_id
        if sq_id and sq_id not in squadra_members_cache and shift.squadra:
            members = []
            if shift.squadra.caposquadra:
                members.append(shift.squadra.caposquadra)
            capo_pk = shift.squadra.caposquadra.pk if shift.squadra.caposquadra else None
            for c in shift.squadra.componenti.all():
                if c.pk != capo_pk and c not in members:
                    members.append(c)
            squadra_members_cache[sq_id] = members

    # RILEVAMENTO SOVRAPPOSIZIONI
    overlaps = []
    per_day_squadra = defaultdict(list)
    for a in all_assigns:
        if a.turno and a.turno.squadra and a.orario_inizio_previsto and a.orario_fine_previsto:
            per_day_squadra[(a.turno.data, a.turno.squadra.id)].append(a)

    for key, assigns in per_day_squadra.items():
        for i in range(len(assigns)):
            for j in range(i + 1, len(assigns)):
                a1, a2 = assigns[i], assigns[j]
                if a1.orario_inizio_previsto < a2.orario_fine_previsto and a2.orario_inizio_previsto < a1.orario_fine_previsto:
                    overlaps.append({
                        'data': key[0].strftime('%d/%m'),
                        'squadra': a1.turno.squadra.nome,
                        'c1': str(a1.cliente),
                        'c2': str(a2.cliente),
                        'orario': f"{a1.orario_inizio_previsto.strftime('%H:%M')}-{a1.orario_fine_previsto.strftime('%H:%M')} vs {a2.orario_inizio_previsto.strftime('%H:%M')}-{a2.orario_fine_previsto.strftime('%H:%M')}"
                    })

    # Pre-carica TimeTracking via ID assegnazione
    assign_ids = [a.id for a in all_assigns]
    all_tt = TimeTracking.objects.filter(assegnazione_id__in=assign_ids).select_related('dipendente')
    tt_map = defaultdict(list)
    for tt_obj in all_tt:
        tt_map[tt_obj.assegnazione_id].append(tt_obj)

    # Pre-carica ASSENZE per la settimana
    from core.models import Assenza, RichiestaSostituzione
    assenze_qs = Assenza.objects.filter(
        data_inizio__lte=dates[-1],
        data_fine__gte=dates[0]
    ).exclude(stato_approvazione='RIFIUTATA').select_related('dipendente')

    assenze_by_dip_date = defaultdict(list)
    for ass in assenze_qs:
        if not ass.data_inizio or not ass.data_fine:
            continue
        start_d = max(ass.data_inizio, dates[0])
        end_d = min(ass.data_fine, dates[-1])
        curr_d = start_d
        while curr_d <= end_d:
            assenze_by_dip_date[(ass.dipendente_id, curr_d)].append(ass)
            curr_d += timedelta(days=1)

    sostituzioni_qs = RichiestaSostituzione.objects.filter(
        assegnazione_originale__turno_id__in=shift_ids,
        stato__in=['ACCETTATA', 'COMPLETATA', 'APPROVATA_RA']
    ).select_related('sostituto', 'assegnazione_originale')
    sostituzioni_by_turno = defaultdict(list)
    for sost in sostituzioni_qs:
        if sost.assegnazione_originale and sost.assegnazione_originale.turno_id:
            sostituzioni_by_turno[sost.assegnazione_originale.turno_id].append(sost)

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
            sq_id = shift.squadra.id if shift.squadra else f"hist_{shift.nome_squadra}"
            sq_nome = shift.squadra.nome if shift.squadra else shift.nome_squadra
            if sq_id not in squadra_colors:
                squadra_colors[sq_id] = COLORS[color_idx % len(COLORS)]
                color_idx += 1

            assignments_data = []
            STATO_COLORS = {
                'green': '#27ae60', 'yellow': '#f39c12',
                'red': '#e74c3c',   'white':  '#bdc3c7',
                'purple': '#8e44ad',
            }
            HOUR_PX = 80
            grid_start_min = 4 * 60

            # Componenti squadra (da cache in memoria)
            squadra_members = list(squadra_members_cache.get(shift.squadra_id, [])) if shift.squadra_id else []

            # Filtra solo assegnazioni con orari previsti non nulli
            valid_assigns = [
                a for a in assigns_per_shift.get(shift.id, [])
                if a.orario_inizio_previsto is not None and a.orario_fine_previsto is not None
            ]
            for assign in sorted(valid_assigns, key=lambda a: a.orario_inizio_previsto):
                start = assign.orario_inizio_previsto.strftime('%H:%M')
                end   = assign.orario_fine_previsto.strftime('%H:%M')

                tt_list = tt_map.get(assign.id, [])
                tt = tt_list[0] if tt_list else None

                esclusi_pks = {m.pk for m in assign.dipendenti_esclusi.all()}
                active_squadra = [m for m in squadra_members if m.pk not in esclusi_pks]
                active_pks = {m.pk for m in active_squadra}
                for tt_item in tt_list:
                    if tt_item.dipendente and tt_item.dipendente.pk not in esclusi_pks and tt_item.dipendente.pk not in active_pks:
                        active_squadra.append(tt_item.dipendente)
                        active_pks.add(tt_item.dipendente.pk)

                # Rileva assenze per i componenti di questo turno in data d
                comp_assenti = []
                for m in active_squadra:
                    ass_list = assenze_by_dip_date.get((m.pk, d), [])
                    if ass_list:
                        a_obj = ass_list[0]
                        comp_assenti.append({
                            'dipendente_id': m.pk,
                            'nome': f"{m.cognome} {m.nome}",
                            'tipo': a_obj.tipo,
                            'tipo_display': a_obj.get_tipo_display()
                        })

                has_sostituti = bool(sostituzioni_by_turno.get(shift.id))

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

                durata_tot = sum(float(t.durata_ore) for t in tt_list if t.durata_ore) if tt_list else (float(tt.durata_ore) if tt and tt.durata_ore else 0)
                is_all_val = all(t.is_validated for t in tt_list) if tt_list else (tt.is_validated if tt else False)
                has_hours = bool(tt_list and any(t.ore_dichiarate or t.check_out for t in tt_list)) or bool(durata_tot > 0)

                # Se TUTTI i componenti attivi sono in assenza e non c'è sostituto con ore lavorate
                if comp_assenti and len(comp_assenti) >= len(active_squadra) and not (has_hours or has_sostituti):
                    ore_stato = 'purple'
                    t_ass = comp_assenti[0]['tipo']
                    if t_ass == 'MALATTIA':
                        ore_label = '🏥 Malattia'
                    elif t_ass == 'FERIE':
                        ore_label = '🏖️ Ferie'
                    else:
                        ore_label = f"📝 {comp_assenti[0]['tipo_display']}"
                elif tt_list and is_all_val and durata_tot > 0:
                    ore_stato = 'green'
                    ore_label = _fmt_ore(durata_tot) + ' ✓'
                elif tt_list and has_hours:
                    ore_stato = 'yellow'
                    ore_label = _fmt_ore(durata_tot)
                elif d < today:
                    ore_stato = 'red'
                    ore_label = "!"
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
                    'squadra_nome': sq_nome,
                    'squadra_id':   shift.squadra_id or '',
                    'start_hour':   sh,
                    'height':       height,
                    'top_abs':      top_abs,
                    'color':        squadra_colors[sq_id],
                    'time_range':   f"{start}-{end}",
                    'ora_inizio':   start,
                    'ora_fine':     end,
                    'ore_previste': assign.ore_previste_contratto or '',
                    'ore_dichiarate': float(durata_tot) if durata_tot else '',
                    'ore_dichiarate_fmt': _fmt_ore(durata_tot) if durata_tot else '',
                    'note':         assign.mansione_svolta or '',
                    'ore_stato':    ore_stato,
                    'ore_label':    ore_label,
                    'ore_badge_html': ore_badge_html,
                    'is_ricorrente': assign.programmazione_feriale_id is not None,
                    'has_assenza':  bool(comp_assenti),
                    'assenti_names': ", ".join([a['nome'] for a in comp_assenti]),
                })

            capo = shift.squadra.caposquadra if shift.squadra else None
            day_data['shifts'].append({
                'squadra':     sq_nome,
                'squadra_id':  shift.squadra_id or '',
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
        'week_range': f"{start_of_week.day:02d} {MONTHS_MAP[start_of_week.month]} - {dates[-1].day:02d} {MONTHS_MAP[dates[-1].month]}",
        'calendar_months': calendar_months,
        'active_month_weeks': active_month_weeks,
        'active_month_key': active_month_key,
        'active_month_label': active_month_label,
        'calendar_months_json': calendar_months_json,
    }

@register.filter
def is_operational_model(model_name):
    return model_name in ['AssegnazioneTurno', 'Assenza', 'TimeTracking', 'Turno', 'ProceduraAvviata']

@register.filter
def is_resource_model(model_name):
    return model_name in ['Cliente', 'Dipendente', 'Mezzo', 'Qualifica', 'CorsoFormazione', 'ModelloProcedura', 'Squadra', 'MessaggioProgrammato']

@register.simple_tag
def active_procedures_badge():
    from core.models import ProceduraAvviata
    from django.utils.safestring import mark_safe
    try:
        count = ProceduraAvviata.objects.filter(stato='IN_CORSO').count()
        if not count:
            return ''
        return mark_safe(
            f'<span style="position:absolute;top:8px;right:8px;background:#D97706;color:white;'
            f'border-radius:12px;min-width:20px;height:20px;font-size:11px;font-weight:bold;'
            f'display:inline-flex;align-items:center;justify-content:center;padding:0 6px">'
            f'{count} in corso</span>'
        )
    except Exception:
        return ''

@register.inclusion_tag('admin/widgets/telegram_feed_widget.html')
def telegram_feed_widget():
    from core.models import TimeTracking, Assenza, Segnalazione
    from core.services import get_richieste_sostituzione_per_assenza

    # Ultime 10 Ore Lavorate inviate dai dipendenti (Telegram / WebApp)
    latest_hours = TimeTracking.objects.filter(
        source__in=['TELEGRAM', 'WEBAPP'],
        ore_dichiarate__gt=0,
    ).select_related(
        'dipendente', 'assegnazione__cliente', 'assegnazione__turno__squadra'
    ).order_by('-id')[:10]

    # Ultime 10 Assenze
    latest_absences = list(Assenza.objects.select_related('dipendente').order_by('-id')[:10])
    for item in latest_absences:
        richieste = list(get_richieste_sostituzione_per_assenza(item))
        item.tot_richieste_sost = len(richieste)
        item.coperte_sost = sum(1 for r in richieste if r.stato in ('ACCETTATA', 'COMPLETATA'))
        item.in_attesa_tg_sost = sum(1 for r in richieste if r.stato == 'INVIATA')
        aperta = next((r for r in richieste if r.stato not in ('ACCETTATA', 'COMPLETATA')), richieste[0] if richieste else None)
        item.prima_richiesta_id = aperta.id if aperta else None
        item.sostituto_corrente_nome = f"{aperta.sostituto.cognome} {aperta.sostituto.nome}" if (aperta and aperta.sostituto) else None
        item.is_avvallata = item.stato_approvazione in ('APPROVATA_AMMINISTRAZIONE', 'APPROVATA') or item.is_processed

    # Ultime 10 Segnalazioni
    latest_reports = Segnalazione.objects.select_related(
        'dipendente'
    ).order_by('-id')[:10]

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
            'cliente_id': prog.cliente_id,
            'tipo': prog.get_tipo_ripetizione_display(),
            'giorno': 'Ogni giorno' if prog.tipo_ripetizione == 'GIORNALIERO' else (prog.get_giorno_settimana_display() if prog.giorno_settimana is not None else f"Giorno {prog.giorno_mese}"),
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
