"""
Viste, serializzatori e API per la Gestione Procedure Operative e Checklist (/procedure/).
"""
import json
from datetime import datetime

from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    ModelloProcedura, PassoModelloProcedura,
    ProceduraAvviata, PassoProceduraAvviata, AvvalloPassoProcedura,
    Cliente, Dipendente, DEFAULT_PROCEDURE, ensure_default_procedure,
)
from .services import (
    get_operatore_portale,
    get_operatori_rapidi_portale,
    passo_bloccato_da_avvallo_precedente,
    richiedi_avvallo_passo_procedura,
    conferma_avvallo_passo_procedura,
)


def _serialize_pratica(pratica):
    """Serializza una ProceduraAvviata con i suoi passaggi e relativi avvalli per risposte JSON."""
    passaggi = list(
        pratica.passaggi.prefetch_related('avvalli__dipendente', 'avvalli__richiesto_da')
        .all()
        .order_by('ordine', 'id')
    )
    totale = len(passaggi)
    completati = sum(1 for p in passaggi if p.completato)
    percentuale = int(round((completati / totale) * 100)) if totale else 0

    primo_blocco = None
    primo_blocco_nomi = []
    for p in passaggi:
        avvs = list(p.avvalli.all())
        if avvs and p.bloccante:
            in_attesa = [a for a in avvs if a.stato != 'APPROVATO']
            if in_attesa or not p.completato:
                primo_blocco = p
                primo_blocco_nomi = [f"{a.dipendente.nome} {a.dipendente.cognome}" for a in (in_attesa or avvs)]
                break

    passaggi_serialized = []
    for p in passaggi:
        avvs = list(p.avvalli.all())
        in_attesa_list = [a for a in avvs if a.stato != 'APPROVATO']
        approvati_list = [a for a in avvs if a.stato == 'APPROVATO']
        is_bloccato_prec = bool(primo_blocco and p.ordine > primo_blocco.ordine)
        nota_rich = next((a.nota_richiesta for a in avvs if a.nota_richiesta), '')

        passaggi_serialized.append({
            'id': p.id,
            'ordine': p.ordine,
            'titolo': p.titolo,
            'descrizione': p.descrizione or '',
            'completato': p.completato,
            'data_completamento_fmt': p.data_completamento.strftime('%d/%m/%Y %H:%M') if p.data_completamento else '',
            'note_esecuzione': p.note_esecuzione or '',
            'richiede_avvallo': p.richiede_avvallo or bool(avvs),
            'bloccante': p.bloccante,
            'nota_richiesta_avvallo': nota_rich,
            'avvalli_totale': len(avvs),
            'avvalli_approvati': len(approvati_list),
            'avvalli_in_attesa': len(in_attesa_list),
            'bloccato_da_precedente': is_bloccato_prec,
            'bloccato_da_ordine': primo_blocco.ordine if is_bloccato_prec else None,
            'bloccato_da_titolo': primo_blocco.titolo if is_bloccato_prec else '',
            'bloccato_da_nomi': ", ".join(primo_blocco_nomi) if is_bloccato_prec else '',
            'avvalli': [
                {
                    'id': a.id,
                    'dipendente_id': a.dipendente_id,
                    'dipendente_nome': f"{a.dipendente.nome} {a.dipendente.cognome}",
                    'dipendente_cognome_nome': f"{a.dipendente.cognome} {a.dipendente.nome}",
                    'has_telegram': bool(a.dipendente.telegram_chat_id),
                    'stato': a.stato,
                    'stato_label': a.get_stato_display(),
                    'nota_richiesta': a.nota_richiesta or '',
                    'nota_risposta': a.nota_risposta or '',
                    'data_richiesta_fmt': a.data_richiesta.strftime('%d/%m/%Y %H:%M') if a.data_richiesta else '',
                    'data_risposta_fmt': a.data_risposta.strftime('%d/%m/%Y %H:%M') if a.data_risposta else '',
                }
                for a in avvs
            ],
        })

    return {
        'id': pratica.id,
        'modello_id': pratica.modello_id,
        'modello_nome': pratica.modello.nome if pratica.modello else 'Procedura Personalizzata',
        'titolo': pratica.titolo,
        'cliente_id': pratica.cliente_id,
        'cliente_nome': str(pratica.cliente) if pratica.cliente else '',
        'dipendente_id': pratica.dipendente_id,
        'dipendente_nome': f"{pratica.dipendente.nome} {pratica.dipendente.cognome}" if pratica.dipendente else '',
        'stato': pratica.stato,
        'stato_label': pratica.get_stato_display(),
        'data_avvio': pratica.data_avvio.strftime('%Y-%m-%d') if pratica.data_avvio else '',
        'data_avvio_fmt': pratica.data_avvio.strftime('%d/%m/%Y') if pratica.data_avvio else '',
        'data_scadenza': pratica.data_scadenza.strftime('%Y-%m-%d') if pratica.data_scadenza else '',
        'data_scadenza_fmt': pratica.data_scadenza.strftime('%d/%m/%Y') if pratica.data_scadenza else '',
        'data_completamento_fmt': pratica.data_completamento.strftime('%d/%m/%Y %H:%M') if pratica.data_completamento else '',
        'note': pratica.note or '',
        'totale_passaggi': totale,
        'passaggi_completati': completati,
        'percentuale': percentuale,
        'passaggi': passaggi_serialized,
    }


