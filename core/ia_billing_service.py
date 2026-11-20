"""
Servizio di gestione, tracciamento consumi e fatturazione crediti IA Google Gemini per KANDOR ERP.
Replica e potenzia la logica di tracciamento crediti, autonomia residua, ricariche
e ripartizione costi/fatturazione per ogni singolo Cliente.
"""
import os
import json
import time
import requests
from decimal import Decimal
from datetime import datetime, date
from django.utils import timezone
from django.conf import settings

# Tariffe ufficiali Google Gemini 1.5/2.0 Flash / 3.8 Flash
# $0.10 / 1M token input, $0.40 / 1M token output (cambio USD -> EUR ~0.92)
DEFAULT_COST_PER_INPUT_TOKEN_EUR = Decimal('0.092000') / Decimal('1000000')
DEFAULT_COST_PER_OUTPUT_TOKEN_EUR = Decimal('0.368000') / Decimal('1000000')
DEFAULT_RICARICO_CLIENTE_PCT = Decimal('30.00') # +30% di markup sui consumi cliente


def _get_json_file_path():
    """Restituisce il path del file JSON persistente su volume media."""
    try:
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root:
            media_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media')
    except Exception:
        media_root = os.path.join(os.getcwd(), 'media')
    os.makedirs(media_root, exist_ok=True)
    return os.path.join(media_root, 'ia_billing_data.json')


def _load_json_data():
    file_path = _get_json_file_path()
    default_data = {
        'prepaid_credit': 20.0,
        'ricariche_totali': 20.0,
        'costo_totale_consumato': 0.0,
        'totale_chiamate': 0,
        'totale_token_input': 0,
        'totale_token_output': 0,
        'ricarico_cliente_pct': 30.0,
        'costo_input_1m': 0.092,
        'costo_output_1m': 0.368,
        'last_top_up_date': timezone.now().date().isoformat(),
        'last_updated': timezone.now().isoformat(),
        'recent_usages': [],
    }
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {**default_data, **data}
        except Exception:
            pass
    return default_data


def _save_json_data(data):
    file_path = _get_json_file_path()
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[IA BILLING] Errore salvataggio file snapshot JSON: {e}")


def get_wallet():
    """Recupera o crea il record singleton del Portafoglio Crediti IA."""
    try:
        from core.models import IACreditWallet
        wallet, created = IACreditWallet.objects.get_or_create(
            pk=1,
            defaults={
                'saldo_residuo': Decimal('20.0000'),
                'ricariche_totali': Decimal('20.0000'),
                'costo_totale_consumato': Decimal('0.000000'),
                'ricarico_cliente_percentuale': Decimal('30.00'),
            }
        )
        return wallet
    except Exception:
        return None


