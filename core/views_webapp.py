import json
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from urllib.parse import quote_plus

from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Q

from .models import (
    Dipendente,
    AssegnazioneTurno,
    TimeTracking,
    Assenza,
    Segnalazione,
    MessaggioChat,
    RichiestaSostituzione,
    ResponsabileArea,
    CorsoDipendente,
    ensure_corsi_per_dipendente,
)


SESSION_KEY_DIP_ID = 'dipendente_app_id'


def _get_photo_url(dip):
    if not dip:
        return None
    if dip.foto and hasattr(dip.foto, 'url'):
        try:
            if dip.foto.url:
                return dip.foto.url
        except Exception:
            pass
    if dip.foto_url:
        return dip.foto_url
    if dip.foto_profilo_url:
        return dip.foto_profilo_url
    return None


def _get_logged_dipendente(request):
    # Permetti accesso diretto tramite link personale (Magic Link WhatsApp: ?cf=...&pin=...)
    cf_q = (request.GET.get('cf') or '').strip().upper().replace(' ', '')
    pin_q = (request.GET.get('pin') or '').strip()
    if cf_q and pin_q:
        cand = Dipendente.objects.filter(codice_fiscale__iexact=cf_q, stato='ATTIVO').first()
        if cand and cand.pin_accesso and cand.pin_accesso.strip() == pin_q:
            request.session[SESSION_KEY_DIP_ID] = cand.pk
            request.session['dipendente_webapp_auth'] = True
            request.session.set_expiry(60 * 60 * 24 * 90)
            return cand

    # Permetti allo staff admin di aprire l'anteprima rapida di un dipendente con ?preview_dip_id=XX
    preview_id = request.GET.get('preview_dip_id')
    if preview_id and getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_staff:
        try:
            dip = Dipendente.objects.filter(pk=int(preview_id)).first()
            if dip:
                request.session[SESSION_KEY_DIP_ID] = dip.pk
                request.session.set_expiry(60 * 60 * 24 * 90)
                return dip
        except (ValueError, TypeError):
            pass

    dip_id = request.session.get(SESSION_KEY_DIP_ID)
    if not dip_id:
        return None
    dip = Dipendente.objects.filter(pk=dip_id, stato='ATTIVO').first()
    if not dip:
        request.session.pop(SESSION_KEY_DIP_ID, None)
        return None
    return dip


def _calcola_ore_previste(assign):
    if assign.ore_previste_contratto and assign.ore_previste_contratto > 0:
        return round(float(assign.ore_previste_contratto), 1)
    if assign.orario_inizio_previsto and assign.orario_fine_previsto:
        dt_start = datetime.combine(date.today(), assign.orario_inizio_previsto)
        dt_end = datetime.combine(date.today(), assign.orario_fine_previsto)
        if dt_end < dt_start:
            dt_end += timedelta(days=1)
        diff = (dt_end - dt_start).total_seconds() / 3600.0
        if diff > 0:
            return round(diff, 1)
    return 4.0


