from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Cliente, Qualifica, Dipendente
from .services import trova_jolly, genera_turni_automatici
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.contrib import messages
import json
import io
import os
from django.conf import settings
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
import io
import os
from django.conf import settings
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseRedirect

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
        
    last_response = None
    selected_employee_id = None
    selected_employee = None
    chat_messages = []
    
    from .models import MessaggioChat
    
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        msg = request.POST.get('message')
        
        if emp_id and msg:
            emp = get_object_or_404(Dipendente, pk=emp_id)
            
            # Salva messaggio OUT nel database
            MessaggioChat.objects.create(
                dipendente=emp, testo=msg, direzione='OUT'
            )
            
            # Invio reale via Telegram
            from .utils_kandor_chat import send_telegram_message
            if emp.telegram_chat_id:
                send_telegram_message(emp.telegram_chat_id, msg)
            
            # Redirect GET per evitare re-submit e aggiornare cronologia
            return HttpResponseRedirect(f'/chat-simulator/?employee_id={emp_id}')
    
    # Converte employee_id a int
    raw_id = request.GET.get('employee_id')
    if raw_id:
        try:
            selected_employee_id = int(raw_id)
        except (ValueError, TypeError):
            pass
    
    # Carica cronologia se selezionato
    if selected_employee_id:
        try:
            selected_employee = Dipendente.objects.get(pk=selected_employee_id)
            chat_messages = list(MessaggioChat.objects.filter(
                dipendente_id=selected_employee_id
            ).order_by('-timestamp')[:50])
            chat_messages.reverse()
            # Segna come letti
            MessaggioChat.objects.filter(
                dipendente_id=selected_employee_id, direzione='IN', letto=False
            ).update(letto=True)
        except Dipendente.DoesNotExist:
            pass

    employees = Dipendente.objects.filter(stato='ATTIVO')
    
    return render(request, 'core/chat_simulator.html', {
        'employees': employees,
        'selected_employee_id': selected_employee_id,
        'selected_employee': selected_employee,
        'chat_messages': chat_messages,
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
        tipo = data.get('tipo', 'straordinario')  # 'ricorrente' o 'straordinario'
        note = data.get('note', '')
        
        if not all([squadra_id, cliente_id, data_turno]):
            return JsonResponse({'status': 'error', 'error': 'Dati mancanti'})
        
        squadra = Squadra.objects.get(pk=squadra_id)
        cliente = Cliente.objects.get(pk=cliente_id)
        
        h1, m1 = map(int, ora_inizio.split(':'))
        h2, m2 = map(int, ora_fine.split(':'))
        t_inizio = dt_time(h1, m1)
        t_fine = dt_time(h2, m2)
        
        # Calcola durata in ore
        minuti_tot = (h2 * 60 + m2) - (h1 * 60 + m1)
        if minuti_tot <= 0:
            minuti_tot = 60
        durata_ore = Decimal(str(round(minuti_tot / 60, 2)))
        
        # Parse data
        parsed_date = dt_date.fromisoformat(data_turno)
        giorno_settimana = parsed_date.weekday()  # 0=Lunedì
        
        prog_feriale = None
        richiesta_str = None
        
        if tipo == 'ricorrente':
            # Disabilita signal per evitare rigenerazione massiva turni (365 giorni)
            from django.db.models.signals import post_save
            from .signals import on_programmazione_save
            post_save.disconnect(on_programmazione_save, sender=ProgrammazioneRicorrente)
            try:
                prog_feriale = ProgrammazioneRicorrente(
                    cliente=cliente,
                    tipo_ripetizione='SETTIMANALE',
                    giorno_settimana=giorno_settimana,
                    ora_inizio=t_inizio,
                    durata=durata_ore,
                    squadra_abituale=squadra,
                    data_inizio_contratto=parsed_date,
                )
                prog_feriale.save()
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
        from .models import AssegnazioneTurno, Cliente
        from datetime import time as dt_time
        
        assign = AssegnazioneTurno.objects.get(pk=assign_id)
        
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
        
        assign.save()
        return JsonResponse({'status': 'ok', 'message': 'Turno aggiornato'})
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


def get_squadre_clienti_json(request):
    """Ritorna JSON con squadre e clienti per la modale del calendario."""
    from .models import Squadra, Cliente
    
    squadre = list(Squadra.objects.all().values('id', 'nome'))
    clienti = list(Cliente.objects.all().order_by('ragione_sociale').values('id', 'ragione_sociale'))
    
    return JsonResponse({'squadre': squadre, 'clienti': clienti})


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
            
            # Gestione messaggi di testo
            message = data.get('message', {})
            chat = message.get('chat', {})
            text = message.get('text', '')
            chat_id = str(chat.get('id', ''))
            first_name = chat.get('first_name', 'Utente')
            
            if chat_id and text:
                # Salva messaggio ricevuto nel database
                try:
                    from .models import MessaggioChat, Dipendente
                    dip = Dipendente.objects.filter(telegram_chat_id=chat_id).first()
                    if dip:
                        MessaggioChat.objects.create(
                            dipendente=dip, testo=text, direzione='IN'
                        )
                except Exception:
                    pass
                
                response = handle_telegram_message(chat_id, text, sender_name=first_name)
                
                if response and token:
                    import requests as req
                    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    
                    if isinstance(response, dict):
                        payload = {'chat_id': chat_id, 'text': response['text']}
                        if response.get('reply_markup'):
                            payload['reply_markup'] = response['reply_markup']
                    else:
                        payload = {'chat_id': chat_id, 'text': response}
                    
                    try:
                        req.post(send_url, json=payload)
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
        if model_name.lower() == 'timetracking':
            item.is_validated = not item.is_validated
            new_state = item.is_validated
        elif model_name.lower() == 'assenza':
            item.is_processed = not item.is_processed
            new_state = item.is_processed
        elif model_name.lower() == 'segnalazione':
            item.risolto = not item.risolto
            new_state = item.risolto
            
        item.save()
        return HttpResponse(json.dumps({'status': 'ok', 'new_state': new_state}), content_type='application/json')
        
    except ModelClass.DoesNotExist:
        return HttpResponse('Item not found', status=404)
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

def manuale_view(request):
    return render(request, 'core/manuale.html')

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
    clienti = Cliente.objects.filter(
        ore_mensili_contratto__gt=0
    ).order_by('ragione_sociale')
    
    analisi = []
    sotto_soglia = []
    totale_fatturato = Decimal('0')
    somma_orari = []
    
    for cliente in clienti:
        importo = float(cliente.importo_mensile_contratto)
        ore_contratto = float(cliente.ore_mensili_contratto)
        importo_orario = round(importo / ore_contratto, 2) if ore_contratto > 0 else 0
        
        # Ore effettivamente lavorate nel mese selezionato
        from django.db.models import F, ExpressionWrapper, DurationField
        
        tt_records = TimeTracking.objects.filter(
            assegnazione__cliente=cliente,
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
            'cliente': cliente.ragione_sociale,
            'cliente_id': cliente.pk,
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
        
        totale_fatturato += cliente.importo_mensile_contratto
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

    # Calcola contratti sotto soglia
    clienti = Cliente.objects.filter(ore_mensili_contratto__gt=0).order_by('ragione_sociale')
    sotto_soglia = []

    for cliente in clienti:
        importo = float(cliente.importo_mensile_contratto)
        ore_contratto = float(cliente.ore_mensili_contratto)
        importo_orario = round(importo / ore_contratto, 2) if ore_contratto > 0 else 0

        # Ore lavorate
        tt_records = TimeTracking.objects.filter(
            assegnazione__cliente=cliente,
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
                'cliente': cliente.ragione_sociale,
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