def get_gemini_api_key():
    """Cerca la chiave API Gemini nell'ambiente, nel volume persistente media o nel .env."""
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        key = os.environ.get('GOOGLE_API_KEY', '').strip()
    if not key:
        # Cerca nel volume media persistente
        try:
            key_path = os.path.join(os.path.dirname(_get_json_file_path()), 'gemini_api_key.txt')
            if os.path.exists(key_path):
                with open(key_path, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
        except Exception:
            pass
    if not key:
        # Cerca nel .env dell'applicazione
        try:
            env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
            if os.path.exists(env_file):
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('GEMINI_API_KEY='):
                            key = line.split('=', 1)[1].strip()
                            break
        except Exception:
            pass
    return key


def imposta_gemini_api_key(new_key):
    """Salva la nuova chiave API Gemini nel volume persistente."""
    new_key = (new_key or '').strip()
    if not new_key:
        return False
    try:
        key_path = os.path.join(os.path.dirname(_get_json_file_path()), 'gemini_api_key.txt')
        with open(key_path, 'w', encoding='utf-8') as f:
            f.write(new_key)
        os.environ['GEMINI_API_KEY'] = new_key
        return True
    except Exception as e:
        print(f"[IA BILLING] Errore salvataggio chiave API: {e}")
        return False


def get_billing_summary():
    """
    Restituisce un dizionario completo con metriche di consumo, credito residuo,
    autonomia, stato chiave API, riepilogo consumi per Cliente e storico recente.
    """
    api_key = get_gemini_api_key()
    key_masked = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) >= 10 else ("Non configurata" if not api_key else "Configurata")

    wallet = get_wallet()
    json_data = _load_json_data()

    if wallet:
        saldo = float(wallet.saldo_residuo)
        ricariche = float(wallet.ricariche_totali)
        costo_consumato = float(wallet.costo_totale_consumato)
        chiamate = wallet.totale_chiamate
        tok_in = wallet.totale_token_input
        tok_out = wallet.totale_token_output
        ricarico_pct = float(wallet.ricarico_cliente_percentuale)
        costo_1m_in = float(wallet.costo_per_1m_input_eur)
        costo_1m_out = float(wallet.costo_per_1m_output_eur)
        data_top_up = wallet.data_ultima_ricarica.strftime('%d/%m/%Y') if wallet.data_ultima_ricarica else ''
        modello = wallet.modello_predefinito
    else:
        saldo = float(json_data.get('prepaid_credit', 20.0)) - float(json_data.get('costo_totale_consumato', 0.0))
        saldo = max(0.0, saldo)
        ricariche = float(json_data.get('ricariche_totali', 20.0))
        costo_consumato = float(json_data.get('costo_totale_consumato', 0.0))
        chiamate = int(json_data.get('totale_chiamate', 0))
        tok_in = int(json_data.get('totale_token_input', 0))
        tok_out = int(json_data.get('totale_token_output', 0))
        ricarico_pct = float(json_data.get('ricarico_cliente_pct', 30.0))
        costo_1m_in = float(json_data.get('costo_input_1m', 0.092))
        costo_1m_out = float(json_data.get('costo_output_1m', 0.368))
        data_top_up = json_data.get('last_top_up_date', '')
        modello = 'gemini-1.5-flash'

    # Autonomia stimata: costo medio per operazione (~0.0003 €)
    costo_medio_op = 0.0003
    if chiamate > 0 and costo_consumato > 0:
        costo_medio_op = max(0.00005, costo_consumato / chiamate)
    operazioni_rimanenti = int(saldo / costo_medio_op) if costo_medio_op > 0 else 65000

    # Percentuale credito residuo
    pct_residua = round(min(100.0, max(0.0, (saldo / ricariche * 100.0))) if ricariche > 0 else 0.0, 1)

    # Recupera storico recente e riepilogo clienti
    recent_usages = []
    clienti_summary = {}
    totale_da_fatturare = 0.0
    totale_gia_fatturato = 0.0

    try:
        from core.models import IAConsumoLog
        logs = list(IAConsumoLog.objects.select_related('cliente', 'dipendente').order_by('-data_ora')[:60])
        for log in logs:
            c_nome = log.cliente.ragione_sociale if log.cliente else "Sistema Generale / Studio"
            c_id = log.cliente.id if log.cliente else 0
            costo_log = float(log.costo_eur)
            prezzo_cli = float(log.prezzo_cliente_eur)
            recent_usages.append({
                'id': log.id,
                'data': log.data_ora.strftime('%d/%m/%Y %H:%M'),
                'operazione': log.operazione,
                'cliente_id': c_id,
                'cliente_nome': c_nome,
                'token_input': log.token_input,
                'token_output': log.token_output,
                'token_totali': log.token_totali,
                'costo_eur': costo_log,
                'prezzo_cliente_eur': prezzo_cli,
                'fatturato': log.fatturato,
            })

            # Aggregato per cliente
            if c_id not in clienti_summary:
                clienti_summary[c_id] = {
                    'cliente_id': c_id,
                    'cliente_nome': c_nome,
                    'chiamate': 0,
                    'token_totali': 0,
                    'costo_vivo_eur': 0.0,
                    'prezzo_totale_eur': 0.0,
                    'da_fatturare_eur': 0.0,
                    'gia_fatturato_eur': 0.0,
                }
            clienti_summary[c_id]['chiamate'] += 1
            clienti_summary[c_id]['token_totali'] += log.token_totali
            clienti_summary[c_id]['costo_vivo_eur'] += costo_log
            clienti_summary[c_id]['prezzo_totale_eur'] += prezzo_cli
            if log.fatturato:
                clienti_summary[c_id]['gia_fatturato_eur'] += prezzo_cli
                totale_gia_fatturato += prezzo_cli
            else:
                clienti_summary[c_id]['da_fatturare_eur'] += prezzo_cli
                totale_da_fatturare += prezzo_cli

    except Exception:
        # Fallback su file JSON
        for u in json_data.get('recent_usages', []):
            c_nome = u.get('cliente_nome', 'Sistema Generale')
            c_id = u.get('cliente_id', 0)
            costo_log = float(u.get('costo_eur', 0.0))
            prezzo_cli = float(u.get('prezzo_cliente_eur', costo_log * (1 + ricarico_pct/100)))
            fatt = bool(u.get('fatturato', False))
            recent_usages.append({
                'id': u.get('id', 0),
                'data': u.get('date', ''),
                'operazione': u.get('operation', 'Elaborazione IA'),
                'cliente_id': c_id,
                'cliente_nome': c_nome,
                'token_input': u.get('inputTokens', 0),
                'token_output': u.get('outputTokens', 0),
                'token_totali': u.get('inputTokens', 0) + u.get('outputTokens', 0),
                'costo_eur': costo_log,
                'prezzo_cliente_eur': prezzo_cli,
                'fatturato': fatt,
            })
            if c_id not in clienti_summary:
                clienti_summary[c_id] = {
                    'cliente_id': c_id,
                    'cliente_nome': c_nome,
                    'chiamate': 0,
                    'token_totali': 0,
                    'costo_vivo_eur': 0.0,
                    'prezzo_totale_eur': 0.0,
                    'da_fatturare_eur': 0.0,
                    'gia_fatturato_eur': 0.0,
                }
            clienti_summary[c_id]['chiamate'] += 1
            clienti_summary[c_id]['token_totali'] += (u.get('inputTokens', 0) + u.get('outputTokens', 0))
            clienti_summary[c_id]['costo_vivo_eur'] += costo_log
            clienti_summary[c_id]['prezzo_totale_eur'] += prezzo_cli
            if fatt:
                clienti_summary[c_id]['gia_fatturato_eur'] += prezzo_cli
                totale_gia_fatturato += prezzo_cli
            else:
                clienti_summary[c_id]['da_fatturare_eur'] += prezzo_cli
                totale_da_fatturare += prezzo_cli

    # Formatta aggregati
    clienti_list = sorted(clienti_summary.values(), key=lambda x: x['da_fatturare_eur'], reverse=True)
    for c in clienti_list:
        c['costo_vivo_eur'] = round(c['costo_vivo_eur'], 4)
        c['prezzo_totale_eur'] = round(c['prezzo_totale_eur'], 4)
        c['da_fatturare_eur'] = round(c['da_fatturare_eur'], 4)
        c['gia_fatturato_eur'] = round(c['gia_fatturato_eur'], 4)

    return {
        'ok': True,
        'saldo_residuo_eur': round(saldo, 4),
        'ricariche_totali_eur': round(ricariche, 2),
        'costo_totale_consumato_eur': round(costo_consumato, 4),
        'totale_da_fatturare_eur': round(totale_da_fatturare, 2),
        'totale_gia_fatturato_eur': round(totale_gia_fatturato, 2),
        'margine_totale_eur': round((totale_da_fatturare + totale_gia_fatturato) - costo_consumato, 4),
        'totale_chiamate': chiamate,
        'totale_token_input': tok_in,
        'totale_token_output': tok_out,
        'totale_token': tok_in + tok_out,
        'percentuale_residua': pct_residua,
        'operazioni_rimanenti': operazioni_rimanenti,
        'modello': modello,
        'gemini_attivo': bool(api_key),
        'key_masked': key_masked,
        'google_billing_url': 'https://aistudio.google.com/billing',
        'data_ultima_ricarica': data_top_up,
        'ricarico_cliente_percentuale': ricarico_pct,
        'costo_1m_input_eur': costo_1m_in,
        'costo_1m_output_eur': costo_1m_out,
        'recent_usages': recent_usages[:50],
        'clienti_summary': clienti_list,
    }


