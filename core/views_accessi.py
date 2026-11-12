from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .accessi_service import (
    CATALOGO_SEZIONI_PORTALE,
    DEFAULT_CODICI_RESPONSABILE,
    TUTTI_CODICI_SEZIONI,
    _genera_password_default,
    _genera_username_da_dipendente,
    assicura_profili_accesso_portale,
    is_utente_programmatore,
)
from .models import Dipendente, ProfiloAccessoPortale


def gestione_accessi_view(request):
    """
    Console riservata al Programmatore (Serra Gian Carlo) per:
    - Visualizzare e gestire il proprio account Programmatore (che vede tutte le sezioni)
    - Abilitare o disabilitare con 1 click le singole sezioni che ciascun Responsabile
      può visualizzare nel proprio accesso personale al portale.
    """
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/admin/login/?next=/gestione-accessi/')

    if not is_utente_programmatore(request.user):
        messages.error(request, "⛔ Accesso riservato all'account Programmatore (Gian Carlo Serra).")
        return HttpResponseRedirect('/admin/')

    assicura_profili_accesso_portale()

    # Se si apre la console Programmatore, eventuale uscita rapida dalla preview se richiesto
    if request.GET.get('exit_preview') == '1' and hasattr(request, 'session'):
        request.session.pop('preview_responsabile_id', None)
        return HttpResponseRedirect('/gestione-accessi/')

    profilo_programmatore = (
        ProfiloAccessoPortale.objects.filter(ruolo='PROGRAMMATORE')
        .select_related('user', 'dipendente')
        .first()
    )
    profili_responsabili = list(
        ProfiloAccessoPortale.objects.filter(ruolo='RESPONSABILE')
        .select_related('user', 'dipendente')
        .order_by('dipendente__cognome', 'dipendente__nome', 'user__username')
    )

    # Raggruppa il catalogo sezioni nei 3 gruppi logici
    gruppi_sezioni = [
        {
            'codice': 'OPERAZIONI',
            'titolo': '1. ⚡ Card Operazioni Frequenti & Moduli Principali',
            'sottotitolo': 'I riquadri principali nella parte alta della Dashboard (Jolly, Report Ore, Paghe, Buste Paga, Chat, Procedure, IA, ecc.)',
            'sezioni': [s for s in CATALOGO_SEZIONI_PORTALE if s['gruppo'] == 'OPERAZIONI'],
        },
        {
            'codice': 'WIDGET',
            'titolo': '2. 📊 Widget, Scadenze & Calendario Settimanale in Dashboard',
            'sottotitolo': 'I pannelli informativi centrali e il Calendario Interattivo della Programmazione Settimanale',
            'sezioni': [s for s in CATALOGO_SEZIONI_PORTALE if s['gruppo'] == 'WIDGET'],
        },
        {
            'codice': 'TABELLE',
            'titolo': '3. 🗂️ Voci di Operatività Giornaliera, Anagrafiche & Sistema',
            'sottotitolo': 'Le singole voci cliccabili nelle tabelle in fondo alla Dashboard (Dipendenti, Clienti, Squadre, Mezzi, Turni, Assenze, ecc.)',
            'sezioni': [s for s in CATALOGO_SEZIONI_PORTALE if s['gruppo'] == 'TABELLE'],
        },
    ]

    # Dipendenti attivi non ancora associati a un profilo accesso (per eventuale aggiunta nuovo responsabile)
    dips_con_profilo = set(
        ProfiloAccessoPortale.objects.exclude(dipendente__isnull=True).values_list('dipendente_id', flat=True)
    )
    dipendenti_disponibili = list(
        Dipendente.objects.exclude(stato='INATTIVO')
        .exclude(id__in=dips_con_profilo)
        .order_by('cognome', 'nome')
    )

    context = {
        'title': 'Console Programmatore — Gestione Accessi & Sezioni Responsabili',
        'profilo_programmatore': profilo_programmatore,
        'profili_responsabili': profili_responsabili,
        'gruppi_sezioni': gruppi_sezioni,
        'totale_sezioni': len(TUTTI_CODICI_SEZIONI),
        'tutti_codici_json': TUTTI_CODICI_SEZIONI,
        'default_codici_json': DEFAULT_CODICI_RESPONSABILE,
        'dipendenti_disponibili': dipendenti_disponibili,
    }
    return render(request, 'admin/gestione_accessi.html', context)


