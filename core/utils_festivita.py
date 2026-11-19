"""
Modulo per la gestione delle Festività Nazionali e Locali (Brembate di Sopra).
Calcola algoritmicamente Pasqua e Pasquetta e unisce le festività fisse e locali.
"""
from datetime import date, timedelta
from typing import Dict, Optional, List


def calcola_pasqua(anno: int) -> date:
    """
    Calcola la data della Domenica di Pasqua per l'anno specificato
    utilizzando l'algoritmo canonico di Butcher / Oudin.
    """
    a = anno % 19
    b = anno // 100
    c = anno % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    return date(anno, mese, giorno)


def get_festivita_italiane_fisse(anno: int) -> Dict[date, Dict[str, str]]:
    """
    Restituisce il dizionario delle festività fisse per l'anno specificato,
    incluse le festività nazionali e il Santo Patrono di Brembate di Sopra (15 Agosto).
    """
    return {
        date(anno, 1, 1): {
            'nome': 'Capodanno',
            'tipo': 'NAZIONALE',
            'descrizione': 'Capodanno (Festività Nazionale)'
        },
        date(anno, 1, 6): {
            'nome': 'Epifania',
            'tipo': 'NAZIONALE',
            'descrizione': 'Epifania (Festività Nazionale)'
        },
        date(anno, 4, 25): {
            'nome': 'Festa della Liberazione',
            'tipo': 'NAZIONALE',
            'descrizione': 'Festa della Liberazione (Festività Nazionale)'
        },
        date(anno, 5, 1): {
            'nome': 'Festa del Lavoro',
            'tipo': 'NAZIONALE',
            'descrizione': 'Festa del Lavoro (Festività Nazionale)'
        },
        date(anno, 6, 2): {
            'nome': 'Festa della Repubblica',
            'tipo': 'NAZIONALE',
            'descrizione': 'Festa della Repubblica (Festività Nazionale)'
        },
        date(anno, 8, 15): {
            'nome': 'Ferragosto e Patrono Brembate di Sopra',
            'tipo': 'NAZIONALE_LOCALE',
            'descrizione': 'Ferragosto / Assunzione di Maria - Festa Patronale di Brembate di Sopra'
        },
        date(anno, 11, 1): {
            'nome': 'Tutti i Santi',
            'tipo': 'NAZIONALE',
            'descrizione': 'Tutti i Santi (Festività Nazionale)'
        },
        date(anno, 12, 8): {
            'nome': 'Immacolata Concezione',
            'tipo': 'NAZIONALE',
            'descrizione': 'Immacolata Concezione (Festività Nazionale)'
        },
        date(anno, 12, 25): {
            'nome': 'Natale',
            'tipo': 'NAZIONALE',
            'descrizione': 'Natale (Festività Nazionale)'
        },
        date(anno, 12, 26): {
            'nome': 'Santo Stefano',
            'tipo': 'NAZIONALE',
            'descrizione': 'Santo Stefano (Festività Nazionale)'
        },
    }


def get_tutte_festivita_anno(anno: int) -> Dict[date, Dict[str, str]]:
    """
    Restituisce tutte le festività dell'anno (fisse + Pasqua + Pasquetta).
    """
    festivita = get_festivita_italiane_fisse(anno)
    pasqua = calcola_pasqua(anno)
    pasquetta = pasqua + timedelta(days=1)

    festivita[pasqua] = {
        'nome': 'Pasqua',
        'tipo': 'NAZIONALE',
        'descrizione': 'Domenica di Pasqua'
    }
    festivita[pasquetta] = {
        'nome': "Lunedì dell'Angelo (Pasquetta)",
        'tipo': 'NAZIONALE',
        'descrizione': "Lunedì dell'Angelo / Pasquetta (Festività Nazionale)"
    }
    return festivita


# Cache in memoria per anno
_FESTIVITA_CACHE: Dict[int, Dict[date, Dict[str, str]]] = {}


def get_festivita(d: date) -> Optional[Dict[str, str]]:
    """
    Verifica se una data `d` è un giorno festivo nazionale o locale (Brembate di Sopra).
    Supporta anche eventuali festività personalizzate registrate nel database.
    Ritorna un dizionario con i dettagli della festività se festivo, altrimenti None.
    """
    if not d:
        return None

    anno = d.year
    if anno not in _FESTIVITA_CACHE:
        _FESTIVITA_CACHE[anno] = get_tutte_festivita_anno(anno)

    festivita_standard = _FESTIVITA_CACHE[anno].get(d)
    if festivita_standard:
        return festivita_standard

    # Controllo festività personalizzate dal DB (se presenti)
    try:
        from core.models import FestivitaPersonalizzata
        f_custom = FestivitaPersonalizzata.objects.filter(attiva=True).filter(
            # O data specifica coincidente
            data=d
        ).first()
        if f_custom:
            return {
                'nome': f_custom.nome,
                'tipo': f_custom.tipo,
                'descrizione': f"{f_custom.nome} ({f_custom.get_tipo_display()})"
            }

        # Oppure ricorrenza annuale per giorno/mese
        f_ricorrente = FestivitaPersonalizzata.objects.filter(
            attiva=True,
            data__isnull=True,
            giorno=d.day,
            mese=d.month
        ).first()
        if f_ricorrente:
            return {
                'nome': f_ricorrente.nome,
                'tipo': f_ricorrente.tipo,
                'descrizione': f"{f_ricorrente.nome} ({f_ricorrente.get_tipo_display()})"
            }
    except Exception:
        # Se la tabella non esiste ancora o durante migrazioni, continua senza errori
        pass

    return None


def is_giorno_festivo(d: date) -> bool:
    """Restituisce True se la data indicata è un giorno festivo, False altrimenti."""
    return get_festivita(d) is not None