def registra_consumo_ia(operazione='Elaborazione IA', token_input=0, token_output=0,
                        cliente=None, cliente_id=None, dipendente=None, dipendente_id=None,
                        modello='gemini-1.5-flash', note=''):
    """
    Registra il consumo di token per un'operazione IA, calcola il costo vivo e il prezzo
    al cliente (incluso ricarico), e aggiorna il credito residuo.
    """
    token_input = max(0, int(token_input or 0))
    token_output = max(0, int(token_output or 0))
    token_totali = token_input + token_output

    wallet = get_wallet()
    if wallet:
        costo_in = (Decimal(str(token_input)) * wallet.costo_per_1m_input_eur) / Decimal('1000000')
        costo_out = (Decimal(str(token_output)) * wallet.costo_per_1m_output_eur) / Decimal('1000000')
        costo_totale = costo_in + costo_out
        ricarico = wallet.ricarico_cliente_percentuale
        prezzo_cliente = costo_totale * (Decimal('1.00') + (ricarico / Decimal('100.00')))
    else:
        costo_totale = (Decimal(str(token_input)) * DEFAULT_COST_PER_INPUT_TOKEN_EUR) + \
                       (Decimal(str(token_output)) * DEFAULT_COST_PER_OUTPUT_TOKEN_EUR)
        prezzo_cliente = costo_totale * (Decimal('1.00') + (DEFAULT_RICARICO_CLIENTE_PCT / Decimal('100.00')))

    # Recupera istanze Cliente/Dipendente se forniti come ID
    cliente_obj = cliente
    if not cliente_obj and cliente_id:
        try:
            from core.models import Cliente
            cliente_obj = Cliente.objects.filter(pk=cliente_id).first()
        except Exception:
            pass

    dipendente_obj = dipendente
    if not dipendente_obj and dipendente_id:
        try:
            from core.models import Dipendente
            dipendente_obj = Dipendente.objects.filter(pk=dipendente_id).first()
        except Exception:
            pass

    # 1. Salva nel DB ORM
    log_id = None
    try:
        from core.models import IAConsumoLog
        log_entry = IAConsumoLog.objects.create(
            operazione=operazione[:150],
            cliente=cliente_obj,
            dipendente=dipendente_obj,
            modello=modello,
            token_input=token_input,
            token_output=token_output,
            token_totali=token_totali,
            costo_eur=costo_totale,
            prezzo_cliente_eur=prezzo_cliente,
            note=note,
        )
        log_id = log_entry.id
    except Exception as e:
        print(f"[IA BILLING] Errore inserimento IAConsumoLog: {e}")

    # 2. Aggiorna il Portafoglio DB
    if wallet:
        try:
            wallet.saldo_residuo = max(Decimal('0.0000'), wallet.saldo_residuo - costo_totale)
            wallet.costo_totale_consumato += costo_totale
            wallet.totale_chiamate += 1
            wallet.totale_token_input += token_input
            wallet.totale_token_output += token_output
            wallet.save(update_fields=[
                'saldo_residuo', 'costo_totale_consumato', 'totale_chiamate',
                'totale_token_input', 'totale_token_output', 'ultimo_aggiornamento'
            ])
        except Exception as e:
            print(f"[IA BILLING] Errore aggiornamento IACreditWallet: {e}")

    # 3. Snapshot di resilienza su file JSON
    json_data = _load_json_data()
    json_data['totale_chiamate'] = int(json_data.get('totale_chiamate', 0)) + 1
    json_data['totale_token_input'] = int(json_data.get('totale_token_input', 0)) + token_input
    json_data['totale_token_output'] = int(json_data.get('totale_token_output', 0)) + token_output
    json_data['costo_totale_consumato'] = float(Decimal(str(json_data.get('costo_totale_consumato', 0.0))) + costo_totale)
    json_data['last_updated'] = timezone.now().isoformat()

    c_nome = cliente_obj.ragione_sociale if cliente_obj else "Sistema Generale"
    recent = json_data.get('recent_usages', [])
    recent.insert(0, {
        'id': log_id or int(time.time()),
        'date': timezone.now().strftime('%d/%m/%Y %H:%M'),
        'operation': operazione,
        'cliente_id': cliente_obj.id if cliente_obj else 0,
        'cliente_nome': c_nome,
        'inputTokens': token_input,
        'outputTokens': token_output,
        'costEur': float(costo_totale),
        'prezzo_cliente_eur': float(prezzo_cliente),
        'fatturato': False,
    })
    json_data['recent_usages'] = recent[:60]
    _save_json_data(json_data)

    return {
        'ok': True,
        'costo_eur': float(costo_totale),
        'prezzo_cliente_eur': float(prezzo_cliente),
        'token_totali': token_totali,
    }


