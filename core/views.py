from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import datetime, timedelta
from functools import wraps
import hmac
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


def _is_staff_or_titolare(request):
    """Restituisce True se l'utente è autenticato come staff/superuser o ha una sessione titolare attiva."""
    if getattr(request, 'user', None) and request.user.is_authenticated and (
        request.user.is_staff or request.user.is_superuser or hasattr(request.user, 'profilo_titolare')
    ):
        return True
    if hasattr(request, 'session') and request.session.get('titolare_id'):
        return True
    return False


def staff_or_titolare_required(view_fn):
    """Decoratore per viste HTML riservate ad Amministrazione / Staff / Titolari."""
    @wraps(view_fn)
    def _wrapped(request, *args, **kwargs):
        if not _is_staff_or_titolare(request):
            return HttpResponseRedirect(f'/admin/login/?next={request.path}')
        return view_fn(request, *args, **kwargs)
    return _wrapped


def staff_or_titolare_api_required(view_fn):
    """Decoratore per endpoint API/AJAX riservati ad Amministrazione / Staff / Titolari (ritorna 403 JSON)."""
    @wraps(view_fn)
    def _wrapped(request, *args, **kwargs):
        if not _is_staff_or_titolare(request):
            return JsonResponse({'status': 'error', 'ok': False, 'error': 'Autenticazione richiesta'}, status=403)
        return view_fn(request, *args, **kwargs)
    return _wrapped


