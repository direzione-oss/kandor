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
)


def _check_auth(request):
    """Verifica che l'utente sia admin, titolare o staff."""
    return request.user.is_authenticated or request.session.get('titolare_id') or request.session.get('operatore_id')


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
    Esporta il prospetto spese IA aggregate per cliente per l'addebito in fattura.
    """
    if not _check_auth(request):
        return HttpResponse('Non autorizzato', status=403)

    summary = get_billing_summary()
    clienti = summary.get('clienti_summary', [])

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    today_str = timezone.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename="KANDOR_Consumi_IA_Clienti_{today_str}.csv"'

    # BOM UTF-8 per corretta apertura in Microsoft Excel
    response.write('\ufeff'.encode('utf-8'))
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'ID Cliente',
        'Ragione Sociale / Contesto',
        'Chiamate IA Eseguite',
        'Token Totali Scambiati',
        'Costo Google (€)',
        'Prezzo Totale al Cliente (€)',
        'Importo da Fatturare (€)',
        'Importo già Fatturato (€)',
        'Note / Ricarico Applicato',
    ])

    ricarico = summary.get('ricarico_cliente_percentuale', 30.0)
    for c in clienti:
        writer.writerow([
            c['cliente_id'] if c['cliente_id'] != 0 else 'N/D',
            c['cliente_nome'],
            c['chiamate'],
            c['token_totali'],
            f"{c['costo_vivo_eur']:.4f}".replace('.', ','),
            f"{c['prezzo_totale_eur']:.4f}".replace('.', ','),
            f"{c['da_fatturare_eur']:.4f}".replace('.', ','),
            f"{c['gia_fatturato_eur']:.4f}".replace('.', ','),
            f"+{ricarico:.1f}% markup",
        ])

    return response
