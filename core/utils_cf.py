import datetime

def extract_data_nascita(cf):
    """
    Estrae la data di nascita dal Codice Fiscale italiano.
    Formato: 6 lettere, 2 cifre anno, 1 lettera mese, 2 cifre giorno.
    Restituisce un oggetto datetime.date o None se fallisce.
    """
    if not cf or len(cf) != 16:
        return None
        
    cf = cf.upper()
    
    try:
        anno_str = cf[6:8]
        mese_char = cf[8]
        giorno_str = cf[9:11]
        
        anno = int(anno_str)
        giorno = int(giorno_str)
        
        # Mappa Mesi
        mesi = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'H': 6, 
                'L': 7, 'M': 8, 'P': 9, 'R': 10, 'S': 11, 'T': 12}
        
        if mese_char not in mesi:
            return None
            
        mese = mesi[mese_char]
        
        # Gestione Sesso (Donne hanno giorno + 40)
        if giorno > 40:
            giorno -= 40
            
        # Gestione Secolo (Euristica semplice per lavoratori: 1900 vs 2000)
        # Anno corrente 2026. Assumiamo range ragionevole.
        current_year = datetime.date.today().year
        current_yy = current_year % 100
        
        # Se l'anno è tra 00 e current_yy (es. 26), è probabile sia 20xx
        # Se è > current_yy (es. 80), è 19xx
        # Aggiungiamo un margine per "futuro": nessuno nasce nel futuro
        # Ma attenzione ai neonati (non sono dipendenti). 
        # Per dipendenti (maggiorenni), se anno = 20(current-18), etc.
        # Semplificazione:
        if anno <= current_yy:
            full_year = 2000 + anno
        else:
            full_year = 1900 + anno
            
        return datetime.date(full_year, mese, giorno)
        
    except (ValueError, IndexError):
        return None
