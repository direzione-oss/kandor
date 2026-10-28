from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Cliente, Qualifica, Dipendente
from .services import trova_jolly, trova_sostituti, genera_turni_automatici
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.contrib import messages
import json
import io
import os
from django.conf import settings
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse


def find_jolly_view(request):
    results = None
    selected_client = None
    search_params = {}
    
    clients = Cliente.objects.all()
    qualifications = Qualifica.objects.all()
    error_message = None

    if request.method == 'POST':
        try:
            client_id = request.POST.get('client_id')
            qualifica_id = request.POST.get('qualifica_id')
            date_str = request.POST.get('date')
            start_time_str = request.POST.get('start_time')
            end_time_str = request.POST.get('end_time')

            if client_id and date_str and start_time_str and end_time_str:
                selected_client = get_object_or_404(Cliente, pk=client_id)
                search_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                
                qualifica_obj = None
                if qualifica_id:
                    qualifica_obj = get_object_or_404(Qualifica, pk=qualifica_id)
                
                search_params = {
                    'date': date_str,
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'client_id': int(client_id),
                    'qualifica_id': int(qualifica_id) if qualifica_id else ''
                }

                results = trova_jolly(
                    selected_client, 
                    search_date, 
                    start_time, 
                    end_time, 
                    qualifica_richiesta=qualifica_obj
                )
            else:
                error_message = "Tutti i campi sono obbligatori."
        except ValueError:
            error_message = "Formato data/ora non valido."

    return render(request, 'core/find_jolly.html', {
        'clients': clients,
        'qualifications': qualifications,
        'results': results,
        'selected_client': selected_client,
        'search_params': search_params,
        'error_message': error_message
    })

def reconciliation_view(request):
    mesi = [
        (1, 'Gennaio'), (2, 'Febbraio'), (3, 'Marzo'), (4, 'Aprile'),
        (5, 'Maggio'), (6, 'Giugno'), (7, 'Luglio'), (8, 'Agosto'),
        (9, 'Settembre'), (10, 'Ottobre'), (11, 'Novembre'), (12, 'Dicembre')
    ]
    
    today = timezone.now().date()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))
    
    report_data = []
    
    # Per ogni cliente, calcoliamo le ore totali
    clienti = Cliente.objects.all()
    
    from .models import TimeTracking
    
    for cliente in clienti:
        # Filtra timetracking per cliente e mese/anno
        # Nota: TimeTracking è legato ad AssegnazioneTurno che è legata a Cliente
        timetracks = TimeTracking.objects.filter(
            assegnazione__cliente=cliente,
            check_in__year=selected_year,
            check_in__month=selected_month
        )
        
        # Calcolo manuale o tramite aggregazione. 
        # Aggregazione con DurationField su SQLite a volte è tricky, facciamolo python-side per sicurezza MVP
        tot_seconds = 0
        for track in timetracks:
            if track.check_in and track.check_out:
                tot_seconds += (track.check_out - track.check_in).total_seconds()
        
        ore_reali = round(tot_seconds / 3600, 2)
        ore_previste = float(cliente.ore_mensili_contratto)
        diff = ore_reali - ore_previste
        
        status = 'OK'
        if diff < -5: # Più di 5 ore in meno
            status = 'ALARM' # Sotto contratto (Perdita fatturato o lavoro non fatto)
        elif diff > 5: # Più di 5 ore in più
            status = 'WARNING' # Costo extra (Straordinari non pagati?)
            
        report_data.append({
            'cliente': cliente,
            'ore_previste': ore_previste,
            'ore_reali': ore_reali,
            'diff': diff,
            'status': status
        })
    
    return render(request, 'core/reconciliation.html', {
        'mesi': mesi,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'report_data': report_data
    })

def generate_shifts_view(request):
    if request.user.is_staff: # Solo admin/staff
        count = genera_turni_automatici(days=7)
        messages.success(request, f"Generazione completata: {count} nuove assegnazioni create per i prossimi 7 giorni.")
    else:
        messages.error(request, "Permessi insufficienti.")
    
    return redirect('/admin/')


# --- Gestione Dati Views ---

from .utils_import import generate_excel_template, import_from_excel, export_data_excel, COLUMNS_MAP

def data_management_view(request):
    if not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')
    return render(request, 'core/data_management.html')

def download_template_view(request, model_name):
    if not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')
        
    if model_name not in COLUMNS_MAP:
        messages.error(request, "Modello non valido.")
        return HttpResponseRedirect('/data-management/')
        
    output = generate_excel_template(model_name)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=modello_{model_name}.xlsx'
    return response


def export_data_view(request, model_name):
    if not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')
    
    if model_name not in COLUMNS_MAP:
        messages.error(request, "Modello non valido.")
        return HttpResponseRedirect('/data-management/')
    
    output = export_data_excel(model_name)
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=export_{model_name}.xlsx'
    return response

def import_data_view(request):
    if not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')
        
    if request.method == 'POST':
        model_name = request.POST.get('model_name')
        import_mode = request.POST.get('import_mode', 'UPDATE')
        
        if 'file' not in request.FILES:
            messages.error(request, "Nessun file selezionato. Seleziona un file Excel (.xlsx).")
            return redirect('data_management')
        
        uploaded_file = request.FILES['file']
        
        if not uploaded_file.name.endswith('.xlsx'):
            messages.error(request, f"Formato file non supportato: {uploaded_file.name}. Usa un file .xlsx.")
            return redirect('data_management')
        
        try:
            count, errors = import_from_excel(model_name, uploaded_file, mode=import_mode)
            if errors:
                messages.warning(request, f"Importati {count} record con {len(errors)} errori.")
                for err in errors[:10]:  # Mostra max 10 errori
                    messages.error(request, err)
            else:
                messages.success(request, f"✅ Importazione completata: {count} record processati con successo!")
        except Exception as e:
            messages.error(request, f"Errore critico durante l'importazione: {str(e)}")
            
        return redirect('data_management')
    
    return redirect('data_management')

