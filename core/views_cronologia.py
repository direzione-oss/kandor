"""
Vista per la Cronologia Lavorazioni & Rollback (UNDO) di Kandor ERP.
Riservata ai soli Responsabili abilitati dal Programmatore e al Super-Admin.
"""
from datetime import datetime, time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .accessi_service import is_utente_programmatore, get_sezioni_abilitate_per_request
from .audit_service import popola_seed_cronologia_se_vuoto
from .models import RegistroOperazione


@login_required
def cronologia_lavorazioni_view(request):
    """
    Dashboard interattiva per visualizzare la cronologia delle lavorazioni
    e permettere ai responsabili abilitati di controllare e annullare (UNDO) le operazioni.
    """
    user = request.user
    is_prog = is_utente_programmatore(user)
    sezioni_abilitate = get_sezioni_abilitate_per_request(request)

    # Controllo abilitazione: deve essere Programmatore oppure avere 'cronologia_lavorazioni' abilitata
    if not is_prog and 'cronologia_lavorazioni' not in sezioni_abilitate:
        messages.error(
            request,
            "⛔ Non disponi dell'abilitazione per consultare la Cronologia Lavorazioni e il modulo UNDO. "
            "Richiedi l'accesso all'account Programmatore."
        )
        return HttpResponseRedirect('/admin/')

    # Popola seed dimostrativo/iniziale se il registro è vuoto
    popola_seed_cronologia_se_vuoto()

    # Gestione POST (esecuzione UNDO)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'esegui_undo':
            op_id = request.POST.get('operazione_id')
            motivo = request.POST.get('motivo', '').strip()
            operazione = get_object_or_404(RegistroOperazione, pk=op_id)

            successo, msg = operazione.esegui_undo(user, motivo=motivo)
            if successo:
                messages.success(request, f"↩️ Operazione annullata: {msg}")
            else:
                messages.error(request, f"❌ Errore annullamento: {msg}")

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
                return JsonResponse({
                    'success': successo,
                    'message': msg,
                    'operazione_id': operazione.id,
                    'annullata': operazione.annullata,
                })
            return HttpResponseRedirect(request.get_full_path())

    # Filtri GET
    qs = RegistroOperazione.objects.select_related('utente', 'annullata_da').all()

    modulo_f = request.GET.get('modulo', '').strip()
    if modulo_f:
        qs = qs.filter(modulo=modulo_f)

    tipo_f = request.GET.get('tipo_azione', '').strip()
    if tipo_f:
        qs = qs.filter(tipo_azione=tipo_f)

    stato_f = request.GET.get('stato', '').strip()
    if stato_f == 'attive':
        qs = qs.filter(annullata=False)
    elif stato_f == 'annullate':
        qs = qs.filter(annullata=True)

    utente_id_f = request.GET.get('utente_id', '').strip()
    if utente_id_f:
        qs = qs.filter(utente_id=utente_id_f)

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(titolo__icontains=q) |
            Q(dettagli__icontains=q) |
            Q(oggetto_descrizione__icontains=q) |
            Q(oggetto_id__icontains=q) |
            Q(motivo_annullamento__icontains=q)
        )

    data_da = request.GET.get('data_da', '').strip()
    if data_da:
        try:
            d_da = datetime.strptime(data_da, '%Y-%m-%d').date()
            dt_da = timezone.make_aware(datetime.combine(d_da, time.min))
            qs = qs.filter(timestamp__gte=dt_da)
        except ValueError:
            pass

    data_a = request.GET.get('data_a', '').strip()
    if data_a:
        try:
            d_a = datetime.strptime(data_a, '%Y-%m-%d').date()
            dt_a = timezone.make_aware(datetime.combine(d_a, time.max))
            qs = qs.filter(timestamp__lte=dt_a)
        except ValueError:
            pass

    # Statistiche rapide per la testata
    oggi = timezone.now().date()
    oggi_min = timezone.make_aware(datetime.combine(oggi, time.min))
    totale_operazioni = RegistroOperazione.objects.count()
    operazioni_oggi = RegistroOperazione.objects.filter(timestamp__gte=oggi_min).count()
    operazioni_annullate = RegistroOperazione.objects.filter(annullata=True).count()
    operatori_count = RegistroOperazione.objects.exclude(utente__isnull=True).values('utente').distinct().count()

    # Paginazione (30 per pagina)
    paginator = Paginator(qs, 30)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Lista utenti che hanno fatto almeno un'operazione per la select
    utenti_ids = RegistroOperazione.objects.exclude(utente__isnull=True).values_list('utente_id', flat=True).distinct()
    utenti_filtro = User.objects.filter(id__in=utenti_ids).order_by('first_name', 'last_name', 'username')

    context = {
        'page_obj': page_obj,
        'operazioni': page_obj.object_list,
        'totale_operazioni': totale_operazioni,
        'operazioni_oggi': operazioni_oggi,
        'operazioni_annullate': operazioni_annullate,
        'operatori_count': operatori_count,
        'modulo_choices': RegistroOperazione.MODULO_CHOICES,
        'tipo_azione_choices': RegistroOperazione.TIPO_AZIONE_CHOICES,
        'utenti_filtro': utenti_filtro,
        'filtri': {
            'modulo': modulo_f,
            'tipo_azione': tipo_f,
            'stato': stato_f,
            'utente_id': utente_id_f,
            'q': q,
            'data_da': data_da,
            'data_a': data_a,
        },
        'is_programmatore_reale': is_prog,
    }

    return render(request, 'core/cronologia_lavorazioni.html', context)
