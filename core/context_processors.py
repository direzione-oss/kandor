from core.daily_quotes import get_daily_quote_info


def daily_quote_context(request):
    """Inietta nella barra superiore di tutti i template la data odierna, la frase positiva del giorno e l'operatore attivo sul portale."""
    info = get_daily_quote_info()
    operatore_portale = None
    operatori_rapidi_portale = []
    try:
        from core.services import get_operatore_portale, get_operatori_rapidi_portale
        operatore_portale = get_operatore_portale(request)
        operatori_rapidi_portale = get_operatori_rapidi_portale()
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
    }