def _serialize_modello(modello):
    """Serializza un ModelloProcedura con i suoi passaggi per risposte JSON."""
    passaggi = list(modello.passaggi.prefetch_related('incaricati_default').all().order_by('ordine', 'id'))
    return {
        'id': modello.id,
        'nome': modello.nome,
        'categoria': modello.categoria or 'Operativa / Contrattuale',
        'descrizione': modello.descrizione or '',
        'attivo': modello.attivo,
        'totale_passaggi': len(passaggi),
        'pratiche_attive': modello.procedure_avviate.filter(stato='IN_CORSO').count(),
        'passaggi': [
            {
                'id': p.id,
                'ordine': p.ordine,
                'titolo': p.titolo,
                'descrizione': p.descrizione or '',
                'obbligatorio': p.obbligatorio,
                'incaricati_default': [
                    {
                        'id': d.id,
                        'nome': f"{d.nome} {d.cognome}",
                    }
                    for d in p.incaricati_default.all()
                ],
            }
            for p in passaggi
        ],
    }


def gestione_procedure_view(request):
    """
    Dashboard completa per la gestione delle Procedure aziendali (/procedure/).
    """
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return redirect_to_login(request.get_full_path(), '/admin/login/')

    ensure_default_procedure()

    operatore_attivo = get_operatore_portale(request)
    operatori_rapidi = get_operatori_rapidi_portale()

    tab_attivo = request.GET.get('tab', 'pratiche').strip()
    if tab_attivo not in ('pratiche', 'modelli'):
        tab_attivo = 'pratiche'

    stato_filter = request.GET.get('stato', 'TUTTE').strip().upper()
    if stato_filter not in ('TUTTE', 'IN_CORSO', 'COMPLETATA', 'ANNULLATA'):
        stato_filter = 'TUTTE'

    vista_filter = request.GET.get('vista', 'TUTTE').strip().upper()
    if vista_filter not in ('TUTTE', 'MIE', 'DA_AVVALLARE'):
        vista_filter = 'TUTTE'

    q = request.GET.get('q', '').strip()
    cliente_filter = request.GET.get('cliente', '').strip()
    modello_filter = request.GET.get('modello', '').strip()
    avvia_cliente_id = request.GET.get('avvia_cliente', '').strip()
    avvia_modello_id = request.GET.get('avvia_modello', '').strip()
    pratica_focus_id = request.GET.get('pratica', '').strip()

    modelli = list(
        ModelloProcedura.objects.prefetch_related('passaggi__incaricati_default', 'procedure_avviate').order_by('ordine', 'nome')
    )

    pratiche_qs = ProceduraAvviata.objects.select_related(
        'modello', 'cliente', 'dipendente'
    ).prefetch_related(
        'passaggi__avvalli__dipendente',
        'passaggi__avvalli__richiesto_da',
    ).order_by('-data_avvio', '-id')

    totale_pratiche = pratiche_qs.count()
    pratiche_in_corso = pratiche_qs.filter(stato='IN_CORSO').count()
    pratiche_completate = pratiche_qs.filter(stato='COMPLETATA').count()
    mie_pratiche_in_corso = pratiche_qs.filter(stato='IN_CORSO', dipendente=operatore_attivo).count() if operatore_attivo else 0
    miei_avvalli_pendenti = (
        AvvalloPassoProcedura.objects.filter(
            dipendente=operatore_attivo,
            stato='IN_ATTESA',
            passo__procedura__stato='IN_CORSO',
        ).count()
        if operatore_attivo else 0
    )

    if stato_filter != 'TUTTE':
        pratiche_qs = pratiche_qs.filter(stato=stato_filter)
    if vista_filter == 'MIE' and operatore_attivo:
        pratiche_qs = pratiche_qs.filter(dipendente=operatore_attivo)
    elif vista_filter == 'DA_AVVALLARE' and operatore_attivo:
        pratiche_qs = pratiche_qs.filter(passaggi__avvalli__dipendente=operatore_attivo, passaggi__avvalli__stato='IN_ATTESA').distinct()
    if cliente_filter.isdigit():
        pratiche_qs = pratiche_qs.filter(cliente_id=int(cliente_filter))
    if modello_filter.isdigit():
        pratiche_qs = pratiche_qs.filter(modello_id=int(modello_filter))
    if q:
        pratiche_qs = pratiche_qs.filter(
            Q(titolo__icontains=q)
            | Q(cliente__ragione_sociale__icontains=q)
            | Q(modello__nome__icontains=q)
            | Q(note__icontains=q)
            | Q(dipendente__nome__icontains=q)
            | Q(dipendente__cognome__icontains=q)
        )

    pratiche = list(pratiche_qs)
    for pr in pratiche:
        pr.serialized_json = json.dumps(_serialize_pratica(pr))
        passi_pr = list(pr.passaggi.all())
        primo_blocco = None
        primo_blocco_nomi = []
        for p in passi_pr:
            avvs = list(p.avvalli.all())
            if avvs and p.bloccante:
                in_att = [a for a in avvs if a.stato != 'APPROVATO']
                if in_att or not p.completato:
                    primo_blocco = p
                    primo_blocco_nomi = [f"{a.dipendente.nome} {a.dipendente.cognome}" for a in (in_att or avvs)]
                    break
        for p in passi_pr:
            avvs = list(p.avvalli.all())
            p.avvalli_list = avvs
            p.avvalli_ids = [a.dipendente_id for a in avvs]
            p.nota_richiesta_avvallo = next((a.nota_richiesta for a in avvs if a.nota_richiesta), '')
            p.ha_avvalli_pendenti = any(a.stato != 'APPROVATO' for a in avvs)
            p.bloccato_da_precedente = bool(primo_blocco and p.ordine > primo_blocco.ordine)
            p.bloccato_da_ordine = primo_blocco.ordine if p.bloccato_da_precedente else None
            p.bloccato_da_titolo = primo_blocco.titolo if p.bloccato_da_precedente else ''
            p.bloccato_da_nomi = ", ".join(primo_blocco_nomi) if p.bloccato_da_precedente else ''

    clienti = Cliente.objects.all().order_by('ragione_sociale')
    dipendenti = list(operatori_rapidi)

    dipendenti_js = [
        {
            'id': d.id,
            'nome': f"{d.nome} {d.cognome}",
            'cognome_nome': f"{d.cognome} {d.nome}",
            'has_telegram': bool(d.telegram_chat_id),
            'is_rapido': any(r.id == d.id for r in operatori_rapidi),
        }
        for d in dipendenti
    ]
    operatori_rapidi_js = [
        {
            'id': r.id,
            'nome': f"{r.nome} {r.cognome}",
            'has_telegram': bool(r.telegram_chat_id),
        }
        for r in operatori_rapidi
    ]

    modello_disdetta = next((m for m in modelli if 'disdetta' in m.nome.lower()), modelli[0] if modelli else None)

    context = {
        **admin.site.each_context(request),
        'title': 'Gestione Procedure Operative',
        'tab_attivo': tab_attivo,
        'stato_filter': stato_filter,
        'vista_filter': vista_filter,
        'q': q,
        'cliente_filter': int(cliente_filter) if cliente_filter.isdigit() else None,
        'modello_filter': int(modello_filter) if modello_filter.isdigit() else None,
        'avvia_cliente_id': int(avvia_cliente_id) if avvia_cliente_id.isdigit() else None,
        'avvia_modello_id': int(avvia_modello_id) if avvia_modello_id.isdigit() else (modello_disdetta.id if modello_disdetta else None),
        'pratica_focus_id': int(pratica_focus_id) if pratica_focus_id.isdigit() else None,
        'modelli': modelli,
        'pratiche': pratiche,
        'clienti': clienti,
        'dipendenti': dipendenti,
        'operatore_attivo': operatore_attivo,
        'operatori_rapidi': operatori_rapidi,
        'dipendenti_json': json.dumps(dipendenti_js),
        'operatori_rapidi_json': json.dumps(operatori_rapidi_js),
        'totale_pratiche': totale_pratiche,
        'pratiche_in_corso': pratiche_in_corso,
        'pratiche_completate': pratiche_completate,
        'mie_pratiche_in_corso': mie_pratiche_in_corso,
        'miei_avvalli_pendenti': miei_avvalli_pendenti,
        'totale_modelli': len(modelli),
        'oggi_iso': timezone.localdate().strftime('%Y-%m-%d'),
    }
    return render(request, 'core/procedure.html', context)


