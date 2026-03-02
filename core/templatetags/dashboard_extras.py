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
        
    from core.models import Turno
    today = timezone.now().date()
    
    # Calculate start of the week (Monday)
    # If offset is 0, it's current week. If -1, previous week, etc.
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    
    # Generate 7 days from Monday
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    # Translate to Italian manually to ensure consistency
    DAYS_MAP = {
        0: 'LUNEDÌ', 1: 'MARTEDÌ', 2: 'MERCOLEDÌ', 3: 'GIOVEDÌ', 4: 'VENERDÌ', 5: 'SABATO', 6: 'DOMENICA'
    }
    MONTHS_MAP = {
        1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu', 7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'
    }

    schedule = []
    for d in dates:
        shifts = Turno.objects.filter(data=d).select_related('squadra', 'mezzo').prefetch_related('assegnazioni__cliente')
        
        day_data = {
            'date_obj': d,
            'day_name': DAYS_MAP[d.weekday()], 
            'day_date': f"{d.day:02d} {MONTHS_MAP[d.month]}", 
            'is_today': d == today,
            'shifts': []
        }
        
        for shift in shifts:
            assignments_data = []
            for assign in shift.assegnazioni.all().order_by('orario_inizio_previsto'):
                start = assign.orario_inizio_previsto.strftime('%H:%M')
                end = assign.orario_fine_previsto.strftime('%H:%M')
                assignments_data.append({
                    'cliente': assign.cliente,
                    'time_range': f"{start} - {end}"
                })

            day_data['shifts'].append({
                'squadra': shift.squadra.nome,
                'mezzo': shift.mezzo.targa if shift.mezzo else 'N/D',
                'caposquadra': shift.squadra.caposquadra.cognome if shift.squadra.caposquadra else '?',
                'assignments': assignments_data
            })
            
        schedule.append(day_data)
        
    return {
        'schedule': schedule,
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
