"""
Viste e API dedicate al Centro IA & Automazioni Zero-Cost (/ia-hub/).
"""
import calendar
import json
from datetime import date
from decimal import Decimal

from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Dipendente, Mezzo, Segnalazione, RichiestaSostituzione,
    TimeTracking, AssegnazioneTurno, Titolare, ResponsabileArea, ProceduraAvviata,
)
from .ai_engine import (
    analizza_anomalie_ore,
    verifica_conformita_turni,
    analizza_marginalita_e_budget_clienti,
    genera_briefing_mattutino,
    classifica_segnalazione,
    analizza_documento_o_certificato,
    is_gemini_configured,
)
from .utils_kandor_chat import send_telegram_message


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

    dipendente_id_raw = request.GET.get('dipendente_id', '').strip()
    dipendente_id = int(dipendente_id_raw) if dipendente_id_raw.isdigit() else None

    # 1. Audit Ore & Paghe (filtrabile per singolo dipendente, es. Ratti Claudio)
    audit_ore = analizza_anomalie_ore(data_inizio, data_fine, dipendente_id=dipendente_id)

    # 2. Segnalazioni recenti con Triage IA (pre-caricando i mezzi in 1 sola query)
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
        'dipendente_id': dipendente_id or '',
    }
    return render(request, 'core/ia_hub.html', context)


@csrf_exempt
def ia_auto_valida_ore_api(request):
    """
    Auto-valida le registrazioni TimeTracking nel periodo selezionato (Modulo 1 - AI Revisore Ore).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        body = request.POST

    # 1. Validazione o rettifica di un singolo TimeTracking (anche dalla tabella Anomalie)
    single_tt_id = body.get('timetracking_id')
    if single_tt_id and str(single_tt_id).isdigit():
        tt = TimeTracking.objects.select_related('dipendente', 'assegnazione__cliente').filter(pk=int(single_tt_id)).first()
        if not tt:
            return JsonResponse({'ok': False, 'error': 'Registrazione ore non trovata'}, status=404)
        ore_override = body.get('ore_dichiarate')
        if ore_override is not None and str(ore_override).strip() != '':
            try:
                val = Decimal(str(float(str(ore_override).replace(',', '.'))))
                if val > 0:
                    tt.ore_dichiarate = val
            except Exception:
                pass
        tt.is_validated = True
        tt.save()
        dip_str = f"{tt.dipendente.cognome} {tt.dipendente.nome}" if tt.dipendente else "Dipendente"
        return JsonResponse({
            'ok': True,
            'validate_count': 1,
            'message': f'✅ Validate {tt.ore_dichiarate}h per {dip_str}!',
        })

    # 2. Compilazione e validazione rapida di un turno non compilato (ORE_MANCANTI)
    assign_id = body.get('assegnazione_id')
    if assign_id and str(assign_id).isdigit() and not body.get('data_inizio'):
        assign = AssegnazioneTurno.objects.filter(pk=int(assign_id)).first()
        if not assign:
            return JsonResponse({'ok': False, 'error': 'Turno non trovato'}, status=404)
        ore_override = body.get('ore_dichiarate')
        try:
            ore_val = Decimal(str(float(str(ore_override or assign.ore_previste_contratto or 3.0).replace(',', '.'))))
        except Exception:
            ore_val = Decimal('3.0')
        dip_id_param = body.get('dipendente_id')
        dips_target = []
        if dip_id_param and str(dip_id_param).isdigit():
            d_obj = Dipendente.objects.filter(pk=int(dip_id_param)).first()
            if d_obj:
                dips_target = [d_obj]
        if not dips_target:
            dips_target = list(assign.dipendenti_presenti)
        cnt = 0
        for d_obj in dips_target:
            tt, created = TimeTracking.objects.get_or_create(
                dipendente=d_obj,
                assegnazione=assign,
                defaults={
                    'ore_dichiarate': ore_val,
                    'is_validated': True,
                    'source': 'ADMIN',
                    'note': 'Validato da Revisore Ore IA',
                }
            )
            if not created:
                tt.ore_dichiarate = ore_val
                tt.is_validated = True
                tt.save()
            cnt += 1
        return JsonResponse({
            'ok': True,
            'validate_count': cnt,
            'message': f'✅ Registrate e validate {ore_val}h per {cnt} dipendente/i!',
        })

    # 3. Validazione di una selezione specifica di ID TimeTracking (checkboxes)
    selected_ids = body.get('timetracking_ids')
    if isinstance(selected_ids, list) and len(selected_ids) > 0:
        clean_ids = [int(x) for x in selected_ids if str(x).isdigit()]
        if clean_ids:
            updated = TimeTracking.objects.filter(id__in=clean_ids).update(is_validated=True)
            return JsonResponse({
                'ok': True,
                'validate_count': updated,
                'message': f'✅ Validate con successo {updated} registrazioni ore selezionate!',
            })

    try:
        data_inizio = date.fromisoformat(body.get('data_inizio'))
        data_fine = date.fromisoformat(body.get('data_fine'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Date non valide'}, status=400)

    dipendente_id = body.get('dipendente_id')
    dip_id_int = int(dipendente_id) if (dipendente_id and str(dipendente_id).isdigit()) else None
    forza_tutte_dip = bool(body.get('forza_tutte_dipendente', False))

    if dip_id_int and forza_tutte_dip:
        updated = TimeTracking.objects.filter(
            dipendente_id=dip_id_int,
            assegnazione__turno__data__gte=data_inizio,
            assegnazione__turno__data__lte=data_fine,
            is_validated=False,
            ore_dichiarate__gt=0,
        ).update(is_validated=True)
        return JsonResponse({
            'ok': True,
            'validate_count': updated,
            'message': f'✅ Validate tutte le {updated} registrazioni ore in attesa del dipendente selezionato!',
        })

    audit = analizza_anomalie_ore(data_inizio, data_fine, dipendente_id=dip_id_int)
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
    Invia il Briefing Mattutino IA (incluso l'avanzamento delle procedure aperte)
    su Telegram a tutti i Titolari, Responsabili Area e operatori incaricati di procedure aperte.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    briefing = genera_briefing_mattutino()
    testo_msg = briefing['testo_telegram']

    destinatari = set()
    for t in Titolare.objects.exclude(telegram_chat_id__isnull=True).exclude(telegram_chat_id=''):
        destinatari.add(t.telegram_chat_id)
    for ra in ResponsabileArea.objects.select_related('dipendente').all():
        if ra.dipendente and ra.dipendente.telegram_chat_id:
            destinatari.add(ra.dipendente.telegram_chat_id)
    for proc in ProceduraAvviata.objects.filter(stato='IN_CORSO').select_related('dipendente'):
        if proc.dipendente and proc.dipendente.telegram_chat_id:
            destinatari.add(proc.dipendente.telegram_chat_id)

    inviati = 0
    for cid in destinatari:
        if send_telegram_message(cid, testo_msg):
            inviati += 1

    return JsonResponse({
        'ok': True,
        'inviati': inviati,
        'destinatari_totali': len(destinatari),
        'briefing_text': testo_msg,
        'message': f'📲 Briefing aggiornato (con stato procedure aperte) inviato su Telegram a {inviati} destinatari.',
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
    Analizza un documento/certificato/attestato (testo o file caricato) tramite il parser IA.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

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
