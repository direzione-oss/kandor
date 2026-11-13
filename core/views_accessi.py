import os
import shutil
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
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


CATALOGO_MANUALI_PORTALE = {
    'programmatore': {
        'codice': 'programmatore',
        'numero': 1,
        'icona': '💻',
        'colore': '#1e40af',
        'bg_light': '#eff6ff',
        'border_color': '#93c5fd',
        'titolo': '1. Manuale Programmatore & Super-Admin',
        'sottotitolo': 'Governance Accessi, Gestione dei 3 Manuali, Architettura VPS & Suite Direzionale Completa',
        'destinatari': 'Gian Carlo Serra (Programmatore / Super-Admin)',
        'pdf_filename': 'MANUALE_PROGRAMMATORE_KANDOR.pdf',
        'docx_filename': 'MANUALE_PROGRAMMATORE_KANDOR.docx',
        'url_pdf': '/manuale-programmatore/pdf/',
        'url_web': '/manuale/',
        'url_docx': '/gestione-accessi/manuale/programmatore/docx/',
    },
    'admin': {
        'codice': 'admin',
        'numero': 2,
        'icona': '📘',
        'colore': '#047857',
        'bg_light': '#ecfdf5',
        'border_color': '#6ee7b7',
        'titolo': '2. Manuale Responsabili & Amministrazione',
        'sottotitolo': 'Introduzione Esaustiva alle Funzioni del Programma e Guida Operativa Passo-Passo (24 Capitoli)',
        'destinatari': 'Titolari, Responsabili d\'Area e Ufficio Amministrativo',
        'pdf_filename': 'MANUALE_UTENTE_KANDOR.pdf',
        'docx_filename': 'MANUALE_UTENTE_KANDOR.docx',
        'url_pdf': '/manuale/pdf/',
        'url_web': '/manuale/',
        'url_docx': '/gestione-accessi/manuale/admin/docx/',
    },
    'dipendente': {
        'codice': 'dipendente',
        'numero': 3,
        'icona': '📲',
        'colore': '#b45309',
        'bg_light': '#fffbeb',
        'border_color': '#fcd34d',
        'titolo': '3. Guida Operativa Dipendente (Web App & Telegram)',
        'sottotitolo': 'Manuale Passo-Passo per Smartphone (/app/) e Assistente Bot Telegram (@kandor_gestionale_bot)',
        'destinatari': 'Tutti i Dipendenti, Operatori di Cantiere e Capisquadra',
        'pdf_filename': 'MANUALE_DIPENDENTE_KANDOR.pdf',
        'docx_filename': 'MANUALE_DIPENDENTE_KANDOR.docx',
        'url_pdf': '/manuale-dipendente/pdf/',
        'url_web': '/manuale-dipendente/',
        'url_docx': '/gestione-accessi/manuale/dipendente/docx/',
    },
}


def get_manuali_media_dir():
    """Restituisce la cartella persistente in MEDIA_ROOT/manuali/ per salvare i PDF e DOCX caricati dal Programmatore."""
    media_root = getattr(settings, 'MEDIA_ROOT', None) or os.path.join(settings.BASE_DIR, 'media')
    target = os.path.join(media_root, 'manuali')
    os.makedirs(target, exist_ok=True)
    return target


def resolve_manuale_file(tipo, ext='pdf'):
    """
    Individua il percorso del file manuale richiesto ('programmatore', 'admin', 'dipendente')
    per l'estensione 'pdf' o 'docx'.
    Priorità:
    1. File personalizzato caricato dal Programmatore in MEDIA_ROOT/manuali/ (persistente su VPS)
    2. File predefinito nella root del progetto (settings.BASE_DIR)
    Se richiesto 'docx' e non ancora presente su disco, lo genera al volo con genera_docx_manuali.py.
    """
    info = CATALOGO_MANUALI_PORTALE.get(tipo)
    if not info:
        return None, None, False

    filename = info['pdf_filename'] if ext == 'pdf' else info['docx_filename']
    custom_dir = get_manuali_media_dir()
    custom_path = os.path.join(custom_dir, filename)
    default_path = os.path.join(settings.BASE_DIR, filename)

    if os.path.exists(custom_path) and os.path.getsize(custom_path) > 0:
        return custom_path, filename, True

    if ext == 'docx' and not os.path.exists(default_path):
        try:
            from genera_docx_manuali import genera_tutti_i_docx
            genera_tutti_i_docx(settings.BASE_DIR)
        except Exception:
            pass

    if ext == 'pdf' and not os.path.exists(default_path):
        try:
            import genera_pdf_manuale
            genera_pdf_manuale.main()
        except Exception:
            pass

    if os.path.exists(default_path):
        return default_path, filename, False

    return None, filename, False