@csrf_exempt
def gestione_procedure_api(request):
    """
    Endpoint API JSON per tutte le operazioni sulle Procedure (Modelli e Pratiche Avviate).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)
    if not request.user.is_staff and not request.session.get('titolare_id'):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = request.POST.dict()

    action = (data.get('action') or '').strip()

    try:
        if action == 'set_operatore_portale':
            return JsonResponse({
                'ok': False,
                'error': 'Il cambio operatore da tendina è disabilitato: ogni operatore deve accedere con le proprie credenziali personali.',
            }, status=403)

        elif action == 'avvia_procedura':
            modello_id = data.get('modello_id')
            cliente_id = data.get('cliente_id')
            dipendente_id = data.get('dipendente_id')
            titolo = (data.get('titolo') or '').strip()
            note = (data.get('note') or '').strip()
            data_avvio_str = (data.get('data_avvio') or '').strip()
            data_scadenza_str = (data.get('data_scadenza') or '').strip()

            modello = ModelloProcedura.objects.filter(pk=modello_id).first() if modello_id else None
            cliente = Cliente.objects.filter(pk=cliente_id).first() if cliente_id else None
            dipendente = Dipendente.objects.filter(pk=dipendente_id).first() if dipendente_id else None
            if not dipendente:
                dipendente = get_operatore_portale(request)

            if not modello and not titolo:
                return JsonResponse({'ok': False, 'error': 'Seleziona una procedura o inserisci un titolo.'}, status=400)

            if not titolo:
                if modello and cliente:
                    titolo = f"{modello.nome} - {cliente.ragione_sociale}"
                elif modello:
                    titolo = modello.nome

            data_avvio = timezone.localdate()
            if data_avvio_str:
                try:
                    data_avvio = datetime.strptime(data_avvio_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            data_scadenza = None
            if data_scadenza_str:
                try:
                    data_scadenza = datetime.strptime(data_scadenza_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            pratica = ProceduraAvviata.objects.create(
                modello=modello,
                titolo=titolo,
                cliente=cliente,
                dipendente=dipendente,
                stato='IN_CORSO',
                data_avvio=data_avvio,
                data_scadenza=data_scadenza,
                note=note,
            )

            if modello:
                pratica.copia_passaggi_da_modello()
                for passo_avv in pratica.passaggi.prefetch_related('avvalli__dipendente').all():
                    inc_ids = [a.dipendente_id for a in passo_avv.avvalli.all()]
                    if inc_ids:
                        richiedi_avvallo_passo_procedura(
                            passo=passo_avv,
                            dipendenti_ids=inc_ids,
                            richiesto_da=dipendente,
                            nota_richiesta='',
                            bloccante=True,
                            reinvia_notifica=True,
                        )

            passaggi_extra = data.get('passaggi_extra') or []
            if isinstance(passaggi_extra, list) and passaggi_extra:
                base_ord = pratica.passaggi.count()
                for idx, p_item in enumerate(passaggi_extra, start=base_ord + 1):
                    p_titolo = (p_item.get('titolo') if isinstance(p_item, dict) else str(p_item)).strip()
                    p_desc = (p_item.get('descrizione', '') if isinstance(p_item, dict) else '').strip()
                    if p_titolo:
                        PassoProceduraAvviata.objects.create(
                            procedura=pratica,
                            ordine=idx,
                            titolo=p_titolo,
                            descrizione=p_desc,
                        )

            return JsonResponse({
                'ok': True,
                'message': f'Procedura "{pratica.titolo}" avviata con successo.',
                'pratica': _serialize_pratica(pratica),
            })

        elif action == 'toggle_passo_pratica':
            passo_id = data.get('passo_id')
            passo = PassoProceduraAvviata.objects.select_related('procedura').prefetch_related('avvalli__dipendente').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Passaggio non trovato.'}, status=404)

            if 'completato' in data and data.get('completato') is not None:
                target_completato = bool(data.get('completato'))
            else:
                target_completato = not passo.completato

            if target_completato:
                passo_blocco, nomi_blocco = passo_bloccato_da_avvallo_precedente(passo)
                if passo_blocco:
                    return JsonResponse({
                        'ok': False,
                        'error': f"⏸️ Il punto #{passo.ordine} è in attesa dell'avvallo del punto #{passo_blocco.ordine} ({passo_blocco.titolo}) da parte di: {', '.join(nomi_blocco)}.",
                        'pratica': _serialize_pratica(passo.procedura),
                    }, status=400)

                avvalli_pendenti = [a for a in passo.avvalli.all() if a.stato != 'APPROVATO']
                if avvalli_pendenti:
                    operatore_curr = get_operatore_portale(request)
                    mio_avv = next((a for a in avvalli_pendenti if operatore_curr and a.dipendente_id == operatore_curr.id), None)
                    if mio_avv:
                        res_avv = conferma_avvallo_passo_procedura(avvallo_id=mio_avv.id, source='PORTALE')
                        return JsonResponse({
                            'ok': res_avv.get('ok', False),
                            'message': res_avv.get('message', ''),
                            'pratica': _serialize_pratica(passo.procedura),
                        })
                    nomi_mancanti = ", ".join(f"{a.dipendente.nome} {a.dipendente.cognome}" for a in avvalli_pendenti)
                    return JsonResponse({
                        'ok': False,
                        'error': f"⏳ Questo passaggio richiede prima l'OK di avvallo da: {nomi_mancanti}. Usa il pulsante '✅ Dai l'OK' del collega.",
                        'pratica': _serialize_pratica(passo.procedura),
                    }, status=400)

            passo.completato = target_completato
            passo.data_completamento = timezone.now() if passo.completato else None
            passo.save(update_fields=['completato', 'data_completamento'])

            pratica = passo.procedura
            pratica.ricalcola_stato()

            return JsonResponse({
                'ok': True,
                'message': f'Punto #{passo.ordine} {"completato ✅" if passo.completato else "riaperto"}.',
                'pratica': _serialize_pratica(pratica),
            })

        elif action == 'richiedi_avvallo_passo':
            passo_id = data.get('passo_id')
            dipendenti_ids = data.get('dipendenti_ids') or []
            nota_richiesta = (data.get('nota_richiesta') or '').strip()
            bloccante = bool(data.get('bloccante', True))
            reinvia_notifica = bool(data.get('reinvia_notifica', False))
            salva_nel_modello = bool(data.get('salva_nel_modello', False))

            passo = PassoProceduraAvviata.objects.select_related('procedura__dipendente', 'procedura__cliente', 'procedura__modello').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Passaggio non trovato.'}, status=404)

            operatore_curr = get_operatore_portale(request) or passo.procedura.dipendente
            res_avv = richiedi_avvallo_passo_procedura(
                passo=passo,
                dipendenti_ids=dipendenti_ids,
                richiesto_da=operatore_curr,
                nota_richiesta=nota_richiesta,
                bloccante=bloccante,
                reinvia_notifica=reinvia_notifica,
            )

            if salva_nel_modello and passo.procedura.modello_id:
                pm = PassoModelloProcedura.objects.filter(
                    modello_id=passo.procedura.modello_id,
                    titolo__iexact=passo.titolo,
                ).first()
                if pm:
                    clean_ids = [int(x) for x in dipendenti_ids if str(x).isdigit()]
                    pm.incaricati_default.set(clean_ids)

            return JsonResponse({
                'ok': True,
                'message': res_avv.get('message', 'Richiesta di avvallo aggiornata.'),
                'notificati_telegram': res_avv.get('notificati_telegram', 0),
                'pratica': _serialize_pratica(passo.procedura),
            })

        elif action == 'conferma_avvallo_passo':
            avvallo_id = data.get('avvallo_id')
            passo_id = data.get('passo_id')
            nota_risposta = (data.get('nota_risposta') or '').strip()

            op_curr = get_operatore_portale(request)
            if not op_curr:
                return JsonResponse({
                    'ok': False,
                    'error': "Per dare l'OK di avvallo devi accedere al portale con il tuo account operatore personale (oppure confermare dal tuo Telegram personale).",
                }, status=403)

            if avvallo_id:
                avv_target = AvvalloPassoProcedura.objects.select_related('dipendente').filter(pk=avvallo_id).first()
                if avv_target and avv_target.dipendente_id != op_curr.id:
                    return JsonResponse({
                        'ok': False,
                        'error': f"⛔ Solo {avv_target.dipendente.nome} {avv_target.dipendente.cognome} (accedendo col proprio account o da Telegram) può dare l'OK per questo avvallo.",
                    }, status=403)

            res = conferma_avvallo_passo_procedura(
                avvallo_id=avvallo_id,
                passo_id=passo_id,
                dipendente_id=op_curr.id,
                nota_risposta=nota_risposta,
                source='PORTALE',
            )
            if not res.get('ok'):
                return JsonResponse({'ok': False, 'error': res.get('error', 'Errore avvallo')}, status=400)

            pratica = res.get('pratica')
            return JsonResponse({
                'ok': True,
                'tutti_approvati': res.get('tutti_approvati', False),
                'message': res.get('message', 'OK registrato!'),
                'pratica': _serialize_pratica(pratica) if pratica else None,
            })

        elif action == 'rimuovi_singolo_avvallo_passo':
            avvallo_id = data.get('avvallo_id')
            avv = AvvalloPassoProcedura.objects.select_related('passo__procedura', 'dipendente').filter(pk=avvallo_id).first()
            if not avv:
                return JsonResponse({'ok': False, 'error': 'Avvallo non trovato.'}, status=404)
            passo = avv.passo
            pratica = passo.procedura
            nome_rimosso = f"{avv.dipendente.nome} {avv.dipendente.cognome}"
            avv.delete()

            restanti = list(passo.avvalli.all())
            passo.richiede_avvallo = bool(restanti)
            if restanti and all(a.stato == 'APPROVATO' for a in restanti) and not passo.completato:
                passo.completato = True
                passo.data_completamento = timezone.now()
            passo.save()
            pratica.ricalcola_stato()

            return JsonResponse({
                'ok': True,
                'message': f"{nome_rimosso} rimosso dall'avvallo del punto #{passo.ordine}.",
                'pratica': _serialize_pratica(pratica),
            })

        elif action == 'segna_avvallo_letto':
            passo_id = data.get('passo_id')
            if passo_id:
                AvvalloPassoProcedura.objects.filter(passo_id=passo_id).update(letto_da_responsabile=True)
            return JsonResponse({'ok': True})

        elif action == 'aggiungi_passo_pratica':
            pratica_id = data.get('pratica_id')
            titolo = (data.get('titolo') or '').strip()
            descrizione = (data.get('descrizione') or '').strip()
            salva_anche_nel_modello = bool(data.get('salva_anche_nel_modello', False))

            if not titolo:
                return JsonResponse({'ok': False, 'error': 'Inserisci il titolo del nuovo punto.'}, status=400)

            pratica = ProceduraAvviata.objects.filter(pk=pratica_id).first()
            if not pratica:
                return JsonResponse({'ok': False, 'error': 'Procedura non trovata.'}, status=404)

            nuovo_ordine = pratica.passaggi.count() + 1
            PassoProceduraAvviata.objects.create(
                procedura=pratica,
                ordine=nuovo_ordine,
                titolo=titolo,
                descrizione=descrizione,
                completato=False,
            )
            pratica.riordina_passaggi()
            pratica.ricalcola_stato()

            modello_serializzato = None
            if salva_anche_nel_modello and pratica.modello:
                ord_mod = pratica.modello.passaggi.count() + 1
                PassoModelloProcedura.objects.create(
                    modello=pratica.modello,
                    ordine=ord_mod,
                    titolo=titolo,
                    descrizione=descrizione,
                    obbligatorio=True,
                )
                pratica.modello.riordina_passaggi()
                modello_serializzato = _serialize_modello(pratica.modello)

            return JsonResponse({
                'ok': True,
                'message': f'Nuovo punto "{titolo}" aggiunto alla procedura.',
                'pratica': _serialize_pratica(pratica),
                'modello': modello_serializzato,
            })

        elif action == 'modifica_passo_pratica':
            passo_id = data.get('passo_id')
            passo = PassoProceduraAvviata.objects.select_related('procedura').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Passaggio non trovato.'}, status=404)

            if 'titolo' in data:
                nuovo_titolo = (data.get('titolo') or '').strip()
                if not nuovo_titolo:
                    return JsonResponse({'ok': False, 'error': 'Il titolo del punto non può essere vuoto.'}, status=400)
                passo.titolo = nuovo_titolo
            if 'descrizione' in data:
                passo.descrizione = (data.get('descrizione') or '').strip()
            if 'note_esecuzione' in data:
                passo.note_esecuzione = (data.get('note_esecuzione') or '').strip()

            passo.save()
            return JsonResponse({
                'ok': True,
                'message': f'Punto #{passo.ordine} aggiornato.',
                'pratica': _serialize_pratica(passo.procedura),
            })

        elif action == 'elimina_passo_pratica':
            passo_id = data.get('passo_id')
            passo = PassoProceduraAvviata.objects.select_related('procedura').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Passaggio non trovato.'}, status=404)

            pratica = passo.procedura
            titolo_rimosso = passo.titolo
            passo.delete()
            pratica.riordina_passaggi()
            pratica.ricalcola_stato()

            return JsonResponse({
                'ok': True,
                'message': f'Punto "{titolo_rimosso}" rimosso dalla procedura.',
                'pratica': _serialize_pratica(pratica),
            })

        elif action == 'sposta_passo_pratica':
            passo_id = data.get('passo_id')
            direzione = (data.get('direzione') or '').strip().lower()
            passo = PassoProceduraAvviata.objects.select_related('procedura').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Passaggio non trovato.'}, status=404)

            pratica = passo.procedura
            passaggi = list(pratica.passaggi.all().order_by('ordine', 'id'))
            idx = next((i for i, p in enumerate(passaggi) if p.id == passo.id), None)
            if idx is not None:
                if direzione == 'up' and idx > 0:
                    passaggi[idx], passaggi[idx - 1] = passaggi[idx - 1], passaggi[idx]
                elif direzione == 'down' and idx < len(passaggi) - 1:
                    passaggi[idx], passaggi[idx + 1] = passaggi[idx + 1], passaggi[idx]

                for nuovo_idx, item in enumerate(passaggi, start=1):
                    if item.ordine != nuovo_idx:
                        item.ordine = nuovo_idx
                        item.save(update_fields=['ordine'])

            return JsonResponse({
                'ok': True,
                'message': 'Ordine dei punti aggiornato.',
                'pratica': _serialize_pratica(pratica),
            })

        elif action == 'modifica_pratica':
            pratica_id = data.get('pratica_id')
            pratica = ProceduraAvviata.objects.filter(pk=pratica_id).first()
            if not pratica:
                return JsonResponse({'ok': False, 'error': 'Pratica non trovata.'}, status=404)

            if 'titolo' in data and (data.get('titolo') or '').strip():
                pratica.titolo = data.get('titolo').strip()
            if 'note' in data:
                pratica.note = (data.get('note') or '').strip()
            if 'cliente_id' in data:
                cid = data.get('cliente_id')
                pratica.cliente = Cliente.objects.filter(pk=cid).first() if cid else None
            if 'dipendente_id' in data:
                did = data.get('dipendente_id')
                pratica.dipendente = Dipendente.objects.filter(pk=did).first() if did else None
            if 'data_scadenza' in data:
                ds = (data.get('data_scadenza') or '').strip()
                if ds:
                    try:
                        pratica.data_scadenza = datetime.strptime(ds, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                else:
                    pratica.data_scadenza = None
            if 'stato' in data and data.get('stato') in ('IN_CORSO', 'COMPLETATA', 'ANNULLATA'):
                pratica.stato = data.get('stato')
                if pratica.stato == 'COMPLETATA' and not pratica.data_completamento:
                    pratica.data_completamento = timezone.now()
                elif pratica.stato != 'COMPLETATA':
                    pratica.data_completamento = None

            pratica.save()
            return JsonResponse({
                'ok': True,
                'message': 'Pratica aggiornata.',
                'pratica': _serialize_pratica(pratica),
            })

        elif action == 'elimina_pratica':
            pratica_id = data.get('pratica_id')
            pratica = ProceduraAvviata.objects.filter(pk=pratica_id).first()
            if not pratica:
                return JsonResponse({'ok': False, 'error': 'Pratica non trovata.'}, status=404)
            titolo = pratica.titolo
            pratica.delete()
            return JsonResponse({
                'ok': True,
                'message': f'Pratica "{titolo}" eliminata.',
                'deleted_id': pratica_id,
            })

        elif action == 'crea_modello':
            nome = (data.get('nome') or '').strip()
            categoria = (data.get('categoria') or 'Operativa / Contrattuale').strip()
            descrizione = (data.get('descrizione') or '').strip()
            passaggi_raw = data.get('passaggi') or []

            if not nome:
                return JsonResponse({'ok': False, 'error': 'Inserisci il nome della procedura.'}, status=400)
            if ModelloProcedura.objects.filter(nome__iexact=nome).exists():
                return JsonResponse({'ok': False, 'error': f'Esiste già una procedura chiamata "{nome}".'}, status=400)

            modello = ModelloProcedura.objects.create(
                nome=nome,
                categoria=categoria or 'Operativa / Contrattuale',
                descrizione=descrizione,
                ordine=ModelloProcedura.objects.count() + 1,
                attivo=True,
            )

            if isinstance(passaggi_raw, str):
                lines = [ln.strip() for ln in passaggi_raw.splitlines() if ln.strip()]
                passaggi_raw = [{'titolo': ln, 'descrizione': ''} for ln in lines]

            if isinstance(passaggi_raw, list):
                for idx, item in enumerate(passaggi_raw, start=1):
                    if isinstance(item, dict):
                        p_titolo = (item.get('titolo') or '').strip()
                        p_desc = (item.get('descrizione') or '').strip()
                    else:
                        p_titolo = str(item).strip()
                        p_desc = ''
                    if p_titolo:
                        PassoModelloProcedura.objects.create(
                            modello=modello,
                            ordine=idx,
                            titolo=p_titolo,
                            descrizione=p_desc,
                            obbligatorio=True,
                        )

            return JsonResponse({
                'ok': True,
                'message': f'Modello di procedura "{modello.nome}" creato con successo.',
                'modello': _serialize_modello(modello),
            })

        elif action == 'modifica_modello':
            modello_id = data.get('modello_id')
            modello = ModelloProcedura.objects.filter(pk=modello_id).first()
            if not modello:
                return JsonResponse({'ok': False, 'error': 'Modello di procedura non trovato.'}, status=404)

            if 'nome' in data:
                nuovo_nome = (data.get('nome') or '').strip()
                if not nuovo_nome:
                    return JsonResponse({'ok': False, 'error': 'Il nome della procedura non può essere vuoto.'}, status=400)
                modello.nome = nuovo_nome
            if 'categoria' in data:
                modello.categoria = (data.get('categoria') or 'Operativa / Contrattuale').strip()
            if 'descrizione' in data:
                modello.descrizione = (data.get('descrizione') or '').strip()

            modello.save()
            return JsonResponse({
                'ok': True,
                'message': f'Procedura "{modello.nome}" aggiornata.',
                'modello': _serialize_modello(modello),
            })

        elif action == 'elimina_modello':
            modello_id = data.get('modello_id')
            modello = ModelloProcedura.objects.filter(pk=modello_id).first()
            if not modello:
                return JsonResponse({'ok': False, 'error': 'Modello non trovato.'}, status=404)
            nome = modello.nome
            modello.delete()
            return JsonResponse({
                'ok': True,
                'message': f'Modello "{nome}" eliminato.',
                'deleted_id': modello_id,
            })

        elif action == 'aggiungi_passo_modello':
            modello_id = data.get('modello_id')
            titolo = (data.get('titolo') or '').strip()
            descrizione = (data.get('descrizione') or '').strip()
            propaga_in_corso = bool(data.get('propaga_in_corso', True))

            if not titolo:
                return JsonResponse({'ok': False, 'error': 'Inserisci il titolo del punto da aggiungere.'}, status=400)

            modello = ModelloProcedura.objects.filter(pk=modello_id).first()
            if not modello:
                return JsonResponse({'ok': False, 'error': 'Modello di procedura non trovato.'}, status=404)

            nuovo_ordine = modello.passaggi.count() + 1
            PassoModelloProcedura.objects.create(
                modello=modello,
                ordine=nuovo_ordine,
                titolo=titolo,
                descrizione=descrizione,
                obbligatorio=True,
            )
            modello.riordina_passaggi()

            pratiche_aggiornate = []
            if propaga_in_corso:
                for pratica in modello.procedure_avviate.filter(stato='IN_CORSO'):
                    if not pratica.passaggi.filter(titolo__iexact=titolo).exists():
                        PassoProceduraAvviata.objects.create(
                            procedura=pratica,
                            ordine=pratica.passaggi.count() + 1,
                            titolo=titolo,
                            descrizione=descrizione,
                            completato=False,
                        )
                        pratica.riordina_passaggi()
                        pratica.ricalcola_stato()
                        pratiche_aggiornate.append(_serialize_pratica(pratica))

            return JsonResponse({
                'ok': True,
                'message': f'Punto "{titolo}" aggiunto a "{modello.nome}".',
                'modello': _serialize_modello(modello),
                'pratiche_aggiornate': pratiche_aggiornate,
            })

        elif action == 'modifica_passo_modello':
            passo_id = data.get('passo_id')
            passo = PassoModelloProcedura.objects.select_related('modello').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Punto del modello non trovato.'}, status=404)

            vecchio_titolo = passo.titolo
            nuovo_titolo = (data.get('titolo') or passo.titolo).strip()
            if not nuovo_titolo:
                return JsonResponse({'ok': False, 'error': 'Il titolo non può essere vuoto.'}, status=400)

            passo.titolo = nuovo_titolo
            if 'descrizione' in data:
                passo.descrizione = (data.get('descrizione') or '').strip()
            passo.save()

            pratiche_aggiornate = []
            if bool(data.get('propaga_in_corso', True)):
                for pratica in passo.modello.procedure_avviate.filter(stato='IN_CORSO'):
                    updated = pratica.passaggi.filter(titolo__iexact=vecchio_titolo).update(
                        titolo=passo.titolo,
                        descrizione=passo.descrizione,
                    )
                    if updated:
                        pratiche_aggiornate.append(_serialize_pratica(pratica))

            return JsonResponse({
                'ok': True,
                'message': f'Punto #{passo.ordine} aggiornato.',
                'modello': _serialize_modello(passo.modello),
                'pratiche_aggiornate': pratiche_aggiornate,
            })

        elif action == 'elimina_passo_modello':
            passo_id = data.get('passo_id')
            propaga_in_corso = bool(data.get('propaga_in_corso', True))
            passo = PassoModelloProcedura.objects.select_related('modello').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Punto non trovato.'}, status=404)

            modello = passo.modello
            titolo_rimosso = passo.titolo
            passo.delete()
            modello.riordina_passaggi()

            pratiche_aggiornate = []
            if propaga_in_corso:
                for pratica in modello.procedure_avviate.filter(stato='IN_CORSO'):
                    qs_del = pratica.passaggi.filter(titolo__iexact=titolo_rimosso, completato=False)
                    if qs_del.exists():
                        qs_del.delete()
                        pratica.riordina_passaggi()
                        pratica.ricalcola_stato()
                        pratiche_aggiornate.append(_serialize_pratica(pratica))

            return JsonResponse({
                'ok': True,
                'message': f'Punto "{titolo_rimosso}" rimosso dal modello "{modello.nome}".',
                'modello': _serialize_modello(modello),
                'pratiche_aggiornate': pratiche_aggiornate,
            })

        elif action == 'sposta_passo_modello':
            passo_id = data.get('passo_id')
            direzione = (data.get('direzione') or '').strip().lower()
            passo = PassoModelloProcedura.objects.select_related('modello').filter(pk=passo_id).first()
            if not passo:
                return JsonResponse({'ok': False, 'error': 'Punto non trovato.'}, status=404)

            modello = passo.modello
            passaggi = list(modello.passaggi.all().order_by('ordine', 'id'))
            idx = next((i for i, p in enumerate(passaggi) if p.id == passo.id), None)
            if idx is not None:
                if direzione == 'up' and idx > 0:
                    passaggi[idx], passaggi[idx - 1] = passaggi[idx - 1], passaggi[idx]
                elif direzione == 'down' and idx < len(passaggi) - 1:
                    passaggi[idx], passaggi[idx + 1] = passaggi[idx + 1], passaggi[idx]

                for nuovo_idx, item in enumerate(passaggi, start=1):
                    if item.ordine != nuovo_idx:
                        item.ordine = nuovo_idx
                        item.save(update_fields=['ordine'])

            return JsonResponse({
                'ok': True,
                'message': 'Ordine dei punti aggiornato.',
                'modello': _serialize_modello(modello),
            })

        elif action == 'ripristina_default_disdetta':
            ensure_default_procedure()
            proc_def = DEFAULT_PROCEDURE[0]
            modello = ModelloProcedura.objects.filter(nome__iexact=proc_def['nome']).first()
            if not modello:
                modello = ModelloProcedura.objects.create(
                    nome=proc_def['nome'],
                    categoria=proc_def['categoria'],
                    descrizione=proc_def['descrizione'],
                    ordine=1,
                    attivo=True,
                )
            modello.passaggi.all().delete()
            for idx, (titolo_p, desc_p) in enumerate(proc_def['passaggi'], start=1):
                PassoModelloProcedura.objects.create(
                    modello=modello,
                    ordine=idx,
                    titolo=titolo_p,
                    descrizione=desc_p,
                    obbligatorio=True,
                )
            return JsonResponse({
                'ok': True,
                'message': 'I 6 punti predefiniti della procedura "Disdetta di un contratto" sono stati ripristinati.',
                'modello': _serialize_modello(modello),
            })

        else:
            return JsonResponse({'ok': False, 'error': f'Azione non riconosciuta: {action}'}, status=400)

    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=500)
