from core.daily_quotes import get_daily_quote_info


def daily_quote_context(request):
    """Inietta nella barra superiore di tutti i template la data odierna e la frase positiva del giorno."""
    info = get_daily_quote_info()
    return {
        "daily_quote_info": info,
        "daily_quote_date": info["date_formatted"],
        "daily_quote_date_short": info["date_short"],
        "daily_quote_text": info["quote"],
        "daily_quotes_json": info["quotes_json"],
    }