def _format_file_size(num_bytes):
    if not num_bytes:
        return "0 KB"
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    return f"{max(1, int(round(num_bytes / 1024)))} KB"


def get_catalogo_manuali_status():
    """Restituisce i metadati completi dei 3 manuali per la Console Programmatore."""
    result = []
    for codice in ['programmatore', 'admin', 'dipendente']:
        base_info = dict(CATALOGO_MANUALI_PORTALE[codice])
        pdf_path, _, is_custom_pdf = resolve_manuale_file(codice, 'pdf')
        docx_path, _, is_custom_docx = resolve_manuale_file(codice, 'docx')

        if pdf_path and os.path.exists(pdf_path):
            stat_pdf = os.stat(pdf_path)
            base_info['pdf_exists'] = True
            base_info['pdf_size_human'] = _format_file_size(stat_pdf.st_size)
            dt_mod = datetime.fromtimestamp(stat_pdf.st_mtime)
            base_info['pdf_updated_at'] = dt_mod.strftime('%d/%m/%Y %H:%M')
            base_info['is_custom_pdf'] = is_custom_pdf
        else:
            base_info['pdf_exists'] = False
            base_info['pdf_size_human'] = 'N/D'
            base_info['pdf_updated_at'] = '—'
            base_info['is_custom_pdf'] = False

        if docx_path and os.path.exists(docx_path):
            stat_docx = os.stat(docx_path)
            base_info['docx_exists'] = True
            base_info['docx_size_human'] = _format_file_size(stat_docx.st_size)
            dt_mod_d = datetime.fromtimestamp(stat_docx.st_mtime)
            base_info['docx_updated_at'] = dt_mod_d.strftime('%d/%m/%Y %H:%M')
            base_info['is_custom_docx'] = is_custom_docx
        else:
            base_info['docx_exists'] = False
            base_info['docx_size_human'] = 'N/D'
            base_info['docx_updated_at'] = '—'
            base_info['is_custom_docx'] = False

        result.append(base_info)
    return result


def scarica_manuale_docx_view(request, tipo):
    """Permette al Programmatore di scaricare il file Word (.docx) modificabile di uno dei 3 manuali."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')

    docx_path, filename, _ = resolve_manuale_file(tipo, 'docx')
    if not docx_path or not os.path.exists(docx_path):
        raise Http404(f"File Word (.docx) per il manuale '{tipo}' non trovato.")

    response = FileResponse(
        open(docx_path, 'rb'),
        as_attachment=True,
        filename=filename,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


def manuale_programmatore_pdf_view(request):
    """Restituisce il PDF del Manuale Programmatore & Super-Admin (caricato dal Programmatore o predefinito)."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseRedirect('/admin/login/')

    pdf_path, filename, _ = resolve_manuale_file('programmatore', 'pdf')
    if not pdf_path or not os.path.exists(pdf_path):
        raise Http404("File PDF del Manuale Programmatore non trovato.")

    as_dl = request.GET.get('download') == '1'
    response = FileResponse(
        open(pdf_path, 'rb'),
        as_attachment=as_dl,
        filename=filename,
        content_type='application/pdf',
    )
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