def _serialize_assign_for_dipendente(assign, dipendente, sost_assign_ids=None):
    sost_assign_ids = sost_assign_ids or set()
    tt = TimeTracking.objects.filter(dipendente=dipendente, assegnazione=assign).first()
    squadra = assign.turno.squadra if assign.turno else None
    esclusi_ids = set(assign.dipendenti_esclusi.values_list('pk', flat=True))

    compagni = []
    if squadra and assign.id not in sost_assign_ids:
        membri = list(squadra.componenti.filter(stato='ATTIVO'))
        if squadra.caposquadra and squadra.caposquadra.stato == 'ATTIVO' and squadra.caposquadra not in membri:
            membri.insert(0, squadra.caposquadra)
        for m in membri:
            if m.pk != dipendente.pk:
                compagni.append({
                    'id': m.pk,
                    'nome': f"{m.nome} {m.cognome}",
                    'presente': m.pk not in esclusi_ids,
                })

    indirizzo = assign.cliente.indirizzo_sede if assign.cliente else ''
    maps_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(indirizzo)}" if indirizzo else ''
    ore_prev = _calcola_ore_previste(assign)
    mansione = assign.mansione_svolta or (assign.cliente.note_mansioni if assign.cliente else '') or ''

    GIORNI_SETT = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    d = assign.turno.data
    giorno_nome = GIORNI_SETT[d.weekday()]

    return {
        'id': assign.id,
        'data_iso': d.strftime('%Y-%m-%d'),
        'data_str': f"{giorno_nome} {d.strftime('%d/%m/%Y')}",
        'data_breve': f"{GIORNI_SETT[d.weekday()][:3]} {d.strftime('%d/%m')}",
        'cliente_nome': assign.cliente.ragione_sociale if assign.cliente else 'Cliente',
        'cliente_indirizzo': indirizzo,
        'maps_url': maps_url,
        'orario_inizio': assign.orario_inizio_previsto.strftime('%H:%M') if assign.orario_inizio_previsto else '',
        'orario_fine': assign.orario_fine_previsto.strftime('%H:%M') if assign.orario_fine_previsto else '',
        'ore_previste': ore_prev,
        'mansione': mansione,
        'squadra_nome': squadra.nome if squadra else '',
        'mezzo_nome': str(assign.turno.mezzo) if (assign.turno and assign.turno.mezzo) else '',
        'is_sostituzione': assign.id in sost_assign_ids,
        'is_compilato': bool(tt and tt.ore_dichiarate is not None),
        'ore_dichiarate': float(tt.ore_dichiarate) if (tt and tt.ore_dichiarate is not None) else None,
        'ore_dichiarate_str': str(round(float(tt.ore_dichiarate), 1)) if (tt and tt.ore_dichiarate is not None) else str(ore_prev),
        'ore_previste_str': str(ore_prev),
        'note_dichiarate': (tt.note or '') if tt else '',
        'compagni': compagni,
        'compagni_json': json.dumps(compagni),
    }


def _get_assegnazioni_dipendente(dipendente, data_inizio, data_fine=None):
    if data_fine is None:
        data_fine = data_inizio

    sost_assign_ids = set(
        RichiestaSostituzione.objects.filter(
            sostituto=dipendente,
            stato__in=['ACCETTATA', 'COMPLETATA'],
            assegnazione_originale__turno__data__gte=data_inizio,
            assegnazione_originale__turno__data__lte=data_fine,
        ).values_list('assegnazione_originale_id', flat=True)
    )

    qs = (
        AssegnazioneTurno.objects.filter(
            turno__data__gte=data_inizio,
            turno__data__lte=data_fine,
        )
        .filter(
            Q(turno__squadra__componenti=dipendente)
            | Q(turno__squadra__caposquadra=dipendente)
            | Q(id__in=sost_assign_ids)
            | Q(timetracks__dipendente=dipendente)
        )
        .select_related('cliente', 'turno', 'turno__squadra', 'turno__mezzo')
        .prefetch_related('dipendenti_esclusi', 'turno__squadra__componenti')
        .distinct()
        .order_by('turno__data', 'orario_inizio_previsto')
    )

    result = []
    for a in qs:
        # Se è stato escluso dal turno (e non ha compilato ore né è sostituto), non mostrarlo
        esclusi_pks = {d.pk for d in a.dipendenti_esclusi.all()}
        if dipendente.pk in esclusi_pks and a.id not in sost_assign_ids:
            if not TimeTracking.objects.filter(dipendente=dipendente, assegnazione=a).exists():
                continue
        result.append(_serialize_assign_for_dipendente(a, dipendente, sost_assign_ids=sost_assign_ids))
    return result


def dipendente_app_login_view(request):
    dip = _get_logged_dipendente(request)
    if dip:
        return HttpResponseRedirect('/app/')

    error = None
    cf_val = (request.GET.get('cf') or '').strip().upper().replace(' ', '')
    pin_get = (request.GET.get('pin') or '').strip()
    if cf_val and pin_get:
        error = "Il link di accesso automatico non è aggiornato (PIN modificato o profilo non attivo). Inserisci il tuo PIN aggiornato."

    if request.method == 'POST':
        cf_val = (request.POST.get('codice_fiscale') or '').strip().upper().replace(' ', '')
        pin_val = (request.POST.get('pin_accesso') or '').strip()

        if not cf_val or not pin_val:
            error = "Inserisci sia il Codice Fiscale sia il PIN di 4 cifre."
        else:
            cand = Dipendente.objects.filter(codice_fiscale__iexact=cf_val).first()
            if not cand:
                error = "Codice Fiscale non trovato in archivio. Verifica di averlo scritto correttamente."
            elif cand.stato != 'ATTIVO':
                error = "Questo profilo dipendente risulta non attivo. Contatta l'Amministrazione."
            else:
                # Assicura che abbia un PIN
                if not cand.pin_accesso:
                    cand.save()
                if cand.pin_accesso.strip() != pin_val:
                    error = "PIN di accesso non corretto. Verifica il PIN di 4 cifre con l'Amministrazione."
                else:
                    request.session[SESSION_KEY_DIP_ID] = cand.pk
                    request.session['dipendente_webapp_auth'] = True
                    # Sessione persistente per 90 giorni sul cellulare
                    request.session.set_expiry(60 * 60 * 24 * 90)
                    return HttpResponseRedirect('/app/')

    return render(request, 'core/dipendente_login.html', {
        'error': error,
        'cf_val': cf_val,
    })