def registra_ricarica(amount, mode='add', date_str=None):
    """Registra una nuova ricarica monetaria o imposta il saldo."""
    try:
        val = Decimal(str(amount))
    except Exception:
        return {'ok': False, 'error': 'Importo non valido'}

    wallet = get_wallet()
    now_date = date.today()
    if date_str:
        try:
            now_date = date.fromisoformat(date_str)
        except Exception:
            pass

    if wallet:
        if mode == 'add':
            wallet.saldo_residuo += val
            wallet.ricariche_totali += val
        else:
            wallet.saldo_residuo = val
            wallet.ricariche_totali = max(wallet.ricariche_totali, val)
        wallet.data_ultima_ricarica = now_date
        wallet.save()

    json_data = _load_json_data()
    if mode == 'add':
        json_data['prepaid_credit'] = float(Decimal(str(json_data.get('prepaid_credit', 20.0))) + val)
        json_data['ricariche_totali'] = float(Decimal(str(json_data.get('ricariche_totali', 20.0))) + val)
    else:
        json_data['prepaid_credit'] = float(val)
        json_data['ricariche_totali'] = max(float(json_data.get('ricariche_totali', 20.0)), float(val))
    json_data['last_top_up_date'] = now_date.isoformat()
    json_data['last_updated'] = timezone.now().isoformat()
    _save_json_data(json_data)

    return {'ok': True, 'nuovo_saldo': float(wallet.saldo_residuo if wallet else json_data['prepaid_credit'])}