def gestione_accessi_view(request):
    """
    Console riservata al Programmatore (Serra Gian Carlo) per:
    - Visualizzare e gestire il proprio account Programmatore (che vede tutte le sezioni)
    - Scaricare i file Word (.docx) modificabili dei 3 manuali e caricare i PDF impaginati definitivi
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

    manuali_portale = get_catalogo_manuali_status()

    context = {
        'title': 'Console Programmatore — Gestione Accessi, Sezioni & Manuali',
        'profilo_programmatore': profilo_programmatore,
        'profili_responsabili': profili_responsabili,
        'gruppi_sezioni': gruppi_sezioni,
        'totale_sezioni': len(TUTTI_CODICI_SEZIONI),
        'tutti_codici_json': TUTTI_CODICI_SEZIONI,
        'default_codici_json': DEFAULT_CODICI_RESPONSABILE,
        'dipendenti_disponibili': dipendenti_disponibili,
        'manuali_portale': manuali_portale,
    }
    return render(request, 'admin/gestione_accessi.html', context)


@require_POST
def gestione_accessi_api_view(request):
    """
    API JSON per il salvataggio istantaneo delle sezioni abilitate, delle credenziali
    e per il caricamento/gestione dei 3 manuali (.docx e .pdf) da parte del Programmatore.
    """
    if not is_utente_programmatore(request.user):
        return JsonResponse({'ok': False, 'error': 'Operazione riservata al Programmatore (Gian Carlo Serra).'}, status=403)

    action = (request.POST.get('action') or '').strip()

    if action == 'upload_manuale':
        tipo = (request.POST.get('tipo_manuale') or '').strip()
        if tipo not in CATALOGO_MANUALI_PORTALE:
            return JsonResponse({'ok': False, 'error': 'Tipologia di manuale non valida.'}, status=400)

        info = CATALOGO_MANUALI_PORTALE[tipo]
        up_pdf = request.FILES.get('file_pdf')
        up_docx = request.FILES.get('file_docx')

        if not up_pdf and not up_docx:
            return JsonResponse({'ok': False, 'error': 'Seleziona almeno un file PDF (o un file Word .docx) da caricare.'}, status=400)

        custom_dir = get_manuali_media_dir()
        aggiornati = []

        if up_pdf:
            if not up_pdf.name.lower().endswith('.pdf'):
                return JsonResponse({'ok': False, 'error': 'Il file PDF deve avere estensione .pdf'}, status=400)
            target_custom_pdf = os.path.join(custom_dir, info['pdf_filename'])
            with open(target_custom_pdf, 'wb+') as dest:
                for chunk in up_pdf.chunks():
                    dest.write(chunk)
            # Sincronizza anche nella cartella base del progetto per compatibilità immediata
            try:
                base_pdf = os.path.join(settings.BASE_DIR, info['pdf_filename'])
                shutil.copy2(target_custom_pdf, base_pdf)
                if tipo == 'admin':
                    for alias_name in ['Manuale di utilizzo del portale Kandor.pdf', 'Kandor_Portal_Operational_Guide.pdf']:
                        shutil.copy2(target_custom_pdf, os.path.join(settings.BASE_DIR, alias_name))
            except Exception:
                pass
            aggiornati.append(f"PDF ({_format_file_size(up_pdf.size)})")

        if up_docx:
            if not up_docx.name.lower().endswith(('.docx', '.doc')):
                return JsonResponse({'ok': False, 'error': 'Il documento modificabile deve avere estensione .docx o .doc'}, status=400)
            target_custom_docx = os.path.join(custom_dir, info['docx_filename'])
            with open(target_custom_docx, 'wb+') as dest:
                for chunk in up_docx.chunks():
                    dest.write(chunk)
            try:
                base_docx = os.path.join(settings.BASE_DIR, info['docx_filename'])
                shutil.copy2(target_custom_docx, base_docx)
            except Exception:
                pass
            aggiornati.append(f"Word DOCX ({_format_file_size(up_docx.size)})")

        # Rileggi lo stato aggiornato del manuale
        stato_list = [m for m in get_catalogo_manuali_status() if m['codice'] == tipo]
        stato_curr = stato_list[0] if stato_list else {}

        return JsonResponse({
            'ok': True,
            'tipo': tipo,
            'message': f"✅ {info['titolo']}: caricato con successo {' + '.join(aggiornati)}!",
            'stato': stato_curr,
        })

    if action == 'rigenera_docx_manuali':
        try:
            from genera_docx_manuali import genera_tutti_i_docx
            # Rimuove eventuali override docx così rigenera i file Word puliti di base
            custom_dir = get_manuali_media_dir()
            tipo_req = (request.POST.get('tipo_manuale') or '').strip()
            for cod, inf in CATALOGO_MANUALI_PORTALE.items():
                if not tipo_req or tipo_req == cod:
                    p_cust = os.path.join(custom_dir, inf['docx_filename'])
                    if os.path.exists(p_cust):
                        os.remove(p_cust)
            genera_tutti_i_docx(settings.BASE_DIR)
            return JsonResponse({
                'ok': True,
                'message': '✅ File Word (.DOCX) modificabili rigenerati con successo!',
                'manuali': get_catalogo_manuali_status(),
            })
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Errore rigenerazione DOCX: {e}'}, status=500)

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