@require_POST
def gestione_accessi_api_view(request):
    """
    API JSON per il salvataggio istantaneo delle sezioni abilitate e delle credenziali
    da parte del Programmatore (Serra Gian Carlo).
    """
    if not is_utente_programmatore(request.user):
        return JsonResponse({'ok': False, 'error': 'Operazione riservata al Programmatore (Gian Carlo Serra).'}, status=403)

    action = (request.POST.get('action') or '').strip()

    if action == 'toggle_sezione':
        prof_id = request.POST.get('profilo_id')
        codice = (request.POST.get('codice') or '').strip()
        abilitata = request.POST.get('abilitata') == '1'

        prof = get_object_or_404(ProfiloAccessoPortale, pk=prof_id)
        if prof.ruolo == 'PROGRAMMATORE':
            return JsonResponse({'ok': True, 'sezioni_abilitate': TUTTI_CODICI_SEZIONI, 'count': len(TUTTI_CODICI_SEZIONI)})

        correnti = list(prof.sezioni_abilitate or [])
        if abilitata and codice in TUTTI_CODICI_SEZIONI and codice not in correnti:
            correnti.append(codice)
        elif not abilitata and codice in correnti:
            correnti.remove(codice)

        prof.sezioni_abilitate = correnti
        prof.save(update_fields=['sezioni_abilitate', 'updated_at'])
        return JsonResponse({
            'ok': True,
            'profilo_id': prof.pk,
            'sezioni_abilitate': correnti,
            'count': len(correnti),
            'totale': len(TUTTI_CODICI_SEZIONI),
        })

    if action == 'set_preset_sezioni':
        prof_id = request.POST.get('profilo_id')
        preset = (request.POST.get('preset') or '').strip().upper()
        prof = get_object_or_404(ProfiloAccessoPortale, pk=prof_id)

        if prof.ruolo == 'PROGRAMMATORE':
            nuove = list(TUTTI_CODICI_SEZIONI)
        elif preset == 'TUTTE':
            nuove = list(TUTTI_CODICI_SEZIONI)
        elif preset == 'NESSUNA':
            nuove = []
        elif preset == 'OPERATIVO_BASE':
            nuove = [
                'jolly', 'report_ore', 'chat_telegram', 'app_dipendenti', 'procedure', 'guide_manuali',
                'widget_procedure_evidenza', 'widget_telegram_feed', 'widget_calendario_settimanale',
                'mod_AssegnazioneTurno', 'mod_Assenza', 'mod_TimeTracking', 'mod_Turno', 'mod_ProceduraAvviata',
                'mod_Dipendente', 'mod_Cliente', 'mod_Squadra', 'mod_Mezzo',
            ]
        else:
            nuove = list(DEFAULT_CODICI_RESPONSABILE)

        prof.sezioni_abilitate = nuove
        prof.save(update_fields=['sezioni_abilitate', 'updated_at'])
        return JsonResponse({
            'ok': True,
            'profilo_id': prof.pk,
            'sezioni_abilitate': nuove,
            'count': len(nuove),
            'totale': len(TUTTI_CODICI_SEZIONI),
        })

    if action == 'copia_sezioni_da':
        target_id = request.POST.get('target_profilo_id')
        source_id = request.POST.get('source_profilo_id')
        target_prof = get_object_or_404(ProfiloAccessoPortale, pk=target_id)
        source_prof = get_object_or_404(ProfiloAccessoPortale, pk=source_id)

        nuove = list(source_prof.sezioni_abilitate or [])
        target_prof.sezioni_abilitate = nuove
        target_prof.save(update_fields=['sezioni_abilitate', 'updated_at'])
        return JsonResponse({
            'ok': True,
            'profilo_id': target_prof.pk,
            'sezioni_abilitate': nuove,
            'count': len(nuove),
            'totale': len(TUTTI_CODICI_SEZIONI),
        })

    if action == 'aggiorna_credenziali':
        prof_id = request.POST.get('profilo_id')
        nuovo_username = (request.POST.get('username') or '').strip()
        nuova_password = (request.POST.get('password') or '').strip()
        attivo = request.POST.get('attivo', '1') == '1'

        prof = get_object_or_404(ProfiloAccessoPortale.objects.select_related('user'), pk=prof_id)
        u = prof.user

        if nuovo_username and nuovo_username.lower() != u.username.lower():
            if User.objects.filter(username__iexact=nuovo_username).exclude(pk=u.pk).exists():
                return JsonResponse({'ok': False, 'error': f"Lo username '{nuovo_username}' è già utilizzato da un altro utente."})
            u.username = nuovo_username

        if nuova_password:
            u.set_password(nuova_password)
            prof.password_visibile = nuova_password

        if prof.ruolo != 'PROGRAMMATORE':
            prof.attivo = attivo
            u.is_active = attivo
        else:
            prof.attivo = True
            u.is_active = True

        u.is_staff = True
        u.is_superuser = True
        u.save()
        prof.save()

        return JsonResponse({
            'ok': True,
            'profilo_id': prof.pk,
            'username': u.username,
            'password_visibile': prof.password_visibile,
            'attivo': prof.attivo,
        })

    if action == 'crea_profilo_responsabile':
        dip_id = request.POST.get('dipendente_id')
        dip = get_object_or_404(Dipendente, pk=dip_id)
        if ProfiloAccessoPortale.objects.filter(dipendente=dip).exists():
            return JsonResponse({'ok': False, 'error': 'Questo responsabile ha già un profilo di accesso configurato.'})

        base_uname = (request.POST.get('username') or '').strip() or _genera_username_da_dipendente(dip)
        pwd = (request.POST.get('password') or '').strip() or _genera_password_default(dip, is_prog=False)

        uname_candidate = base_uname
        counter = 2
        while User.objects.filter(username__iexact=uname_candidate).exists():
            uname_candidate = f"{base_uname}{counter}"
            counter += 1

        u = User(
            username=uname_candidate,
            first_name=(dip.nome or '').strip().title(),
            last_name=(dip.cognome or '').strip().title(),
            email=(dip.email or '').strip(),
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        u.set_password(pwd)
        u.save()

        # Abilita anche il flag responsabile notifiche se non attivo
        if not dip.riceve_notifiche_messaggi:
            Dipendente.objects.filter(pk=dip.pk).update(riceve_notifiche_messaggi=True)

        prof = ProfiloAccessoPortale.objects.create(
            user=u,
            dipendente=dip,
            ruolo='RESPONSABILE',
            password_visibile=pwd,
            sezioni_abilitate=list(DEFAULT_CODICI_RESPONSABILE),
            attivo=True,
        )
        return JsonResponse({'ok': True, 'profilo_id': prof.pk})

    return JsonResponse({'ok': False, 'error': f'Azione non valida: {action}'}, status=400)