@staff_or_titolare_required
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
                prefix = "[Tutti] "
                all_text = (prefix + msg) if msg else "[Tutti]"
                for dip in dipendenti:
                    try:
                        if send_and_record_telegram_to_employee(dip, text=all_text, attachments=attachments):
                            sent += 1
                    except Exception:
                        pass
                broadcast_result = f"Inviato a {sent} dipendenti"
                return HttpResponseRedirect(f'/chat-simulator/?broadcast=all&broadcast_ok={sent}')

            elif broadcast_target == 'responsabili':
                # Invio SOLO ai Responsabili abilitati (RIC.NOT. = True)
                responsabili_qs = Dipendente.objects.filter(stato='ATTIVO', riceve_notifiche_messaggi=True)
                sent = 0
                prefix = "[Responsabili] "
                resp_text = (prefix + msg) if msg else "[Responsabili]"
                for dip in responsabili_qs:
                    try:
                        if send_and_record_telegram_to_employee(dip, text=resp_text, attachments=attachments):
                            sent += 1
                    except Exception:
                        pass
                return HttpResponseRedirect(f'/chat-simulator/?broadcast=responsabili&broadcast_ok={sent}&sq=Responsabili')

            elif broadcast_target.startswith('squadra_'):
                # Invio a una SQUADRA
                sq_id = broadcast_target.replace('squadra_', '')
                try:
                    sq = Squadra.objects.get(pk=sq_id)
                    dipendenti = list(sq.componenti.filter(stato='ATTIVO'))
                    if sq.caposquadra and sq.caposquadra.stato == 'ATTIVO' and sq.caposquadra not in dipendenti:
                        dipendenti.insert(0, sq.caposquadra)
                    sent = 0
                    prefix = f"[{sq.nome}] "
                    sq_text = (prefix + msg) if msg else f"[{sq.nome}]"
                    for dip in dipendenti:
                        try:
                            if send_and_record_telegram_to_employee(dip, text=sq_text, attachments=attachments):
                                sent += 1
                        except Exception:
                            pass
                    return HttpResponseRedirect(f'/chat-simulator/?broadcast=squadra_{sq.id}&broadcast_ok={sent}&sq={sq.nome}')
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
    broadcast_prefix = ''
    if broadcast_mode == 'all':
        broadcast_label = 'Tutti i dipendenti'
        broadcast_prefix = '[Tutti]'
    elif broadcast_mode == 'responsabili':
        broadcast_label = '🔔 Solo i Responsabili'
        broadcast_prefix = '[Responsabili]'
    elif broadcast_mode.startswith('squadra_'):
        try:
            bsq = Squadra.objects.get(pk=broadcast_mode.replace('squadra_', ''))
            broadcast_label = f'Squadra {bsq.nome}'
            broadcast_prefix = f'[{bsq.nome}]'
        except Squadra.DoesNotExist:
            broadcast_mode = ''

    # Carica storico dei messaggi inviati al gruppo (Responsabili / Squadra / Tutti)
    if broadcast_mode and not selected_employee_id and broadcast_prefix:
        raw_bcast_msgs = list(
            MessaggioChat.objects.filter(
                direzione='OUT',
                testo__startswith=broadcast_prefix,
            )
            .select_related('dipendente')
            .order_by('-timestamp', '-id')[:400]
        )
        raw_bcast_msgs.reverse()
        grouped_bcast = []
        for rm in raw_bcast_msgs:
            dip_name = f"{rm.dipendente.nome} {rm.dipendente.cognome}" if rm.dipendente else ''
            if grouped_bcast:
                prev = grouped_bcast[-1]
                same_content = (
                    prev['testo'] == rm.testo
                    and prev['foto_url'] == (rm.foto_url or '')
                    and prev['allegato_url'] == (rm.allegato_url or '')
                    and prev['allegato_nome'] == (rm.allegato_nome or '')
                )
                time_diff = abs((rm.timestamp - prev['timestamp']).total_seconds()) if (rm.timestamp and prev['timestamp']) else 999
                if same_content and time_diff <= 30:
                    if dip_name and dip_name not in prev['destinatari_list']:
                        prev['destinatari_list'].append(dip_name)
                        prev['destinatari_count'] = len(prev['destinatari_list'])
                        prev['destinatari_elenco'] = ", ".join(prev['destinatari_list'])
                    continue
            grouped_bcast.append({
                'id': rm.id,
                'direzione': 'OUT',
                'testo': rm.testo,
                'foto_url': rm.foto_url or '',
                'allegato_url': rm.allegato_url or '',
                'allegato_nome': rm.allegato_nome or '',
                'timestamp': rm.timestamp,
                'destinatari_list': [dip_name] if dip_name else [],
                'destinatari_count': 1 if dip_name else 0,
                'destinatari_elenco': dip_name,
            })
        chat_messages = grouped_bcast

    from django.db.models import Count, Q
    employees = Dipendente.objects.filter(stato='ATTIVO').annotate(
        unread_count=Count('messaggi_chat', filter=Q(messaggi_chat__direzione='IN', messaggi_chat__letto=False))
    ).order_by('-unread_count', 'nome', 'cognome')
    responsabili = list(
        Dipendente.objects.filter(stato='ATTIVO', riceve_notifiche_messaggi=True).order_by('cognome', 'nome')
    )
    squadre = Squadra.objects.all()
    total_unread = sum(e.unread_count for e in employees)
    
    return render(request, 'core/chat_simulator.html', {
        'employees': employees,
        'responsabili': responsabili,
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
@staff_or_titolare_api_required
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
@staff_or_titolare_api_required
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

        # Gestione dipendenti esclusi (M2M) e sostituti diretti da scheda turno
        if 'dipendenti_esclusi' in data or 'sostituzioni_esclusi' in data:
            from .services import gestisci_sostituzioni_turno_admin
            esclusi = data.get('dipendenti_esclusi')
            if esclusi is None:
                esclusi = list(assign.dipendenti_esclusi.values_list('pk', flat=True))
            gestisci_sostituzioni_turno_admin(
                assign,
                esclusi,
                data.get('sostituzioni_esclusi')
            )

        return JsonResponse({'status': 'ok', 'message': 'Turno aggiornato'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@csrf_exempt
@staff_or_titolare_api_required
def assegna_sostituto_turno_ajax(request, assign_id):
    """
    Salva immediatamente dall'interno della scheda turno la deselezione di un componente
    e l'eventuale selezione del sostituto (senza necessità di validazione assenza).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    try:
        from .models import AssegnazioneTurno
        from .services import gestisci_sostituzioni_turno_admin

        assign = AssegnazioneTurno.objects.select_related('turno__squadra', 'cliente').get(pk=assign_id)
        data = json.loads(request.body) if request.body else {}

        esclusi = data.get('dipendenti_esclusi')
        if esclusi is None:
            esclusi = list(assign.dipendenti_esclusi.values_list('pk', flat=True))
            dip_id = data.get('dipendente_escluso_id')
            riattiva = data.get('riattiva_dipendente', False)
            if dip_id and str(dip_id).isdigit():
                dip_id_int = int(dip_id)
                if riattiva:
                    esclusi = [x for x in esclusi if x != dip_id_int]
                elif dip_id_int not in esclusi:
                    esclusi.append(dip_id_int)

        sost_map = data.get('sostituzioni_esclusi')
        if sost_map is None and data.get('dipendente_escluso_id'):
            sost_map = {str(data.get('dipendente_escluso_id')): data.get('sostituto_id')}

        gestisci_sostituzioni_turno_admin(assign, esclusi, sost_map)

        return JsonResponse({
            'status': 'ok',
            'message': 'Sostituzione turno aggiornata',
            'esclusi_ids': list(assign.dipendenti_esclusi.values_list('pk', flat=True)),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@csrf_exempt
@staff_or_titolare_api_required
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
@staff_or_titolare_api_required
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
@staff_or_titolare_api_required
def validate_ore_ajax(request, assign_id):
    """Valida, invalida o inserisce le ore di un'assegnazione turno per TUTTI i componenti attivi della squadra (escludendo gli assenti e gli esclusi)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'POST richiesto'})
    try:
        from .models import TimeTracking, AssegnazioneTurno, Dipendente, Assenza
        from decimal import Decimal
        from .models import RichiestaSostituzione

        assign = AssegnazioneTurno.objects.select_related('turno__squadra__caposquadra').get(pk=assign_id)
        squadra = assign.turno.squadra
        sq_nome = assign.turno.nome_squadra
        data_turno = assign.turno.data

        data = json.loads(request.body) if request.body else {}
        action = data.get('action', 'validate')
        ore_param = data.get('ore')
        note_param = (data.get('note') or '').strip() if 'note' in data else None
        validate_flag = data.get('validate', False) or (action == 'validate')

        if 'dipendenti_esclusi' in data or 'sostituzioni_esclusi' in data:
            from .services import gestisci_sostituzioni_turno_admin
            esclusi_input = data.get('dipendenti_esclusi')
            if esclusi_input is None:
                esclusi_input = list(assign.dipendenti_esclusi.values_list('pk', flat=True))
            gestisci_sostituzioni_turno_admin(
                assign,
                esclusi_input,
                data.get('sostituzioni_esclusi')
            )

        esclusi_ids = set(assign.dipendenti_esclusi.values_list('pk', flat=True))

        # Trova dipendenti della squadra in ASSENZA per questa data
        assenti_ids = set(Assenza.objects.filter(
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).exclude(stato_approvazione='RIFIUTATA').values_list('dipendente_id', flat=True))

        # Raccogli componenti attivi (non esclusi dal turno E NON IN ASSENZA)
        active_dips = []
        active_pks = set()
        if squadra:
            if squadra.caposquadra and squadra.caposquadra.pk not in esclusi_ids and squadra.caposquadra.pk not in assenti_ids:
                active_dips.append(squadra.caposquadra)
                active_pks.add(squadra.caposquadra.pk)
            for c in squadra.componenti.exclude(pk=squadra.caposquadra.pk if squadra.caposquadra else None):
                if c.pk not in esclusi_ids and c.pk not in assenti_ids and c.pk not in active_pks:
                    active_dips.append(c)
                    active_pks.add(c.pk)

        # Includi eventuali componenti storici (con TimeTracking già associato al turno)
        for tt_existing in TimeTracking.objects.filter(assegnazione=assign).select_related('dipendente'):
            dip_ex = tt_existing.dipendente
            if dip_ex and dip_ex.pk not in esclusi_ids and dip_ex.pk not in assenti_ids and dip_ex.pk not in active_pks:
                active_dips.append(dip_ex)
                active_pks.add(dip_ex.pk)

        # Includi eventuali SOSTITUTI confermati (COMPLETATA / ACCETTATA) per questa assegnazione
        sost_confermate = RichiestaSostituzione.objects.filter(
            assegnazione_originale=assign,
            stato__in=['ACCETTATA', 'COMPLETATA'],
            sostituto__isnull=False
        ).select_related('sostituto')
        for sc in sost_confermate:
            if sc.sostituto and sc.sostituto.pk not in active_pks and sc.sostituto.pk not in assenti_ids:
                active_dips.append(sc.sostituto)
                active_pks.add(sc.sostituto.pk)

        # Rimuovi eventuali TimeTracking registrati per i dipendenti in ASSENZA o esclusi per questo turno
        if assenti_ids:
            TimeTracking.objects.filter(assegnazione=assign, dipendente_id__in=assenti_ids).delete()
        if esclusi_ids:
            TimeTracking.objects.filter(assegnazione=assign, dipendente_id__in=esclusi_ids).delete()

        if not active_dips:
            return JsonResponse({
                'status': 'ok',
                'message': f"Tutti i componenti della squadra {sq_nome} sono in assenza o esclusi per la data {data_turno.strftime('%d/%m')}.",
                'validated': False,
                'count': 0,
            })

        # Determina il valore delle ore da applicare (globale o individuale per singolo dipendente)
        ore_per_dip_raw = data.get('ore_per_dipendente') or {}
        single_dip_id = data.get('dipendente_id')
        ore_val = None
        if ore_param is not None and str(ore_param).strip() != '':
            ore_val = Decimal(str(float(str(ore_param).replace(',', '.'))))
            if ore_val <= 0:
                return JsonResponse({
                    'status': 'error',
                    'error': 'Inserisci un numero di ore valido (> 0).',
                }, status=400)
        elif action != 'unvalidate':
            first_tt = TimeTracking.objects.filter(assegnazione=assign, dipendente__in=active_dips).order_by('id').first()
            if first_tt and (first_tt.ore_dichiarate is not None or first_tt.durata_ore):
                ore_val = Decimal(str(first_tt.ore_dichiarate or first_tt.durata_ore))
            elif assign.ore_previste_contratto:
                ore_val = Decimal(str(assign.ore_previste_contratto))
            elif assign.orario_inizio_previsto and assign.orario_fine_previsto:
                t1 = assign.orario_inizio_previsto
                t2 = assign.orario_fine_previsto
                minuti = (t2.hour * 60 + t2.minute) - (t1.hour * 60 + t1.minute)
                if minuti < 0:
                    minuti += 24 * 60
                ore_val = Decimal(str(round(minuti / 60.0, 2)))

        target_dips = active_dips
        if single_dip_id:
            try:
                sd_int = int(single_dip_id)
                target_dips = [d for d in active_dips if d.pk == sd_int]
                if not target_dips:
                    dip_extra = Dipendente.objects.filter(pk=sd_int).first()
                    if dip_extra and dip_extra.pk not in assenti_ids and dip_extra.pk not in esclusi_ids:
                        target_dips = [dip_extra]
            except (ValueError, TypeError):
                pass

        # Applica ai componenti attivi selezionati (con supporto ad ore individuali per dipendente)
        updated_count = 0
        if action == 'unvalidate':
            for tt in TimeTracking.objects.filter(assegnazione=assign, dipendente__in=target_dips):
                tt.is_validated = False
                tt.save()
                updated_count += 1
        else:
            for dip in target_dips:
                dip_ore = ore_val
                raw_ind = ore_per_dip_raw.get(str(dip.pk)) if isinstance(ore_per_dip_raw, dict) else None
                if raw_ind is not None and str(raw_ind).strip() != '':
                    try:
                        val_ind = Decimal(str(float(str(raw_ind).replace(',', '.'))))
                        if val_ind > 0:
                            dip_ore = val_ind
                    except (ValueError, TypeError):
                        pass

                default_note = note_param if note_param else f"Ore valide ({dip.cognome} {dip.nome} - {sq_nome})"
                existing_tts = list(TimeTracking.objects.filter(dipendente=dip, assegnazione=assign).order_by('id'))
                if existing_tts:
                    tt = existing_tts[0]
                    if len(existing_tts) > 1:
                        TimeTracking.objects.filter(id__in=[t.id for t in existing_tts[1:]]).delete()
                    if dip_ore is not None:
                        tt.ore_dichiarate = dip_ore
                    if note_param is not None and note_param != '':
                        tt.note = note_param
                    if validate_flag:
                        tt.is_validated = True
                    tt.save()
                else:
                    TimeTracking.objects.create(
                        dipendente=dip,
                        assegnazione=assign,
                        ore_dichiarate=dip_ore,
                        is_validated=validate_flag,
                        source='ADMIN',
                        note=default_note,
                    )
                updated_count += 1

        status_msg = "Ore validate" if (validate_flag and action != 'unvalidate') else ("Validazione rimossa" if action == 'unvalidate' else "Ore salvate")
        return JsonResponse({
            'status': 'ok',
            'message': f"{status_msg} per {updated_count} dipendente/i ({sq_nome})",
            'validated': validate_flag and action != 'unvalidate',
            'count': updated_count,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@staff_or_titolare_api_required
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


@staff_or_titolare_api_required
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
                'is_sostituto_turno': bool(sostituto_di),
                'escluso': (dip.pk in esclusi_ids) if not sostituto_di else False,
                'in_assenza': ass is not None,
                'assenza_id': ass.id if ass else None,
                'stato_approvazione': ass.stato_approvazione if ass else None,
                'tipo_assenza': ass.tipo if ass else None,
                'assenza_display': f"🏥 {ass.get_tipo_display()}" if ass else None,
                'richiesta_sostituzione_id': req_sost.id if req_sost else None,
                'richiesta_sostituzione_stato': req_sost.stato if req_sost else None,
                'sostituto_id': req_sost.sostituto_id if req_sost else None,
                'sostituto_assegnato': f"{req_sost.sostituto.cognome} {req_sost.sostituto.nome}" if (req_sost and req_sost.sostituto) else None,
                'ore_dichiarate': ore_d if not ass else None,
                'is_validated': (tt.is_validated if tt else False) if not ass else False,
                'source': tt.source if tt else None,
                'note': tt.note if tt else '',
            }

        componenti = []
        presenti_ids = set()
        squadra_orig_ids = set()
        if squadra:
            if squadra.caposquadra:
                componenti.append(_build_comp_dict(squadra.caposquadra, 'Caposquadra'))
                presenti_ids.add(squadra.caposquadra.pk)
                squadra_orig_ids.add(squadra.caposquadra.pk)
            for c in squadra.componenti.exclude(pk=squadra.caposquadra.pk if squadra.caposquadra else None):
                componenti.append(_build_comp_dict(c, 'Componente'))
                presenti_ids.add(c.pk)
                squadra_orig_ids.add(c.pk)

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

        # Costruisci l'elenco dei sostituti selezionabili direttamente dalla scheda turno
        sostituti_disponibili = []
        sost_seen_ids = set()
        try:
            from .services import trova_sostituti
            from .models import Dipendente
            cand_list = trova_sostituti(
                cliente=assign.cliente,
                data=data_turno,
                ora_inizio=assign.orario_inizio_previsto,
                ora_fine=assign.orario_fine_previsto,
                escludi_dipendenti_ids=list(squadra_orig_ids),
            )
            for s in cand_list:
                d_cand = s['dipendente']
                dist_val = round(s['distanza_km'], 1) if s['distanza_km'] != float('inf') else None
                sostituti_disponibili.append({
                    'id': d_cand.pk,
                    'nome': f"{d_cand.cognome} {d_cand.nome}",
                    'distanza_km': dist_val,
                    'ai_score': s.get('ai_score', 50),
                    'compatibilita': s.get('compatibilita', 'libero'),
                    'consigliato': True,
                })
                sost_seen_ids.add(d_cand.pk)

            # Includi anche eventuali altri dipendenti (es. già assegnati o su altri turni) come scelta manuale
            for d_extra in Dipendente.objects.exclude(pk__in=squadra_orig_ids).order_by('cognome', 'nome'):
                if d_extra.pk not in sost_seen_ids and d_extra.pk not in assenze_map:
                    sostituti_disponibili.append({
                        'id': d_extra.pk,
                        'nome': f"{d_extra.cognome} {d_extra.nome}",
                        'distanza_km': None,
                        'ai_score': None,
                        'compatibilita': 'altro',
                        'consigliato': False,
                    })
                    sost_seen_ids.add(d_extra.pk)
        except Exception:
            pass

        return JsonResponse({
            'componenti': componenti,
            'esclusi_ids': esclusi_ids,
            'sostituti_disponibili': sostituti_disponibili,
            'assign_id': assign.id,
            'ore_previste': float(assign.ore_previste_contratto) if assign.ore_previste_contratto else None,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


def _salva_foto_profilo_media(telegram_foto_url, dipendente_id):
    """
    Scarica la foto da Telegram e la salva in modo permanente nel volume Media locale (/app/media)
    sul campo Dipendente.foto.
    Ritorna l'URL permanente Media, prevenendo l'uso di URL Telegram temporanei.
    """
    try:
        import requests as req
        from django.core.files.base import ContentFile
        from .models import Dipendente

        resp = req.get(telegram_foto_url, timeout=15)
        if not resp.ok:
            return None
        foto_bytes = resp.content

        dip = Dipendente.objects.filter(pk=dipendente_id).first()
        file_name = f"dipendente_{dipendente_id}.jpg"
        if dip:
            dip.foto.save(file_name, ContentFile(foto_bytes), save=True)
            return dip.foto.url if dip.foto else None
    except Exception as e:
        print(f"[FotoProfiloUpload] Errore salvataggio foto profilo: {e}")

    return None


def _salva_chat_foto_media(telegram_foto_url, chat_id):
    """
    Scarica la foto dalla chat Telegram e la salva in modo permanente nel volume Media locale (/app/media).
    Ritorna l'URL permanente Media o il Telegram URL come fallback.
    """
    try:
        import requests as req
        import uuid
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile

        resp = req.get(telegram_foto_url, timeout=15)
        if not resp.ok:
            return telegram_foto_url
        foto_bytes = resp.content

        file_name = f"chat_images/chat_{chat_id}_{uuid.uuid4().hex[:8]}.jpg"
        saved_path = default_storage.save(file_name, ContentFile(foto_bytes))
        return default_storage.url(saved_path)
    except Exception as e:
        print(f"[ChatFotoUpload] Errore salvataggio foto chat: {e}")

    return telegram_foto_url


# Alias per retrocompatibilità
_upload_foto_profilo_supabase = _salva_foto_profilo_media
_upload_chat_foto_supabase = _salva_chat_foto_media

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
                        # Salva risposta bot nello storico (anche se il dipendente si è appena accreditato)
                        if not dip:
                            from .models import Dipendente
                            dip = Dipendente.objects.filter(telegram_chat_id=chat_id).first()
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
@staff_or_titolare_api_required
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

@staff_or_titolare_required
def manuale_pdf_view(request):
    """Restituisce il file PDF completo con screenshot del Manuale Utente Kandor (v3.2)."""
    import os
    from django.http import FileResponse, Http404
    pdf_path = os.path.join(settings.BASE_DIR, 'MANUALE_UTENTE_KANDOR.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(open(pdf_path, 'rb'), content_type='application/pdf', filename='MANUALE_UTENTE_KANDOR.pdf')
    raise Http404("File PDF del manuale non trovato.")


def manuale_dipendente_pdf_view(request):
    """Restituisce il file PDF della Guida Operativa Dipendente Kandor (v3.2)."""
    import os
    from django.http import FileResponse, Http404
    pdf_path = os.path.join(settings.BASE_DIR, 'MANUALE_DIPENDENTE_KANDOR.pdf')
    if os.path.exists(pdf_path):
        return FileResponse(open(pdf_path, 'rb'), content_type='application/pdf', filename='MANUALE_DIPENDENTE_KANDOR.pdf')
    raise Http404("File PDF del manuale dipendente non trovato.")


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


@staff_or_titolare_required
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
        assegnazione__turno__data__gte=lun, assegnazione__turno__data__lte=ven
    ).aggregate(tot=Sum('ore_dichiarate'))
    ore_settimana = round(float(ore_r['tot'] or 0), 1)
    
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

    # --- Contabilità Industriale & Semaforo Direzionale MOL ---
    contabilita_industriale = {}
    cantieri_perdita = 0
    cantieri_erosione = 0
    cantieri_ottimi = 0
    richieste_materiali_aperte = 0
    lavori_extra_da_fatturare = 0
    ispezioni_mese = 0
    try:
        from .views_erp_pro import calcola_contabilita_industriale_mese
        from .models import ConsegnaRichiestaMateriale, RichiestaStraordinaria, IspezioneQualitaCantiere
        contabilita_industriale = calcola_contabilita_industriale_mese(
            anno=oggi.year,
            mese=oggi.month,
            soglia_oraria=soglia_default,
        )
        cantieri_perdita = len(contabilita_industriale.get('cantieri_perdita', []))
        cantieri_erosione = len(contabilita_industriale.get('cantieri_erosione', []))
        cantieri_ottimi = len(contabilita_industriale.get('cantieri_ottimi', []))
        if cantieri_perdita > 0:
            alerts.append({
                'msg': f'🔴 {cantieri_perdita} cantiere/i in PERDITA o sotto soglia nel mese corrente (verifica MOL in Contabilità Industriale)',
                'critico': True,
            })
        elif cantieri_erosione > 0:
            alerts.append({
                'msg': f'🟠 {cantieri_erosione} cantiere/i in EROSIONE DI MARGINE nel mese corrente',
                'critico': False,
            })
        richieste_materiali_aperte = ConsegnaRichiestaMateriale.objects.filter(stato__in=['RICHIESTA', 'IN_CONSEGNA']).count()
        if richieste_materiali_aperte > 0:
            alerts.append({
                'msg': f'🧴 {richieste_materiali_aperte} richiesta/e materiali dai cantieri in attesa di consegna',
                'critico': False,
            })
        lavori_extra_da_fatturare = RichiestaStraordinaria.objects.filter(stato_fatturazione='DA_FATTURARE').count()
        if lavori_extra_da_fatturare > 0:
            alerts.append({
                'msg': f'🧾 {lavori_extra_da_fatturare} lavoro/i straordinario/i DA FATTURARE',
                'critico': False,
            })
        ispezioni_mese = IspezioneQualitaCantiere.objects.filter(data_ispezione__year=oggi.year, data_ispezione__month=oggi.month).count()
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
        'contabilita_industriale': contabilita_industriale,
        'cantieri_perdita': cantieri_perdita,
        'cantieri_erosione': cantieri_erosione,
        'cantieri_ottimi': cantieri_ottimi,
        'richieste_materiali_aperte': richieste_materiali_aperte,
        'lavori_extra_da_fatturare': lavori_extra_da_fatturare,
        'ispezioni_mese': ispezioni_mese,
    })


@csrf_exempt
def titolari_riepilogo_view(request):
    """Endpoint per trigger esterno del riepilogo settimanale (cron-job.org).
    Chiamare con GET /titolari/riepilogo/?token=SECRET
    Configurare SECRET in settings come RIEPILOGO_TOKEN.
    """
    from django.conf import settings
    token_atteso = (getattr(settings, 'RIEPILOGO_TOKEN', '') or '').strip()
    token_ricevuto = (request.GET.get('token') or request.headers.get('X-Cron-Token') or '').strip()
    
    if not token_atteso or not token_ricevuto or not hmac.compare_digest(token_ricevuto, token_atteso):
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
<div style="position: fixed; bottom: 20px; right: 20px; display: flex; gap: 10px;" class="print-btn">
    <a href="/manuale-dipendente/pdf/" target="_blank" style="background: #10b981; color: white; text-decoration: none; padding: 12px 20px; border-radius: 8px; font-size: 15px; font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">⬇️ Scarica PDF Dipendente</a>
    <button onclick="window.print()" style="background: #ff6f00; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 15px; font-weight: bold; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">🖨️ Stampa</button>
</div>
</body>
</html>"""
    
    return HttpResponse(page_html)

@staff_or_titolare_required
def extend_contract_view(request, prog_id):
    """Prolunga un contratto di 12 mesi e rigenera i turni."""
    from .models import ProgrammazioneRicorrente
    from .signals import _genera_turni_singola_programmazione
    from dateutil.relativedelta import relativedelta
    
    prog = get_object_or_404(ProgrammazioneRicorrente, pk=prog_id)
    
    if prog.data_fine_contratto:
        old_date = prog.data_fine_contratto
        # Proroga di 12 mesi dalla data fine attuale
        prog.data_fine_contratto = old_date + relativedelta(months=12)
        prog.save()
        
        # Rigenera i turni della programmazione per coprire il nuovo periodo
        count = _genera_turni_singola_programmazione(prog, days=365, only_future=True)
        
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


@csrf_exempt
@staff_or_titolare_api_required
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
@staff_or_titolare_api_required
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
@staff_or_titolare_api_required
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
        qualifica_richiesta=qualifica,
        includi_tutti_attivi=True,
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
            'ha_telegram': bool(getattr(dip, 'telegram_chat_id', None)),
            'ai_score': r.get('ai_score', 50),
            'ai_motivi': r.get('ai_motivi', []),
            'presenze_cliente': r.get('presenze_cliente', 0),
            'ore_settimana': r.get('ore_settimana', 0.0),
            'conformita_ok': r.get('conformita_ok', True),
            'occupato_fascia': r.get('occupato_fascia', False),
            'impegni_concomitanti': r.get('impegni_concomitanti', []),
            'is_sostituto_anagrafica': r.get('is_sostituto_anagrafica', True),
        })
    
    return JsonResponse({'ok': True, 'sostituti': sostituti_list})


@csrf_exempt
@staff_or_titolare_api_required
def get_sostituti_richiesta_api(request, richiesta_id):
    """
    Ritorna l'elenco di tutti i sostituti compatibili/disponibili per una richiesta di sostituzione,
    evidenziando quali sono stati precedentemente selezionati, l'ordine di selezione,
    l'eventuale sostituto attualmente contattato/assegnato e gli altri turni collegati alla stessa assenza.
    Include anche i dipendenti già impegnati in altri turni (con indicazione dell'orario) e quelli senza Telegram.
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
        qualifica_richiesta=qualifica,
        escludi_richiesta_id=richiesta.id,
        includi_tutti_attivi=True,
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
            'occupato_fascia': r.get('occupato_fascia', False),
            'impegni_concomitanti': r.get('impegni_concomitanti', []),
            'is_sostituto_anagrafica': r.get('is_sostituto_anagrafica', True),
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
                    'is_sostituto_corrente': (richiesta.sostituto_id == dip.id),
                    'occupato_fascia': False,
                    'impegni_concomitanti': [],
                    'is_sostituto_anagrafica': bool(dip.is_sostituto),
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
@staff_or_titolare_api_required
def invia_notifiche_sostituti_api(request):
    """
    Riceve l'elenco dei sostituti selezionati e il loro ordine di preferenza,
    aggiorna la RichiestaSostituzione e invia la notifica al primo sostituto in lista.
    Se il primo sostituto NON ha Telegram, lo conferma automaticamente dall'Ufficio!
    Se applica_a_periodo=True, imposta la stessa coda e invia/conferma anche sugli altri turni dell'assenza.
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
    richieste_ids_param = data.get('richieste_ids')

    if not richiesta_id:
        return JsonResponse({'ok': False, 'error': 'richiesta_id obbligatorio'}, status=400)

    if not isinstance(sostituti_ids, list) or len(sostituti_ids) == 0:
        return JsonResponse({'ok': False, 'error': 'Seleziona almeno un sostituto'}, status=400)

    from .models import RichiestaSostituzione, Dipendente, Assenza
    from .services import approva_e_invia_sostituto, assegna_sostituto_da_ufficio, get_richieste_sostituzione_per_assenza, avvia_sostituzione_per_assenza

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

    primo_dip = Dipendente.objects.filter(pk=valid_ids[0]).first()
    # Se il 1° sostituto selezionato NON ha Telegram (es. Ratti Claudio), l'Amministrazione lo conferma subito dall'Ufficio!
    if primo_dip and not getattr(primo_dip, 'telegram_chat_id', None):
        res_uff = assegna_sostituto_da_ufficio(
            richiesta_id=richiesta.pk,
            sostituto_id=primo_dip.pk,
            applica_a_periodo=applica_a_periodo,
            richieste_ids=richieste_ids_param,
        )
        if not res_uff.get('ok'):
            return JsonResponse({'ok': False, 'error': res_uff.get('error', 'Errore durante la conferma')}, status=400)
        primo_dip_nome = res_uff.get('sostituto_nome', str(primo_dip))
        turni_cnt = res_uff.get('turni_aggiornati', 1)
        extra_msg = f" su {turni_cnt} turni selezionati" if turni_cnt > 1 else ""
        return JsonResponse({
            'ok': True,
            'message': f"Il sostituto {primo_dip_nome} non utilizza Telegram: è stato CONFERMATO direttamente dall'Ufficio{extra_msg}!",
            'sostituto_corrente': primo_dip_nome,
            'totale_selezionati': len(valid_ids),
            'turni_aggiornati': turni_cnt,
        })

    richieste_target = [richiesta]
    clean_req_ids = [int(x) for x in richieste_ids_param if str(x).isdigit()] if isinstance(richieste_ids_param, list) else []
    if clean_req_ids:
        qs_sel = RichiestaSostituzione.objects.filter(
            pk__in=clean_req_ids,
            dipendente_assente=richiesta.dipendente_assente,
        ).order_by('assegnazione_originale__turno__data')
        if qs_sel.exists():
            richieste_target = list(qs_sel)
    elif applica_a_periodo:
        data_turno = richiesta.assegnazione_originale.turno.data
        assenza = Assenza.objects.filter(
            dipendente=richiesta.dipendente_assente,
            data_inizio__lte=data_turno,
            data_fine__gte=data_turno
        ).order_by('-id').first()
        if assenza:
            if assenza.stato_approvazione == 'APPROVATA':
                avvia_sostituzione_per_assenza(assenza)
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
@staff_or_titolare_api_required
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
@staff_or_titolare_api_required
def conferma_sostituto_ufficio_api(request):
    """
    Endpoint per confermare direttamente dall'ufficio (Amministrazione) il sostituto
    per una RichiestaSostituzione, sia scegliendo un candidato libero dalla lista,
    sia confermando per conto del dipendente a cui era già stata inviata la richiesta Telegram
    (se non riesce a rispondere dal cellulare).
    Supporta anche l'azione 'passa_successivo' e 'non_sostituire'.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'ok': False, 'error': 'Dati JSON non validi'}, status=400)

    richiesta_id = data.get('richiesta_id')
    azione = data.get('azione', 'conferma')  # 'conferma', 'passa_successivo', 'non_sostituire'

    if not richiesta_id:
        return JsonResponse({'ok': False, 'error': 'richiesta_id obbligatorio'}, status=400)

    if azione == 'passa_successivo':
        from .services import gestisci_risposta_sostituto
        richiesta = gestisci_risposta_sostituto(richiesta_id, accettato=False)
        if not richiesta:
            return JsonResponse({'ok': False, 'error': 'Impossibile passare al sostituto successivo'}, status=400)
        if richiesta.stato == 'INVIATA' and richiesta.sostituto:
            msg = f"Passato al candidato successivo: notifica inviata a {richiesta.sostituto.cognome} {richiesta.sostituto.nome}."
        elif richiesta.stato == 'COMPLETATA' and richiesta.sostituto:
            msg = f"Passato al candidato successivo ({richiesta.sostituto.cognome} {richiesta.sostituto.nome}) e confermato dall'Ufficio."
        else:
            msg = f"Lista candidati esaurita (stato: {richiesta.get_stato_display()}). Puoi confermare un sostituto direttamente dall'ufficio."
        return JsonResponse({
            'ok': True,
            'message': msg,
            'stato': richiesta.stato,
            'sostituto_corrente_id': richiesta.sostituto_id,
            'sostituto_corrente_nome': f"{richiesta.sostituto.cognome} {richiesta.sostituto.nome}" if richiesta.sostituto else None
        })

    if azione == 'non_sostituire':
        from .models import RichiestaSostituzione, Assenza, TimeTracking
        applica_a_periodo = bool(data.get('applica_a_periodo', False))
        try:
            richiesta = RichiestaSostituzione.objects.select_related('assegnazione_originale__turno', 'dipendente_assente').get(pk=richiesta_id)
        except RichiestaSostituzione.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Richiesta non trovata'}, status=404)
        targets = [richiesta]
        if applica_a_periodo:
            dt = richiesta.assegnazione_originale.turno.data
            ass = Assenza.objects.filter(dipendente=richiesta.dipendente_assente, data_inizio__lte=dt, data_fine__gte=dt).exclude(stato_approvazione='RIFIUTATA').order_by('-id').first()
            if ass:
                altre = RichiestaSostituzione.objects.filter(
                    dipendente_assente=richiesta.dipendente_assente,
                    assegnazione_originale__turno__data__gte=ass.data_inizio,
                    assegnazione_originale__turno__data__lte=ass.data_fine,
                ).exclude(pk=richiesta.pk).select_related('assegnazione_originale__turno')
                targets.extend(list(altre))
        for rq in targets:
            old_sost = rq.sostituto_id
            rq.sostituto = None
            rq.stato = 'NON_SOSTITUITO'
            rq.save(update_fields=['sostituto', 'stato'])
            if rq.dipendente_assente_id:
                TimeTracking.objects.filter(assegnazione=rq.assegnazione_originale, dipendente_id=rq.dipendente_assente_id).delete()
            if old_sost:
                TimeTracking.objects.filter(assegnazione=rq.assegnazione_originale, dipendente_id=old_sost).delete()
        return JsonResponse({
            'ok': True,
            'message': f"Turno segnato come Non Sostituito su {len(targets)} turno/i.",
            'turni_aggiornati': len(targets),
        })

    sostituto_id = data.get('sostituto_id')
    applica_a_periodo = bool(data.get('applica_a_periodo', False))
    richieste_ids_param = data.get('richieste_ids')

    from .services import assegna_sostituto_da_ufficio
    res = assegna_sostituto_da_ufficio(
        richiesta_id=richiesta_id,
        sostituto_id=sostituto_id,
        applica_a_periodo=applica_a_periodo,
        richieste_ids=richieste_ids_param,
    )
    if not res.get('ok'):
        return JsonResponse({'ok': False, 'error': res.get('error', 'Errore durante la conferma')}, status=400)

    return JsonResponse({
        'ok': True,
        'message': res.get('message', 'Sostituto confermato con successo'),
        'sostituto_nome': res.get('sostituto_nome'),
        'turni_aggiornati': res.get('turni_aggiornati', 1)
    })


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
    """
    Endpoint diagnostico di sistema: riservato esclusivamente ai Superuser autenticati.
    Non modifica né resetta mai alcuna password e non espone configurazioni sensibili.
    """
    import traceback
    from django.db import connection
    from django.http import JsonResponse
    from django.contrib.auth import get_user_model

    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'error': 'Accesso negato: privilegi di superuser richiesti.'}, status=403)

    info = {}
    try:
        connection.ensure_connection()
        info['connection'] = 'OK'

        tables = connection.introspection.table_names()
        info['tables_count'] = len(tables)
        info['migration_result'] = 'MIGRATION_OK'

        User = get_user_model()
        info['users_count'] = User.objects.count()

        # Test Widgets rendering
        from core.templatetags.dashboard_extras import (
            expiring_vehicles_widget, upcoming_birthdays_widget,
            weekly_schedule_widget, telegram_feed_widget, expiring_contracts_widget
        )
        try:
            expiring_vehicles_widget()
            info['widget_expiring_vehicles'] = 'OK'
        except Exception as e:
            info['widget_expiring_vehicles_error'] = str(e)

        try:
            upcoming_birthdays_widget()
            info['widget_upcoming_birthdays'] = 'OK'
        except Exception as e:
            info['widget_upcoming_birthdays_error'] = str(e)

        try:
            weekly_schedule_widget({'request': request})
            info['widget_weekly_schedule'] = 'OK'
        except Exception as e:
            info['widget_weekly_schedule_error'] = str(e)

        try:
            telegram_feed_widget()
            info['widget_telegram_feed'] = 'OK'
        except Exception as e:
            info['widget_telegram_feed_error'] = str(e)

        try:
            expiring_contracts_widget()
            info['widget_expiring_contracts'] = 'OK'
        except Exception as e:
            info['widget_expiring_contracts_error'] = str(e)

    except Exception as e:
        info['error'] = str(e)
        if settings.DEBUG:
            info['traceback'] = traceback.format_exc()

    return JsonResponse(info)




# ==============================================================================
# RE-EXPORT VISTE MODULARIZZATE (Paghe, Ore, Contratti, Centro IA, Procedure)
# ==============================================================================
from .views_paghe import (
    reconciliation_view,
    analisi_contratti_view,
    pdf_contratti_sotto_soglia,
    verifica_ore_view,
    pdf_verifica_ore,
    report_paghe_view,
    pdf_report_paghe,
    export_paghe_csv,
    salva_modifica_cedolino_ajax,
)
from .views_ia import (
    ia_hub_view,
    ia_auto_valida_ore_api,
    ia_invia_briefing_api,
    ia_mezzo_manutenzione_api,
    ia_analizza_documento_api,
)
from .views_procedure import (
    _serialize_pratica,
    _serialize_modello,
    gestione_procedure_view,
    gestione_procedure_api,
)
