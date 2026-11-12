import os
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .buste_paga_service import (
    costruisci_dati_whatsapp_cedolino,
    crea_dipendente_da_cedolino,
    elabora_lotto_buste_paga,
    invia_cedolino_telegram,
    invia_lotto_telegram_massivo,
    normalizza_telefono_whatsapp,
    segna_cedolino_inviato_whatsapp,
    trova_dipendente_per_cf_o_nome,
)
from .models import CedolinoDipendente, Dipendente, LottoBustePaga


def _is_authorized_admin_or_titolare(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return hasattr(user, 'profilo_titolare')


def buste_paga_view(request):
    """
    Sezione principale per il caricamento del PDF unico del commercialista,
    la suddivisione automatica per Codice Fiscale e l'invio massivo/singolo
    tramite Telegram e WhatsApp.
    """
    if not _is_authorized_admin_or_titolare(request.user):
        return HttpResponseRedirect('/admin/login/?next=/buste-paga/')

    if request.method == 'POST' and request.FILES.get('pdf_file'):
        pdf_file = request.FILES['pdf_file']
        periodo_override = (request.POST.get('periodo') or '').strip()
        note = (request.POST.get('note') or '').strip()
        auto_invia_telegram = request.POST.get('auto_invia_telegram') == '1'
        auto_crea_mancanti = request.POST.get('auto_crea_mancanti') == '1'

        try:
            res = elabora_lotto_buste_paga(
                file_obj=pdf_file,
                filename=pdf_file.name,
                periodo_override=periodo_override,
                note=note,
                user=request.user,
            )
            lotto = res['lotto']

            creati_auto = 0
            if auto_crea_mancanti:
                for ced in lotto.cedolini.filter(dipendente__isnull=True):
                    c_res = crea_dipendente_da_cedolino(ced)
                    if c_res.get('ok'):
                        creati_auto += 1

            msg_parts = [
                f"✅ PDF elaborato con successo ({res['totale_pagine']} pagine totali): "
                f"estratti {res['totale_cedolini']} cedolini per Codice Fiscale "
                f"({res['associati_count']} associati automaticamente ai dipendenti"
                + (f", {res['cf_allineati_count']} CF allineati" if res['cf_allineati_count'] else "")
                + (f", {creati_auto} nuovi dipendenti creati in anagrafica" if creati_auto else "")
                + ")."
            ]

            if auto_invia_telegram:
                tg_res = invia_lotto_telegram_massivo(lotto, force_resend=False)
                msg_parts.append(
                    f" ✈️ Invio automatico Telegram completato: {tg_res['inviati']} buste paga inviate"
                    + (f" ({tg_res['senza_telegram']} dipendenti senza Telegram collegato)." if tg_res['senza_telegram'] else ".")
                )

            messages.success(request, "".join(msg_parts))
            return HttpResponseRedirect(f"{reverse('buste_paga')}?lotto_id={lotto.pk}")
        except Exception as e:
            messages.error(request, f"❌ Errore durante l'elaborazione del PDF: {e}")

    lotti = list(LottoBustePaga.objects.all().order_by('-created_at')[:30])
    lotto_id = request.GET.get('lotto_id')
    lotto_attivo = None
    if lotto_id and str(lotto_id).isdigit():
        lotto_attivo = LottoBustePaga.objects.filter(pk=int(lotto_id)).first()
    if not lotto_attivo and lotti:
        lotto_attivo = lotti[0]

    cedolini_rows = []
    stats = {
        'totale': 0,
        'associati': 0,
        'non_associati': 0,
        'con_telegram': 0,
        'con_whatsapp': 0,
        'inviati_telegram': 0,
        'da_inviare_telegram': 0,
        'inviati_whatsapp': 0,
        'inviati_almeno_uno': 0,
        'scaricati': 0,
    }

    if lotto_attivo:
        qs_ced = lotto_attivo.cedolini.select_related('dipendente').order_by('nominativo_pdf', 'codice_fiscale')
        for ced in qs_ced:
            dip = ced.dipendente
            has_tg = bool(dip and (dip.telegram_chat_id or '').strip())
            wa_info = costruisci_dati_whatsapp_cedolino(ced, request=request)
            has_wa = wa_info['has_phone']

            stats['totale'] += 1
            if dip:
                stats['associati'] += 1
            else:
                stats['non_associati'] += 1
            if has_tg:
                stats['con_telegram'] += 1
                if not ced.inviato_telegram:
                    stats['da_inviare_telegram'] += 1
            if has_wa:
                stats['con_whatsapp'] += 1
            if ced.inviato_telegram:
                stats['inviati_telegram'] += 1
            if ced.inviato_whatsapp:
                stats['inviati_whatsapp'] += 1
            if ced.inviato_telegram or ced.inviato_whatsapp:
                stats['inviati_almeno_uno'] += 1
            if ced.scaricato_dipendente:
                stats['scaricati'] += 1

            cedolini_rows.append({
                'cedolino': ced,
                'dipendente': dip,
                'has_telegram': has_tg,
                'has_whatsapp': has_wa,
                'telefono_raw': wa_info['raw_phone'],
                'telefono_display': (dip.telefono if dip else '') or '',
                'wa_url': wa_info['wa_url'],
                'download_url': wa_info['download_url'],
            })

    tutti_dipendenti = list(
        Dipendente.objects.all().order_by('cognome', 'nome').values('id', 'cognome', 'nome', 'codice_fiscale', 'stato')
    )

    context = {
        'title': 'Gestione & Invio Automatico Buste Paga',
        'lotti': lotti,
        'lotto_attivo': lotto_attivo,
        'cedolini_rows': cedolini_rows,
        'stats': stats,
        'tutti_dipendenti': tutti_dipendenti,
    }
    return render(request, 'admin/buste_paga.html', context)


@require_POST
def buste_paga_api_view(request):
    """
    Endpoint API JSON per tutte le azioni interattive sulla sezione Buste Paga:
    - invia_singolo_telegram
    - invia_massivo_telegram
    - segna_whatsapp
    - associa_dipendente
    - crea_dipendente
    - crea_tutti_dipendenti_mancanti
    - aggiorna_telefono_dipendente
    - riassocia_lotto
    - elimina_lotto
    """
    if not _is_authorized_admin_or_titolare(request.user):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    action = (request.POST.get('action') or '').strip()

    if action == 'invia_singolo_telegram':
        ced_id = request.POST.get('cedolino_id')
        force = request.POST.get('force') == '1'
        ced = get_object_or_404(CedolinoDipendente.objects.select_related('dipendente', 'lotto'), pk=ced_id)
        res = invia_cedolino_telegram(ced, force_resend=force)
        return JsonResponse(res)

    if action == 'invia_massivo_telegram':
        lotto_id = request.POST.get('lotto_id')
        force = request.POST.get('force') == '1'
        lotto = get_object_or_404(LottoBustePaga, pk=lotto_id)
        res = invia_lotto_telegram_massivo(lotto, force_resend=force)
        return JsonResponse(res)

    if action == 'segna_whatsapp':
        ced_id = request.POST.get('cedolino_id')
        ced = get_object_or_404(CedolinoDipendente.objects.select_related('dipendente', 'lotto'), pk=ced_id)
        wa_data = segna_cedolino_inviato_whatsapp(ced, request=request)
        return JsonResponse({
            'ok': True,
            'wa_url': wa_data['wa_url'],
            'data_invio': wa_data['data_invio'],
            'has_phone': wa_data['has_phone'],
        })

    if action == 'associa_dipendente':
        ced_id = request.POST.get('cedolino_id')
        dip_id = request.POST.get('dipendente_id')
        allinea_cf = request.POST.get('allinea_cf') == '1'
        ced = get_object_or_404(CedolinoDipendente, pk=ced_id)
        if not dip_id:
            ced.dipendente = None
            ced.save(update_fields=['dipendente'])
            return JsonResponse({'ok': True, 'message': 'Associazione rimossa'})

        dip = get_object_or_404(Dipendente, pk=dip_id)
        ced.dipendente = dip
        ced.save(update_fields=['dipendente'])

        if allinea_cf and ced.codice_fiscale and len(ced.codice_fiscale) == 16:
            conflitto = Dipendente.objects.filter(codice_fiscale__iexact=ced.codice_fiscale).exclude(pk=dip.pk).exists()
            if not conflitto:
                Dipendente.objects.filter(pk=dip.pk).update(codice_fiscale=ced.codice_fiscale.upper())
                dip.codice_fiscale = ced.codice_fiscale.upper()

        wa_info = costruisci_dati_whatsapp_cedolino(ced, request=request)
        return JsonResponse({
            'ok': True,
            'dipendente_id': dip.pk,
            'dipendente_nome': f"{dip.cognome} {dip.nome}",
            'has_telegram': bool((dip.telegram_chat_id or '').strip()),
            'has_whatsapp': wa_info['has_phone'],
            'wa_url': wa_info['wa_url'],
            'telefono': dip.telefono or '',
        })

    if action == 'crea_dipendente':
        ced_id = request.POST.get('cedolino_id')
        ced = get_object_or_404(CedolinoDipendente.objects.select_related('lotto'), pk=ced_id)
        res = crea_dipendente_da_cedolino(ced)
        if not res.get('ok'):
            return JsonResponse(res)
        dip = res['dipendente']
        wa_info = costruisci_dati_whatsapp_cedolino(ced, request=request)
        return JsonResponse({
            'ok': True,
            'created': res.get('created', True),
            'dipendente_id': dip.pk,
            'dipendente_nome': f"{dip.cognome} {dip.nome}",
            'has_telegram': bool((dip.telegram_chat_id or '').strip()),
            'has_whatsapp': wa_info['has_phone'],
            'wa_url': wa_info['wa_url'],
        })

    if action == 'crea_tutti_dipendenti_mancanti':
        lotto_id = request.POST.get('lotto_id')
        lotto = get_object_or_404(LottoBustePaga, pk=lotto_id)
        creati = 0
        associati = 0
        for ced in lotto.cedolini.filter(dipendente__isnull=True):
            res = crea_dipendente_da_cedolino(ced)
            if res.get('ok'):
                associati += 1
                if res.get('created'):
                    creati += 1
        return JsonResponse({
            'ok': True,
            'creati': creati,
            'associati': associati,
        })

    if action == 'aggiorna_telefono_dipendente':
        ced_id = request.POST.get('cedolino_id')
        telefono = (request.POST.get('telefono') or '').strip()
        ced = get_object_or_404(CedolinoDipendente.objects.select_related('dipendente', 'lotto'), pk=ced_id)
        if not ced.dipendente:
            return JsonResponse({'ok': False, 'error': 'Associa o crea prima il dipendente in anagrafica.'})
        dip = ced.dipendente
        dip.telefono = telefono
        Dipendente.objects.filter(pk=dip.pk).update(telefono=telefono)
        wa_info = costruisci_dati_whatsapp_cedolino(ced, request=request)
        return JsonResponse({
            'ok': True,
            'telefono': telefono,
            'has_whatsapp': wa_info['has_phone'],
            'wa_url': wa_info['wa_url'],
        })

    if action == 'riassocia_lotto':
        lotto_id = request.POST.get('lotto_id')
        lotto = get_object_or_404(LottoBustePaga, pk=lotto_id)
        nuovi_associati = 0
        for ced in lotto.cedolini.filter(dipendente__isnull=True):
            dip, _ = trova_dipendente_per_cf_o_nome(ced.codice_fiscale, ced.nominativo_pdf, aggiorna_cf_se_refuso=True)
            if dip:
                ced.dipendente = dip
                ced.save(update_fields=['dipendente'])
                nuovi_associati += 1
        return JsonResponse({'ok': True, 'nuovi_associati': nuovi_associati})

    if action == 'elimina_lotto':
        lotto_id = request.POST.get('lotto_id')
        lotto = get_object_or_404(LottoBustePaga, pk=lotto_id)
        lotto.delete()
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': f'Azione non riconosciuta: {action}'}, status=400)


def scarica_busta_paga_token_view(request, token):
    """
    Endpoint pubblico protetto da token crittografico univoco per permettere al dipendente
    di visualizzare o scaricare la propria busta paga in PDF direttamente dal link WhatsApp
    o dalla Web App Dipendenti.
    """
    cedolino = get_object_or_404(CedolinoDipendente.objects.select_related('dipendente', 'lotto'), token_download=token)
    if not cedolino.file_pdf:
        raise Http404("File PDF della busta paga non disponibile.")

    # Se non è lo staff admin in anteprima, registra lo scaricamento da parte del dipendente
    is_admin_preview = request.GET.get('preview') == '1' and getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_staff
    if not is_admin_preview and not cedolino.scaricato_dipendente:
        cedolino.scaricato_dipendente = True
        cedolino.data_primo_scarico = timezone.now()
        cedolino.save(update_fields=['scaricato_dipendente', 'data_primo_scarico'])

    try:
        file_handle = cedolino.file_pdf.open('rb')
    except Exception:
        raise Http404("File PDF non trovato sul disco.")

    filename = os.path.basename(cedolino.file_pdf.name) or f"Busta_Paga_{cedolino.codice_fiscale}.pdf"
    as_attachment = request.GET.get('download') == '1'
    response = FileResponse(file_handle, content_type='application/pdf', as_attachment=as_attachment, filename=filename)
    return response