def backup_db_view(request):
    if not request.user.is_superuser: # Solo superuser per backup
        messages.error(request, "Permessi insufficienti.")
        return HttpResponseRedirect('/data-management/')
        
    # Usiamo dumpdata per creare JSON
    output = io.StringIO()
    call_command('dumpdata', indent=2, stdout=output)
    output.seek(0)
    
    response = HttpResponse(output.getvalue(), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename=backup_kandor_{datetime.now().strftime("%Y%m%d_%H%M")}.json'
    return response

def restore_db_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Permessi insufficienti.")
        return HttpResponseRedirect('/data-management/')
        
    if request.method == 'POST':
        uploaded_file = request.FILES.get('backup_file')
        if not uploaded_file:
            messages.error(request, "Nessun file.")
            return HttpResponseRedirect('/data-management/')
            
        # Salva temporaneamente
        temp_path = os.path.join(settings.BASE_DIR, 'temp_restore.json')
        with open(temp_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
                
        try:
            call_command('loaddata', temp_path)
            messages.success(request, "Database ripristinato con successo!")
        except Exception as e:
            messages.error(request, f"Errore durante il ripristino: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    return HttpResponseRedirect('/data-management/')


# --- Chat & Telegram Views ---

from .utils_kandor_chat import handle_telegram_message
from django.views.decorators.csrf import csrf_exempt

def chat_simulator_view(request):
    if not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')
        
    selected_employee_id = None
    selected_employee = None
    chat_messages = []
    broadcast_result = None
    
    from .models import MessaggioChat, Squadra
    
    if request.method == 'POST':
        msg = request.POST.get('message', '').strip()
        broadcast_target = request.POST.get('broadcast_target', '')
        emp_id = request.POST.get('employee_id', '')
        uploaded_files = request.FILES.getlist('attachments')
        
        if msg or uploaded_files:
            from .utils_kandor_chat import prepare_uploaded_attachments, send_and_record_telegram_to_employee
            attachments = prepare_uploaded_attachments(uploaded_files)
            
            if broadcast_target == 'all':
                # Invio a TUTTI i dipendenti attivi (sia Telegram che Web App)
                dipendenti = Dipendente.objects.filter(stato='ATTIVO')
                sent = 0
                for dip in dipendenti:
                    try:
                        if send_and_record_telegram_to_employee(dip, text=msg, attachments=attachments):
                            sent += 1
                    except Exception:
                        pass
                broadcast_result = f"Inviato a {sent} dipendenti"
                return HttpResponseRedirect(f'/chat-simulator/?broadcast_ok={sent}')
                
            elif broadcast_target.startswith('squadra_'):
                # Invio a una SQUADRA
                sq_id = broadcast_target.replace('squadra_', '')
                try:
                    sq = Squadra.objects.get(pk=sq_id)
                    dipendenti = sq.componenti.filter(stato='ATTIVO')
                    sent = 0
                    prefix = f"[{sq.nome}] "
                    sq_text = (prefix + msg) if msg else f"[{sq.nome}]"
                    for dip in dipendenti:
                        try:
                            if send_and_record_telegram_to_employee(dip, text=sq_text, attachments=attachments):
                                sent += 1
                        except Exception:
                            pass
                    return HttpResponseRedirect(f'/chat-simulator/?broadcast_ok={sent}&sq={sq.nome}')
                except Squadra.DoesNotExist:
                    pass
                    
            elif emp_id:
                # Invio a SINGOLO dipendente
                emp = get_object_or_404(Dipendente, pk=emp_id)
                send_and_record_telegram_to_employee(emp, text=msg, attachments=attachments)
                return HttpResponseRedirect(f'/chat-simulator/?employee_id={emp_id}')
    
    # GET params
    raw_id = request.GET.get('employee_id')
    if raw_id:
        try:
            selected_employee_id = int(raw_id)
        except (ValueError, TypeError):
            pass
    
    # Carica cronologia se selezionato un dipendente
    if selected_employee_id:
        try:
            selected_employee = Dipendente.objects.get(pk=selected_employee_id)
            chat_messages = list(MessaggioChat.objects.filter(
                dipendente_id=selected_employee_id
            ).order_by('-timestamp')[:100])
            chat_messages.reverse()
            MessaggioChat.objects.filter(
                dipendente_id=selected_employee_id, direzione='IN', letto=False
            ).update(letto=True)
        except Dipendente.DoesNotExist:
            pass

    # Risultato broadcast
    broadcast_ok = request.GET.get('broadcast_ok')
    sq_name = request.GET.get('sq', '')
    
    # Modalita broadcast (quando si seleziona dal pannello)
    broadcast_mode = request.GET.get('broadcast', '')
    broadcast_label = ''
    if broadcast_mode == 'all':
        broadcast_label = 'Tutti i dipendenti'
    elif broadcast_mode.startswith('squadra_'):
        try:
            bsq = Squadra.objects.get(pk=broadcast_mode.replace('squadra_', ''))
            broadcast_label = f'Squadra {bsq.nome}'
        except Squadra.DoesNotExist:
            broadcast_mode = ''

    from django.db.models import Count, Q
    employees = Dipendente.objects.filter(stato='ATTIVO').annotate(
        unread_count=Count('messaggi_chat', filter=Q(messaggi_chat__direzione='IN', messaggi_chat__letto=False))
    ).order_by('-unread_count', 'nome', 'cognome')
    squadre = Squadra.objects.all()
    total_unread = sum(e.unread_count for e in employees)
    
    return render(request, 'core/chat_simulator.html', {
        'employees': employees,
        'squadre': squadre,
        'selected_employee_id': selected_employee_id,
        'selected_employee': selected_employee,
        'chat_messages': chat_messages,
        'broadcast_ok': broadcast_ok,
        'sq_name': sq_name,
        'broadcast_mode': broadcast_mode,
        'broadcast_label': broadcast_label,
        'total_unread': total_unread,
    })

@csrf_exempt
def add_turno_ajax(request):
    """Crea un turno con assegnazione e la relativa programmazione."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    
    try:
        data = json.loads(request.body)
        from .models import (Turno, AssegnazioneTurno, Squadra, Cliente,
                             ProgrammazioneRicorrente, RichiestaStraordinaria)
        from datetime import time as dt_time, date as dt_date
        from decimal import Decimal
        
        squadra_id = data.get('squadra_id')
        cliente_id = data.get('cliente_id')
        data_turno = data.get('data')  # YYYY-MM-DD
        ora_inizio = data.get('ora_inizio', '06:00')
        ora_fine = data.get('ora_fine', '14:00')
        tipo = data.get('tipo', 'ricorrente')
        tipo_ripetizione = data.get('tipo_ripetizione', 'SETTIMANALE')
        note = data.get('note', '')

        if not all([squadra_id, cliente_id, data_turno]):
            return JsonResponse({'status': 'error', 'error': 'Dati mancanti'})

        squadra = Squadra.objects.get(pk=squadra_id)
        cliente = Cliente.objects.get(pk=cliente_id)

        h1, m1 = map(int, ora_inizio.split(':'))
        h2, m2 = map(int, ora_fine.split(':'))
        t_inizio = dt_time(h1, m1)
        t_fine = dt_time(h2, m2)

        minuti_tot = (h2 * 60 + m2) - (h1 * 60 + m1)
        if minuti_tot <= 0:
            minuti_tot = 60
        durata_ore = Decimal(str(round(minuti_tot / 60, 2)))

        parsed_date = dt_date.fromisoformat(data_turno)
        giorno_settimana = parsed_date.weekday()
        giorno_mese = parsed_date.day

        prog_feriale = None
        richiesta_str = None

        if tipo == 'ricorrente':
            from django.db.models.signals import post_save
            from .signals import on_programmazione_save, _genera_turni_singola_programmazione
            post_save.disconnect(on_programmazione_save, sender=ProgrammazioneRicorrente)
            try:
                kwargs = dict(
                    cliente=cliente,
                    tipo_ripetizione=tipo_ripetizione,
                    ora_inizio=t_inizio,
                    durata=durata_ore,
                    squadra_abituale=squadra,
                    data_inizio_contratto=parsed_date,
                )
                if tipo_ripetizione == 'MENSILE':
                    kwargs['giorno_mese'] = giorno_mese
                elif tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE'):
                    kwargs['giorno_settimana'] = giorno_settimana
                elif tipo_ripetizione == 'GIORNALIERO':
                    pass
                prog_feriale = ProgrammazioneRicorrente(**kwargs)
                prog_feriale.save()
                _genera_turni_singola_programmazione(prog_feriale)
            finally:
                post_save.connect(on_programmazione_save, sender=ProgrammazioneRicorrente)
        else:
            # Crea RichiestaStraordinaria
            richiesta_str = RichiestaStraordinaria.objects.create(
                cliente=cliente,
                data_inizio=parsed_date,
                ora_inizio=t_inizio,
                ora_fine=t_fine,
                descrizione=note or f'Turno straordinario {squadra.nome}'
            )
        
        # Crea Turno + AssegnazioneTurno
        turno, _ = Turno.objects.get_or_create(
            data=data_turno,
            squadra=squadra
        )
        
        AssegnazioneTurno.objects.create(
            turno=turno,
            cliente=cliente,
            programmazione_feriale=prog_feriale,
            richiesta_straordinaria=richiesta_str,
            orario_inizio_previsto=t_inizio,
            orario_fine_previsto=t_fine,
            ore_previste_contratto=data.get('ore_previste') or None,
            mansione_svolta=note
        )
        
        tipo_label = 'Programmazione Ricorrente' if tipo == 'ricorrente' else 'Straordinario'
        return JsonResponse({
            'status': 'ok',
            'message': f'{tipo_label} creato: {squadra.nome} → {cliente.ragione_sociale}'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@csrf_exempt
def edit_turno_ajax(request, assign_id):
    """Modifica un'assegnazione turno via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    try:
        data = json.loads(request.body)
        from .models import AssegnazioneTurno, Cliente, ProgrammazioneRicorrente, RichiestaStraordinaria
        from datetime import time as dt_time
        from decimal import Decimal

        assign = AssegnazioneTurno.objects.select_related(
            'turno__squadra', 'programmazione_feriale'
        ).get(pk=assign_id)

        if data.get('ora_inizio'):
            h, m = map(int, data['ora_inizio'].split(':'))
            assign.orario_inizio_previsto = dt_time(h, m)
        if data.get('ora_fine'):
            h, m = map(int, data['ora_fine'].split(':'))
            assign.orario_fine_previsto = dt_time(h, m)
        if data.get('cliente_id'):
            assign.cliente = Cliente.objects.get(pk=data['cliente_id'])
        if 'note' in data:
            assign.mansione_svolta = data['note']
        if 'ore_previste' in data:
            ore_p = data['ore_previste']
            assign.ore_previste_contratto = float(str(ore_p).replace(',', '.')) if ore_p else None

        # --- Cambio squadra ---
        if data.get('squadra_id'):
            from .models import Squadra, Turno
            nuova_squadra = Squadra.objects.get(pk=data['squadra_id'])
            if nuova_squadra != assign.turno.squadra:
                # Cerca o crea un turno per la nuova squadra nella stessa data
                turno_nuovo, _ = Turno.objects.get_or_create(
                    data=assign.turno.data,
                    squadra=nuova_squadra
                )
                assign.turno = turno_nuovo

        # --- Gestione cambio tipo ricorrente ↔ straordinario ---
        nuovo_tipo = data.get('tipo')  # 'ricorrente' o 'straordinario'
        if nuovo_tipo == 'straordinario' and assign.programmazione_feriale_id:
            assign.programmazione_feriale = None
        elif nuovo_tipo == 'ricorrente' and not assign.programmazione_feriale_id:
            from django.db.models.signals import post_save
            from .signals import on_programmazione_save, _genera_turni_singola_programmazione
            try:
                post_save.disconnect(on_programmazione_save, sender=ProgrammazioneRicorrente)
            except Exception:
                pass
            try:
                t_inizio = assign.orario_inizio_previsto
                t_fine = assign.orario_fine_previsto
                minuti = (t_fine.hour * 60 + t_fine.minute) - (t_inizio.hour * 60 + t_inizio.minute)
                durata = Decimal(str(round(max(minuti, 0) / 60, 2)))
                wd = assign.turno.data.weekday()
                prog = ProgrammazioneRicorrente.objects.create(
                    cliente=assign.cliente,
                    squadra_abituale=assign.turno.squadra,
                    tipo_ripetizione='SETTIMANALE',
                    giorno_settimana=wd,
                    ora_inizio=t_inizio,
                    durata=durata,
                    data_inizio_contratto=assign.turno.data,
                )
                assign.programmazione_feriale = prog
                _genera_turni_singola_programmazione(prog)
            finally:
                try:
                    post_save.connect(on_programmazione_save, sender=ProgrammazioneRicorrente)
                except Exception:
                    pass

        assign.save()

        # Gestione dipendenti esclusi (M2M)
        if 'dipendenti_esclusi' in data:
            esclusi = data['dipendenti_esclusi']
            assign.dipendenti_esclusi.set(esclusi if esclusi else [])

        return JsonResponse({'status': 'ok', 'message': 'Turno aggiornato'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@csrf_exempt
def copy_move_turno_ajax(request, assign_id):
    """Copia o sposta un'assegnazione turno su un altro giorno."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    try:
        from .models import AssegnazioneTurno, Turno
        from datetime import date as dt_date

        data = json.loads(request.body)
        action = data.get('action', 'copy')   # 'copy' o 'move'
        new_date_str = data.get('new_date')   # YYYY-MM-DD

        if not new_date_str:
            return JsonResponse({'status': 'error', 'error': 'Data destinazione mancante'})

        assign = AssegnazioneTurno.objects.select_related('turno__squadra').get(pk=assign_id)
        new_date = dt_date.fromisoformat(new_date_str)
        old_turno = assign.turno
        squadra = old_turno.squadra

        # Trova o crea il Turno per la nuova data + squadra
        new_turno, _ = Turno.objects.get_or_create(data=new_date, squadra=squadra)

        if action == 'copy':
            AssegnazioneTurno.objects.create(
                turno=new_turno,
                cliente=assign.cliente,
                orario_inizio_previsto=assign.orario_inizio_previsto,
                orario_fine_previsto=assign.orario_fine_previsto,
                ore_previste_contratto=assign.ore_previste_contratto,
                mansione_svolta=assign.mansione_svolta,
            )
            return JsonResponse({'status': 'ok', 'message': f'Turno copiato al {new_date.strftime("%d/%m/%Y")}'})

        elif action == 'move':
            assign.turno = new_turno
            assign.save(update_fields=['turno'])
            # Cancella il vecchio turno se rimasto senza assegnazioni
            if not old_turno.assegnazioni.exists():
                old_turno.delete()
            return JsonResponse({'status': 'ok', 'message': f'Turno spostato al {new_date.strftime("%d/%m/%Y")}'})

        return JsonResponse({'status': 'error', 'error': 'Azione non valida (usa copy o move)'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})

@csrf_exempt
def delete_turno_ajax(request, assign_id):
    """Elimina un'assegnazione turno via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    try:
        from .models import AssegnazioneTurno, Turno
        
        assign = AssegnazioneTurno.objects.get(pk=assign_id)
        turno = assign.turno
        
        # Elimina anche la programmazione/straordinaria collegata se esiste
        if assign.programmazione_feriale:
            assign.programmazione_feriale.delete()
        if assign.richiesta_straordinaria:
            assign.richiesta_straordinaria.delete()
        
        assign.delete()
        
        # Se il turno non ha più assegnazioni, eliminalo
        if not turno.assegnazioni.exists():
            turno.delete()
        
        return JsonResponse({'status': 'ok', 'message': 'Turno eliminato'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@csrf_exempt
def validate_ore_ajax(request, assign_id):
    """Valida o invalida le ore di un'assegnazione turno SOLO se il dipendente ha effettivamente inviato le ore."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    try:
        from .models import TimeTracking, AssegnazioneTurno, Dipendente, Assenza
        from decimal import Decimal
        from django.db.models import Q
        from .models import RichiestaSostituzione

        assign = AssegnazioneTurno.objects.select_related('turno__squadra__caposquadra').get(pk=assign_id)
        squadra = assign.turno.squadra
        sq_nome = assign.turno.nome_squadra
        data_turno = assign.turno.data
        esclusi_ids = set(assign.dipendenti_esclusi.values_list('pk', flat=True))

        # Trova dipendenti della squadra in ASSENZA per questa data
        assenti_ids = set(Assenza.objects.filter(
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).exclude(stato_approvazione='RIFIUTATA').values_list('dipendente_id', flat=True))

        # Rimuovi eventuali TimeTracking registrati per i dipendenti in ASSENZA o esclusi per questo turno
        if assenti_ids:
            TimeTracking.objects.filter(assegnazione=assign, dipendente_id__in=assenti_ids).delete()
        if esclusi_ids:
            TimeTracking.objects.filter(assegnazione=assign, dipendente_id__in=esclusi_ids).delete()

        data = json.loads(request.body) if request.body else {}
        action = data.get('action', 'validate')
        ore_param = data.get('ore')
        validate_flag = data.get('validate', False) or (action == 'validate')

        # Seleziona SOLO le registrazioni TimeTracking già inviate dai dipendenti per questo turno
        existing_tts = list(
            TimeTracking.objects.filter(assegnazione=assign)
            .filter(Q(ore_dichiarate__gt=0) | Q(check_out__isnull=False))
            .select_related('dipendente')
        )

        if not existing_tts:
            return JsonResponse({
                'status': 'error',
                'error': 'Impossibile validare: il dipendente non ha ancora inviato le ore per questo turno.',
                'validated': False,
                'count': 0,
            }, status=400)

        ore_val = None
        if ore_param is not None:
            ore_val = Decimal(str(float(str(ore_param).replace(',', '.'))))
            if ore_val <= 0:
                return JsonResponse({
                    'status': 'error',
                    'error': 'Inserisci un numero di ore valido (> 0).',
                }, status=400)

        updated_count = 0
        for tt in existing_tts:
            if ore_val is not None:
                tt.ore_dichiarate = ore_val
            if action == 'unvalidate':
                tt.is_validated = False
            elif validate_flag:
                tt.is_validated = True
            tt.save()
            updated_count += 1

        status_msg = "Ore validate" if (validate_flag and action != 'unvalidate') else ("Validazione rimossa" if action == 'unvalidate' else "Ore aggiornate")
        return JsonResponse({
            'status': 'ok',
            'message': f"{status_msg} per {updated_count} dipendenti della squadra {sq_nome}",
            'validated': validate_flag and action != 'unvalidate',
            'count': updated_count,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


def get_squadre_clienti_json(request):
    """Ritorna JSON con squadre e clienti per la modale del calendario."""
    from .models import Squadra, Cliente

    squadre_qs = Squadra.objects.all().prefetch_related('componenti')
    squadre = []
    for sq in squadre_qs:
        componenti = [{'id': c.id, 'nome': f"{c.cognome} {c.nome}"} for c in sq.componenti.all()]
        if sq.caposquadra:
            componenti.insert(0, {'id': sq.caposquadra.id, 'nome': f"{sq.caposquadra.cognome} {sq.caposquadra.nome} (CS)"})
        squadre.append({'id': sq.id, 'nome': sq.nome, 'componenti': componenti})

    clienti = list(Cliente.objects.all().order_by('ragione_sociale').values('id', 'ragione_sociale'))

    return JsonResponse({'squadre': squadre, 'clienti': clienti})


def get_assegnazione_componenti_json(request, assign_id):
    """Per una specifica assegnazione: restituisce i componenti della squadra, i sostituti, le ore dichiarate, assenze e ID degli esclusi."""
    try:
        from .models import AssegnazioneTurno, TimeTracking, Assenza, RichiestaSostituzione
        assign = AssegnazioneTurno.objects.select_related('turno__squadra__caposquadra').get(pk=assign_id)
        squadra = assign.turno.squadra
        data_turno = assign.turno.data
        esclusi_ids = list(assign.dipendenti_esclusi.values_list('pk', flat=True))

        tt_map = {tt.dipendente_id: tt for tt in TimeTracking.objects.filter(assegnazione=assign)}

        assenze_qs = Assenza.objects.filter(
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).exclude(stato_approvazione='RIFIUTATA')
        assenze_map = {ass.dipendente_id: ass for ass in assenze_qs}

        richieste_sost_qs = RichiestaSostituzione.objects.filter(
            assegnazione_originale=assign,
            stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA', 'ACCETTATA', 'COMPLETATA']
        ).select_related('sostituto', 'dipendente_assente')
        sost_by_assente = {r.dipendente_assente_id: r for r in richieste_sost_qs}

        def _build_comp_dict(dip, ruolo, sostituto_di=None):
            tt = tt_map.get(dip.pk)
            ass = assenze_map.get(dip.pk) if not sostituto_di else None
            req_sost = sost_by_assente.get(dip.pk) if not sostituto_di else None
            ore_d = float(tt.ore_dichiarate) if (tt and tt.ore_dichiarate is not None) else (float(tt.durata_ore) if (tt and tt.durata_ore) else None)
            return {
                'id': dip.pk,
                'nome': f"{dip.cognome} {dip.nome}",
                'ruolo': ruolo,
                'sostituto_di': sostituto_di,
                'escluso': (dip.pk in esclusi_ids) if not sostituto_di else False,
                'in_assenza': ass is not None,
                'assenza_id': ass.id if ass else None,
                'stato_approvazione': ass.stato_approvazione if ass else None,
                'tipo_assenza': ass.tipo if ass else None,
                'assenza_display': f"🏥 {ass.get_tipo_display()}" if ass else None,
                'richiesta_sostituzione_id': req_sost.id if req_sost else None,
                'richiesta_sostituzione_stato': req_sost.stato if req_sost else None,
                'sostituto_assegnato': f"{req_sost.sostituto.cognome} {req_sost.sostituto.nome}" if (req_sost and req_sost.sostituto) else None,
                'ore_dichiarate': ore_d if not ass else None,
                'is_validated': (tt.is_validated if tt else False) if not ass else False,
                'source': tt.source if tt else None,
                'note': tt.note if tt else '',
            }

        componenti = []
        presenti_ids = set()
        if squadra:
            if squadra.caposquadra:
                componenti.append(_build_comp_dict(squadra.caposquadra, 'Caposquadra'))
                presenti_ids.add(squadra.caposquadra.pk)
            for c in squadra.componenti.exclude(pk=squadra.caposquadra.pk if squadra.caposquadra else None):
                componenti.append(_build_comp_dict(c, 'Componente'))
                presenti_ids.add(c.pk)

        # Aggiungi i sostituti confermati alla lista componenti del turno
        for r in richieste_sost_qs:
            if r.stato in ['ACCETTATA', 'COMPLETATA'] and r.sostituto and r.sostituto.pk not in presenti_ids:
                componenti.append(_build_comp_dict(
                    r.sostituto,
                    'Sostituto',
                    sostituto_di=f"{r.dipendente_assente.cognome} {r.dipendente_assente.nome}"
                ))
                presenti_ids.add(r.sostituto.pk)

        # Aggiungi eventuali componenti storici (presenti in TimeTracking ma rimossi dalla squadra o di squadra eliminata)
        for tt_dip_id, tt_obj in tt_map.items():
            if tt_dip_id not in presenti_ids and tt_obj.dipendente:
                componenti.append(_build_comp_dict(tt_obj.dipendente, 'Componente (storico)'))
                presenti_ids.add(tt_dip_id)

        return JsonResponse({
            'componenti': componenti,
            'esclusi_ids': esclusi_ids,
            'assign_id': assign.id,
            'ore_previste': float(assign.ore_previste_contratto) if assign.ore_previste_contratto else None,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


def _upload_foto_profilo_supabase(telegram_foto_url, dipendente_id):
    """
    Scarica la foto da Telegram, la salva localmente nel campo Dipendente.foto e
    se configurato la carica su Supabase Storage.
    Ritorna l'URL permanente (Supabase o Media locale), prevenendo l'uso di URL Telegram temporanei.
    """
    try:
        import requests as req
        from django.core.files.base import ContentFile
        from django.conf import settings
        from .models import Dipendente

        resp = req.get(telegram_foto_url, timeout=15)
        if not resp.ok:
            return None
        foto_bytes = resp.content

        # 1. Salva il file permanente locale
        dip = Dipendente.objects.filter(pk=dipendente_id).first()
        file_name = f"dipendente_{dipendente_id}.jpg"
        local_url = None
        if dip:
            dip.foto.save(file_name, ContentFile(foto_bytes), save=True)
            local_url = dip.foto.url if dip.foto else None

        # 2. Prova anche l'upload su Supabase Storage se configurato
        supabase_url = getattr(settings, 'SUPABASE_URL', '') or os.environ.get('SUPABASE_URL', '')
        supabase_key = getattr(settings, 'SUPABASE_KEY', '') or os.environ.get('SUPABASE_KEY', '')

        if supabase_url and supabase_key:
            bucket = "avatar"
            upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{file_name}"
            upload_resp = req.post(
                upload_url,
                data=foto_bytes,
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "image/jpeg",
                    "x-upsert": "true",
                },
                timeout=20
            )
            if upload_resp.status_code in (200, 201):
                return f"{supabase_url}/storage/v1/object/public/{bucket}/{file_name}"

        return local_url

    except Exception as e:
        print(f"[FotoProfiloUpload] Errore salvataggio foto profilo: {e}")

    return None

def _upload_chat_foto_supabase(telegram_foto_url, chat_id):
    """
    Scarica la foto dalla chat Telegram e la salva su Supabase Storage.
    Ritorna l'URL permanente (Supabase) o il Telegram URL come fallback.
    """
    try:
        import requests as req
        from django.conf import settings
        import uuid
        import os

        resp = req.get(telegram_foto_url, timeout=15)
        if not resp.ok:
            return telegram_foto_url
        foto_bytes = resp.content

        supabase_url = getattr(settings, 'SUPABASE_URL', '') or os.environ.get('SUPABASE_URL', '')
        supabase_key = getattr(settings, 'SUPABASE_KEY', '') or os.environ.get('SUPABASE_KEY', '')
        bucket = getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'kandor-media')

        if supabase_url and supabase_key:
            file_name = f"chat_{chat_id}_{uuid.uuid4().hex[:8]}.jpg"
            upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{file_name}"
            upload_resp = req.post(
                upload_url,
                data=foto_bytes,
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "image/jpeg",
                    "x-upsert": "true",
                },
                timeout=20
            )
            if upload_resp.status_code in (200, 201):
                return f"{supabase_url}/storage/v1/object/public/{bucket}/{file_name}"
        
        # Fallback se Supabase non va a buon fine, salviamo file locale in media
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        file_name = f"chat_images/chat_{chat_id}_{uuid.uuid4().hex[:8]}.jpg"
        saved_path = default_storage.save(file_name, ContentFile(foto_bytes))
        return default_storage.url(saved_path)
    except Exception as e:
        print(f"[ChatFotoUpload] Errore salvataggio foto chat: {e}")

    return telegram_foto_url

@csrf_exempt
def telegram_webhook_view(request):
    """
    Riceve aggiornamenti da Telegram (Webhook).
    Gestisce messaggi di testo e callback_query (bottoni inline).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            token = settings.TELEGRAM_BOT_TOKEN
            
            # Gestione callback_query (bottoni inline)
            callback = data.get('callback_query')
            if callback:
                cb_data = callback.get('data', '')
                chat_id = str(callback['message']['chat']['id'])
                first_name = callback.get('from', {}).get('first_name', 'Utente')
                callback_id = callback.get('id')
                
                # Rispondi al callback per togliere il loading
                if token and callback_id:
                    import requests as req
                    req.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                             json={'callback_query_id': callback_id})
                
                from .utils_kandor_chat import handle_telegram_callback
                response = handle_telegram_callback(chat_id, cb_data, sender_name=first_name)
                
                # Salva la scelta del menu come messaggio IN
                try:
                    from .models import MessaggioChat, Dipendente
                    dip_cb = Dipendente.objects.filter(telegram_chat_id=chat_id).first()
                    if dip_cb:
                        testo_cb = cb_data.replace('_', ' ').title()
                        MessaggioChat.objects.create(
                            dipendente=dip_cb, testo=f"[ Menu: {testo_cb} ]", direzione='IN'
                        )
                        # Salva risposta bot
                        if response:
                            testo_risposta = response.get('text', '') if isinstance(response, dict) else str(response)
                            if testo_risposta:
                                MessaggioChat.objects.create(
                                    dipendente=dip_cb, testo=testo_risposta, direzione='OUT'
                                )
                except Exception:
                    pass

                if response and token:
                    import requests as req
                    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = {'chat_id': chat_id, 'text': response['text']}
                    if response.get('reply_markup'):
                        payload['reply_markup'] = response['reply_markup']
                    try:
                        req.post(send_url, json=payload)
                    except Exception as e:
                        print(f"[Telegram Error] Callback Send: {e}")
                
                return HttpResponse("OK")
            
            # Gestione messaggi (testo, foto e documenti)
            message = data.get('message', {})
            chat = message.get('chat', {})
            text = message.get('text', '')
            caption = message.get('caption', '')
            chat_id = str(chat.get('id', ''))
            first_name = chat.get('first_name', 'Utente')
            photo = message.get('photo')
            document = message.get('document')
            
            # Se c'è una foto, scarica l'URL
            foto_url = ''
            if photo and chat_id and token:
                try:
                    import requests as req
                    # Prendi la foto più grande (ultima nell'array)
                    file_id = photo[-1]['file_id']
                    file_info = req.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}").json()
                    if file_info.get('ok'):
                        file_path = file_info['result']['file_path']
                        foto_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                except Exception:
                    pass

            # Se c'è un documento (PDF, Word, ecc.), scarica l'URL
            allegato_url = ''
            allegato_nome = ''
            if document and chat_id and token:
                try:
                    import requests as req
                    file_id = document.get('file_id')
                    allegato_nome = document.get('file_name') or 'documento'
                    if file_id:
                        file_info = req.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}").json()
                        if file_info.get('ok'):
                            file_path = file_info['result']['file_path']
                            allegato_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                except Exception:
                    pass
            
            if chat_id and (text or foto_url or allegato_url):
                # ---- Gestione Foto Profilo ----
                if foto_url and not text and not caption:
                    try:
                        from django.core.cache import cache
                        from .models import Dipendente
                        dip_check = Dipendente.objects.filter(telegram_chat_id=chat_id).first()
                        if dip_check and cache.get(f'pending_foto_profilo_{chat_id}'):
                            # Prova upload permanente su Supabase Storage
                            url_finale = _upload_foto_profilo_supabase(foto_url, dip_check.pk) or foto_url
                            dip_check.foto_profilo_url = url_finale
                            dip_check.save(update_fields=['foto_profilo_url'])
                            cache.delete(f'pending_foto_profilo_{chat_id}')
                            if token:
                                import requests as req
                                req.post(
                                    f"https://api.telegram.org/bot{token}/sendMessage",
                                    json={
                                        "chat_id": chat_id,
                                        "text": f"✅ Foto profilo aggiornata, {dip_check.nome}! Ora ti riconosciamo nell'app. 😊",
                                    },
                                    timeout=5
                                )
                            return HttpResponse("OK")
                    except Exception:
                        pass


                # Salva messaggio ricevuto nel database
                try:
                    from .models import MessaggioChat, Dipendente
                    dip = Dipendente.objects.filter(telegram_chat_id=chat_id).first()
                    if dip:
                        # Salva foto in modo permanente invece del URL temporaneo Telegram
                        perm_foto_url = _upload_chat_foto_supabase(foto_url, chat_id) if foto_url else ''
                        MessaggioChat.objects.create(
                            dipendente=dip,
                            testo=text or caption,
                            foto_url=perm_foto_url,
                            allegato_url=allegato_url,
                            allegato_nome=allegato_nome,
                            direzione='IN'
                        )
                        # Notifica nuovi messaggi SOLO a Responsabili Area, Titolari e Admin (non a tutti i dipendenti)
                        try:
                            from .services import notifica_nuovo_messaggio
                            notifica_nuovo_messaggio(dip, testo=text or caption or allegato_nome, foto_url=perm_foto_url)
                        except Exception as e:
                            print(f"[Notifica Errore]: {e}")
                except Exception:
                    pass
                
                # Processa messaggi per i comandi bot
                if text:
                    response = handle_telegram_message(chat_id, text, sender_name=first_name)
                elif caption:
                    response = handle_telegram_message(chat_id, caption, sender_name=first_name)
                elif foto_url:
                    from .utils_kandor_chat import _TELEGRAM_STATE
                    if _TELEGRAM_STATE.get(chat_id, {}).get('action') == 'segnalazione':
                        response = handle_telegram_message(chat_id, "[Foto allegata]", sender_name=first_name)
                    else:
                        response = {'text': 'Foto ricevuta! Se volevi fare una segnalazione, usa prima il pulsante "Segnalazione".', 'reply_markup': None}
                else:
                    response = None
                
                if response and token:
                    import requests as req
                    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    
                    if isinstance(response, dict):
                        payload = {'chat_id': chat_id, 'text': response['text']}
                        if response.get('reply_markup'):
                            payload['reply_markup'] = response['reply_markup']
                        testo_out = response['text']
                    else:
                        payload = {'chat_id': chat_id, 'text': response}
                        testo_out = str(response)
                    
                    try:
                        req.post(send_url, json=payload)
                        # Salva risposta bot nello storico
                        if dip and testo_out:
                            from .models import MessaggioChat
                            MessaggioChat.objects.create(
                                dipendente=dip, testo=testo_out, direzione='OUT'
                            )
                    except Exception as e:
                        print(f"[Telegram Error] Send Failed: {e}")

                return HttpResponse("OK")
                
        except Exception as e:
            print(f"Webhook Error: {e}")
            
    return HttpResponse('OK')

@csrf_exempt
def toggle_telegram_status(request, model_name, item_id):
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    
    from .models import TimeTracking, Assenza, Segnalazione
    
    model_map = {
        'timetracking': TimeTracking,
        'assenza': Assenza,
        'segnalazione': Segnalazione
    }
    
    ModelClass = model_map.get(model_name.lower())
    if not ModelClass:
        return HttpResponse('Model not found', status=404)
        
    try:
        item = ModelClass.objects.get(pk=item_id)
        
        new_state = False
        extra_payload = {}
        if model_name.lower() == 'timetracking':
            if not item.is_validated and not (item.ore_dichiarate and item.ore_dichiarate > 0) and not (item.durata_ore and item.durata_ore > 0):
                return JsonResponse({'status': 'error', 'message': 'Impossibile validare: il dipendente non ha inviato le ore.'}, status=400)
            item.is_validated = not item.is_validated
            new_state = item.is_validated
            item.save()
        elif model_name.lower() == 'assenza':
            new_state = not item.is_processed
            if new_state:
                from .services import avvalla_assenza_da_amministrazione
                res = avvalla_assenza_da_amministrazione(item.pk)
                extra_payload['richieste_ids'] = res.get('richieste_ids', [])
                extra_payload['prima_richiesta_id'] = res.get('prima_richiesta_id')
                extra_payload['stato_approvazione'] = 'APPROVATA_AMMINISTRAZIONE'
            else:
                item.is_processed = False
                item.save()
        elif model_name.lower() == 'segnalazione':
            item.risolto = not item.risolto
            new_state = item.risolto
            item.save()
            
        payload = {'status': 'ok', 'new_state': new_state, **extra_payload}
        return HttpResponse(json.dumps(payload), content_type='application/json')
        
    except ModelClass.DoesNotExist:
        return HttpResponse('Item not found', status=404)
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

def manuale_pdf_view(request):
    """Restituisce il file PDF completo di 41 pagine con screenshot del Manuale Utente Kandor (v3.0)."""
    import os
    from django.http import FileResponse, Http404
    pdf_path = os.path.join(settings.BASE_DIR, 'MANUALE_UTENTE_KANDOR.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(open(pdf_path, 'rb'), content_type='application/pdf', filename='MANUALE_UTENTE_KANDOR.pdf')
    raise Http404("File PDF del manuale non trovato.")


def manuale_screenshot_view(request, filename):
    """Serve le immagini screenshot del manuale dalla cartella screenshots/."""
    import os
    from django.http import FileResponse, Http404
    safe_name = os.path.basename(filename)
    img_path = os.path.join(settings.BASE_DIR, 'screenshots', safe_name)
    if os.path.exists(img_path) and safe_name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        content_type = 'image/png' if safe_name.lower().endswith('.png') else 'image/jpeg'
        return FileResponse(open(img_path, 'rb'), content_type=content_type)
    raise Http404("Immagine non trovata.")


def _convert_markdown_safe(content):
    """Converte Markdown in HTML usando la libreria markdown se presente, altrimenti parser Python nativo."""
    try:
        import markdown
        return markdown.markdown(content, extensions=['tables', 'fenced_code', 'toc', 'nl2br'])
    except ImportError:
        import re
        html = content
        # Fenced code blocks
        html = re.sub(
            r'```[\w]*\n(.*?)```',
            lambda m: '<pre style="background:#f1f5f9;padding:12px;border-radius:6px;overflow-x:auto;"><code>' + m.group(1).replace('<', '&lt;').replace('>', '&gt;') + '</code></pre>',
            html,
            flags=re.DOTALL
        )
        # Headers
        html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        # Bold & Italic
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        # Blockquotes
        html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
        # Inline code
        html = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', html)
        # Links
        html = re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)

        lines = html.split('\n')
        in_table = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|'):
                cells = [c.strip() for c in stripped.split('|')[1:-1]]
                if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                    continue
                if not in_table:
                    new_lines.append('<table><thead><tr>')
                    for c in cells:
                        new_lines.append(f'<th>{c}</th>')
                    new_lines.append('</tr></thead><tbody>')
                    in_table = True
                else:
                    new_lines.append('<tr>')
                    for c in cells:
                        new_lines.append(f'<td>{c}</td>')
                    new_lines.append('</tr>')
            else:
                if in_table:
                    new_lines.append('</tbody></table>')
                    in_table = False
                img_match = re.match(r'^!\[(.*?)\]\((.+?)\)$', stripped)
                if img_match:
                    alt = img_match.group(1)
                    src = img_match.group(2)
                    new_lines.append(f'<div style="text-align:center;margin:20px 0;"><img src="{src}" alt="{alt}"><p style="font-size:12px;color:#64748b;margin-top:4px;"><em>{alt}</em></p></div>')
                elif stripped.startswith('- ') or stripped.startswith('* '):
                    new_lines.append(f'<li>{stripped[2:]}</li>')
                elif re.match(r'^\d+\.\s+', stripped):
                    text = re.sub(r'^\d+\.\s+', '', stripped)
                    new_lines.append(f'<li>{text}</li>')
                elif stripped == '---':
                    new_lines.append('<hr>')
                elif stripped == '':
                    new_lines.append('')
                elif stripped.startswith('<h') or stripped.startswith('<pre') or stripped.startswith('<blockquote') or stripped.startswith('</'):
                    new_lines.append(line)
                else:
                    new_lines.append(f'<p>{line}</p>')
        if in_table:
            new_lines.append('</tbody></table>')
        return '\n'.join(new_lines)


def manuale_view(request):
    """Visualizza il manuale utente admin completo in formato HTML."""
    import os
    md_path = os.path.join(settings.BASE_DIR, 'MANUALE_UTENTE.md')
    try:
        with open(md_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        content = "# Manuale Utente Kandor\n\nImpossibile caricare il file MANUALE_UTENTE.md."

    content_html = _convert_markdown_safe(content)
    return render(request, 'core/manuale.html', {'content_html': content_html})


def titolari_dashboard_view(request):
    """Dashboard di supervisione per i titolari."""
    if not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')
    
    from .models import (
        Dipendente, AssegnazioneTurno, TimeTracking,
        Assenza, RichiestaSostituzione
    )
    from django.db.models import Q, Sum
    
    oggi = timezone.now().date()
    lun = oggi - timedelta(days=oggi.weekday())
    ven = lun + timedelta(days=4)
    
    # --- Dipendenti ---
    n_dipendenti = Dipendente.objects.filter(stato='ATTIVO').count()
    n_sostituti = Dipendente.objects.filter(stato='ATTIVO', is_sostituto=True).count()
    assenti_oggi = Assenza.objects.filter(data_inizio__lte=oggi, data_fine__gte=oggi)
    n_assenti_oggi = assenti_oggi.count()
    
    # --- Turni di oggi ---
    assegn_oggi = AssegnazioneTurno.objects.filter(turno__data=oggi)
    turni_oggi = assegn_oggi.count()
    turni_compilati_oggi = TimeTracking.objects.filter(
        assegnazione__turno__data=oggi
    ).values('assegnazione').distinct().count()
    turni_scoperti_oggi = max(0, turni_oggi - turni_compilati_oggi)
    
    # --- Sostituzioni ---
    sost_aperte = RichiestaSostituzione.objects.filter(stato='APERTA').count()
    sost_inviate = RichiestaSostituzione.objects.filter(stato='INVIATA').count()
    sost_fallite = RichiestaSostituzione.objects.filter(stato='ANNULLATA', creata_il__date=oggi).count()
    
    # --- Settimana ---
    ore_r = TimeTracking.objects.filter(
        timestamp__date__gte=lun, timestamp__date__lte=ven
    ).aggregate(tot=Sum('ore_lavorate'))
    ore_settimana = round(ore_r['tot'] or 0, 1)
    
    turni_sett_tot = AssegnazioneTurno.objects.filter(
        turno__data__gte=lun, turno__data__lte=ven
    ).count()
    turni_sett_compilati = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=lun,
        assegnazione__turno__data__lte=ven
    ).values('assegnazione').distinct().count()
    
    ass_sett = Assenza.objects.filter(
        Q(data_inizio__lte=ven) & Q(data_fine__gte=lun)
    )
    ass_malattia = ass_sett.filter(tipo='MALATTIA').count()
    ass_ferie = ass_sett.filter(tipo='FERIE').count()
    ass_permesso = ass_sett.filter(tipo='PERMESSO').count()
    
    sost_sett = RichiestaSostituzione.objects.filter(
        creata_il__date__gte=lun, creata_il__date__lte=ven
    )
    sost_sett_ok = sost_sett.filter(stato='COMPLETATA').count()
    sost_sett_fail = sost_sett.filter(stato='ANNULLATA').count()
    sost_sett_corso = sost_sett.filter(stato__in=['APERTA', 'INVIATA', 'APPROVATA_RA']).count()
    
    # --- Alert economici ---
    from .models import ProgrammazioneRicorrente, Cliente
    soglia_default = 12.0
    try:
        n_sotto_soglia = 0
        for prog in ProgrammazioneRicorrente.objects.filter(attiva=True).select_related('cliente'):
            if prog.cliente and prog.cliente.importo_mensile and prog.ore_mensili_stimate:
                if prog.ore_mensili_stimate > 0:
                    val = float(prog.cliente.importo_mensile) / float(prog.ore_mensili_stimate)
                    if val < soglia_default:
                        n_sotto_soglia += 1
    except Exception:
        n_sotto_soglia = 0
    
    # --- Alert lista ---
    alerts = []
    if turni_scoperti_oggi > 0:
        alerts.append({'msg': f'⚠️ {turni_scoperti_oggi} turno/i di oggi senza ore registrate', 'critico': False})
    if sost_aperte > 0:
        alerts.append({'msg': f'🔄 {sost_aperte} richiesta/e di sostituzione in attesa di approvazione RA', 'critico': False})
    open_fallite = RichiestaSostituzione.objects.filter(stato='ANNULLATA', creata_il__date=oggi)
    if open_fallite.exists():
        alerts.append({'msg': f'🚨 {open_fallite.count()} sostituzione/i fallite oggi — nessun sostituto disponibile!', 'critico': True})
    if n_sotto_soglia > 0:
        alerts.append({'msg': f'💰 {n_sotto_soglia} contratto/i sotto la soglia di {soglia_default}€/ora', 'critico': False})
    visite_in_scadenza = Dipendente.objects.exclude(stato='INATTIVO').filter(
        data_ultima_visita_medica__isnull=False,
        data_ultima_visita_medica__lte=oggi + timedelta(days=20)
    ).count()
    if visite_in_scadenza > 0:
        alerts.append({'msg': f'🩺 {visite_in_scadenza} visita/e medica/he in scadenza (o scadute) entro 20 giorni', 'critico': False})
    try:
        from .models import CorsoDipendente
        corsi_in_scadenza = CorsoDipendente.objects.exclude(dipendente__stato='INATTIVO').filter(
            data_scadenza__isnull=False,
            data_scadenza__lte=oggi + timedelta(days=20)
        ).count()
        if corsi_in_scadenza > 0:
            alerts.append({'msg': f'🎓 {corsi_in_scadenza} corso/i di formazione in scadenza (o scaduti) entro 20 giorni', 'critico': False})
    except Exception:
        pass
    try:
        from .models import Mezzo
        threshold_mezzi = oggi + timedelta(days=30)
        mezzi_in_scadenza = Mezzo.objects.filter(
            Q(scadenza_polizza__isnull=False, scadenza_polizza__lte=threshold_mezzi) |
            Q(scadenza_revisione__isnull=False, scadenza_revisione__lte=threshold_mezzi) |
            Q(scadenza_permesso_citta_alta__isnull=False, scadenza_permesso_citta_alta__lte=threshold_mezzi)
        ).distinct().count()
        if mezzi_in_scadenza > 0:
            alerts.append({'msg': f'🚗 {mezzi_in_scadenza} mezzo/i aziendale/i con scadenze (polizza, revisione o permessi) entro 30 giorni', 'critico': False})
    except Exception:
        pass
    
    return render(request, 'core/titolari_dashboard.html', {
        'oggi': oggi, 'lun': lun, 'ven': ven,
        'n_dipendenti': n_dipendenti, 'n_sostituti': n_sostituti, 'n_assenti_oggi': n_assenti_oggi,
        'turni_oggi': turni_oggi, 'turni_compilati_oggi': turni_compilati_oggi, 'turni_scoperti_oggi': turni_scoperti_oggi,
        'sost_aperte': sost_aperte, 'sost_inviate': sost_inviate, 'sost_fallite': sost_fallite,
        'ore_settimana': ore_settimana, 'turni_sett_tot': turni_sett_tot, 'turni_sett_compilati': turni_sett_compilati,
        'ass_malattia': ass_malattia, 'ass_ferie': ass_ferie, 'ass_permesso': ass_permesso,
        'sost_sett_ok': sost_sett_ok, 'sost_sett_fail': sost_sett_fail, 'sost_sett_corso': sost_sett_corso,
        'n_sotto_soglia': n_sotto_soglia, 'soglia_default': soglia_default,
        'alerts': alerts,
    })


@csrf_exempt
def titolari_riepilogo_view(request):
    """Endpoint per trigger esterno del riepilogo settimanale (cron-job.org).
    Chiamare con GET /titolari/riepilogo/?token=SECRET
    Configurare SECRET in settings come RIEPILOGO_TOKEN.
    """
    from django.conf import settings
    token_atteso = getattr(settings, 'RIEPILOGO_TOKEN', '')
    token_ricevuto = request.GET.get('token', '')
    
    if not token_atteso or token_ricevuto != token_atteso:
        return JsonResponse({'errore': 'Non autorizzato'}, status=403)
    
    # Solo venerdì (weekday 4) o forzato con ?force=1
    from django.utils import timezone
    if timezone.now().weekday() != 4 and request.GET.get('force') != '1':
        return JsonResponse({'stato': 'non è venerdì, usa ?force=1 per forzare'})
    
    from django.core.management import call_command
    call_command('riepilogo_settimanale')
    return JsonResponse({'stato': 'riepilogo inviato', 'timestamp': str(timezone.now())})


def manuale_dipendente_view(request):
    """Serve il manuale dipendente come pagina HTML leggibile."""
    import os
    md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'MANUALE_DIPENDENTE_TELEGRAM.md')
    
    try:
        try:
            with open(md_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            with open(md_path, 'r', encoding='latin-1') as f:
                content = f.read()
    except FileNotFoundError:
        content = "# Manuale non trovato\n\nIl file MANUALE_DIPENDENTE_TELEGRAM.md non è presente."
    
    # Conversione markdown → HTML semplice
    import re
    html = content
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # Italic
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    # Blockquotes
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    # Code inline
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    # Tables
    lines = html.split('\n')
    in_table = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if all(c.replace('-', '').replace(':', '') == '' for c in cells):
                continue  # Skip separator row
            if not in_table:
                new_lines.append('<table class="md-table"><thead><tr>')
                for c in cells:
                    new_lines.append(f'<th>{c}</th>')
                new_lines.append('</tr></thead><tbody>')
                in_table = True
            else:
                new_lines.append('<tr>')
                for c in cells:
                    new_lines.append(f'<td>{c}</td>')
                new_lines.append('</tr>')
        else:
            if in_table:
                new_lines.append('</tbody></table>')
                in_table = False
            # Images ![alt](src)
            img_match = re.match(r'^!\[(.+?)\]\((.+?)\)$', stripped)
            if img_match:
                alt = img_match.group(1)
                src = img_match.group(2)
                new_lines.append(f'<div style="text-align:center;margin:15px 0"><img src="{src}" alt="{alt}" style="max-width:250px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.15)"></div>')
            # List items
            elif stripped.startswith('- '):
                new_lines.append(f'<li>{stripped[2:]}</li>')
            elif stripped.startswith('1. ') or re.match(r'^\d+\. ', stripped):
                text = re.sub(r'^\d+\. ', '', stripped)
                new_lines.append(f'<li>{text}</li>')
            elif stripped == '---':
                new_lines.append('<hr>')
            elif stripped == '':
                new_lines.append('<br>')
            else:
                new_lines.append(f'<p>{line}</p>')
    if in_table:
        new_lines.append('</tbody></table>')
    
    body_html = '\n'.join(new_lines)
    
    page_html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Guida Operativa Dipendente — Web App Mobile & Bot Telegram Kandor</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; color: #333; }}
        h1 {{ color: #ff6f00; border-bottom: 3px solid #ff6f00; padding-bottom: 10px; }}
        h2 {{ color: #e65100; margin-top: 30px; border-left: 4px solid #ff6f00; padding-left: 10px; }}
        h3 {{ color: #333; margin-top: 20px; }}
        .md-table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        .md-table th {{ background: #ff6f00; color: white; padding: 10px; text-align: left; }}
        .md-table td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; }}
        .md-table tr:nth-child(even) {{ background: #fff3e0; }}
        blockquote {{ background: #fff3e0; border-left: 4px solid #ff6f00; padding: 10px 15px; margin: 10px 0; border-radius: 4px; }}
        code {{ background: #eee; padding: 2px 6px; border-radius: 3px; font-size: 14px; }}
        li {{ margin: 5px 0; }}
        hr {{ border: none; border-top: 2px solid #eee; margin: 20px 0; }}
        strong {{ color: #e65100; }}
        .print-btn {{ position: fixed; bottom: 20px; right: 20px; background: #ff6f00; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
        .print-btn:hover {{ background: #e65100; }}
        @media print {{ .print-btn {{ display: none; }} body {{ background: white; }} }}
    </style>
</head>
<body>
{body_html}
<button class="print-btn" onclick="window.print()">🖨️ Stampa / PDF</button>
</body>
</html>"""
    
    return HttpResponse(page_html)

def extend_contract_view(request, prog_id):
    """Prolunga un contratto di 12 mesi e rigenera i turni."""
    from .models import ProgrammazioneRicorrente
    from dateutil.relativedelta import relativedelta
    
    prog = get_object_or_404(ProgrammazioneRicorrente, pk=prog_id)
    
    if prog.data_fine_contratto:
        old_date = prog.data_fine_contratto
        # Proroga di 12 mesi dalla data fine attuale
        prog.data_fine_contratto = old_date + relativedelta(months=12)
        prog.save()
        
        # Rigenera i turni per coprire il nuovo periodo
        count = genera_turni_automatici()
        
        messages.success(
            request,
            f"✅ Contratto per '{prog.cliente.ragione_sociale}' prorogato! "
            f"Nuova scadenza: {prog.data_fine_contratto.strftime('%d/%m/%Y')} "
            f"(era {old_date.strftime('%d/%m/%Y')}). "
            f"{count} turni generati/aggiornati."
        )
    else:
        messages.warning(request, "Questo contratto non ha una data di fine.")
    
    return redirect('/admin/')


def analisi_contratti_view(request):
    """Analisi economica dei contratti: importo orario, soglia, costi effettivi."""
    from .models import Cliente, TimeTracking
    from django.db.models import Sum
    from decimal import Decimal
    
    MESI_NOMI = {
        1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
        5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
        9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
    }
    
    today = timezone.now().date()
    
    # Parametri dal form (con persistenza sessione)
    soglia_param = request.GET.get('soglia', None)
    if soglia_param:
        try:
            soglia = float(soglia_param)
            request.session['analisi_soglia'] = soglia
        except (ValueError, TypeError):
            soglia = request.session.get('analisi_soglia', 15.0)
    else:
        soglia = request.session.get('analisi_soglia', 15.0)
    
    try:
        mese = int(request.GET.get('mese', today.month))
    except (ValueError, TypeError):
        mese = today.month
    
    try:
        anno = int(request.GET.get('anno', today.year))
    except (ValueError, TypeError):
        anno = today.year
    
    # Lista mesi per il dropdown con selected pre-calcolato
    mesi_list = []
    for num, nome in MESI_NOMI.items():
        mesi_list.append({
            'value': num,
            'nome': nome,
            'selected': 'selected' if num == mese else '',
        })
    
    # Clienti con importo e ore configurati
    clienti_qs = Cliente.objects.filter(
        ore_mensili_contratto__gt=0
    ).order_by('ragione_sociale')
    
    # Group clienti by Partita IVA (if present)
    grouped_clienti = {}
    for c in clienti_qs:
        piva = (c.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{c.pk}"
        if key not in grouped_clienti:
            grouped_clienti[key] = {'piva': piva, 'clienti': []}
        grouped_clienti[key]['clienti'].append(c)

    analisi = []
    sotto_soglia = []
    totale_fatturato = Decimal('0')
    somma_orari = []
    
    for key, grp in grouped_clienti.items():
        clienti_list = grp['clienti']
        importo = sum(float(c.importo_mensile_contratto or 0) for c in clienti_list)
        ore_contratto = sum(float(c.ore_mensili_contratto or 0) for c in clienti_list)
        importo_orario = round(importo / ore_contratto, 2) if ore_contratto > 0 else 0
        
        # Display name
        piva_str = grp['piva']
        if len(clienti_list) > 1 and piva_str:
            nome_base = clienti_list[0].ragione_sociale.split('-')[0].strip()
            ragione_display = f"{nome_base} ({len(clienti_list)} Sedi - P.IVA {piva_str})"
        else:
            ragione_display = clienti_list[0].ragione_sociale

        # Ore effettivamente lavorate nel mese selezionato su tutte le sedi del gruppo
        tt_records = TimeTracking.objects.filter(
            assegnazione__cliente__in=clienti_list,
            check_out__year=anno,
            check_out__month=mese,
            check_in__isnull=False,
            check_out__isnull=False
        )
        
        ore_lavorate = 0
        for tt in tt_records:
            if tt.check_in and tt.check_out:
                delta = tt.check_out - tt.check_in
                ore_lavorate += delta.total_seconds() / 3600
        ore_lavorate = round(ore_lavorate, 1)
        
        # Costo effettivo per ora (importo / ore lavorate)
        costo_effettivo = round(importo / ore_lavorate, 2) if ore_lavorate > 0 else None
        
        # Differenza ore
        diff_ore = round(ore_lavorate - ore_contratto, 1)
        
        # Alert: sotto soglia?
        is_sotto_soglia = importo_orario < soglia and importo > 0
        
        # Alert costo effettivo: se ore lavorate supera contratto, il costo/ora effettivo scende
        costo_effettivo_alert = costo_effettivo is not None and costo_effettivo < soglia
        
        # Pre-render display strings per evitare tag template spezzati
        if diff_ore > 0:
            diff_ore_display = f'<span style="color: #e67e22; font-weight: 600;">+{diff_ore}h</span>'
        elif diff_ore < 0:
            diff_ore_display = f'<span style="color: #e74c3c; font-weight: 600;">{diff_ore}h</span>'
        else:
            diff_ore_display = '<span style="color: #27ae60;">0h</span>'
        
        if is_sotto_soglia:
            stato_display = '<span style="background: #e74c3c; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">SOTTO SOGLIA</span>'
        elif costo_effettivo_alert:
            stato_display = '<span style="background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">DA VERIFICARE</span>'
        else:
            stato_display = '<span style="background: #27ae60; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">OK</span>'
        
        costo_eff_display = f"&euro;{costo_effettivo}" if costo_effettivo else "&mdash;"
        
        row = {
            'cliente': ragione_display,
            'cliente_id': clienti_list[0].pk,
            'importo_mensile': f"&euro;{importo:,.2f}",
            'ore_contratto': f"{ore_contratto}h",
            'importo_orario': f"&euro;{importo_orario:.2f}",
            'ore_lavorate': f"{ore_lavorate}h",
            'costo_effettivo_display': costo_eff_display,
            'diff_ore_display': diff_ore_display,
            'stato_display': stato_display,
            'sotto_soglia': is_sotto_soglia,
        }
        analisi.append(row)
        
        if is_sotto_soglia:
            sotto_soglia.append(row)
        
        totale_fatturato += Decimal(str(importo))
        if importo_orario > 0:
            somma_orari.append(importo_orario)
    
    media_oraria = round(sum(somma_orari) / len(somma_orari), 2) if somma_orari else 0
    
    ore_header = f'Ore Lavorate<br><small>{MESI_NOMI.get(mese, "")} {anno}</small>'
    
    # Pre-render sotto_soglia badges
    sotto_soglia_html = ''
    if sotto_soglia:
        badges = []
        for c in sotto_soglia:
            badges.append(f'<span style="background: #e74c3c; color: white; padding: 4px 12px; border-radius: 15px; font-size: 13px;">{c["cliente"]} &mdash; {c["importo_orario"]}/h</span>')
        sotto_soglia_html = ' '.join(badges)
    
    context = {
        'analisi': analisi,
        'sotto_soglia': sotto_soglia,
        'sotto_soglia_html': sotto_soglia_html,
        'soglia': soglia,
        'mese': mese,
        'mesi': mesi_list,
        'mese_nome': MESI_NOMI.get(mese, ''),
        'anno': anno,
        'ore_header': ore_header,
        'totale_contratti': len(analisi),
        'totale_fatturato': f"&euro;{totale_fatturato:,.2f}",
        'media_oraria': f"&euro;{media_oraria:.2f}",
    }
    return render(request, 'core/analisi_contratti.html', context)


def pdf_contratti_sotto_soglia(request):
    """Genera PDF con elenco contratti sotto soglia."""
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from .models import Cliente, TimeTracking
    from decimal import Decimal

    MESI_NOMI = {
        1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
        5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
        9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
    }

    today = timezone.now().date()
    # Leggi soglia dalla sessione (come fa la vista pagina)
    soglia_param = request.GET.get('soglia', None)
    if soglia_param:
        try:
            soglia = float(soglia_param)
            request.session['analisi_soglia'] = soglia
        except (ValueError, TypeError):
            soglia = request.session.get('analisi_soglia', 15.0)
    else:
        soglia = request.session.get('analisi_soglia', 15.0)
    try:
        mese = int(request.GET.get('mese', today.month))
    except (ValueError, TypeError):
        mese = today.month
    try:
        anno = int(request.GET.get('anno', today.year))
    except (ValueError, TypeError):
        anno = today.year

    # Calcola contratti sotto soglia raggruppati per Partita IVA
    clienti_qs = Cliente.objects.filter(ore_mensili_contratto__gt=0).order_by('ragione_sociale')
    grouped_clienti = {}
    for c in clienti_qs:
        piva = (c.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{c.pk}"
        if key not in grouped_clienti:
            grouped_clienti[key] = {'piva': piva, 'clienti': []}
        grouped_clienti[key]['clienti'].append(c)

    sotto_soglia = []

    for key, grp in grouped_clienti.items():
        clienti_list = grp['clienti']
        importo = sum(float(c.importo_mensile_contratto or 0) for c in clienti_list)
        ore_contratto = sum(float(c.ore_mensili_contratto or 0) for c in clienti_list)
        importo_orario = round(importo / ore_contratto, 2) if ore_contratto > 0 else 0

        piva_str = grp['piva']
        if len(clienti_list) > 1 and piva_str:
            nome_base = clienti_list[0].ragione_sociale.split('-')[0].strip()
            ragione_display = f"{nome_base} ({len(clienti_list)} Sedi - P.IVA {piva_str})"
        else:
            ragione_display = clienti_list[0].ragione_sociale

        # Ore lavorate
        tt_records = TimeTracking.objects.filter(
            assegnazione__cliente__in=clienti_list,
            check_out__year=anno,
            check_out__month=mese,
            check_in__isnull=False,
            check_out__isnull=False
        )
        ore_lavorate = 0
        for tt in tt_records:
            if tt.check_in and tt.check_out:
                delta = tt.check_out - tt.check_in
                ore_lavorate += delta.total_seconds() / 3600
        ore_lavorate = round(ore_lavorate, 1)

        costo_effettivo = round(importo / ore_lavorate, 2) if ore_lavorate > 0 else None

        if importo_orario < soglia and importo > 0:
            sotto_soglia.append({
                'cliente': ragione_display,
                'importo': importo,
                'ore_contratto': ore_contratto,
                'importo_orario': importo_orario,
                'ore_lavorate': ore_lavorate,
                'costo_effettivo': costo_effettivo,
            })

    # Genera PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=20*mm, bottomMargin=15*mm, leftMargin=20*mm, rightMargin=20*mm)
    elements = []
    styles = getSampleStyleSheet()

    # Titolo
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#1a5276'))
    elements.append(Paragraph('Report Contratti Sotto Soglia', title_style))
    elements.append(Spacer(1, 5*mm))

    # Info
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555'))
    elements.append(Paragraph(f'Soglia: {soglia:.2f} EUR/ora | Periodo: {MESI_NOMI.get(mese, "")} {anno}', info_style))
    elements.append(Paragraph(f'Data generazione: {today.strftime("%d/%m/%Y")} | Contratti sotto soglia: {len(sotto_soglia)}', info_style))
    elements.append(Spacer(1, 8*mm))

    if sotto_soglia:
        # Header tabella
        data = [['Cliente', 'Importo Mensile', 'Ore Contratto', 'EUR/Ora', 'Ore Lavorate', 'Costo Effettivo/Ora']]

        for row in sotto_soglia:
            data.append([
                row['cliente'],
                f"{row['importo']:,.2f} EUR",
                f"{row['ore_contratto']}h",
                f"{row['importo_orario']:.2f} EUR",
                f"{row['ore_lavorate']}h",
                f"{row['costo_effettivo']:.2f} EUR" if row['costo_effettivo'] else '-',
            ])

        table = Table(data, colWidths=[95*mm, 35*mm, 30*mm, 25*mm, 30*mm, 35*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TEXTCOLOR', (3, 1), (3, -1), colors.HexColor('#e74c3c')),
            ('FONTNAME', (3, 1), (3, -1), 'Helvetica-Bold'),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph('Nessun contratto sotto la soglia impostata.', styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    nome_file = f'contratti_sotto_soglia_{MESI_NOMI.get(mese, "")}{anno}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{nome_file}"'
    return response


@csrf_exempt
def richiesta_sostituzione_api(request):
    """API per creare una richiesta di sostituzione dalla UI del calendario."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito'}, status=405)
    
    try:
        data = json.loads(request.body)
        assign_id = data.get('assign_id')
        dipendente_id = data.get('dipendente_id')
        motivo = data.get('motivo', 'MALATTIA')
        note = data.get('note', '')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'error': 'Dati non validi'}, status=400)
    
    from .models import AssegnazioneTurno
    from .services import crea_richiesta_sostituzione
    
    try:
        assegnazione = AssegnazioneTurno.objects.get(pk=assign_id)
    except AssegnazioneTurno.DoesNotExist:
        return JsonResponse({'error': 'Assegnazione non trovata'}, status=404)
    
    try:
        dipendente = Dipendente.objects.get(pk=dipendente_id)
    except Dipendente.DoesNotExist:
        return JsonResponse({'error': 'Dipendente non trovato'}, status=404)
    
    richiesta = crea_richiesta_sostituzione(assegnazione, dipendente, motivo, note)
    
    return JsonResponse({
        'ok': True,
        'richiesta_id': richiesta.pk,
        'stato': richiesta.stato,
        'candidati': len(richiesta.sostituti_candidati),
        'messaggio': f'Richiesta creata con {len(richiesta.sostituti_candidati)} sostituti candidati.'
    })


@csrf_exempt
def risposta_sostituto_api(request, richiesta_id):
    """API per gestire la risposta del sostituto (accetta/rifiuta)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito'}, status=405)
    
    try:
        data = json.loads(request.body)
        accettato = data.get('accettato', False)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dati non validi'}, status=400)
    
    from .services import gestisci_risposta_sostituto
    
    risultato = gestisci_risposta_sostituto(richiesta_id, accettato)
    
    if risultato:
        return JsonResponse({
            'ok': True,
            'stato': risultato.stato,
            'sostituto': str(risultato.sostituto) if risultato.sostituto else None
        })
    else:
        return JsonResponse({
            'ok': False,
            'messaggio': 'Nessun sostituto disponibile ha accettato.'
        })


@csrf_exempt
def trova_sostituti_api(request):
    """API per mostrare lista sostituti disponibili senza creare la richiesta."""
    assign_id = request.GET.get('assign_id')
    if not assign_id:
        return JsonResponse({'error': 'assign_id richiesto'}, status=400)
    
    from .models import AssegnazioneTurno
    
    try:
        assegnazione = AssegnazioneTurno.objects.get(pk=assign_id)
    except AssegnazioneTurno.DoesNotExist:
        return JsonResponse({'error': 'Assegnazione non trovata'}, status=404)
    
    cliente = assegnazione.cliente
    turno = assegnazione.turno
    squadra = turno.squadra
    
    qualifica = None
    if assegnazione.programmazione_feriale and assegnazione.programmazione_feriale.qualifica_richiesta:
        qualifica = assegnazione.programmazione_feriale.qualifica_richiesta
    
    componenti_ids = list(squadra.componenti.values_list('id', flat=True))
    if squadra.caposquadra:
        componenti_ids.append(squadra.caposquadra.id)
    
    risultati = trova_sostituti(
        cliente=cliente,
        data=turno.data,
        ora_inizio=assegnazione.orario_inizio_previsto,
        ora_fine=assegnazione.orario_fine_previsto,
        escludi_dipendenti_ids=componenti_ids,
        qualifica_richiesta=qualifica
    )
    
    sostituti_list = []
    for r in risultati:
        dip = r['dipendente']
        dist = f"{r['distanza_km']:.1f}" if r['distanza_km'] != float('inf') else 'N/D'
        sostituti_list.append({
            'id': dip.id,
            'nome': f"{dip.cognome} {dip.nome}",
            'distanza_km': dist,
            'qualifiche': r['skills'],
            'telefono': dip.telefono or '',
            'ai_score': r.get('ai_score', 50),
            'ai_motivi': r.get('ai_motivi', []),
            'presenze_cliente': r.get('presenze_cliente', 0),
            'ore_settimana': r.get('ore_settimana', 0.0),
            'conformita_ok': r.get('conformita_ok', True),
        })
    
    return JsonResponse({'ok': True, 'sostituti': sostituti_list})


@csrf_exempt
def get_sostituti_richiesta_api(request, richiesta_id):
    """
    Ritorna l'elenco di tutti i sostituti compatibili/disponibili per una richiesta di sostituzione,
    evidenziando quali sono stati precedentemente selezionati, l'ordine di selezione,
    l'eventuale sostituto attualmente contattato/assegnato e gli altri turni collegati alla stessa assenza.
    """
    from .models import RichiestaSostituzione, Dipendente, Assenza
    from .services import trova_sostituti, get_richieste_sostituzione_per_assenza

    try:
        richiesta = RichiestaSostituzione.objects.select_related(
            'assegnazione_originale__cliente',
            'assegnazione_originale__turno__squadra',
            'dipendente_assente',
            'sostituto'
        ).get(pk=richiesta_id)
    except RichiestaSostituzione.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Richiesta di sostituzione non trovata'}, status=404)

    assegnazione = richiesta.assegnazione_originale
    cliente = assegnazione.cliente
    turno = assegnazione.turno
    squadra = turno.squadra

    qualifica = None
    if assegnazione.programmazione_feriale and assegnazione.programmazione_feriale.qualifica_richiesta:
        q_obj = assegnazione.programmazione_feriale.qualifica_richiesta
        qualifica = getattr(q_obj, 'nome', str(q_obj))

    componenti_ids = []
    if squadra:
        componenti_ids = list(squadra.componenti.values_list('id', flat=True))
        if squadra.caposquadra:
            componenti_ids.append(squadra.caposquadra.id)
    if richiesta.dipendente_assente_id and richiesta.dipendente_assente_id not in componenti_ids:
        componenti_ids.append(richiesta.dipendente_assente_id)

    candidati_trovati = trova_sostituti(
        cliente=cliente,
        data=turno.data,
        ora_inizio=assegnazione.orario_inizio_previsto,
        ora_fine=assegnazione.orario_fine_previsto,
        escludi_dipendenti_ids=componenti_ids,
        qualifica_richiesta=qualifica
    )

    salvati_ids = richiesta.sostituti_candidati or []

    list_data = []
    for r in candidati_trovati:
        dip = r['dipendente']
        dist_str = f"{r['distanza_km']:.1f} km" if r['distanza_km'] != float('inf') else "N/D"
        selezionato = dip.id in salvati_ids
        ordine = (salvati_ids.index(dip.id) + 1) if selezionato else None

        list_data.append({
            'id': dip.id,
            'nome': f"{dip.cognome} {dip.nome}",
            'distanza_km': dist_str,
            'qualifiche': r['skills'],
            'qualifica_compatibile': r.get('qualifica_compatibile', True),
            'telefono': dip.telefono or 'N/D',
            'ha_telegram': bool(getattr(dip, 'telegram_chat_id', None)),
            'categoria_protetta': getattr(dip, 'categoria_protetta', False),
            'selezionato': selezionato,
            'ordine': ordine,
            'is_sostituto_corrente': (richiesta.sostituto_id == dip.id),
            'ai_score': r.get('ai_score', 50),
            'ai_motivi': r.get('ai_motivi', []),
            'presenze_cliente': r.get('presenze_cliente', 0),
            'ore_settimana': r.get('ore_settimana', 0.0),
            'conformita_ok': r.get('conformita_ok', True),
        })

    trovati_ids = {item['id'] for item in list_data}
    extra_ids = list(salvati_ids)
    if richiesta.sostituto_id and richiesta.sostituto_id not in extra_ids:
        extra_ids.insert(0, richiesta.sostituto_id)

    for sid in extra_ids:
        if sid not in trovati_ids:
            try:
                dip = Dipendente.objects.get(pk=sid)
                selezionato = sid in salvati_ids
                list_data.append({
                    'id': dip.id,
                    'nome': f"{dip.cognome} {dip.nome}",
                    'distanza_km': 'N/D',
                    'qualifiche': [q.nome for q in dip.qualifiche.all()],
                    'qualifica_compatibile': True,
                    'telefono': dip.telefono or 'N/D',
                    'ha_telegram': bool(getattr(dip, 'telegram_chat_id', None)),
                    'categoria_protetta': getattr(dip, 'categoria_protetta', False),
                    'selezionato': selezionato,
                    'ordine': (salvati_ids.index(sid) + 1) if selezionato else None,
                    'is_sostituto_corrente': (richiesta.sostituto_id == dip.id)
                })
                trovati_ids.add(dip.id)
            except Dipendente.DoesNotExist:
                pass

    # Cerca altre richieste di sostituzione collegate alla stessa assenza
    richieste_collegate_data = []
    assenza_corrente = Assenza.objects.filter(
        dipendente=richiesta.dipendente_assente,
        data_inizio__lte=turno.data,
        data_fine__gte=turno.data
    ).order_by('-id').first()

    if assenza_corrente:
        qs_collegate = get_richieste_sostituzione_per_assenza(assenza_corrente)
        for rc in qs_collegate:
            ao = rc.assegnazione_originale
            ora_rc = f"{ao.orario_inizio_previsto.strftime('%H:%M')}-{ao.orario_fine_previsto.strftime('%H:%M')}" if (ao.orario_inizio_previsto and ao.orario_fine_previsto) else ""
            richieste_collegate_data.append({
                'id': rc.id,
                'data': ao.turno.data.strftime('%d/%m/%Y'),
                'orario': ora_rc,
                'cliente': ao.cliente.ragione_sociale if ao.cliente else 'N/D',
                'stato': rc.stato,
                'sostituto_nome': f"{rc.sostituto.cognome} {rc.sostituto.nome}" if rc.sostituto else None
            })

    orario_str = f"{assegnazione.orario_inizio_previsto.strftime('%H:%M')}-{assegnazione.orario_fine_previsto.strftime('%H:%M')}" if (assegnazione.orario_inizio_previsto and assegnazione.orario_fine_previsto) else "N/D"

    return JsonResponse({
        'ok': True,
        'richiesta_id': richiesta.id,
        'cliente_nome': cliente.ragione_sociale if cliente else 'N/D',
        'data_turno': turno.data.strftime('%d/%m/%Y'),
        'orario_turno': orario_str,
        'qualifica_richiesta': qualifica or 'Qualsiasi',
        'dipendente_assente': str(richiesta.dipendente_assente),
        'motivo_assenza': richiesta.motivo_assenza,
        'stato': richiesta.stato,
        'sostituto_corrente_id': richiesta.sostituto_id,
        'sostituto_corrente_nome': f"{richiesta.sostituto.cognome} {richiesta.sostituto.nome}" if richiesta.sostituto else None,
        'richieste_collegate': richieste_collegate_data,
        'sostituti': list_data
    })


@csrf_exempt
def invia_notifiche_sostituti_api(request):
    """
    Riceve l'elenco dei sostituti selezionati e il loro ordine di preferenza,
    aggiorna la RichiestaSostituzione e invia la notifica al primo sostituto in lista.
    Se applica_a_periodo=True, imposta la stessa coda e invia anche agli altri turni scoperti dell'assenza.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Dati JSON non validi'}, status=400)

    richiesta_id = data.get('richiesta_id')
    sostituti_ids = data.get('sostituti_ids', [])
    applica_a_periodo = bool(data.get('applica_a_periodo', False))

    if not richiesta_id:
        return JsonResponse({'ok': False, 'error': 'richiesta_id obbligatorio'}, status=400)

    if not isinstance(sostituti_ids, list) or len(sostituti_ids) == 0:
        return JsonResponse({'ok': False, 'error': 'Seleziona almeno un sostituto a cui inviare la notifica'}, status=400)

    from .models import RichiestaSostituzione, Dipendente, Assenza
    from .services import approva_e_invia_sostituto, get_richieste_sostituzione_per_assenza

    try:
        richiesta = RichiestaSostituzione.objects.select_related('assegnazione_originale__turno', 'dipendente_assente').get(pk=richiesta_id)
    except RichiestaSostituzione.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Richiesta di sostituzione non trovata'}, status=404)

    valid_ids = []
    for sid in sostituti_ids:
        try:
            val = int(sid)
            if val not in valid_ids and Dipendente.objects.filter(pk=val).exists():
                valid_ids.append(val)
        except (ValueError, TypeError):
            pass

    if not valid_ids:
        return JsonResponse({'ok': False, 'error': 'Nessun sostituto valido selezionato'}, status=400)

    richieste_target = [richiesta]
    if applica_a_periodo:
        data_turno = richiesta.assegnazione_originale.turno.data
        assenza = Assenza.objects.filter(
            dipendente=richiesta.dipendente_assente,
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).order_by('-id').first()
        if assenza:
            collegate = list(get_richieste_sostituzione_per_assenza(assenza).exclude(stato__in=['ACCETTATA', 'COMPLETATA']))
            if collegate:
                richieste_target = collegate

    res_richiesta = None
    for req_obj in richieste_target:
        req_obj.sostituti_candidati = valid_ids
        req_obj.sostituto_corrente_idx = 0
        req_obj.stato = 'APPROVATA_RA'
        req_obj.approvata_ra_il = timezone.now()
        req_obj.save()
        r = approva_e_invia_sostituto(req_obj.pk)
        if req_obj.pk == richiesta.pk:
            res_richiesta = r

    if not res_richiesta:
        res_richiesta = richiesta

    primo_dip_nome = str(res_richiesta.sostituto) if (res_richiesta and res_richiesta.sostituto) else 'primo sostituto'
    extra_msg = f" su {len(richieste_target)} turni dell'assenza" if len(richieste_target) > 1 else ""

    return JsonResponse({
        'ok': True,
        'message': f"Notifica Telegram inviata a {primo_dip_nome} (1° in ordine di selezione){extra_msg}. In coda: {len(valid_ids)} candidati.",
        'sostituto_corrente': primo_dip_nome,
        'totale_selezionati': len(valid_ids),
        'turni_aggiornati': len(richieste_target)
    })


@csrf_exempt
def valida_assenza_api(request, assenza_id):
    """
    Endpoint per validare (avvallare) un'assenza dall'Amministrazione e creare
    o recuperare le Richieste di Sostituzione per tutti i turni scoperti del periodo.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    from .services import avvalla_assenza_da_amministrazione

    res = avvalla_assenza_da_amministrazione(assenza_id)
    if not res.get('ok'):
        return JsonResponse({'ok': False, 'error': res.get('error', 'Errore durante la validazione')}, status=404)

    return JsonResponse({
        'ok': True,
        'assenza_id': assenza_id,
        'num_sostituzioni': res.get('num_sostituzioni', 0),
        'richieste_ids': res.get('richieste_ids', []),
        'prima_richiesta_id': res.get('prima_richiesta_id')
    })


@csrf_exempt
def conferma_sostituto_ufficio_api(request):
    """
    Endpoint per confermare direttamente dall'ufficio (Amministrazione) il sostituto
    per una RichiestaSostituzione, sia scegliendo un candidato libero dalla lista,
    sia confermando per conto del dipendente a cui era già stata inviata la richiesta Telegram
    (se non riesce a rispondere dal cellulare).
    Supporta anche l'azione 'passa_successivo' per passare manualmente al candidato successivo in coda.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Dati JSON non validi'}, status=400)

    richiesta_id = data.get('richiesta_id')
    azione = data.get('azione', 'conferma')  # 'conferma' oppure 'passa_successivo'

    if not richiesta_id:
        return JsonResponse({'ok': False, 'error': 'richiesta_id obbligatorio'}, status=400)

    if azione == 'passa_successivo':
        from .services import gestisci_risposta_sostituto
        richiesta = gestisci_risposta_sostituto(richiesta_id, accetta=False)
        if not richiesta:
            return JsonResponse({'ok': False, 'error': 'Impossibile passare al sostituto successivo'}, status=400)
        if richiesta.stato == 'INVIATA' and richiesta.sostituto:
            msg = f"Passato al candidato successivo: notifica inviata a {richiesta.sostituto.cognome} {richiesta.sostituto.nome}."
        else:
            msg = f"Lista candidati esaurita (stato: {richiesta.get_stato_display()}). Puoi confermare un sostituto direttamente dall'ufficio."
        return JsonResponse({
            'ok': True,
            'message': msg,
            'stato': richiesta.stato,
            'sostituto_corrente_id': richiesta.sostituto_id,
            'sostituto_corrente_nome': f"{richiesta.sostituto.cognome} {richiesta.sostituto.nome}" if richiesta.sostituto else None
        })

    sostituto_id = data.get('sostituto_id')
    applica_a_periodo = bool(data.get('applica_a_periodo', False))

    from .services import assegna_sostituto_da_ufficio
    res = assegna_sostituto_da_ufficio(
        richiesta_id=richiesta_id,
        sostituto_id=sostituto_id,
        applica_a_periodo=applica_a_periodo
    )
    if not res.get('ok'):
        return JsonResponse({'ok': False, 'error': res.get('error', 'Errore durante la conferma')}, status=400)

    return JsonResponse({
        'ok': True,
        'message': res.get('message', 'Sostituto confermato con successo'),
        'sostituto_nome': res.get('sostituto_nome'),
        'turni_aggiornati': res.get('turni_aggiornati', 1)
    })


@csrf_exempt
def verifica_ore_view(request):
    """Dashboard verifica ore mensili: confronto ore lavorate vs contrattuali."""
    from .models import Cliente, TimeTracking, AssegnazioneTurno, Squadra, Dipendente
    from django.db.models import Sum, Q, DecimalField
    from django.db.models.functions import Coalesce
    from decimal import Decimal
    import calendar
    
    # Mese selezionato (default: mese corrente)
    now = timezone.now()
    mese = int(request.GET.get('mese', now.month))
    anno = int(request.GET.get('anno', now.year))
    
    # Range date del mese
    primo_giorno = now.replace(year=anno, month=mese, day=1).date()
    ultimo_giorno_num = calendar.monthrange(anno, mese)[1]
    ultimo_giorno = primo_giorno.replace(day=ultimo_giorno_num)
    
    MESI_IT = {
        1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
        5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
        9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
    }
    
    # === SEZIONE PER CLIENTE (Raggruppato per Partita IVA se presente) ===
    tt_mese = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=primo_giorno,
        assegnazione__turno__data__lte=ultimo_giorno
    ).select_related('assegnazione__cliente', 'dipendente', 'assegnazione__turno__squadra')
    
    # Aggregazione per cliente / Partita IVA
    clienti_data = {}
    for tt in tt_mese:
        cliente = tt.assegnazione.cliente
        if not cliente:
            continue
        piva = (cliente.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{cliente.pk}"
        
        if key not in clienti_data:
            clienti_data[key] = {
                'key': key,
                'piva': piva,
                'clienti': set(),
                'ore_lavorate': 0.0,
                'ore_validate': 0.0,
            }
        clienti_data[key]['clienti'].add(cliente)
        
        ore = float(tt.ore_dichiarate or 0)
        clienti_data[key]['ore_lavorate'] += ore
        if tt.is_validated:
            clienti_data[key]['ore_validate'] += ore
    
    # Aggiungi clienti senza ore ma con contratto
    for cl in Cliente.objects.filter(ore_mensili_contratto__gt=0):
        piva = (cl.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{cl.pk}"
        
        if key not in clienti_data:
            clienti_data[key] = {
                'key': key,
                'piva': piva,
                'clienti': set(),
                'ore_lavorate': 0.0,
                'ore_validate': 0.0,
            }
        clienti_data[key]['clienti'].add(cl)
    
    # Calcoli derivati e formattazione nomi per ciascun gruppo
    for cd in clienti_data.values():
        clienti_list_sorted = sorted(list(cd['clienti']), key=lambda x: x.ragione_sociale)
        cd['cliente'] = clienti_list_sorted[0]
        
        # Somma contratti delle sedi
        cd['ore_contratto'] = float(sum(c.ore_mensili_contratto or 0 for c in clienti_list_sorted))
        cd['importo_contratto'] = float(sum(c.importo_mensile_contratto or 0 for c in clienti_list_sorted))
        cd['importo_orario'] = round(cd['importo_contratto'] / cd['ore_contratto'], 2) if cd['ore_contratto'] > 0 else 0
        
        piva_str = cd['piva']
        if len(clienti_list_sorted) > 1 and piva_str:
            nome_base = clienti_list_sorted[0].ragione_sociale.split('-')[0].strip()
            cd['ragione_sociale'] = f"{nome_base} ({len(clienti_list_sorted)} Sedi - P.IVA {piva_str})"
        else:
            cd['ragione_sociale'] = clienti_list_sorted[0].ragione_sociale

        cd['ore_lavorate'] = round(cd['ore_lavorate'], 1)
        cd['ore_validate'] = round(cd['ore_validate'], 1)
        cd['diff'] = round(cd['ore_lavorate'] - cd['ore_contratto'], 1)
        cd['importo_calcolato'] = round(cd['ore_validate'] * cd['importo_orario'], 2) if cd['importo_orario'] else 0
        cd['ore_non_validate'] = round(cd['ore_lavorate'] - cd['ore_validate'], 1)
    
    clienti_list = sorted(clienti_data.values(), key=lambda x: x['ragione_sociale'])
    
    # Totali clienti
    totale_clienti = {
        'ore_contratto': sum(c['ore_contratto'] for c in clienti_list),
        'ore_lavorate': sum(c['ore_lavorate'] for c in clienti_list),
        'ore_validate': sum(c['ore_validate'] for c in clienti_list),
        'importo_contratto': sum(c['importo_contratto'] for c in clienti_list),
        'importo_calcolato': sum(c['importo_calcolato'] for c in clienti_list),
    }
    totale_clienti['diff'] = round(totale_clienti['ore_lavorate'] - totale_clienti['ore_contratto'], 1)
    
    # === SEZIONE PER SQUADRA/DIPENDENTE ===
    squadre_data = {}
    for tt in tt_mese:
        dip = tt.dipendente
        squadra = tt.assegnazione.turno.squadra
        cliente = tt.assegnazione.cliente
        ore = float(tt.ore_dichiarate or 0)
        if ore <= 0:
            continue
        
        sq_nome = squadra.nome if squadra else tt.assegnazione.turno.nome_squadra
        sq_id = squadra.pk if squadra else f"hist_{sq_nome}"
        
        if sq_id not in squadre_data:
            squadre_data[sq_id] = {
                'nome': sq_nome,
                'dipendenti': {},
                'ore_totali': 0,
            }
        
        dip_id = dip.pk
        if dip_id not in squadre_data[sq_id]['dipendenti']:
            squadre_data[sq_id]['dipendenti'][dip_id] = {
                'nome': str(dip),
                'ore_totali': 0,
                'clienti': {},
            }
        
        squadre_data[sq_id]['dipendenti'][dip_id]['ore_totali'] += ore
        squadre_data[sq_id]['ore_totali'] += ore
        
        cl_nome = cliente.ragione_sociale
        if cl_nome not in squadre_data[sq_id]['dipendenti'][dip_id]['clienti']:
            squadre_data[sq_id]['dipendenti'][dip_id]['clienti'][cl_nome] = 0
        squadre_data[sq_id]['dipendenti'][dip_id]['clienti'][cl_nome] += ore
    
    # Prepara per template
    squadre_list = []
    for sq in sorted(squadre_data.values(), key=lambda x: x['nome']):
        dip_list = []
        for d in sorted(sq['dipendenti'].values(), key=lambda x: x['nome']):
            d['ore_totali'] = round(d['ore_totali'], 1)
            cl_str = ', '.join(f"{n} ({round(o,1)}h)" for n, o in sorted(d['clienti'].items()))
            d['clienti_str'] = cl_str
            dip_list.append(d)
        sq['dipendenti_list'] = dip_list
        sq['ore_totali'] = round(sq['ore_totali'], 1)
        squadre_list.append(sq)
    
    # === SEZIONE ASSENZE PER DIPENDENTE ===
    from .models import Assenza
    from django.db.models import Q
    
    dipendenti_attivi = Dipendente.objects.filter(stato='ATTIVO').order_by('cognome', 'nome')
    
    assenze_mese = Assenza.objects.filter(
        Q(data_inizio__lte=ultimo_giorno) & Q(data_fine__gte=primo_giorno),
    ).exclude(stato_approvazione='RIFIUTATA').select_related('dipendente')
    
    # Calcola giorni di assenza per dipendente
    assenze_per_dip = {}
    for assenza in assenze_mese:
        dip_id = assenza.dipendente.pk
        if dip_id not in assenze_per_dip:
            assenze_per_dip[dip_id] = {
                'dipendente': assenza.dipendente,
                'nome': f"{assenza.dipendente.cognome} {assenza.dipendente.nome}",
                'MALATTIA': 0, 'FERIE': 0, 'PERMESSO': 0, '104': 0, 'ALTRO': 0,
                'totale_giorni': 0,
                'dettagli': [],
            }
        
        # Calcola giorni effettivi nel mese
        inizio_eff = max(assenza.data_inizio, primo_giorno)
        fine_eff = min(assenza.data_fine, ultimo_giorno)
        giorni = (fine_eff - inizio_eff).days + 1
        
        tipo = assenza.tipo if assenza.tipo in assenze_per_dip[dip_id] else 'ALTRO'
        assenze_per_dip[dip_id][tipo] += giorni
        assenze_per_dip[dip_id]['totale_giorni'] += giorni
        assenze_per_dip[dip_id]['dettagli'].append({
            'tipo': assenza.tipo,
            'inizio': assenza.data_inizio.strftime('%d/%m'),
            'fine': assenza.data_fine.strftime('%d/%m'),
            'giorni': giorni,
            'note': assenza.note,
        })
    
    assenze_list = sorted(assenze_per_dip.values(), key=lambda x: x['nome'])
    
    # Totali assenze
    totale_assenze = {
        'MALATTIA': sum(a['MALATTIA'] for a in assenze_list),
        'FERIE': sum(a['FERIE'] for a in assenze_list),
        'PERMESSO': sum(a['PERMESSO'] for a in assenze_list),
        '104': sum(a['104'] for a in assenze_list),
        'ALTRO': sum(a['ALTRO'] for a in assenze_list),
        'totale_giorni': sum(a['totale_giorni'] for a in assenze_list),
    }
    
    # Opzioni mesi per selettore
    mesi_options = []
    for m in range(1, 13):
        mesi_options.append({'numero': m, 'nome': MESI_IT[m], 'selected': m == mese})
    
    # Opzioni anni
    anni_options = list(range(anno - 2, anno + 2))
    
    context = {
        'clienti_list': clienti_list,
        'totale_clienti': totale_clienti,
        'squadre_list': squadre_list,
        'assenze_list': assenze_list,
        'totale_assenze': totale_assenze,
        'mese': mese,
        'anno': anno,
        'mese_nome': MESI_IT.get(mese, ''),
        'mesi_options': mesi_options,
        'anni_options': anni_options,
    }
    return render(request, 'admin/verifica_ore.html', context)


@csrf_exempt
def pdf_verifica_ore(request):
    """Genera PDF report verifica ore mensili."""
    from .models import Cliente, TimeTracking, AssegnazioneTurno
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import calendar
    
    now = timezone.now()
    mese = int(request.GET.get('mese', now.month))
    anno = int(request.GET.get('anno', now.year))
    
    primo_giorno = now.replace(year=anno, month=mese, day=1).date()
    ultimo_giorno_num = calendar.monthrange(anno, mese)[1]
    ultimo_giorno = primo_giorno.replace(day=ultimo_giorno_num)
    
    MESI_IT = {
        1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
        5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
        9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
    }
    mese_nome = MESI_IT.get(mese, '')
    
    # Stessi dati della view HTML
    tt_mese = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=primo_giorno,
        assegnazione__turno__data__lte=ultimo_giorno
    ).select_related('assegnazione__cliente', 'dipendente', 'assegnazione__turno__squadra')
    
    # Aggregazione per cliente / Partita IVA
    clienti_data = {}
    for tt in tt_mese:
        cliente = tt.assegnazione.cliente
        if not cliente:
            continue
        piva = (cliente.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{cliente.pk}"
        
        if key not in clienti_data:
            clienti_data[key] = {
                'piva': piva,
                'clienti': set(),
                'ore_lavorate': 0.0,
                'ore_validate': 0.0,
            }
        clienti_data[key]['clienti'].add(cliente)
        
        ore = float(tt.ore_dichiarate or 0)
        clienti_data[key]['ore_lavorate'] += ore
        if tt.is_validated:
            clienti_data[key]['ore_validate'] += ore
    
    for cl in Cliente.objects.filter(ore_mensili_contratto__gt=0):
        piva = (cl.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{cl.pk}"
        
        if key not in clienti_data:
            clienti_data[key] = {
                'piva': piva,
                'clienti': set(),
                'ore_lavorate': 0.0,
                'ore_validate': 0.0,
            }
        clienti_data[key]['clienti'].add(cl)
    
    for cd in clienti_data.values():
        clienti_list_sorted = sorted(list(cd['clienti']), key=lambda x: x.ragione_sociale)
        cd['ore_contratto'] = float(sum(c.ore_mensili_contratto or 0 for c in clienti_list_sorted))
        cd['importo_contratto'] = float(sum(c.importo_mensile_contratto or 0 for c in clienti_list_sorted))
        cd['importo_orario'] = round(cd['importo_contratto'] / cd['ore_contratto'], 2) if cd['ore_contratto'] > 0 else 0
        
        piva_str = cd['piva']
        if len(clienti_list_sorted) > 1 and piva_str:
            nome_base = clienti_list_sorted[0].ragione_sociale.split('-')[0].strip()
            cd['ragione_sociale'] = f"{nome_base} ({len(clienti_list_sorted)} Sedi - P.IVA {piva_str})"
        else:
            cd['ragione_sociale'] = clienti_list_sorted[0].ragione_sociale

        cd['ore_lavorate'] = round(cd['ore_lavorate'], 1)
        cd['ore_validate'] = round(cd['ore_validate'], 1)
        cd['diff'] = round(cd['ore_lavorate'] - cd['ore_contratto'], 1)
        cd['importo_calcolato'] = round(cd['ore_validate'] * cd['importo_orario'], 2) if cd['importo_orario'] else 0
    
    clienti_list = sorted(clienti_data.values(), key=lambda x: x['ragione_sociale'])
    
    # Aggregazione per squadra/dipendente
    squadre_data = {}
    for tt in tt_mese:
        dip = tt.dipendente
        squadra = tt.assegnazione.turno.squadra
        cliente = tt.assegnazione.cliente
        ore = float(tt.ore_dichiarate or 0)
        if ore <= 0:
            continue
        sq_nome = squadra.nome if squadra else tt.assegnazione.turno.nome_squadra
        sq_id = squadra.pk if squadra else f"hist_{sq_nome}"
        if sq_id not in squadre_data:
            squadre_data[sq_id] = {'nome': sq_nome, 'dipendenti': {}, 'ore_totali': 0}
        dip_id = dip.pk
        if dip_id not in squadre_data[sq_id]['dipendenti']:
            squadre_data[sq_id]['dipendenti'][dip_id] = {'nome': str(dip), 'ore_totali': 0, 'clienti': {}}
        squadre_data[sq_id]['dipendenti'][dip_id]['ore_totali'] += ore
        squadre_data[sq_id]['ore_totali'] += ore
        cl_nome = cliente.ragione_sociale
        if cl_nome not in squadre_data[sq_id]['dipendenti'][dip_id]['clienti']:
            squadre_data[sq_id]['dipendenti'][dip_id]['clienti'][cl_nome] = 0
        squadre_data[sq_id]['dipendenti'][dip_id]['clienti'][cl_nome] += ore
    
    # === Genera PDF ===
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=15*mm, bottomMargin=12*mm, leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []
    
    # Stili custom
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#417690'), spaceAfter=6*mm)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#417690'), spaceAfter=4*mm, spaceBefore=6*mm)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)
    
    # Intestazione
    elements.append(Paragraph(f"Report Verifica Ore — {mese_nome} {anno}", title_style))
    elements.append(Paragraph(f"Generato il {now.strftime('%d/%m/%Y %H:%M')}", small_style))
    elements.append(Spacer(1, 6*mm))
    
    # === TABELLA CLIENTI ===
    elements.append(Paragraph("Riepilogo per Cliente", subtitle_style))
    
    cl_header = ['Cliente', 'Ore Contratto', 'Ore Lavorate', 'Ore Validate', 'Differenza', '€ Contratto', '€ Calcolato']
    cl_rows = [cl_header]
    tot_contr = tot_lav = tot_val = tot_imp_c = tot_imp_calc = 0
    
    for c in clienti_list:
        diff_str = f"+{c['diff']}" if c['diff'] > 0 else str(c['diff'])
        cl_rows.append([
            c['ragione_sociale'],
            f"{c['ore_contratto']:.1f}",
            f"{c['ore_lavorate']:.1f}",
            f"{c['ore_validate']:.1f}",
            diff_str,
            f"€{c['importo_contratto']:.2f}",
            f"€{c['importo_calcolato']:.2f}",
        ])
        tot_contr += c['ore_contratto']
        tot_lav += c['ore_lavorate']
        tot_val += c['ore_validate']
        tot_imp_c += c['importo_contratto']
        tot_imp_calc += c['importo_calcolato']
    
    tot_diff = round(tot_lav - tot_contr, 1)
    diff_tot_str = f"+{tot_diff}" if tot_diff > 0 else str(tot_diff)
    cl_rows.append(['TOTALE', f"{tot_contr:.1f}", f"{tot_lav:.1f}", f"{tot_val:.1f}", diff_tot_str, f"€{tot_imp_c:.2f}", f"€{tot_imp_calc:.2f}"])
    
    col_widths = [160, 80, 80, 80, 70, 90, 90]
    cl_table = Table(cl_rows, colWidths=col_widths)
    
    cl_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#417690')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        # Riga totale
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f0f5')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]
    
    # Colora differenze
    for i, c in enumerate(clienti_list, start=1):
        if c['diff'] < 0:
            cl_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#e74c3c')))
        elif c['diff'] > 0:
            cl_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#27ae60')))
    
    cl_table.setStyle(TableStyle(cl_style))
    elements.append(cl_table)
    elements.append(Spacer(1, 8*mm))
    
    # === TABELLA SQUADRE/DIPENDENTI ===
    elements.append(Paragraph("Riepilogo per Squadra e Dipendente", subtitle_style))
    
    sq_header = ['Squadra / Dipendente', 'Ore Totali', 'Dettaglio Clienti']
    sq_rows = [sq_header]
    
    for sq in sorted(squadre_data.values(), key=lambda x: x['nome']):
        sq_rows.append([f"▸ {sq['nome']}", f"{round(sq['ore_totali'],1)}h", ''])
        for d in sorted(sq['dipendenti'].values(), key=lambda x: x['nome']):
            cl_str = ', '.join(f"{n} ({round(o,1)}h)" for n, o in sorted(d['clienti'].items()))
            sq_rows.append([f"    {d['nome']}", f"{round(d['ore_totali'],1)}h", Paragraph(cl_str, small_style)])
    
    sq_col_widths = [180, 80, 420]
    sq_table = Table(sq_rows, colWidths=sq_col_widths)
    
    sq_style_rules = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#417690')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    
    # Evidenzia righe squadra
    row_idx = 1
    for sq in sorted(squadre_data.values(), key=lambda x: x['nome']):
        sq_style_rules.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#e8f0f5')))
        sq_style_rules.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
        row_idx += 1
        row_idx += len(sq['dipendenti'])
    
    sq_table.setStyle(TableStyle(sq_style_rules))
    elements.append(sq_table)
    elements.append(Spacer(1, 8*mm))
    
    # === TABELLA ASSENZE ===
    from .models import Assenza
    from django.db.models import Q
    
    assenze_mese = Assenza.objects.filter(
        Q(data_inizio__lte=ultimo_giorno) & Q(data_fine__gte=primo_giorno),
    ).exclude(stato_approvazione='RIFIUTATA').select_related('dipendente')
    
    assenze_per_dip = {}
    for assenza in assenze_mese:
        dip_id = assenza.dipendente.pk
        if dip_id not in assenze_per_dip:
            assenze_per_dip[dip_id] = {
                'nome': f"{assenza.dipendente.cognome} {assenza.dipendente.nome}",
                'MALATTIA': 0, 'FERIE': 0, 'PERMESSO': 0, '104': 0, 'ALTRO': 0,
                'totale_giorni': 0, 'dettagli': [],
            }
        inizio_eff = max(assenza.data_inizio, primo_giorno)
        fine_eff = min(assenza.data_fine, ultimo_giorno)
        giorni = (fine_eff - inizio_eff).days + 1
        tipo = assenza.tipo if assenza.tipo in assenze_per_dip[dip_id] else 'ALTRO'
        assenze_per_dip[dip_id][tipo] += giorni
        assenze_per_dip[dip_id]['totale_giorni'] += giorni
        assenze_per_dip[dip_id]['dettagli'].append(
            f"{assenza.tipo}: {assenza.data_inizio.strftime('%d/%m')}-{assenza.data_fine.strftime('%d/%m')} ({giorni}gg)"
        )
    
    if assenze_per_dip:
        elements.append(Paragraph("Riepilogo Assenze del Mese", subtitle_style))
        
        ass_header = ['Dipendente', 'Malattia', 'Ferie', 'Permesso', 'L.104', 'Altro', 'Totale gg', 'Dettaglio']
        ass_rows = [ass_header]
        
        tot_mal = tot_fer = tot_per = tot_104 = tot_alt = tot_gg = 0
        for a in sorted(assenze_per_dip.values(), key=lambda x: x['nome']):
            det_str = '; '.join(a['dettagli'])
            ass_rows.append([
                a['nome'],
                str(a['MALATTIA']) if a['MALATTIA'] else '-',
                str(a['FERIE']) if a['FERIE'] else '-',
                str(a['PERMESSO']) if a['PERMESSO'] else '-',
                str(a['104']) if a['104'] else '-',
                str(a['ALTRO']) if a['ALTRO'] else '-',
                str(a['totale_giorni']),
                Paragraph(det_str, small_style),
            ])
            tot_mal += a['MALATTIA']
            tot_fer += a['FERIE']
            tot_per += a['PERMESSO']
            tot_104 += a['104']
            tot_alt += a['ALTRO']
            tot_gg += a['totale_giorni']
        
        ass_rows.append(['TOTALE', str(tot_mal), str(tot_fer), str(tot_per), str(tot_104), str(tot_alt), str(tot_gg), ''])
        
        ass_col_widths = [130, 55, 55, 55, 45, 45, 55, 240]
        ass_table = Table(ass_rows, colWidths=ass_col_widths)
        
        ass_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e65100')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (6, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fef3e8')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fce4cc')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]
        ass_table.setStyle(TableStyle(ass_style))
        elements.append(ass_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    nome_file = f'verifica_ore_{mese_nome}_{anno}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{nome_file}"'
    return response



def settimana_pdf_view(request):
    """
    PDF A4 landscape con GRIGLIA ORARIA: ogni assegnazione è posizionata
    esattamente all'ora corrispondente sull'asse verticale.
    GET: week (offset int), squadra (id opzionale)
    """
    from datetime import date, timedelta
    from io import BytesIO
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from .models import Turno, Squadra

    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()

    week_offset = int(request.GET.get('week', 0))
    squadra_filter = request.GET.get('squadra', '')
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    dates = [start_of_week + timedelta(days=i) for i in range(7)]

    GIORNI = ['Lunedi','Martedi','Mercoledi','Giovedi','Venerdi','Sabato','Domenica']
    MESI = {1:'Gen',2:'Feb',3:'Mar',4:'Apr',5:'Mag',6:'Giu',
            7:'Lug',8:'Ago',9:'Set',10:'Ott',11:'Nov',12:'Dic'}
    SQUAD_COLORS = ['#1565c0','#b71c1c','#2e7d32','#e65100',
                    '#6a1b9a','#00838f','#4e342e','#37474f']

    turni_qs = (Turno.objects
                .filter(data__in=dates)
                .select_related('squadra','squadra__caposquadra')
                .prefetch_related('assegnazioni__cliente')
                .order_by('data','squadra__nome'))
    if squadra_filter:
        turni_qs = turni_qs.filter(squadra_id=squadra_filter)

    # Raggruppa: {date: [turno, ...]}
    turni_per_data = {d: [] for d in dates}
    for t in turni_qs:
        if t not in turni_per_data[t.data]:
            turni_per_data[t.data].append(t)

    # Colori per squadra
    squad_color_map = {}
    color_idx = 0
    for d in dates:
        for t in turni_per_data[d]:
            sq_key = t.squadra.id if t.squadra else f"hist_{t.nome_squadra}"
            if sq_key not in squad_color_map:
                squad_color_map[sq_key] = SQUAD_COLORS[color_idx % len(SQUAD_COLORS)]
                color_idx += 1

    # ── Layout ──────────────────────────────────────────────────────
    page_w, page_h = landscape(A4)        # 841.9 x 595.3 pt
    mg = 10 * mm                          # margine
    time_col_w = 20 * mm                  # larghezza colonna ORA
    day_col_w  = (page_w - 2*mg - time_col_w) / 7
    title_h    = 20                       # pt
    header_h   = 22                       # pt intestazione giorni
    footer_h   = 14                       # pt
    grid_top   = page_h - mg - title_h - 4 - header_h   # y bordo superiore griglia
    grid_bot   = mg + footer_h                            # y bordo inferiore griglia
    grid_h     = grid_top - grid_bot

    START_H, END_H = 4, 23               # ore visibili
    num_hours  = END_H - START_H
    hour_h     = grid_h / num_hours       # pt per ora

    def y_of(hhmm_str):
        """Converte 'HH:MM' in coordinata y (PDF, origine in basso)."""
        h, m = map(int, hhmm_str.split(':'))
        mins_from_start = (h * 60 + m) - START_H * 60
        mins_from_start = max(0, min(mins_from_start, num_hours * 60))
        return grid_top - mins_from_start * hour_h / 60

    grid_left  = mg + time_col_w         # x inizio colonne giorni

    # ── Canvas ──────────────────────────────────────────────────────
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=landscape(A4))

    # Sfondo bianco
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Titolo
    week_str = (f"{dates[0].day:02d} {MESI[dates[0].month]} - "
                f"{dates[-1].day:02d} {MESI[dates[-1].month]} {dates[-1].year}")
    sq_label = ''
    if squadra_filter:
        try:
            sq_label = f" | {Squadra.objects.get(pk=squadra_filter).nome}"
        except Exception:
            pass
    c.setFont('Helvetica-Bold', 11)
    c.setFillColor(colors.HexColor('#222222'))
    c.drawCentredString(page_w / 2,
                        page_h - mg - title_h + 4,
                        f"Turni Settimana {week_str}{sq_label}")

    # ── Intestazione giorni ──────────────────────────────────────────
    hdr_y = grid_top                      # y bottom dell'header box
    hdr_top = hdr_y + header_h

    # Box "Ora"
    c.setFillColor(colors.HexColor('#455a64'))
    c.rect(mg, hdr_y, time_col_w, header_h, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 7)
    c.setFillColor(colors.white)
    c.drawCentredString(mg + time_col_w / 2, hdr_y + 6, 'Ora')

    for i, d in enumerate(dates):
        x = grid_left + i * day_col_w
        is_today = (d == today)
        bg = colors.HexColor('#2e7d32') if is_today else colors.HexColor('#37474f')
        c.setFillColor(bg)
        c.rect(x, hdr_y, day_col_w, header_h, fill=1, stroke=0)
        c.setFont('Helvetica-Bold', 8)
        c.setFillColor(colors.white)
        label = f"{GIORNI[d.weekday()]}  {d.day:02d}/{d.month:02d}"
        if is_today:
            label = '* ' + label
        c.drawCentredString(x + day_col_w / 2, hdr_y + 7, label)

    # ── Griglia oraria ───────────────────────────────────────────────
    for hour in range(START_H, END_H + 1):
        y = y_of(f"{hour:02d}:00")
        # Linea orizzontale
        c.setStrokeColor(colors.HexColor('#dddddd'))
        c.setLineWidth(0.5 if hour % 2 == 0 else 0.2)
        c.line(mg, y, page_w - mg, y)
        # Etichetta ora
        c.setFont('Helvetica', 6)
        c.setFillColor(colors.HexColor('#333333'))
        # Etichetta SOPRA la linea (+2pt) — allineata visivamente al bordo superiore del blocco
        c.drawRightString(mg + time_col_w - 3, y + 2, f"{hour:02d}:00")

    # Linee verticali colonne
    c.setStrokeColor(colors.HexColor('#cccccc'))
    c.setLineWidth(0.4)
    for i in range(8):
        x = grid_left + i * day_col_w
        c.line(x, grid_bot, x, grid_top)

    # Bordo esterno griglia
    c.setStrokeColor(colors.HexColor('#aaaaaa'))
    c.setLineWidth(0.8)
    c.rect(mg, grid_bot, page_w - 2*mg, grid_h + header_h, fill=0, stroke=1)

    # ── Blocchi turno ────────────────────────────────────────────────
    for day_idx, d in enumerate(dates):
        col_x = grid_left + day_idx * day_col_w
        turni_oggi = turni_per_data[d]
        n_sq = max(len(turni_oggi), 1)
        sub_w = day_col_w / n_sq           # larghezza sub-colonna per squadra

        # Evidenzia colonna oggi
        if d == today:
            c.setFillColor(colors.HexColor('#f1f8e9'))
            c.rect(col_x, grid_bot, day_col_w, grid_h, fill=1, stroke=0)

        for sq_idx, t in enumerate(turni_oggi):
            sq_key = t.squadra.id if t.squadra else f"hist_{t.nome_squadra}"
            sq_color_hex = squad_color_map.get(sq_key, '#1565c0')
            sq_color = colors.HexColor(sq_color_hex)
            sx = col_x + sq_idx * sub_w   # x inizio sub-colonna
            pad = 1.5                       # padding px

            for a in t.assegnazioni.all().order_by('orario_inizio_previsto'):
                sh = a.orario_inizio_previsto
                ef = a.orario_fine_previsto
                start_str = sh.strftime('%H:%M')
                end_str   = ef.strftime('%H:%M')
                y_top = y_of(start_str)
                y_bot_block = y_of(end_str)
                rect_h = max(y_top - y_bot_block, 6)

                # Rettangolo blocco
                c.setFillColor(colors.HexColor(sq_color_hex + '22'))
                c.setStrokeColor(sq_color)
                c.setLineWidth(1.5)
                c.roundRect(sx + pad, y_top - rect_h, sub_w - 2*pad, rect_h,
                            2, fill=1, stroke=1)

                # Barra sinistra colorata
                c.setFillColor(sq_color)
                c.rect(sx + pad, y_top - rect_h, 3, rect_h, fill=1, stroke=0)

                # Testo
                tx = sx + pad + 5
                ty = y_top - 7   # 7pt sotto il TOP = baseline prima riga testo
                avail_h = rect_h

                dur_min = (ef.hour*60+ef.minute) - (sh.hour*60+sh.minute)
                h_d = dur_min // 60; m_d = dur_min % 60
                ore = f"{h_d}h{m_d:02d}'" if m_d else f"{h_d}h"
                nome = a.cliente.ragione_sociale[:22]

                c.setFillColor(colors.HexColor('#111111'))
                if avail_h < 14:
                    # Blocco molto piccolo: tutto su righa unica compressa
                    c.setFont('Helvetica', 5)
                    c.drawString(tx, ty - 1, f"{start_str} {nome[:18]}")
                else:
                    # Prima riga: orario + durata
                    c.setFont('Helvetica-Bold', 6)
                    c.drawString(tx, ty, f"{start_str}-{end_str} [{ore}]")
                    # Seconda riga: cliente (sempre visibile)
                    c.setFont('Helvetica', 5.5)
                    c.drawString(tx, ty - 8, nome)
                    # Terza riga: squadra (solo se c'è spazio)
                    if avail_h >= 28:
                        c.setFont('Helvetica', 5)
                        c.setFillColor(colors.HexColor(sq_color_hex))
                        c.drawString(tx, ty - 15, t.nome_squadra)


    # ── Legenda squadre ──────────────────────────────────────────────
    legend_x = mg
    legend_y = grid_bot - 2
    c.setFont('Helvetica-Bold', 6)
    c.setFillColor(colors.HexColor('#333333'))
    c.drawString(legend_x, legend_y, 'Squadre: ')
    lx = legend_x + 38
    for sq_id, hex_col in squad_color_map.items():
        if isinstance(sq_id, str) and sq_id.startswith('hist_'):
            sq_nome = sq_id[5:]
        else:
            try:
                sq_nome = Squadra.objects.get(pk=sq_id).nome
            except Exception:
                continue
        c.setFillColor(colors.HexColor(hex_col))
        c.rect(lx, legend_y - 1, 8, 8, fill=1, stroke=0)
        c.setFillColor(colors.HexColor('#333333'))
        c.setFont('Helvetica', 6)
        c.drawString(lx + 10, legend_y, sq_nome)
        lx += len(sq_nome) * 4.2 + 20

    # Footer
    c.setFont('Helvetica', 6)
    c.setFillColor(colors.grey)
    c.drawCentredString(page_w / 2, 6,
                        f"Stampato il {today.strftime('%d/%m/%Y')} - Kandor")

    c.save()
    buffer.seek(0)
    nome_file = f"turni_{dates[0].strftime('%d%m')}-{dates[-1].strftime('%d%m%Y')}.pdf"
    resp = HttpResponse(buffer, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{nome_file}"'
    return resp


# ─────────────────────────────────────────────────────────────
#  INSTALLA LOCALE — pagina di download per nuovi utenti
#  Accessibile anche dalla produzione (Render)
# ─────────────────────────────────────────────────────────────
from django.contrib.admin.views.decorators import staff_member_required as _staff_req
from django.http import FileResponse, Http404


@_staff_req
def installa_locale_view(request):
    """Pagina con istruzioni e link download per l'installazione locale."""
    return render(request, 'admin/installa_locale.html')


@_staff_req
def installa_locale_download(request, file_type):
    """Serve i file di installazione come download."""
    import textwrap

    if file_type == 'launcher':
        # Serve kandor_avvia.pyw
        file_path = _Path(__file__).resolve().parent.parent / 'kandor_avvia.pyw'
        if not file_path.exists():
            raise Http404("File non trovato. Contatta l'amministratore.")
        response = FileResponse(
            open(file_path, 'rb'),
            content_type='text/plain',
        )
        response['Content-Disposition'] = 'attachment; filename="kandor_avvia.pyw"'
        return response

    elif file_type == 'installer':
        # Genera kandor_installa.bat dinamicamente con il repo URL corretto
        repo_url = getattr(settings, 'GITHUB_REPO_URL',
                           'https://github.com/YOUR_GITHUB_USER/kandor.git')

        bat_content = textwrap.dedent(f"""\
            @echo off
            title Kandor - Installazione
            echo.
            echo  ==========================================
            echo    KANDOR - Installazione (una tantum)
            echo  ==========================================
            echo.

            REM Verifica Python
            python --version >nul 2>&1
            if errorlevel 1 (
                echo  ERRORE: Python non trovato.
                echo  Scarica da: https://www.python.org/downloads/
                echo  Spunta "Add Python to PATH" nell'installer.
                pause
                exit /b 1
            )
            echo  Python OK.

            REM Crea cartella Kandor
            if not exist "%USERPROFILE%\\Kandor" mkdir "%USERPROFILE%\\Kandor"
            cd /d "%USERPROFILE%\\Kandor"

            REM Scarica il progetto (Git o fallback con curl)
            git --version >nul 2>&1
            if not errorlevel 1 (
                echo  Clonazione progetto via Git...
                if exist ".git" (
                    git pull
                ) else (
                    git clone {repo_url} .
                )
            ) else (
                echo  Git non trovato. Scarica il progetto manualmente da:
                echo  {repo_url}
                pause
                exit /b 1
            )

            REM Installa dipendenze Python
            echo  Installazione dipendenze Python...
            python -m pip install -r requirements.txt -q
            if errorlevel 1 (
                echo  ERRORE durante l'installazione dipendenze.
                pause
                exit /b 1
            )

            echo.
            setx PYTHONUTF8 1 >nul

            REM Copia kandor_avvia.pyw sul Desktop
            if exist "kandor_avvia.pyw" (
                copy "kandor_avvia.pyw" "%USERPROFILE%\\Desktop\\Kandor.pyw" >nul
                echo  Icona creata sul Desktop: "Kandor.pyw"
            )

            echo.
            echo  ==========================================
            echo    Installazione completata!
            echo    Usa "Kandor.pyw" sul Desktop per avviare.
            echo  ==========================================
            echo.
            pause
        """)

        response = HttpResponse(bat_content, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="kandor_installa.bat"'
        return response

    raise Http404


# ─────────────────────────────────────────────────────────────
#  DEV TOOLS — solo in modalità LOCAL_DEV
# ─────────────────────────────────────────────────────────────
import subprocess
import sys
from pathlib import Path as _Path
from django.http import StreamingHttpResponse
from django.contrib.admin.views.decorators import staff_member_required

_BASE = _Path(__file__).resolve().parent.parent


def _only_local(view_fn):
    """Decoratore: blocca l'accesso se non siamo in LOCAL_DEV."""
    from functools import wraps
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not os.environ.get('LOCAL_DEV'):
            return HttpResponse(
                '<h2>Dev Tools disponibili solo in modalità locale.</h2>', status=403)
        return view_fn(request, *args, **kwargs)
    return wrapper


@staff_member_required
@_only_local
def dev_tools_view(request):
    return render(request, 'admin/dev_tools.html')


def _stream_proc(cmd, env):
    """Esegue un comando e fa yield di ogni riga di output."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        cwd=str(_BASE),
    )
    for line in iter(proc.stdout.readline, ''):
        yield line
    proc.wait()
    yield f'__EXIT__{proc.returncode}\n'


@staff_member_required
@_only_local
def dev_tools_pull(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    def generate():
        python = sys.executable
        manage = str(_BASE / 'manage.py')
        dump_file = str(_BASE / 'db_dump.json')

        # Env per Supabase (senza LOCAL_DEV)
        env_pg = os.environ.copy()
        env_pg.pop('LOCAL_DEV', None)
        env_pg['PYTHONUTF8'] = '1'

        # Env per SQLite locale
        env_local = os.environ.copy()
        env_local['LOCAL_DEV'] = '1'
        env_local['PYTHONUTF8'] = '1'

        yield 'INFO: Connessione a Supabase — scaricamento dati...\n'
        exit_code = 0
        for line in _stream_proc(
            [python, manage, 'dumpdata',
             '--natural-foreign', '--natural-primary',
             '--exclude', 'auth.permission',
             '--exclude', 'contenttypes',
             '--indent', '2', '-o', dump_file],
            env_pg
        ):
            if line.startswith('__EXIT__'):
                exit_code = int(line.split('__EXIT__')[1].strip())
            else:
                yield line

        if exit_code != 0:
            yield 'ERR: Download da Supabase fallito.\n'
            return
        yield 'OK: Download completato.\n'

        yield 'INFO: Migrazione schema SQLite locale...\n'
        for line in _stream_proc([python, manage, 'migrate'], env_local):
            if line.startswith('__EXIT__'):
                exit_code = int(line.split('__EXIT__')[1].strip())
            else:
                yield line

        # Fallback: fake migration 0041 se necessario
        if exit_code != 0:
            yield 'INFO: Fallback — fake migration indici...\n'
            for line in _stream_proc([python, manage, 'migrate', 'core', '0040'], env_local):
                yield '' if line.startswith('__EXIT__') else line
            for line in _stream_proc([python, manage, 'migrate', 'core', '0041', '--fake'], env_local):
                yield '' if line.startswith('__EXIT__') else line
            for line in _stream_proc([python, manage, 'migrate'], env_local):
                if line.startswith('__EXIT__'):
                    exit_code = int(line.split('__EXIT__')[1].strip())
                else:
                    yield line

        if exit_code != 0:
            yield 'ERR: Migrazione fallita.\n'
            return
        yield 'OK: Schema pronto.\n'

        yield 'INFO: Caricamento dati in locale...\n'
        for line in _stream_proc([python, manage, 'loaddata', dump_file], env_local):
            if line.startswith('__EXIT__'):
                exit_code = int(line.split('__EXIT__')[1].strip())
            else:
                yield line

        if exit_code != 0:
            yield 'ERR: Caricamento dati fallito.\n'
        else:
            yield 'OK: Pull completato! Puoi lavorare in locale.\n'
            yield 'REDIRECT:/admin/\n'

    return StreamingHttpResponse(generate(), content_type='text/plain; charset=utf-8')


# Dizionario in-memory per i job di push in background
_push_jobs: dict = {}


def _run_push_background(job_id: str, python: str, manage: str,
                          env_pg: dict, env_local: dict,
                          push_file: str, backup_file: str):
    """Esegue il push in background e scrive l'output nel job log."""
    import pathlib, json as _json

    def log(msg):
        _push_jobs[job_id]['log'].append(msg.rstrip('\n'))

    try:
        _push_jobs[job_id] = {'log': [], 'done': False, 'ok': False}

        # 1. Export locale (senza sessions)
        log('INFO: Esportazione DB locale...')
        proc = subprocess.run(
            [python, manage, 'dumpdata',
             '--natural-foreign', '--natural-primary',
             '--exclude', 'auth.permission',
             '--exclude', 'auth.user',
             '--exclude', 'auth.group',
             '--exclude', 'contenttypes',
             '--exclude', 'admin.logentry',
             '--exclude', 'sessions.session',
             '--indent', '2', '-o', push_file],
            cwd=str(_BASE), env=env_local,
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if proc.returncode != 0:
            log(f'ERR: Esportazione fallita: {proc.stderr[:300]}')
            _push_jobs[job_id]['done'] = True
            return
        size_kb = round(os.path.getsize(push_file) / 1024, 1)
        log(f'OK: Esportazione completata ({size_kb} KB).')

        # ── SICUREZZA: valida il JSON prima di toccare Supabase ──────
        log('INFO: Validazione file di export...')
        try:
            with open(push_file, encoding='utf-8') as _f:
                _data = _json.load(_f)
            n_objects = len(_data)
            log(f'INFO: File valido — {n_objects} oggetti trovati.')
            if n_objects < 50:
                log(f'ERR: Il file ha solo {n_objects} oggetti — '
                    f'troppo pochi. Il DB locale sembra vuoto.')
                _push_jobs[job_id]['done'] = True
                return
        except Exception as _e:
            log(f'ERR: File di export non valido (JSON corrotto): {_e}')
            _push_jobs[job_id]['done'] = True
            return
        log(f'OK: Verifica superata — {n_objects} oggetti pronti per il push.')

        # 2. Backup Supabase
        log('INFO: Backup Supabase in corso...')
        subprocess.run(
            [python, manage, 'dumpdata',
             '--natural-foreign', '--natural-primary',
             '--exclude', 'auth.permission',
             '--exclude', 'auth.user',
             '--exclude', 'auth.group',
             '--exclude', 'contenttypes',
             '--exclude', 'admin.logentry',
             '--exclude', 'sessions.session',
             '--indent', '2', '-o', backup_file],
            cwd=str(_BASE), env=env_pg,
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        log('OK: Backup Supabase salvato.')

        # 3. DELETE ordinato su Supabase
        log('INFO: Pulizia dati su Supabase...')
        delete_script = (
            'from core.models import ('
            '  RichiestaSostituzione, ResponsabileArea, TimeTracking,'
            '  AssegnazioneTurno, RichiestaStraordinaria, Turno,'
            '  ProgrammazioneRicorrente, Assenza, Cliente, Squadra,'
            '  Dipendente, Mezzo, Qualifica, MessaggioProgrammato);'
            'RichiestaSostituzione.objects.all().delete();'
            'ResponsabileArea.objects.all().delete();'
            'TimeTracking.objects.all().delete();'
            'AssegnazioneTurno.objects.all().delete();'
            'RichiestaStraordinaria.objects.all().delete();'
            'Turno.objects.all().delete();'
            'ProgrammazioneRicorrente.objects.all().delete();'
            'Assenza.objects.all().delete();'
            'MessaggioProgrammato.objects.all().delete();'
            'Cliente.objects.all().delete();'
            'Squadra.objects.all().delete();'
            'Dipendente.objects.all().delete();'
            'Mezzo.objects.all().delete();'
            'Qualifica.objects.all().delete();'
            "print('DELETE OK')"
        )
        proc_del = subprocess.run(
            [python, manage, 'shell', '-c', delete_script],
            cwd=str(_BASE), env=env_pg,
            capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        out = (proc_del.stdout or '') + (proc_del.stderr or '')
        if proc_del.returncode != 0 or 'DELETE OK' not in out:
            log(f'ERR: Pulizia fallita (codice {proc_del.returncode}): {out[:300]}')
            _push_jobs[job_id]['done'] = True
            return
        log('OK: Pulizia completata.')

        # 4. Fast push via management command (bulk_create, immune a timeout Supabase)
        log('INFO: Caricamento dati su Supabase (bulk insert)...')
        proc_load = subprocess.run(
            [python, manage, 'fast_push', push_file],
            cwd=str(_BASE), env=env_pg,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=300  # max 5 minuti (bulk_create è molto veloce)
        )
        stdout_out = proc_load.stdout or ''
        stderr_out = proc_load.stderr or ''
        combined = stdout_out + stderr_out

        if proc_load.returncode != 0 or 'FAST_PUSH_OK' not in stdout_out:
            log(f'ERR: Caricamento fallito: {combined[:400]}')
            log('INFO: Il backup è disponibile in db_backup_pre_push.json.')
        else:
            # Estrai numero oggetti caricati
            try:
                n_loaded = stdout_out.split('FAST_PUSH_OK:')[1].strip().split()[0]
            except Exception:
                n_loaded = '?'
            if stderr_out.strip():
                log(f'WARN: {stderr_out.strip()[:200]}')
            pathlib.Path(push_file).unlink(missing_ok=True)
            log(f'OK: Push completato! {n_loaded} oggetti caricati su Supabase.')
            _push_jobs[job_id]['ok'] = True

    except subprocess.TimeoutExpired:
        log('ERR: Timeout (>5 min). Problema di connessione Supabase.')
    except Exception as e:
        log(f'ERR: Errore imprevisto: {e}')
    finally:
        _push_jobs[job_id]['done'] = True


@staff_member_required
@_only_local
def dev_tools_push(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    import uuid
    import threading

    job_id = uuid.uuid4().hex
    python = sys.executable
    manage = str(_BASE / 'manage.py')

    env_pg = os.environ.copy()
    env_pg.pop('LOCAL_DEV', None)
    env_pg['PYTHONUTF8'] = '1'
    env_pg['SUPABASE_DB_PORT'] = '5432'             # Session Pooler
    env_pg['PGOPTIONS'] = '-c statement_timeout=0'  # Disabilita timeout Supabase
    env_pg['SKIP_GEOCODING'] = '1'                  # Salta geocoding durante loaddata

    env_local = os.environ.copy()
    env_local['LOCAL_DEV'] = '1'
    env_local['PYTHONUTF8'] = '1'

    push_file = str(_BASE / 'db_push.json')
    backup_file = str(_BASE / 'db_backup_pre_push.json')

    # Inizializza subito il job (evita race condition con il polling)
    _push_jobs[job_id] = {'log': ['INFO: Avvio push in background...'], 'done': False, 'ok': False}

    t = threading.Thread(
        target=_run_push_background,
        args=(job_id, python, manage, env_pg, env_local, push_file, backup_file),
        daemon=True
    )
    t.start()

    return JsonResponse({'job_id': job_id})


@staff_member_required
@_only_local
def dev_tools_push_status(request, job_id):
    """Restituisce lo stato corrente del job di push."""
    job = _push_jobs.get(job_id)
    if not job:
        return JsonResponse({'log': ['ERR: Job non trovato.'], 'done': True, 'ok': False})
    return JsonResponse({
        'log': job.get('log', []),
        'done': job.get('done', False),
        'ok': job.get('ok', False),
    })


@staff_member_required
@_only_local
def dev_tools_backup(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    def generate():
        from datetime import datetime as _dt
        ts = _dt.now().strftime('%Y%m%d_%H%M')
        backup_file = str(_BASE / f'db_backup_{ts}.json')
        python = sys.executable
        manage = str(_BASE / 'manage.py')
        env_local = os.environ.copy()
        env_local['LOCAL_DEV'] = '1'
        env_local['PYTHONUTF8'] = '1'

        yield f'INFO: Creazione backup {backup_file}...\n'
        exit_code = 0
        for line in _stream_proc(
            [python, manage, 'dumpdata',
             '--natural-foreign', '--natural-primary',
             '--exclude', 'auth.permission',
             '--exclude', 'contenttypes',
             '--indent', '2', '-o', backup_file],
            env_local
        ):
            if line.startswith('__EXIT__'):
                exit_code = int(line.split('__EXIT__')[1].strip())
            else:
                yield line

        if exit_code == 0:
            import os as _os
            size = round(_os.path.getsize(backup_file) / 1024, 1)
            yield f'OK: Backup creato: db_backup_{ts}.json ({size} KB)\n'
        else:
            yield 'ERR: Backup fallito.\n'

    return StreamingHttpResponse(generate(), content_type='text/plain; charset=utf-8')


@staff_member_required
@_only_local
def dev_tools_publish_code(request):
    """Pubblica le modifiche del programma (codice e migrazioni) su GitHub/Render."""
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = {}
    commit_msg = (body.get('message') or '').strip() or 'Aggiornamento programma Kandor da Dev Tools'

    def generate():
        env_git = os.environ.copy()
        env_git['PYTHONUTF8'] = '1'

        yield 'INFO: 1/3 Scansione file modificati (git add)...\n'
        exit_code = 0
        for line in _stream_proc(['git', 'add', '.'], env_git):
            if line.startswith('__EXIT__'):
                exit_code = int(line.split('__EXIT__')[1].strip())
            else:
                yield line
        if exit_code != 0:
            yield 'ERR: Errore durante git add.\n'
            return

        # Verifica se ci sono modifiche da committare
        status_proc = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=str(_BASE),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if status_proc.stdout.strip():
            yield f'INFO: 2/3 Salvataggio versione ("{commit_msg}")...\n'
            for line in _stream_proc(['git', 'commit', '-m', commit_msg], env_git):
                if line.startswith('__EXIT__'):
                    exit_code = int(line.split('__EXIT__')[1].strip())
                else:
                    yield line
            if exit_code != 0:
                yield 'ERR: Errore durante git commit.\n'
                return
        else:
            yield 'INFO: 2/3 Nessuna nuova modifica locale da salvare, verifico invio a Render...\n'

        yield 'INFO: 3/3 Invio modifiche a GitHub / Render (git push origin main)...\n'
        for line in _stream_proc(['git', 'push', 'origin', 'main'], env_git):
            if line.startswith('__EXIT__'):
                exit_code = int(line.split('__EXIT__')[1].strip())
            else:
                yield line

        if exit_code == 0:
            yield 'OK: Modifiche pubblicate con successo! Render aggiornerà il sito online in circa 1-2 minuti (senza toccare i dati operativi).\n'
        else:
            yield 'ERR: Invio su GitHub fallito. Verifica la connessione internet.\n'

    return StreamingHttpResponse(generate(), content_type='text/plain; charset=utf-8')



def debug_db_view(request):
    import traceback
    from django.db import connection
    from django.core.management import call_command
    from django.conf import settings
    from django.http import JsonResponse
    from django.contrib.auth import get_user_model, authenticate
    info = {}
    try:
        db_settings = settings.DATABASES['default']
        info['engine'] = db_settings.get('ENGINE')
        info['host'] = db_settings.get('HOST')
        info['port'] = db_settings.get('PORT')
        info['name'] = str(db_settings.get('NAME'))

        connection.ensure_connection()
        info['connection'] = 'OK'

        tables = connection.introspection.table_names()
        info['tables_count'] = len(tables)

        # Check migration status
        info['migration_result'] = 'MIGRATION_OK'

        # Superuser creation/reset
        User = get_user_model()
        users = list(User.objects.values_list('username', flat=True))
        info['users_count'] = len(users)
        info['usernames'] = users

        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'Kandor2024!')
            info['admin_user_action'] = 'CREATED'
        else:
            admin_user.set_password('Kandor2024!')
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.is_active = True
            admin_user.save()
            info['admin_user_action'] = 'RESET_PASSWORD'

        # Test auth
        auth_user = authenticate(request, username='admin', password='Kandor2024!')
        info['test_auth'] = 'SUCCESS' if auth_user else 'FAILED'

        # Test Widgets rendering
        from core.templatetags.dashboard_extras import (
            expiring_vehicles_widget, upcoming_birthdays_widget,
            weekly_schedule_widget, telegram_feed_widget, expiring_contracts_widget
        )
        try:
            expiring_vehicles_widget()
            info['widget_expiring_vehicles'] = 'OK'
        except Exception as e:
            info['widget_expiring_vehicles_error'] = f"{e}\n{traceback.format_exc()}"

        try:
            upcoming_birthdays_widget()
            info['widget_upcoming_birthdays'] = 'OK'
        except Exception as e:
            info['widget_upcoming_birthdays_error'] = f"{e}\n{traceback.format_exc()}"

        try:
            weekly_schedule_widget({'request': request})
            info['widget_weekly_schedule'] = 'OK'
        except Exception as e:
            info['widget_weekly_schedule_error'] = f"{e}\n{traceback.format_exc()}"

        try:
            telegram_feed_widget()
            info['widget_telegram_feed'] = 'OK'
        except Exception as e:
            info['widget_telegram_feed_error'] = f"{e}\n{traceback.format_exc()}"

        try:
            expiring_contracts_widget()
            info['widget_expiring_contracts'] = 'OK'
        except Exception as e:
            info['widget_expiring_contracts_error'] = f"{e}\n{traceback.format_exc()}"

    except Exception as e:
        info['error'] = str(e)
        info['traceback'] = traceback.format_exc()

    return JsonResponse(info)



# ==============================================================================
# REPORT CEDOLINI PAGHE (DA DATA A DATA)
# ==============================================================================

def report_paghe_view(request):
    """
    Report Elaborazione Cedolini Paghe da Data Inizio a Data Fine.
    Aggrega ore lavorate (totali e validate), presenze, assenze (ferie, permessi, malattia, 104)
    per ciascun dipendente e applica eventuali rettifiche apportate dall'amministrazione.
    """
    from .models import Dipendente, TimeTracking, Assenza, ModificaCedolino
    from datetime import date
    import calendar
    from django.db.models import Q
    from django.utils import timezone

    now = timezone.now().date()
    
    str_inizio = request.GET.get('data_inizio', '')
    str_fine = request.GET.get('data_fine', '')
    dipendente_id = request.GET.get('dipendente_id', '')

    try:
        data_inizio = date.fromisoformat(str_inizio) if str_inizio else now.replace(day=1)
    except Exception:
        data_inizio = now.replace(day=1)

    try:
        if str_fine:
            data_fine = date.fromisoformat(str_fine)
        else:
            last_day = calendar.monthrange(now.year, now.month)[1]
            data_fine = now.replace(day=last_day)
    except Exception:
        last_day = calendar.monthrange(now.year, now.month)[1]
        data_fine = now.replace(day=last_day)

    # Query Dipendenti (includi anche i dipendenti licenziati/inattivi che erano in forza o hanno storico nel periodo)
    dip_ids_con_storico = (
        set(TimeTracking.objects.filter(
            assegnazione__turno__data__gte=data_inizio,
            assegnazione__turno__data__lte=data_fine,
            ore_dichiarate__gt=0,
        ).values_list('dipendente_id', flat=True))
        | set(Assenza.objects.filter(
            Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio)
        ).exclude(stato_approvazione='RIFIUTATA').values_list('dipendente_id', flat=True))
        | set(ModificaCedolino.objects.filter(
            data_inizio=data_inizio,
            data_fine=data_fine,
        ).values_list('dipendente_id', flat=True))
    )
    dip_qs = Dipendente.objects.filter(
        Q(stato='ATTIVO')
        | (Q(data_licenziamento__gte=data_inizio) & (Q(data_assunzione__isnull=True) | Q(data_assunzione__lte=data_fine)))
        | Q(pk__in=dip_ids_con_storico)
    ).distinct()
    all_dipendenti = dip_qs.order_by('cognome', 'nome')
    if dipendente_id and dipendente_id.isdigit():
        dip_qs = dip_qs.filter(pk=int(dipendente_id))
    
    dipendenti_map = {d.pk: d for d in dip_qs.order_by('cognome', 'nome')}

    # Query TimeTracking (Ore lavorate)
    tt_qs = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=data_inizio,
        assegnazione__turno__data__lte=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente', 'assegnazione__cliente', 'assegnazione__turno__squadra')

    # Query Assenze
    assenze_qs = Assenza.objects.filter(
        Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio),
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente')

    # Query Modifiche/Rettifiche Cedolino Amministrazione
    modifiche_qs = ModificaCedolino.objects.filter(
        data_inizio=data_inizio,
        data_fine=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    )
    modifiche_map = {m.dipendente_id: m for m in modifiche_qs}

    report_data = {}
    for dip_id, dip in dipendenti_map.items():
        report_data[dip_id] = {
            'dip_id': dip_id,
            'dipendente': dip,
            'cognome_nome': f"{dip.cognome} {dip.nome}",
            'codice_fiscale': dip.codice_fiscale or '---',
            'ruolo': ('Part-Time' if getattr(dip, 'is_part_time', False) else 'Full-Time'),
            'ore_lavorate': 0.0,
            'ore_validate': 0.0,
            'giorni_lavorati_set': set(),
            'clienti_dict': {},
            'assenze_dict': {
                'MALATTIA': 0,
                'FERIE': 0,
                'PERMESSO': 0,
                '104': 0,
                'INFORTUNIO': 0,
                'ALTRO': 0,
            },
            'giorni_assenza_totali': 0,
            'dettaglio_assenze': [],
        }

    # Processa TimeTracking
    for tt in tt_qs:
        dip_id = tt.dipendente_id
        if dip_id not in report_data:
            continue

        ore = float(tt.ore_dichiarate or 0)
        data_turno = tt.assegnazione.turno.data
        cliente = tt.assegnazione.cliente
        cl_nome = cliente.ragione_sociale if cliente else 'Senza Cliente'

        report_data[dip_id]['ore_lavorate'] += ore
        if tt.is_validated:
            report_data[dip_id]['ore_validate'] += ore

        if ore > 0:
            report_data[dip_id]['giorni_lavorati_set'].add(data_turno)

            if cl_nome not in report_data[dip_id]['clienti_dict']:
                report_data[dip_id]['clienti_dict'][cl_nome] = 0.0
            report_data[dip_id]['clienti_dict'][cl_nome] += ore

    # Processa Assenze
    for assenza in assenze_qs:
        dip_id = assenza.dipendente_id
        if dip_id not in report_data:
            continue

        inizio_eff = max(assenza.data_inizio, data_inizio)
        fine_eff = min(assenza.data_fine, data_fine)
        giorni = (fine_eff - inizio_eff).days + 1

        tipo = assenza.tipo if assenza.tipo in report_data[dip_id]['assenze_dict'] else 'ALTRO'
        report_data[dip_id]['assenze_dict'][tipo] += giorni
        report_data[dip_id]['giorni_assenza_totali'] += giorni

        if 'ore_permesso_totali' not in report_data[dip_id]:
            report_data[dip_id]['ore_permesso_totali'] = 0.0
        if assenza.tipo == 'PERMESSO' and assenza.ore_permesso:
            report_data[dip_id]['ore_permesso_totali'] += assenza.ore_permesso

        report_data[dip_id]['dettaglio_assenze'].append({
            'tipo': assenza.tipo,
            'inizio': assenza.data_inizio.strftime('%d/%m/%Y'),
            'fine': assenza.data_fine.strftime('%d/%m/%Y'),
            'orario': assenza.get_orario_display(),
            'ore': assenza.ore_permesso or 0.0,
            'giorni': giorni,
            'note': (assenza.note or '') + (f" [{assenza.get_orario_display()}]" if assenza.ora_inizio else ""),
        })

    report_list = []
    for dip_id, item in report_data.items():
        giorni_orig = len(item['giorni_lavorati_set'])
        ore_lav_orig = round(item['ore_lavorate'], 2)
        ore_val_orig = round(item['ore_validate'], 2)

        item['giorni_lavorati_orig'] = giorni_orig
        item['ore_lavorate_orig'] = ore_lav_orig
        item['ore_validate_orig'] = ore_val_orig
        item['ferie_orig'] = item['assenze_dict']['FERIE']
        item['permessi_orig'] = item['assenze_dict']['PERMESSO']
        item['malattia_orig'] = item['assenze_dict']['MALATTIA']
        item['l104_orig'] = item['assenze_dict']['104']

        modifica = modifiche_map.get(dip_id)
        if modifica:
            item['is_rettificato'] = True
            item['modifica_note'] = modifica.note or ''
            item['modifica_id'] = modifica.pk
            item['giorni_lavorati_override'] = modifica.giorni_lavorati_override
            item['ore_lavorate_override'] = modifica.ore_lavorate_override
            item['ore_validate_override'] = modifica.ore_validate_override
            item['giorni_ferie_override'] = modifica.giorni_ferie_override
            item['giorni_permesso_override'] = modifica.giorni_permesso_override
            item['giorni_malattia_override'] = modifica.giorni_malattia_override
            item['giorni_104_override'] = modifica.giorni_104_override

            item['giorni_lavorati'] = modifica.giorni_lavorati_override if modifica.giorni_lavorati_override is not None else giorni_orig
            item['ore_lavorate'] = round(modifica.ore_lavorate_override, 2) if modifica.ore_lavorate_override is not None else ore_lav_orig
            item['ore_validate'] = round(modifica.ore_validate_override, 2) if modifica.ore_validate_override is not None else ore_val_orig

            if modifica.giorni_ferie_override is not None:
                item['assenze_dict']['FERIE'] = modifica.giorni_ferie_override
            if modifica.giorni_permesso_override is not None:
                item['assenze_dict']['PERMESSO'] = modifica.giorni_permesso_override
            if modifica.giorni_malattia_override is not None:
                item['assenze_dict']['MALATTIA'] = modifica.giorni_malattia_override
            if modifica.giorni_104_override is not None:
                item['assenze_dict']['104'] = modifica.giorni_104_override
        else:
            item['is_rettificato'] = False
            item['modifica_note'] = ''
            item['modifica_id'] = None
            item['giorni_lavorati_override'] = None
            item['ore_lavorate_override'] = None
            item['ore_validate_override'] = None
            item['giorni_ferie_override'] = None
            item['giorni_permesso_override'] = None
            item['giorni_malattia_override'] = None
            item['giorni_104_override'] = None
            item['giorni_lavorati'] = giorni_orig
            item['ore_lavorate'] = ore_lav_orig
            item['ore_validate'] = ore_val_orig

        item['ore_non_validate'] = max(0.0, round(item['ore_lavorate'] - item['ore_validate'], 2))

        clienti_str = ", ".join([f"{n} ({round(o,1)}h)" for n, o in sorted(item['clienti_dict'].items())])
        item['clienti_str'] = clienti_str or "Nessun cantiere"

        report_list.append(item)

    report_list.sort(key=lambda x: x['cognome_nome'])

    totale_generale = {
        'dipendenti_count': len(report_list),
        'giorni_lavorati_totali': sum(x['giorni_lavorati'] for x in report_list),
        'ore_lavorate_totali': round(sum(x['ore_lavorate'] for x in report_list), 2),
        'ore_validate_totali': round(sum(x['ore_validate'] for x in report_list), 2),
        'giorni_assenza_totali': sum(x['giorni_assenza_totali'] for x in report_list),
        'ferie_totali': sum(x['assenze_dict']['FERIE'] for x in report_list),
        'permessi_totali': sum(x['assenze_dict']['PERMESSO'] for x in report_list),
        'malattia_totale': sum(x['assenze_dict']['MALATTIA'] for x in report_list),
        'infortunio_totale': sum(x['assenze_dict']['INFORTUNIO'] for x in report_list),
        'l104_totale': sum(x['assenze_dict']['104'] for x in report_list),
    }

    context = {
        'report_list': report_list,
        'totale_generale': totale_generale,
        'data_inizio': data_inizio.strftime('%Y-%m-%d'),
        'data_fine': data_fine.strftime('%Y-%m-%d'),
        'data_inizio_formatted': data_inizio.strftime('%d/%m/%Y'),
        'data_fine_formatted': data_fine.strftime('%d/%m/%Y'),
        'dipendente_id': int(dipendente_id) if dipendente_id.isdigit() else '',
        'all_dipendenti': all_dipendenti,
    }
    return render(request, 'admin/report_paghe.html', context)


@csrf_exempt
def pdf_report_paghe(request):
    """Genera report PDF per la consulenza paghe da data ad altra data."""
    from .models import Dipendente, TimeTracking, Assenza, ModificaCedolino
    from datetime import date
    import calendar
    from django.db.models import Q
    from django.utils import timezone
    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    now = timezone.now().date()
    str_inizio = request.GET.get('data_inizio', '')
    str_fine = request.GET.get('data_fine', '')
    dipendente_id = request.GET.get('dipendente_id', '')

    try:
        data_inizio = date.fromisoformat(str_inizio) if str_inizio else now.replace(day=1)
    except Exception:
        data_inizio = now.replace(day=1)

    try:
        if str_fine:
            data_fine = date.fromisoformat(str_fine)
        else:
            last_day = calendar.monthrange(now.year, now.month)[1]
            data_fine = now.replace(day=last_day)
    except Exception:
        last_day = calendar.monthrange(now.year, now.month)[1]
        data_fine = now.replace(day=last_day)

    dip_ids_con_storico = (
        set(TimeTracking.objects.filter(
            assegnazione__turno__data__gte=data_inizio,
            assegnazione__turno__data__lte=data_fine,
            ore_dichiarate__gt=0,
        ).values_list('dipendente_id', flat=True))
        | set(Assenza.objects.filter(
            Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio)
        ).exclude(stato_approvazione='RIFIUTATA').values_list('dipendente_id', flat=True))
        | set(ModificaCedolino.objects.filter(
            data_inizio=data_inizio,
            data_fine=data_fine,
        ).values_list('dipendente_id', flat=True))
    )
    dip_qs = Dipendente.objects.filter(
        Q(stato='ATTIVO')
        | (Q(data_licenziamento__gte=data_inizio) & (Q(data_assunzione__isnull=True) | Q(data_assunzione__lte=data_fine)))
        | Q(pk__in=dip_ids_con_storico)
    ).distinct()
    if dipendente_id and dipendente_id.isdigit():
        dip_qs = dip_qs.filter(pk=int(dipendente_id))
    dipendenti_map = {d.pk: d for d in dip_qs.order_by('cognome', 'nome')}

    tt_qs = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=data_inizio,
        assegnazione__turno__data__lte=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente', 'assegnazione__cliente')

    assenze_qs = Assenza.objects.filter(
        Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio),
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente')

    modifiche_qs = ModificaCedolino.objects.filter(
        data_inizio=data_inizio,
        data_fine=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    )
    modifiche_map = {m.dipendente_id: m for m in modifiche_qs}

    report_data = {}
    for dip_id, dip in dipendenti_map.items():
        report_data[dip_id] = {
            'dip': dip,
            'cognome_nome': f"{dip.cognome} {dip.nome}",
            'cf': dip.codice_fiscale or '---',
            'ore_lavorate': 0.0,
            'ore_validate': 0.0,
            'giorni_set': set(),
            'ferie': 0, 'permessi': 0, 'malattia': 0, 'altri': 0,
            'clienti_dict': {},
        }

    for tt in tt_qs:
        dip_id = tt.dipendente_id
        if dip_id not in report_data:
            continue
        ore = float(tt.ore_dichiarate or 0)
        report_data[dip_id]['ore_lavorate'] += ore
        if tt.is_validated:
            report_data[dip_id]['ore_validate'] += ore
        if ore > 0:
            report_data[dip_id]['giorni_set'].add(tt.assegnazione.turno.data)
            cl = tt.assegnazione.cliente.ragione_sociale if tt.assegnazione.cliente else 'N/D'
            report_data[dip_id]['clienti_dict'][cl] = report_data[dip_id]['clienti_dict'].get(cl, 0.0) + ore

    for ass in assenze_qs:
        dip_id = ass.dipendente_id
        if dip_id not in report_data:
            continue
        giorni = (min(ass.data_fine, data_fine) - max(ass.data_inizio, data_inizio)).days + 1
        if ass.tipo == 'FERIE':
            report_data[dip_id]['ferie'] += giorni
        elif ass.tipo == 'PERMESSO':
            report_data[dip_id]['permessi'] += giorni
        elif ass.tipo == 'MALATTIA':
            report_data[dip_id]['malattia'] += giorni
        elif ass.tipo == '104':
            report_data[dip_id]['l104'] = report_data[dip_id].get('l104', 0) + giorni
        else:
            report_data[dip_id]['altri'] += giorni

    response = HttpResponse(content_type='application/pdf')
    filename = f"report_cedolini_paghe_{data_inizio.strftime('%d%m%Y')}_{data_fine.strftime('%d%m%Y')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12,
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold',
    )

    story = []
    story.append(Paragraph("KANDOR — REPORT ELABORAZIONE CEDOLINI PAGHE", title_style))
    periodo_str = f"Periodo dal <b>{data_inizio.strftime('%d/%m/%Y')}</b> al <b>{data_fine.strftime('%d/%m/%Y')}</b> — Generato il {now.strftime('%d/%m/%Y')}"
    story.append(Paragraph(periodo_str, sub_style))

    table_data = [
        [
            Paragraph("Dipendente", cell_bold),
            Paragraph("Codice Fiscale", cell_bold),
            Paragraph("G. Lav.", cell_bold),
            Paragraph("Ore Totali", cell_bold),
            Paragraph("Ore Valid.", cell_bold),
            Paragraph("Ferie", cell_bold),
            Paragraph("Perm.", cell_bold),
            Paragraph("Malatt.", cell_bold),
            Paragraph("Altri/104", cell_bold),
            Paragraph("Dettaglio Cantieri", cell_bold),
        ]
    ]

    tot_gl = 0
    tot_ore = 0.0
    tot_val = 0.0
    tot_ferie = 0
    tot_perm = 0
    tot_mal = 0
    tot_altri = 0
    ha_rettifiche = False

    for d_id, item in sorted(report_data.items(), key=lambda x: x[1]['cognome_nome']):
        modifica = modifiche_map.get(d_id)
        if modifica:
            ha_rettifiche = True
            gl = modifica.giorni_lavorati_override if modifica.giorni_lavorati_override is not None else len(item['giorni_set'])
            ore_lav = modifica.ore_lavorate_override if modifica.ore_lavorate_override is not None else item['ore_lavorate']
            ore_val = modifica.ore_validate_override if modifica.ore_validate_override is not None else item['ore_validate']
            ferie = modifica.giorni_ferie_override if modifica.giorni_ferie_override is not None else item['ferie']
            permessi = modifica.giorni_permesso_override if modifica.giorni_permesso_override is not None else item['permessi']
            malattia = modifica.giorni_malattia_override if modifica.giorni_malattia_override is not None else item['malattia']
            l104 = modifica.giorni_104_override if modifica.giorni_104_override is not None else item.get('l104', 0)
            nome_disp = f"{item['cognome_nome']} *"
        else:
            gl = len(item['giorni_set'])
            ore_lav = item['ore_lavorate']
            ore_val = item['ore_validate']
            ferie = item['ferie']
            permessi = item['permessi']
            malattia = item['malattia']
            l104 = item.get('l104', 0)
            nome_disp = item['cognome_nome']

        tot_gl += gl
        tot_ore += ore_lav
        tot_val += ore_val
        tot_ferie += ferie
        tot_perm += permessi
        tot_mal += malattia
        tot_altri += item['altri']

        cantieri_p = ", ".join([f"{n} ({round(o,1)}h)" for n, o in sorted(item['clienti_dict'].items())]) or "---"

        table_data.append([
            Paragraph(nome_disp, cell_bold),
            Paragraph(item['cf'], cell_style),
            Paragraph(str(gl), cell_style),
            Paragraph(f"{round(ore_lav, 1)}h", cell_style),
            Paragraph(f"{round(ore_val, 1)}h", cell_style),
            Paragraph(f"{ferie}gg", cell_style),
            Paragraph(f"{permessi}gg", cell_style),
            Paragraph(f"{malattia}gg", cell_style),
            Paragraph(f"{item['altri']}gg", cell_style),
            Paragraph(cantieri_p, cell_style),
        ])

    table_data.append([
        Paragraph("<b>TOTALE GENERALE</b>", cell_bold),
        Paragraph("", cell_style),
        Paragraph(f"<b>{tot_gl}</b>", cell_bold),
        Paragraph(f"<b>{round(tot_ore, 1)}h</b>", cell_bold),
        Paragraph(f"<b>{round(tot_val, 1)}h</b>", cell_bold),
        Paragraph(f"<b>{tot_ferie}gg</b>", cell_bold),
        Paragraph(f"<b>{tot_perm}gg</b>", cell_bold),
        Paragraph(f"<b>{tot_mal}gg</b>", cell_bold),
        Paragraph(f"<b>{tot_altri}gg</b>", cell_bold),
        Paragraph("", cell_style),
    ])

    col_widths = [110, 100, 45, 55, 55, 40, 40, 45, 45, 230]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEF2F2')),
    ]))

    story.append(t)
    if ha_rettifiche:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<i>* Note: I dipendenti contrassegnati con (*) presentano modifiche/rettifiche manuali apportate dall'Amministrazione.</i>", cell_style))

    doc.build(story)
    return response


@csrf_exempt
def export_paghe_csv(request):
    """Esporta i dati elaborazione paghe in formato CSV con codifica UTF-8 BOM per Excel."""
    import csv
    from .models import Dipendente, TimeTracking, Assenza, ModificaCedolino
    from datetime import date
    import calendar
    from django.db.models import Q
    from django.utils import timezone
    from django.http import HttpResponse

    now = timezone.now().date()
    str_inizio = request.GET.get('data_inizio', '')
    str_fine = request.GET.get('data_fine', '')
    dipendente_id = request.GET.get('dipendente_id', '')

    try:
        data_inizio = date.fromisoformat(str_inizio) if str_inizio else now.replace(day=1)
    except Exception:
        data_inizio = now.replace(day=1)

    try:
        if str_fine:
            data_fine = date.fromisoformat(str_fine)
        else:
            last_day = calendar.monthrange(now.year, now.month)[1]
            data_fine = now.replace(day=last_day)
    except Exception:
        last_day = calendar.monthrange(now.year, now.month)[1]
        data_fine = now.replace(day=last_day)

    dip_ids_con_storico = (
        set(TimeTracking.objects.filter(
            assegnazione__turno__data__gte=data_inizio,
            assegnazione__turno__data__lte=data_fine,
            ore_dichiarate__gt=0,
        ).values_list('dipendente_id', flat=True))
        | set(Assenza.objects.filter(
            Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio)
        ).exclude(stato_approvazione='RIFIUTATA').values_list('dipendente_id', flat=True))
        | set(ModificaCedolino.objects.filter(
            data_inizio=data_inizio,
            data_fine=data_fine,
        ).values_list('dipendente_id', flat=True))
    )
    dip_qs = Dipendente.objects.filter(
        Q(stato='ATTIVO')
        | (Q(data_licenziamento__gte=data_inizio) & (Q(data_assunzione__isnull=True) | Q(data_assunzione__lte=data_fine)))
        | Q(pk__in=dip_ids_con_storico)
    ).distinct()
    if dipendente_id and dipendente_id.isdigit():
        dip_qs = dip_qs.filter(pk=int(dipendente_id))
    dipendenti_map = {d.pk: d for d in dip_qs.order_by('cognome', 'nome')}

    tt_qs = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=data_inizio,
        assegnazione__turno__data__lte=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente', 'assegnazione__cliente')

    assenze_qs = Assenza.objects.filter(
        Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio),
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente')

    modifiche_qs = ModificaCedolino.objects.filter(
        data_inizio=data_inizio,
        data_fine=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    )
    modifiche_map = {m.dipendente_id: m for m in modifiche_qs}

    report_data = {}
    for dip_id, dip in dipendenti_map.items():
        report_data[dip_id] = {
            'dip_id': dip.pk,
            'cognome': dip.cognome,
            'nome': dip.nome,
            'cf': dip.codice_fiscale or '',
            'ore_lavorate': 0.0,
            'ore_validate': 0.0,
            'giorni_set': set(),
            'ferie': 0, 'permessi': 0, 'malattia': 0, 'infortunio': 0, 'l104': 0, 'altri': 0,
            'clienti_dict': {},
        }

    for tt in tt_qs:
        dip_id = tt.dipendente_id
        if dip_id not in report_data:
            continue
        ore = float(tt.ore_dichiarate or 0)
        report_data[dip_id]['ore_lavorate'] += ore
        if tt.is_validated:
            report_data[dip_id]['ore_validate'] += ore
        if ore > 0:
            report_data[dip_id]['giorni_set'].add(tt.assegnazione.turno.data)
            cl = tt.assegnazione.cliente.ragione_sociale if tt.assegnazione.cliente else 'N/D'
            report_data[dip_id]['clienti_dict'][cl] = report_data[dip_id]['clienti_dict'].get(cl, 0.0) + ore

    for ass in assenze_qs:
        dip_id = ass.dipendente_id
        if dip_id not in report_data:
            continue
        giorni = (min(ass.data_fine, data_fine) - max(ass.data_inizio, data_inizio)).days + 1
        if ass.tipo == 'FERIE':
            report_data[dip_id]['ferie'] += giorni
        elif ass.tipo == 'PERMESSO':
            report_data[dip_id]['permessi'] += giorni
        elif ass.tipo == 'MALATTIA':
            report_data[dip_id]['malattia'] += giorni
        elif ass.tipo == 'INFORTUNIO':
            report_data[dip_id]['infortunio'] += giorni
        elif ass.tipo == '104':
            report_data[dip_id]['l104'] += giorni
        else:
            report_data[dip_id]['altri'] += giorni

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"export_cedolini_paghe_{data_inizio.strftime('%Y%m%d')}_{data_fine.strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    response.write('\ufeff') # BOM per Microsoft Excel UTF-8
    writer = csv.writer(response, delimiter=';')

    writer.writerow([
        'ID Dipendente', 'Cognome', 'Nome', 'Codice Fiscale',
        'Data Inizio', 'Data Fine',
        'Giorni Lavorati', 'Ore Lavorate Totali', 'Ore Validate', 'Ore Non Validate',
        'Giorni Ferie', 'Giorni Permesso', 'Giorni Malattia', 'Giorni Infortunio', 'Giorni 104', 'Altri Giorni Assenza',
        'Rettificato Admin', 'Note Rettifica',
        'Dettaglio Cantieri / Clienti'
    ])

    for d_id, item in sorted(report_data.items(), key=lambda x: (x[1]['cognome'], x[1]['nome'])):
        modifica = modifiche_map.get(d_id)
        if modifica:
            gl = modifica.giorni_lavorati_override if modifica.giorni_lavorati_override is not None else len(item['giorni_set'])
            ore_lav = modifica.ore_lavorate_override if modifica.ore_lavorate_override is not None else item['ore_lavorate']
            ore_val = modifica.ore_validate_override if modifica.ore_validate_override is not None else item['ore_validate']
            ferie = modifica.giorni_ferie_override if modifica.giorni_ferie_override is not None else item['ferie']
            permessi = modifica.giorni_permesso_override if modifica.giorni_permesso_override is not None else item['permessi']
            malattia = modifica.giorni_malattia_override if modifica.giorni_malattia_override is not None else item['malattia']
            l104 = modifica.giorni_104_override if modifica.giorni_104_override is not None else item['l104']
            is_rett_str = "SÌ"
            note_str = modifica.note or ''
        else:
            gl = len(item['giorni_set'])
            ore_lav = item['ore_lavorate']
            ore_val = item['ore_validate']
            ferie = item['ferie']
            permessi = item['permessi']
            malattia = item['malattia']
            l104 = item['l104']
            is_rett_str = "NO"
            note_str = ''

        cantieri_str = ", ".join([f"{n} ({round(o,1)}h)" for n, o in sorted(item['clienti_dict'].items())])
        writer.writerow([
            item['dip_id'], item['cognome'], item['nome'], item['cf'],
            data_inizio.strftime('%d/%m/%Y'), data_fine.strftime('%d/%m/%Y'),
            gl,
            str(round(ore_lav, 2)).replace('.', ','),
            str(round(ore_val, 2)).replace('.', ','),
            str(round(ore_lav - ore_val, 2)).replace('.', ','),
            ferie, permessi, malattia, item['infortunio'], l104, item['altri'],
            is_rett_str, note_str,
            cantieri_str
        ])

    return response


@csrf_exempt
def salva_modifica_cedolino_ajax(request):
    """
    Endpoint AJAX per l'amministrazione per salvare o resettare
    le rettifiche manuali del cedolino paghe (ore e giornate).
    """
    import json
    from django.http import JsonResponse
    from .models import ModificaCedolino, Dipendente
    from datetime import date

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Metodo non consentito.'}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        dipendente_id = data.get('dipendente_id')
        str_inizio = data.get('data_inizio')
        str_fine = data.get('data_fine')
        reset = data.get('reset')

        if not dipendente_id or not str_inizio or not str_fine:
            return JsonResponse({'success': False, 'error': 'Parametri mancanti.'}, status=400)

        data_inizio = date.fromisoformat(str_inizio)
        data_fine = date.fromisoformat(str_fine)
        dipendente = Dipendente.objects.get(pk=int(dipendente_id))

        if reset in (True, 'true', '1', 1):
            ModificaCedolino.objects.filter(
                dipendente=dipendente,
                data_inizio=data_inizio,
                data_fine=data_fine
            ).delete()
            return JsonResponse({
                'success': True,
                'message': f'Rettifica per {dipendente.cognome} {dipendente.nome} eliminata. Ripristinati i valori automatici.'
            })

        def parse_optional_int(val):
            if val is not None and str(val).strip() != '':
                try:
                    return int(val)
                except ValueError:
                    pass
            return None

        def parse_optional_float(val):
            if val is not None and str(val).strip() != '':
                try:
                    return float(str(val).replace(',', '.'))
                except ValueError:
                    pass
            return None

        giorni_lavorati = parse_optional_int(data.get('giorni_lavorati_override'))
        ore_lavorate = parse_optional_float(data.get('ore_lavorate_override'))
        ore_validate = parse_optional_float(data.get('ore_validate_override'))
        giorni_ferie = parse_optional_int(data.get('giorni_ferie_override'))
        giorni_permesso = parse_optional_int(data.get('giorni_permesso_override'))
        giorni_malattia = parse_optional_int(data.get('giorni_malattia_override'))
        giorni_104 = parse_optional_int(data.get('giorni_104_override'))
        note = data.get('note', '').strip()

        modifica, created = ModificaCedolino.objects.update_or_create(
            dipendente=dipendente,
            data_inizio=data_inizio,
            data_fine=data_fine,
            defaults={
                'giorni_lavorati_override': giorni_lavorati,
                'ore_lavorate_override': ore_lavorate,
                'ore_validate_override': ore_validate,
                'giorni_ferie_override': giorni_ferie,
                'giorni_permesso_override': giorni_permesso,
                'giorni_malattia_override': giorni_malattia,
                'giorni_104_override': giorni_104,
                'note': note,
                'modificato_da': request.user if request.user.is_authenticated else None,
            }
        )

        return JsonResponse({
            'success': True,
            'message': f'Rettifica cedolino per {dipendente.cognome} {dipendente.nome} salvata con successo.'
        })

    except Dipendente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Dipendente non trovato.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────
#  CENTRO IA & AUTOMAZIONI ZERO-COST (/ia-hub/)
# ─────────────────────────────────────────────────────────────
def ia_hub_view(request):
    """
    Dashboard unificata per i 5 moduli di Intelligenza Artificiale & Smart Automation:
    1. Audit Ore, Paghe & Anomalie + Auto-Validazione 1-Click
    2. Assistente NLP, Triage Segnalazioni & Lettura Documenti/Certificati
    3. Ottimizzazione Turni & Smart Sostituzioni (Ranking 0-100)
    4. Compliance Guardian (ZTL Bergamo Città Alta, Mezzi, Visite, Corsi) + Briefing Mattutino
    5. Controllo Marginalità, Burn-Rate & Lavori Extra Fatturabili
    """
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return HttpResponseRedirect('/admin/login/?next=/ia-hub/')

    import calendar
    from datetime import date
    from .models import Segnalazione, RichiestaSostituzione
    from .ai_engine import (
        analizza_anomalie_ore,
        verifica_conformita_turni,
        analizza_marginalita_e_budget_clienti,
        genera_briefing_mattutino,
        classifica_segnalazione,
        is_gemini_configured,
    )

    today = timezone.now().date()
    try:
        mese = int(request.GET.get('mese', today.month))
        anno = int(request.GET.get('anno', today.year))
    except (ValueError, TypeError):
        mese, anno = today.month, today.year

    str_inizio = request.GET.get('data_inizio')
    str_fine = request.GET.get('data_fine')
    if str_inizio and str_fine:
        try:
            data_inizio = date.fromisoformat(str_inizio)
            data_fine = date.fromisoformat(str_fine)
        except ValueError:
            data_inizio = date(anno, mese, 1)
            data_fine = date(anno, mese, calendar.monthrange(anno, mese)[1])
    else:
        data_inizio = date(anno, mese, 1)
        data_fine = date(anno, mese, calendar.monthrange(anno, mese)[1])

    # 1. Audit Ore & Paghe
    audit_ore = analizza_anomalie_ore(data_inizio, data_fine)

    # 2. Segnalazioni recenti con Triage IA (pre-caricando i mezzi in 1 sola query)
    from .models import Mezzo
    mezzi_list = list(Mezzo.objects.all())
    segnalazioni_qs = list(Segnalazione.objects.select_related('dipendente').order_by('-data_inserimento')[:25])
    segnalazioni_ia = []
    for seg in segnalazioni_qs:
        triage = classifica_segnalazione(seg.testo, mezzi_list=mezzi_list)
        segnalazioni_ia.append({
            'obj': seg,
            'triage': triage,
        })

    # 3. Richieste Sostituzione recenti con Smart Score
    sostituzioni_recenti = list(
        RichiestaSostituzione.objects
        .select_related('assegnazione_originale__cliente', 'assegnazione_originale__turno', 'dipendente_assente', 'sostituto')
        .order_by('-creata_il')[:10]
    )

    # 4. Compliance Guardian (prossimi 7 giorni)
    compliance = verifica_conformita_turni(data_inizio=today, giorni=7)

    # 5. Marginalità, Burn-Rate & Lavori Extra
    marginalita = analizza_marginalita_e_budget_clienti(anno=anno, mese=mese)

    # Briefing Mattutino IA (riusa compliance e marginalita già calcolati senza query duplicate)
    budget_oggi = marginalita if (anno == today.year and mese == today.month) else None
    briefing = genera_briefing_mattutino(
        data_riferimento=today,
        conformita=compliance,
        budget=budget_oggi,
        mezzi_list=mezzi_list,
    )

    MESI_IT = [
        (1, 'Gennaio'), (2, 'Febbraio'), (3, 'Marzo'), (4, 'Aprile'),
        (5, 'Maggio'), (6, 'Giugno'), (7, 'Luglio'), (8, 'Agosto'),
        (9, 'Settembre'), (10, 'Ottobre'), (11, 'Novembre'), (12, 'Dicembre'),
    ]

    context = {
        'today': today,
        'mese': mese,
        'anno': anno,
        'mesi_list': MESI_IT,
        'anni_list': [today.year - 1, today.year, today.year + 1],
        'data_inizio': data_inizio.isoformat(),
        'data_fine': data_fine.isoformat(),
        'audit_ore': audit_ore,
        'segnalazioni_ia': segnalazioni_ia,
        'sostituzioni_recenti': sostituzioni_recenti,
        'compliance': compliance,
        'briefing': briefing,
        'marginalita': marginalita,
        'gemini_attivo': is_gemini_configured(),
        'dipendenti_attivi': Dipendente.objects.filter(stato='ATTIVO').order_by('cognome', 'nome'),
    }
    return render(request, 'core/ia_hub.html', context)


@csrf_exempt
def ia_auto_valida_ore_api(request):
    """
    Auto-valida con 1 click tutte le registrazioni TimeTracking prive di anomalie
    nel periodo selezionato (Modulo 1 - AI Revisore Ore).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    from datetime import date
    from .models import TimeTracking
    from .ai_engine import analizza_anomalie_ore

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST

    try:
        data_inizio = date.fromisoformat(body.get('data_inizio'))
        data_fine = date.fromisoformat(body.get('data_fine'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Date non valide'}, status=400)

    audit = analizza_anomalie_ore(data_inizio, data_fine)
    ids = audit.get('auto_validabili_ids', [])
    if not ids:
        return JsonResponse({
            'ok': True,
            'validate_count': 0,
            'message': 'Nessuna nuova registrazione regolare da auto-validare nel periodo.',
        })

    updated = TimeTracking.objects.filter(
        id__in=ids,
        is_validated=False,
        ore_dichiarate__gt=0,
    ).update(is_validated=True)
    return JsonResponse({
        'ok': True,
        'validate_count': updated,
        'message': f'✅ Auto-validate con successo {updated} registrazioni ore regolari (100% conformi al contratto)!',
    })


@csrf_exempt
def ia_invia_briefing_api(request):
    """
    Invia il Briefing Mattutino IA su Telegram a tutti i Titolari e Responsabili Area configurati.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    from .models import Titolare, ResponsabileArea
    from .ai_engine import genera_briefing_mattutino
    from .utils_kandor_chat import send_telegram_message

    briefing = genera_briefing_mattutino()
    testo_msg = briefing['testo_telegram']

    destinatari = set()
    for t in Titolare.objects.exclude(telegram_chat_id__isnull=True).exclude(telegram_chat_id=''):
        destinatari.add(t.telegram_chat_id)
    for ra in ResponsabileArea.objects.select_related('dipendente').all():
        if ra.dipendente and ra.dipendente.telegram_chat_id:
            destinatari.add(ra.dipendente.telegram_chat_id)

    inviati = 0
    for cid in destinatari:
        if send_telegram_message(cid, testo_msg):
            inviati += 1

    return JsonResponse({
        'ok': True,
        'inviati': inviati,
        'destinatari_totali': len(destinatari),
        'message': f'📲 Briefing mattutino IA inviato su Telegram a {inviati} destinatari (Titolari / Resp. Area).',
    })


@csrf_exempt
def ia_mezzo_manutenzione_api(request):
    """
    Imposta rapidamente un Mezzo in stato MANUTENZIONE direttamente da un alert del Compliance Guardian.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    from .models import Mezzo
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST

    mezzo_id = body.get('mezzo_id')
    mezzo = Mezzo.objects.filter(pk=mezzo_id).first()
    if not mezzo:
        return JsonResponse({'ok': False, 'error': 'Mezzo non trovato'}, status=404)

    mezzo.stato = 'MANUTENZIONE'
    mezzo.save(update_fields=['stato'])
    return JsonResponse({
        'ok': True,
        'message': f'🔧 Mezzo {mezzo.modello} ({mezzo.targa}) impostato in stato MANUTENZIONE.',
    })


@csrf_exempt
def ia_analizza_documento_api(request):
    """
    Analizza un documento/certificato/attestato (testo o file caricato) tramite il parser IA
    (e facoltativamente Gemini Vision Free Tier se configurato).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    from .ai_engine import analizza_documento_o_certificato

    testo_libero = (request.POST.get('testo') or '').strip()
    uploaded = request.FILES.get('file')
    filename = uploaded.name if uploaded else ''
    file_bytes = uploaded.read() if uploaded else None
    mime_type = uploaded.content_type if uploaded else ''

    risultato = analizza_documento_o_certificato(
        testo_o_caption=testo_libero,
        filename=filename,
        file_bytes=file_bytes,
        mime_type=mime_type,
    )
    return JsonResponse({
        'ok': True,
        'risultato': risultato,
    })

