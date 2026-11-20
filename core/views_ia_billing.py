"""
Viste ed endpoint API per il Monitoraggio Crediti IA Google Gemini e Fatturazione Clienti (/api/ia/billing/...).
"""
import csv
import json
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .ia_billing_service import (
    get_billing_summary,
    registra_ricarica,
    marca_consumi_fatturati,
    configura_tariffe,
    esegui_test_connessione,
    imposta_gemini_api_key,
)


def _check_auth(request):
    """Verifica che l'utente sia autenticato e abbia la sezione 'credito_ia' abilitata."""
    if not (request.user.is_authenticated or request.session.get('titolare_id') or request.session.get('operatore_id')):
        return False
    try:
        from .accessi_service import get_sezioni_abilitate_per_request
        sezioni = get_sezioni_abilitate_per_request(request)
        if sezioni and 'credito_ia' not in sezioni:
            return False
    except Exception:
        pass
    return True


def ia_billing_status_api(request):
    """
    GET /api/ia/billing/status/
    Restituisce metriche crediti, riepilogo consumi clienti e ultimi log.
    Se ?ping=1, esegue anche il test live di connessione Google API.
    """
    if not _check_auth(request):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    summary = get_billing_summary()

    if request.GET.get('ping') == '1':
        ping_res = esegui_test_connessione()
        summary['ping'] = ping_res
        # Ricarica summary aggiornato con il consumo del ping
        summary = {**get_billing_summary(), 'ping': ping_res}

    return JsonResponse(summary)


@csrf_exempt
def ia_billing_ricarica_api(request):
    """
    POST /api/ia/billing/ricarica/
    Payload JSON: { amount: 20.00, mode: 'add' | 'set', date: 'YYYY-MM-DD' }
    """
    if not _check_auth(request):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
        amount = float(data.get('amount', 20.0))
        mode = data.get('mode', 'add')
        date_str = data.get('date')
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Payload non valido: {e}'}, status=400)

    res = registra_ricarica(amount=amount, mode=mode, date_str=date_str)
    res['summary'] = get_billing_summary()
    return JsonResponse(res)


@csrf_exempt
def ia_billing_test_connection_api(request):
    """
    POST /api/ia/billing/test-connection/
    Esegue test live a Google Gemini con misura latenza ms.
    """
    if not _check_auth(request):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)

    ping_res = esegui_test_connessione()
    summary = get_billing_summary()
    return JsonResponse({
        'ok': ping_res.get('ok', False),
        'ping': ping_res,
        'summary': summary,
    })


@csrf_exempt
def ia_billing_marca_fatturato_api(request):
    """
    POST /api/ia/billing/marca-fatturato/
    Payload JSON: { cliente_id: 123 } oppure { log_ids: [1, 2, 3] }
    """
    if not _check_auth(request):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
        cliente_id = data.get('cliente_id')
        log_ids = data.get('log_ids')
    except Exception:
        cliente_id = None
        log_ids = None

    res = marca_consumi_fatturati(cliente_id=cliente_id, log_ids=log_ids)
    res['summary'] = get_billing_summary()
    return JsonResponse(res)


@csrf_exempt
def ia_billing_configura_tariffe_api(request):
    """
    POST /api/ia/billing/configura-tariffe/
    Payload JSON: { costo_input_1m, costo_output_1m, ricarico_pct }
    """
    if not _check_auth(request):
        return JsonResponse({'ok': False, 'error': 'Non autorizzato'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
        in_1m = data.get('costo_input_1m')
        out_1m = data.get('costo_output_1m')
        ricarico = data.get('ricarico_pct')
        api_key = data.get('gemini_api_key')
        if api_key:
            imposta_gemini_api_key(api_key)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Dati errati: {e}'}, status=400)

    res = configura_tariffe(
        costo_input_1m=in_1m,
        costo_output_1m=out_1m,
        ricarico_pct=ricarico,
    )
    res['summary'] = get_billing_summary()
    return JsonResponse(res)


def ia_billing_export_csv_view(request):
    """
    GET /api/ia/billing/export-clienti-csv/
    Esporta il prospetto generale consumi IA del programma Kandor da addebitare al cliente.
    """
    if not _check_auth(request):
        return HttpResponse('Non autorizzato', status=403)

    summary = get_billing_summary()
    usages = summary.get('recent_usages', [])

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    today_str = timezone.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename="KANDOR_Prospetto_Spese_IA_{today_str}.csv"'

    # BOM UTF-8 per corretta apertura in Microsoft Excel
    response.write('\ufeff'.encode('utf-8'))
    writer = csv.writer(response, delimiter=';')

    # Sezione 1: Sintesi Generale Kandor per Fattura
    writer.writerow(['PROSPETTO GENERALE CONSUMI IA — PROGRAMMA KANDOR'])
    writer.writerow(['Data Esportazione', timezone.now().strftime('%d/%m/%Y %H:%M')])
    writer.writerow(['Totale Chiamate IA Kandor', summary.get('totale_chiamate', 0)])
    writer.writerow(['Token Totali Scambiati', summary.get('totale_token', 0)])
    writer.writerow(['Costo Vivo Google (€)', f"{summary.get('costo_totale_consumato_eur', 0.0):.4f}".replace('.', ',')])
    writer.writerow(['Ricarico Applicato', f"+{summary.get('ricarico_cliente_percentuale', 30.0):.1f}%"])
    writer.writerow(['TOTALE DA FAR PAGARE AL CLIENTE (€)', f"{summary.get('totale_da_fatturare_eur', 0.0):.2f}".replace('.', ',')])
    writer.writerow([])

    # Sezione 2: Dettaglio Registro Operazioni
    writer.writerow([
        'Data / Ora',
        'Operazione / Funzione Kandor',
        'Token Input',
        'Token Output',
        'Token Totali',
        'Costo Google (€)',
        'Importo da Addebitare (€)',
        'Stato Contabile',
    ])

    for u in usages:
        writer.writerow([
            u.get('data', ''),
            u.get('operazione', 'Elaborazione IA'),
            u.get('token_input', 0),
            u.get('token_output', 0),
            u.get('token_totali', 0),
            f"{u.get('costo_eur', 0.0):.6f}".replace('.', ','),
            f"{u.get('prezzo_cliente_eur', 0.0):.6f}".replace('.', ','),
            'Incassato' if u.get('fatturato') else 'Da fatturare',
        ])

    return response