def marca_consumi_fatturati(cliente_id=None, log_ids=None):
    """Marca i consumi come già fatturati al cliente."""
    count = 0
    try:
        from core.models import IAConsumoLog
        qs = IAConsumoLog.objects.filter(fatturato=False)
        if log_ids:
            qs = qs.filter(id__in=log_ids)
        elif cliente_id:
            qs = qs.filter(cliente_id=cliente_id)
        count = qs.update(fatturato=True, data_fatturazione=timezone.now())
    except Exception as e:
        print(f"[IA BILLING] Errore marca_consumi_fatturati DB: {e}")

    # Aggiorna anche lo snapshot JSON
    json_data = _load_json_data()
    for u in json_data.get('recent_usages', []):
        if log_ids and u.get('id') in log_ids:
            u['fatturato'] = True
        elif cliente_id and str(u.get('cliente_id')) == str(cliente_id):
            u['fatturato'] = True
    _save_json_data(json_data)

    return {'ok': True, 'aggiornati': count}


def configura_tariffe(costo_input_1m=None, costo_output_1m=None, ricarico_pct=None):
    """Aggiorna le tariffe e la percentuale di ricarico da applicare ai clienti."""
    wallet = get_wallet()
    if wallet:
        if costo_input_1m is not None:
            wallet.costo_per_1m_input_eur = Decimal(str(costo_input_1m))
        if costo_output_1m is not None:
            wallet.costo_per_1m_output_eur = Decimal(str(costo_output_1m))
        if ricarico_pct is not None:
            wallet.ricarico_cliente_percentuale = Decimal(str(ricarico_pct))
        wallet.save()

    json_data = _load_json_data()
    if costo_input_1m is not None:
        json_data['costo_input_1m'] = float(costo_input_1m)
    if costo_output_1m is not None:
        json_data['costo_output_1m'] = float(costo_output_1m)
    if ricarico_pct is not None:
        json_data['ricarico_cliente_pct'] = float(ricarico_pct)
    _save_json_data(json_data)

    return {'ok': True}


def esegui_test_connessione():
    """
    Esegue una vera chiamata API Google Gemini live di test con prompt leggero ("Ping Kandor"),
    misura la latenza in millisecondi e registra i token consumati.
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return {
            'ok': False,
            'message': 'Nessuna chiave GEMINI_API_KEY impostata nel sistema.',
            'latency_ms': 0,
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Rispondi esclusivamente con un JSON: {\"status\": \"ok\", \"service\": \"KANDOR ERP\"}"}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "maxOutputTokens": 30,
        }
    }

    start_t = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=8)
        latency = int((time.time() - start_t) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            usage = data.get('usageMetadata', {})
            p_tok = usage.get('promptTokenCount', 15)
            c_tok = usage.get('candidatesTokenCount', 10)
            # Registra consumo del test live
            registra_consumo_ia(
                operazione="Test Connessione Live API",
                token_input=p_tok,
                token_output=c_tok,
                note=f"Ping effettuato con successo in {latency}ms"
            )
            return {
                'ok': True,
                'message': f"Connessione Google Gemini attiva e verificata ({latency} ms)",
                'latency_ms': latency,
                'token_input': p_tok,
                'token_output': c_tok,
                'http_status': 200,
            }
        else:
            return {
                'ok': False,
                'message': f"Errore Google API HTTP {resp.status_code}: {resp.text[:120]}",
                'latency_ms': latency,
                'http_status': resp.status_code,
            }
    except Exception as e:
        latency = int((time.time() - start_t) * 1000)
        return {
            'ok': False,
            'message': f"Eccezione di connessione: {str(e)[:120]}",
            'latency_ms': latency,
        }