def dipendente_app_logout_view(request):
    request.session.pop(SESSION_KEY_DIP_ID, None)
    return HttpResponseRedirect('/app/login/')


def dipendente_app_view(request):
    dip = _get_logged_dipendente(request)
    if not dip:
        return HttpResponseRedirect('/app/login/')

    today = timezone.now().date()
    active_tab = request.GET.get('tab', 'home')

    # Data selezionata per il calendario
    cal_date_str = request.GET.get('data', '')
    try:
        cal_date = datetime.strptime(cal_date_str, '%Y-%m-%d').date() if cal_date_str else today
    except ValueError:
        cal_date = today

    # 1. Turni di Oggi
    turni_oggi = _get_assegnazioni_dipendente(dip, today, today)

    # 2. Turni da compilare e turni compilati negli ultimi 31 giorni
    thirty_one_days_ago = today - timedelta(days=31)
    turni_31gg = _get_assegnazioni_dipendente(dip, thirty_one_days_ago, today)
    turni_da_compilare = [t for t in turni_31gg if not t['is_compilato']]
    turni_compilati_31gg = [t for t in reversed(turni_31gg) if t['is_compilato']]

    # 3. Turni del giorno selezionato nel Calendario + striscia 7 giorni
    turni_calendario = _get_assegnazioni_dipendente(dip, cal_date, cal_date)
    start_strip = cal_date - timedelta(days=2)
    GIORNI_BREVI = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
    strip_days = []
    for i in range(7):
        d_item = start_strip + timedelta(days=i)
        strip_days.append({
            'iso': d_item.strftime('%Y-%m-%d'),
            'giorno_breve': GIORNI_BREVI[d_item.weekday()],
            'numero': d_item.strftime('%d'),
            'mese': d_item.strftime('%m'),
            'is_selected': d_item == cal_date,
            'is_today': d_item == today,
        })

    # 4. Richieste di sostituzione in attesa di risposta dal dipendente (Sostituto / Jolly)
    richieste_sost_inviate = list(
        RichiestaSostituzione.objects.filter(
            sostituto=dip,
            stato='INVIATA',
            assegnazione_originale__turno__data__gte=today,
        ).select_related(
            'dipendente_assente',
            'assegnazione_originale__cliente',
            'assegnazione_originale__turno',
        ).order_by('assegnazione_originale__turno__data')
    )

    # Se il dipendente è anche Responsabile d'Area, mostra eventuali richieste APERTE
    ra = ResponsabileArea.objects.filter(dipendente=dip).first()
    richieste_ra_aperte = []
    sostituti_disponibili = []
    if ra:
        richieste_ra_aperte = list(
            RichiestaSostituzione.objects.filter(
                responsabile_area=ra,
                stato='APERTA',
                assegnazione_originale__turno__data__gte=today,
            ).select_related(
                'dipendente_assente',
                'assegnazione_originale__cliente',
                'assegnazione_originale__turno',
            ).order_by('assegnazione_originale__turno__data')
        )
        if richieste_ra_aperte:
            sostituti_disponibili = list(
                Dipendente.objects.filter(stato='ATTIVO', is_sostituto=True).order_by('cognome', 'nome')
            )

    # 5. Assenze recenti del dipendente
    assenze_recenti = list(
        Assenza.objects.filter(dipendente=dip).order_by('-data_inizio', '-id')[:15]
    )

    # 6. Messaggi Chat con l'ufficio
    messaggi_chat = list(
        MessaggioChat.objects.filter(dipendente=dip).order_by('-timestamp')[:60]
    )
    messaggi_chat.reverse()

    # 7. Segnalazioni inviate dal dipendente
    segnalazioni_recenti = list(
        Segnalazione.objects.filter(dipendente=dip).order_by('-data_inserimento')[:15]
    )

    # 8. Corsi di formazione e scadenza visita medica
    try:
        ensure_corsi_per_dipendente(dip)
    except Exception:
        pass
    corsi_dip = list(
        CorsoDipendente.objects.filter(dipendente=dip)
        .exclude(stato='NON_PREVISTO')
        .select_related('corso')
        .order_by('corso__ordine', 'corso__nome')
    )
    scadenza_visita_medica = None
    stato_visita_medica = 'NON_INDICATA'
    if dip.data_ultima_visita_medica:
        try:
            scadenza_visita_medica = dip.data_ultima_visita_medica.replace(year=dip.data_ultima_visita_medica.year + 1)
        except ValueError:
            scadenza_visita_medica = dip.data_ultima_visita_medica + timedelta(days=365)
        if scadenza_visita_medica < today:
            stato_visita_medica = 'SCADUTA'
        elif scadenza_visita_medica <= today + timedelta(days=30):
            stato_visita_medica = 'IN_SCADENZA'
        else:
            stato_visita_medica = 'VALIDA'

    GIORNI_SETT_FULL = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']

    context = {
        'dipendente': dip,
        'foto_url': _get_photo_url(dip),
        'today': today,
        'today_iso': today.strftime('%Y-%m-%d'),
        'today_str': f"{GIORNI_SETT_FULL[today.weekday()]} {today.strftime('%d/%m/%Y')}",
        'active_tab': active_tab,
        'turni_oggi': turni_oggi,
        'turni_da_compilare': turni_da_compilare,
        'turni_compilati_31gg': turni_compilati_31gg,
        'cal_date': cal_date,
        'cal_date_iso': cal_date.strftime('%Y-%m-%d'),
        'cal_date_str': f"{GIORNI_SETT_FULL[cal_date.weekday()]} {cal_date.strftime('%d/%m/%Y')}",
        'prev_date_iso': (cal_date - timedelta(days=1)).strftime('%Y-%m-%d'),
        'next_date_iso': (cal_date + timedelta(days=1)).strftime('%Y-%m-%d'),
        'strip_days': strip_days,
        'turni_calendario': turni_calendario,
        'richieste_sost_inviate': richieste_sost_inviate,
        'richieste_ra_aperte': richieste_ra_aperte,
        'sostituti_disponibili': sostituti_disponibili,
        'assenze_recenti': assenze_recenti,
        'messaggi_chat': messaggi_chat,
        'segnalazioni_recenti': segnalazioni_recenti,
        'corsi_dip': corsi_dip,
        'scadenza_visita_medica': scadenza_visita_medica,
        'stato_visita_medica': stato_visita_medica,
    }
    response = render(request, 'core/dipendente_app.html', context)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


