from core.daily_quotes import get_daily_quote_info


def daily_quote_context(request):
    """Inietta nella barra superiore e nei template la data odierna, la frase positiva, l'operatore autenticato e i permessi sezioni."""
    info = get_daily_quote_info()
    operatore_portale = None
    operatori_rapidi_portale = []
    profilo_accesso_portale = None
    is_programmatore_reale = False
    in_preview_responsabile = False
    sezioni_abilitate_portale = set()
    try:
        from core.services import get_operatore_portale, get_operatori_rapidi_portale
        from core.accessi_service import (
            get_profilo_accesso_corrente,
            get_sezioni_abilitate_per_request,
            TUTTI_CODICI_SEZIONI,
        )
        operatore_portale = get_operatore_portale(request)
        operatori_rapidi_portale = get_operatori_rapidi_portale()
        profilo_accesso_portale, is_programmatore_reale, in_preview_responsabile = get_profilo_accesso_corrente(request)
        sezioni_abilitate_portale = get_sezioni_abilitate_per_request(request)
    except Exception:
        from core.accessi_service import TUTTI_CODICI_SEZIONI
        sezioni_abilitate_portale = set(TUTTI_CODICI_SEZIONI)

    # Info sintetiche credito IA per topbar e widget
    ia_billing_info = {
        'saldo_residuo': 20.0,
        'totale_chiamate': 0,
        'gemini_attivo': False,
    }
    try:
        from core.ia_billing_service import get_billing_summary
        b_sum = get_billing_summary()
        ia_billing_info = {
            'saldo_residuo': b_sum.get('saldo_residuo_eur', 20.0),
            'totale_chiamate': b_sum.get('totale_chiamate', 0),
            'gemini_attivo': b_sum.get('gemini_attivo', False),
            'da_fatturare_eur': b_sum.get('totale_da_fatturare_eur', 0.0),
        }
    except Exception:
        pass

    return {
        "daily_quote_info": info,
        "daily_quote_date": info["date_formatted"],
        "daily_quote_date_short": info["date_short"],
        "daily_quote_text": info["quote"],
        "daily_quotes_json": info["quotes_json"],
        "operatore_portale": operatore_portale,
        "operatori_rapidi_portale": operatori_rapidi_portale,
        "profilo_accesso_portale": profilo_accesso_portale,
        "is_programmatore_reale": is_programmatore_reale,
        "in_preview_responsabile": in_preview_responsabile,
        "sezioni_abilitate_portale": sezioni_abilitate_portale,
        "ia_billing": ia_billing_info,
    }
