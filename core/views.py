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
from django.http import HttpResponse, HttpResponseRedirect
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
    last_message = None
    selected_employee_id = None
    
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        msg = request.POST.get('message')
        
        if emp_id and msg:
            selected_employee_id = int(emp_id)
            last_message = msg
            
            emp = get_object_or_404(Dipendente, pk=emp_id)
            
            # INVIO REALE (Unica Modalità)
            from .utils_kandor_chat import send_telegram_message
            if not emp.telegram_chat_id:
                last_response = "⚠️ ERRORE: Questo dipendente non ha un Telegram Chat ID impostato."
            else:
                success = send_telegram_message(emp.telegram_chat_id, msg)
                if success:
                    last_response = f"✅ Messaggio inviato con successo a {emp.nome} (ID: {emp.telegram_chat_id})."
                else:
                    last_response = f"❌ Errore nell'invio del messaggio a {emp.nome}. Controlla il token del bot."

    employees = Dipendente.objects.filter(stato='ATTIVO')
    
    return render(request, 'core/chat_simulator.html', {
        'employees': employees,
        'last_response': last_response,
        'last_message': last_message,
        'selected_employee_id': selected_employee_id
    })

@csrf_exempt
def telegram_webhook_view(request):
    """
    Riceve aggiornamenti da Telegram (Webhook).
    Formato JSON standard Telegram.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Basic parsing per messaggi diretti
            message = data.get('message', {})
            chat = message.get('chat', {})
            text = message.get('text', '')
            chat_id = str(chat.get('id', ''))
            first_name = chat.get('first_name', 'Utente')
            
            if chat_id and text:
                response_text = handle_telegram_message(chat_id, text, sender_name=first_name)
                
                # Risposta Tramite API Diretta (più affidabile)
                if response_text:
                    token = settings.TELEGRAM_BOT_TOKEN
                    if token:
                        import requests
                        send_url = f"https://api.telegram.org/bot{token}/sendMessage"
                        try:
                            requests.post(send_url, json={'chat_id': chat_id, 'text': response_text})
                        except Exception as network_error:
                            print(f"[Telegram Error] Send Failed: {network_error}")

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
    
    # Parametri dal form
    try:
        soglia = float(request.GET.get('soglia', 15.0))
    except (ValueError, TypeError):
        soglia = 15.0
    
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
            stato_display = '<span style="background: #e74c3c; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">⚠️ SOTTO SOGLIA</span>'
        elif costo_effettivo_alert:
            stato_display = '<span style="background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">📊 DA VERIFICARE</span>'
        else:
            stato_display = '<span style="background: #27ae60; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">✅ OK</span>'
        
        row = {
            'cliente': cliente.ragione_sociale,
            'cliente_id': cliente.pk,
            'importo_mensile': f"{importo:,.2f}",
            'ore_contratto': ore_contratto,
            'importo_orario': f"{importo_orario:.2f}",
            'ore_lavorate': ore_lavorate,
            'costo_effettivo': f"{costo_effettivo:.2f}" if costo_effettivo else None,
            'diff_ore': diff_ore,
            'diff_ore_display': diff_ore_display,
            'sotto_soglia': is_sotto_soglia,
            'costo_effettivo_alert': costo_effettivo_alert,
            'stato_display': stato_display,
        }
        analisi.append(row)
        
        if is_sotto_soglia:
            sotto_soglia.append(row)
        
        totale_fatturato += cliente.importo_mensile_contratto
        if importo_orario > 0:
            somma_orari.append(importo_orario)
    
    media_oraria = round(sum(somma_orari) / len(somma_orari), 2) if somma_orari else 0
    
    ore_header = f'Ore Lavorate<br><small>{MESI_NOMI.get(mese, "")} {anno}</small>'
    
    context = {
        'analisi': analisi,
        'sotto_soglia': sotto_soglia,
        'soglia': soglia,
        'mese': mese,
        'mesi': mesi_list,
        'mese_nome': MESI_NOMI.get(mese, ''),
        'anno': anno,
        'ore_header': ore_header,
        'totale_contratti': len(analisi),
        'totale_fatturato': f"{totale_fatturato:,.2f}",
        'media_oraria': f"{media_oraria:.2f}",
    }
    return render(request, 'core/analisi_contratti.html', context)