def dipendente_app_action_view(request):
    """Endpoint unificato AJAX/POST per tutte le azioni della Web App Dipendenti."""
    dip = _get_logged_dipendente(request)
    if not dip:
        return JsonResponse({'ok': False, 'error': 'Sessione scaduta. Effettua nuovamente il login.', 'redirect': '/app/login/'}, status=401)

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito.'}, status=405)

    action = (request.POST.get('action') or '').strip()

    # 1. SALVA ORE TURNO (+ conferma presenze squadra)
    if action == 'salva_ore':
        assign_id = request.POST.get('assign_id')
        ore_raw = (request.POST.get('ore') or '').strip().replace(',', '.')
        note = (request.POST.get('note') or '').strip()
        presenti_ids_raw = request.POST.getlist('presenti_ids[]') or request.POST.getlist('presenti_ids')
        gestisci_squadra = request.POST.get('gestisci_squadra') == '1'

        try:
            assign = AssegnazioneTurno.objects.select_related('cliente', 'turno', 'turno__squadra').get(pk=int(assign_id))
        except (ValueError, TypeError, AssegnazioneTurno.DoesNotExist):
            return JsonResponse({'ok': False, 'error': 'Turno non trovato.'})

        try:
            ore_val = float(ore_raw)
            if ore_val <= 0 or ore_val > 24:
                return JsonResponse({'ok': False, 'error': 'Inserisci un numero di ore valido (tra 0.5 e 24).'})
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Formato ore non valido.'})

        ore_dec = Decimal(str(round(ore_val, 1)))
        tt, _ = TimeTracking.objects.get_or_create(
            dipendente=dip,
            assegnazione=assign,
            defaults={'source': 'WEBAPP'},
        )
        tt.ore_dichiarate = ore_dec
        tt.note = note
        tt.source = 'WEBAPP'
        tt.save()
        # Assicura che chi compila non sia tra gli esclusi
        assign.dipendenti_esclusi.remove(dip)

        # Gestione squadra (come su Telegram _salva_ore_turno)
        squadra = assign.turno.squadra if assign.turno else None
        sost_assign_ids = set(
            RichiestaSostituzione.objects.filter(
                sostituto=dip,
                stato__in=['ACCETTATA', 'COMPLETATA'],
                assegnazione_originale=assign,
            ).values_list('assegnazione_originale_id', flat=True)
        )

        compagni_aggiornati = 0
        compagni_esclusi = 0
        if squadra and assign.id not in sost_assign_ids:
            presenti_set = {int(x) for x in presenti_ids_raw if str(x).isdigit()}
            membri = list(squadra.componenti.filter(stato='ATTIVO'))
            if squadra.caposquadra and squadra.caposquadra.stato == 'ATTIVO' and squadra.caposquadra not in membri:
                membri.insert(0, squadra.caposquadra)

            from .utils_kandor_chat import send_telegram_message

            for comp in membri:
                if comp.pk == dip.pk:
                    continue
                is_present = (comp.pk in presenti_set) if gestisci_squadra else (comp not in assign.dipendenti_esclusi.all())
                if is_present:
                    assign.dipendenti_esclusi.remove(comp)
                    tt_comp, created_comp = TimeTracking.objects.get_or_create(
                        dipendente=comp,
                        assegnazione=assign,
                        defaults={'source': 'WEBAPP'},
                    )
                    if created_comp or not tt_comp.ore_dichiarate:
                        tt_comp.ore_dichiarate = ore_dec
                        tt_comp.note = f"Inserito da {dip.nome} {dip.cognome}" + (f" - {note}" if note else "")
                        tt_comp.source = 'WEBAPP'
                        tt_comp.save()
                        compagni_aggiornati += 1
                        if comp.telegram_chat_id:
                            data_str = assign.turno.data.strftime('%d/%m/%Y')
                            try:
                                send_telegram_message(
                                    comp.telegram_chat_id,
                                    f"ℹ️ *{dip.nome} {dip.cognome}* ha registrato *{ore_val}h* per la squadra "
                                    f"presso *{assign.cliente.ragione_sociale}* ({data_str}).",
                                )
                            except Exception:
                                pass
                else:
                    assign.dipendenti_esclusi.add(comp)
                    TimeTracking.objects.filter(dipendente=comp, assegnazione=assign).delete()
                    compagni_esclusi += 1

        msg = f"✅ Registrate {ore_val:g}h presso {assign.cliente.ragione_sociale}."
        if compagni_aggiornati:
            msg += f" Ore estese a {compagni_aggiornati} colleghi di squadra."
        if compagni_esclusi:
            msg += f" ({compagni_esclusi} colleghi segnati assenti)."
        return JsonResponse({'ok': True, 'message': msg})

    # 2. INVIA COMUNICAZIONE ASSENZA (Malattia, Ferie, Permesso, Legge 104)
    elif action == 'invia_assenza':
        tipo = (request.POST.get('tipo') or 'PERMESSO').strip().upper()
        modalita = (request.POST.get('modalita') or 'GIORNI').strip().upper()
        data_inizio_str = (request.POST.get('data_inizio') or '').strip()
        data_fine_str = (request.POST.get('data_fine') or '').strip()
        ora_inizio_str = (request.POST.get('ora_inizio') or '').strip()
        ora_fine_str = (request.POST.get('ora_fine') or '').strip()
        note = (request.POST.get('note') or '').strip()

        if tipo not in ('MALATTIA', 'FERIE', 'PERMESSO', '104'):
            return JsonResponse({'ok': False, 'error': 'Tipologia di assenza non valida.'})

        if tipo == '104' and not dip.usufruisce_104:
            return JsonResponse({'ok': False, 'error': 'Non risulti abilitato ai permessi Legge 104. Contatta l\'Amministrazione.'})

        try:
            d_start = datetime.strptime(data_inizio_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Inserisci una data di inizio valida.'})

        if modalita == 'ORARIA':
            d_end = d_start
            try:
                t_start = datetime.strptime(ora_inizio_str, '%H:%M').time()
                t_end = datetime.strptime(ora_fine_str, '%H:%M').time()
            except ValueError:
                return JsonResponse({'ok': False, 'error': 'Inserisci sia l\'ora di inizio sia l\'ora di fine (es. 08:00 - 12:00).'})
            if t_end <= t_start:
                return JsonResponse({'ok': False, 'error': 'L\'ora di fine deve essere successiva all\'ora di inizio.'})
        else:
            t_start = None
            t_end = None
            try:
                d_end = datetime.strptime(data_fine_str, '%Y-%m-%d').date() if data_fine_str else d_start
            except ValueError:
                d_end = d_start
            if d_end < d_start:
                return JsonResponse({'ok': False, 'error': 'La data di fine non può essere precedente alla data di inizio.'})

        from .utils_kandor_chat import _gestisci_assenza_con_sostituzione
        _gestisci_assenza_con_sostituzione(
            dip,
            tipo=tipo,
            data_inizio=d_start,
            data_fine=d_end,
            ora_inizio=t_start,
            ora_fine=t_end,
        )
        # Aggiorna source e note sull'ultima assenza creata per il dipendente
        ultima_assenza = Assenza.objects.filter(
            dipendente=dip,
            tipo=tipo,
            data_inizio=d_start,
            data_fine=d_end,
        ).order_by('-id').first()
        if ultima_assenza:
            ultima_assenza.source = 'WEBAPP'
            if note:
                ultima_assenza.note = note
            ultima_assenza.save(update_fields=['source', 'note'])

        return JsonResponse({
            'ok': True,
            'message': '✅ Comunicazione di assenza inviata all\'Amministrazione! Riceverai conferma appena sarà validata.',
        })

    # 3. RISPONDI A RICHIESTA DI SOSTITUZIONE (Sostituto / Jolly)
    elif action == 'rispondi_sostituzione':
        richiesta_id = request.POST.get('richiesta_id')
        decisione = (request.POST.get('decisione') or '').strip().lower()
        try:
            richiesta = RichiestaSostituzione.objects.get(pk=int(richiesta_id), sostituto=dip)
        except (ValueError, TypeError, RichiestaSostituzione.DoesNotExist):
            return JsonResponse({'ok': False, 'error': 'Richiesta di sostituzione non trovata.'})

        from .services import gestisci_risposta_sostituto
        accettato = (decisione == 'accetta')
        gestisci_risposta_sostituto(richiesta.pk, accettato=accettato)
        if accettato:
            return JsonResponse({'ok': True, 'message': '✅ Hai accettato la sostituzione! Il turno è stato aggiunto al tuo calendario.'})
        else:
            return JsonResponse({'ok': True, 'message': '❌ Hai rifiutato la sostituzione. L\'Amministrazione è stata avvisata.'})

    # 4. GESTIONE SOSTITUZIONE DA RESPONSABILE D'AREA
    elif action == 'gestisci_sostituzione_ra':
        richiesta_id = request.POST.get('richiesta_id')
        decisione = (request.POST.get('decisione') or '').strip().lower()
        sostituto_id = request.POST.get('sostituto_id')

        ra = ResponsabileArea.objects.filter(dipendente=dip).first()
        if not ra:
            return JsonResponse({'ok': False, 'error': 'Non autorizzato.'}, status=403)

        try:
            richiesta = RichiestaSostituzione.objects.get(pk=int(richiesta_id), responsabile_area=ra)
        except (ValueError, TypeError, RichiestaSostituzione.DoesNotExist):
            return JsonResponse({'ok': False, 'error': 'Richiesta non trovata.'})

        if decisione == 'rifiuta':
            richiesta.stato = 'RIFIUTATA_RA'
            richiesta.save(update_fields=['stato'])
            return JsonResponse({'ok': True, 'message': 'Richiesta di sostituzione rifiutata.'})
        else:
            from .services import approva_e_invia_sostituto
            sost_pk = int(sostituto_id) if (sostituto_id and str(sostituto_id).isdigit()) else None
            ok = approva_e_invia_sostituto(richiesta.pk, sostituto_id=sost_pk)
            if ok:
                return JsonResponse({'ok': True, 'message': '✅ Richiesta approvata e inviata al sostituto!'})
            return JsonResponse({'ok': False, 'error': 'Seleziona un sostituto disponibile.'})

    # 5. INVIA SEGNALAZIONE (Guasti, Materiali, Problemi Cantiere) + TRIAGE IA
    elif action == 'invia_segnalazione':
        testo = (request.POST.get('messaggio') or '').strip()
        if not testo:
            return JsonResponse({'ok': False, 'error': 'Scrivi il testo della segnalazione prima di inviare.'})

        from .utils_kandor_chat import _crea_segnalazione_con_triage_ia
        seg, triage = _crea_segnalazione_con_triage_ia(dip, testo)
        try:
            from .services import notifica_nuovo_messaggio
            notifica_nuovo_messaggio(dip, f"🚨 SEGNALAZIONE APP [{triage['urgenza']} - {triage['categoria']}]: {testo}")
        except Exception:
            pass
        return JsonResponse({
            'ok': True,
            'message': f"🚨 Segnalazione registrata! Triage IA: [{triage['urgenza']}] {triage['categoria']} — {triage['azione_consigliata']}",
            'triage': triage,
        })

    # 6. INVIA MESSAGGIO CHAT ALL'UFFICIO (testo + foto/allegato)
    elif action == 'invia_messaggio_chat':
        testo = (request.POST.get('testo') or '').strip()
        uploaded_files = request.FILES.getlist('allegato')

        if not testo and not uploaded_files:
            return JsonResponse({'ok': False, 'error': 'Scrivi un messaggio o allega un file/foto.'})

        from .utils_kandor_chat import prepare_uploaded_attachments
        from .services import notifica_nuovo_messaggio

        created_msgs = []
        if uploaded_files:
            attachments = prepare_uploaded_attachments(uploaded_files)
            for idx, att in enumerate(attachments):
                cap = testo if idx == 0 else ''
                label_testo = cap if cap else f"📎 Allegato: {att['name']}"
                msg_obj = MessaggioChat.objects.create(
                    dipendente=dip,
                    testo=label_testo,
                    foto_url=att['url'] if att.get('is_image') else '',
                    allegato_url=att['url'] if not att.get('is_image') else '',
                    allegato_nome=att['name'],
                    direzione='IN',
                )
                created_msgs.append(msg_obj)
            try:
                notifica_nuovo_messaggio(dip, testo or f"[Allegato: {attachments[0]['name']}]")
            except Exception:
                pass
        else:
            msg_obj = MessaggioChat.objects.create(
                dipendente=dip,
                testo=testo,
                direzione='IN',
            )
            created_msgs.append(msg_obj)
            try:
                notifica_nuovo_messaggio(dip, testo)
            except Exception:
                pass

        return JsonResponse({
            'ok': True,
            'messages': [
                {
                    'id': m.id,
                    'testo': m.testo,
                    'direzione': m.direzione,
                    'foto_url': m.foto_url or '',
                    'allegato_url': m.allegato_url or '',
                    'allegato_nome': m.allegato_nome or '',
                    'ora': timezone.localtime(m.timestamp).strftime('%d/%m %H:%M'),
                }
                for m in created_msgs
            ],
        })

    # 7. POLLING MESSAGGI CHAT
    elif action == 'poll_chat':
        msgs = list(MessaggioChat.objects.filter(dipendente=dip).order_by('-timestamp')[:60])
        msgs.reverse()
        return JsonResponse({
            'ok': True,
            'messages': [
                {
                    'id': m.id,
                    'testo': m.testo,
                    'direzione': m.direzione,
                    'foto_url': m.foto_url or '',
                    'allegato_url': m.allegato_url or '',
                    'allegato_nome': m.allegato_nome or '',
                    'ora': timezone.localtime(m.timestamp).strftime('%d/%m %H:%M'),
                }
                for m in msgs
            ],
        })

    # 8. AGGIORNA FOTO PROFILO
    elif action == 'aggiorna_foto':
        foto_file = request.FILES.get('foto')
        if not foto_file:
            return JsonResponse({'ok': False, 'error': 'Seleziona o scatta una foto.'})

        dip.foto = foto_file
        dip.save()
        new_url = _get_photo_url(dip)
        if new_url:
            dip.foto_profilo_url = new_url
            dip.save(update_fields=['foto_profilo_url'])
        return JsonResponse({
            'ok': True,
            'message': '📸 Foto profilo aggiornata con successo!',
            'foto_url': new_url or '',
        })

    # 9. ASSISTENTE IA IN LINGUAGGIO NATURALE / VOCALE (registra ore, assenze, segnalazioni)
    elif action == 'assistente_ia':
        testo = (request.POST.get('testo') or '').strip()
        if not testo:
            return JsonResponse({'ok': False, 'error': 'Scrivi o detta una richiesta (es. "Oggi 4 ore da Condominio Verdi" o "Domani malattia").'})

        from .ai_engine import interpreta_messaggio_libero
        from .utils_kandor_chat import _salva_ore_turno, _gestisci_assenza_con_sostituzione, _crea_segnalazione_con_triage_ia

        parsed = interpreta_messaggio_libero(dip, testo)
        intent = parsed.get('intent')

        if intent == 'REGISTRA_ORE' and parsed.get('ore') and parsed.get('assegnazione_id'):
            ass = AssegnazioneTurno.objects.select_related('cliente', 'turno').filter(pk=parsed['assegnazione_id']).first()
            if ass:
                _salva_ore_turno(dip, ass, parsed['ore'], testo)
                return JsonResponse({
                    'ok': True,
                    'intent': 'REGISTRA_ORE',
                    'message': f"🤖 Assistente IA: Registrate {parsed['ore']:g}h per {ass.cliente.ragione_sociale} ({ass.turno.data.strftime('%d/%m/%Y')})!",
                })

        if intent == 'ASSENZA' and parsed.get('tipo_assenza'):
            tipo = parsed['tipo_assenza']
            d_ini = parsed.get('data_inizio') or timezone.now().date()
            d_fin = parsed.get('data_fine') or d_ini
            _gestisci_assenza_con_sostituzione(dip, tipo, f"Richiesta {tipo} via Assistente IA WebApp", "", data_inizio=d_ini, data_fine=d_fin)
            return JsonResponse({
                'ok': True,
                'intent': 'ASSENZA',
                'message': f"🤖 Assistente IA: Inviata richiesta di {tipo} ({d_ini.strftime('%d/%m/%Y')} - {d_fin.strftime('%d/%m/%Y')}) in attesa di avvallo!",
            })

        if intent == 'SEGNALAZIONE':
            seg, triage = _crea_segnalazione_con_triage_ia(dip, testo)
            return JsonResponse({
                'ok': True,
                'intent': 'SEGNALAZIONE',
                'message': f"🤖 Assistente IA: Segnalazione registrata [{triage['urgenza']} - {triage['categoria']}]. {triage['azione_consigliata']}",
            })

        return JsonResponse({
            'ok': False,
            'error': '🤖 Non sono riuscito ad associare automaticamente un turno o un\'assenza. Prova a specificare le ore e il cantiere (es. "Oggi 4 ore da Rossi") oppure "Domani malattia".',
        })

    return JsonResponse({'ok': False, 'error': f'Azione non riconosciuta: {action}'}, status=400)


def dipendente_app_manifest_view(request):
    manifest = {
        "name": "Kandor - App Dipendenti",
        "short_name": "Kandor",
        "description": "App Dipendenti Kandor: turni, registrazione ore, calendario, assenze, sostituzioni e chat con l'ufficio.",
        "start_url": "/app/",
        "scope": "/app/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0F172A",
        "theme_color": "#FF6F00",
        "icons": [
            {
                "src": "/app/icon.svg",
                "sizes": "192x192 512x512",
                "type": "image/svg+xml",
                "purpose": "any maskable"
            }
        ]
    }
    return JsonResponse(manifest)


def dipendente_app_icon_view(request):
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F172A"/>
      <stop offset="100%" stop-color="#1E293B"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF8F00"/>
      <stop offset="100%" stop-color="#FF6F00"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#bg)"/>
  <circle cx="256" cy="256" r="196" fill="none" stroke="url(#accent)" stroke-width="16" opacity="0.9"/>
  <path d="M168 140 h48 v102 l92 -102 h58 l-98 106 l104 126 h-60 l-78 -96 l-18 20 v76 h-48 z" fill="url(#accent)"/>
</svg>"""
    return HttpResponse(svg, content_type="image/svg+xml")


def dipendente_app_sw_view(request):
    js = """const CACHE_NAME = 'kandor-app-v1';
self.addEventListener('install', (event) => {
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
"""
    response = HttpResponse(js, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/app/"
    return response
