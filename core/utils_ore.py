from decimal import Decimal
import re

def parse_ore_input(val, default=None):
    """
    Converte un input ore (es. '1:34', '01:34', '1h34', '1h 34m', '1.5', '8')
    in Decimal con 2 cifre decimali rappresentante le ore decimali.
    Se val è vuoto o non valido, restituisce default o solleva ValueError.
    """
    if val is None:
        return default
    
    val_str = str(val).strip()
    if not val_str:
        return default

    # 1. Formato con i due punti: es. "1:34", "01:34", "0:45", "12:00"
    if ':' in val_str:
        parts = val_str.split(':')
        if len(parts) == 2:
            try:
                h = int(parts[0].strip() or 0)
                m = int(parts[1].strip() or 0)
                if h < 0 or m < 0:
                    raise ValueError("Ore o minuti negativi")
                minuti_tot = h * 60 + m
                return Decimal(str(round(minuti_tot / 60.0, 2)))
            except (ValueError, TypeError):
                pass

    # 2. Formato con 'h' esplicito: es. "1h34", "1h 34m", "1h34'", "2h", "8h"
    if 'h' in val_str.lower():
        hm_match = re.match(r'^(\d+)\s*h(?:our[s]?)?(?:\s*(\d+)\s*(?:m|min|\')?)?$', val_str, re.IGNORECASE)
        if hm_match:
            h = int(hm_match.group(1) or 0)
            m = int(hm_match.group(2) or 0)
            minuti_tot = h * 60 + m
            return Decimal(str(round(minuti_tot / 60.0, 2)))

    # Formato solo minuti espliciti: es. "45m", "45min", "45'"
    m_match = re.match(r'^(\d+)\s*(?:m|min|\')$', val_str, re.IGNORECASE)
    if m_match:
        m = int(m_match.group(1))
        return Decimal(str(round(m / 60.0, 2)))

    # 3. Formato numerico standard (es. "8", "7.5", "1,5", "1.50")
    clean_num = val_str.replace(',', '.')
    try:
        f = float(clean_num)
        if f < 0:
            raise ValueError("Ore negative")
        return Decimal(str(round(f, 2)))
    except (ValueError, TypeError):
        pass

    if default is not None:
        return default
    raise ValueError(f"Formato ore non valido: '{val}'")


def format_ore_hhmm(val, include_zero=True):
    """
    Converte un valore ore numerico (float, Decimal, int) in stringa "H:MM" (es. 1.57 -> "1:34", 8.0 -> "8:00").
    """
    if val is None or val == '':
        return "0:00" if include_zero else ""
    try:
        f = float(val)
        if f <= 0:
            return "0:00" if include_zero else ""
        neg = f < 0
        f = abs(f)
        h = int(f)
        m = int(round((f - h) * 60))
        if m >= 60:
            h += 1
            m = 0
        res = f"{h}:{m:02d}"
        return f"-{res}" if neg else res
    except (ValueError, TypeError):
        return str(val)


def format_ore_estese(val):
    """
    Converte 1.57 -> "1h34'", 7.5 -> "7h30'", 8.0 -> "8h", 0.5 -> "30'"
    """
    if val is None or val == '':
        return "—"
    try:
        f = float(val)
        if f <= 0:
            return "0h"
        h = int(f)
        m = int(round((f - h) * 60))
        if m >= 60:
            h += 1
            m = 0
        if h and m:
            return f"{h}h{m:02d}'"
        elif h:
            return f"{h}h"
        else:
            return f"{m}'"
    except (ValueError, TypeError):
        return str(val)
