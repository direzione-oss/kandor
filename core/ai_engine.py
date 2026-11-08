"""
Motore di Intelligenza Artificiale e Automazioni Smart per Kandor (Zero-Cost + Hybrid Gemini API).

Implementa i 5 moduli IA del portale Kandor:
1. Audit Automatico Ore, Paghe e Anomalie ("AI Revisore Ore" & Auto-Validazione)
2. Assistente Conversazionale NLP (Telegram + Web App), Vision/OCR Certificati e Triage Segnalazioni
3. Ottimizzazione Turni e "Smart Sostituzioni" (Scoring predittivo 0-100)
4. Controllo Conformità, Sicurezza e Scadenze ("Compliance Guardian" + Briefing Mattutino)
5. Controllo Marginalità, Burn-Rate e Lavori Extra Cantieri ("AI Budget & Extra")
"""

import os
import re
import json
import calendar
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from geopy.distance import geodesic


# ==============================================================================
# HELPER OPZIONALE: GOOGLE GEMINI FREE TIER (SE CONFIGURATO IN ENV)
# ==============================================================================

def is_gemini_configured():
    """Restituisce True se è presente una chiave API Gemini (opzionale, piano gratuito Google AI Studio)."""
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    return bool(key)


def call_gemini_json(prompt, image_bytes=None, mime_type='image/jpeg'):
    """
    Chiama l'API gratuita di Google Gemini Flash (se GEMINI_API_KEY è impostata)
    e restituisce un dizionario JSON. In assenza di chiave o errore, restituisce None
    attivando automaticamente il motore euristico/locale a costo zero.
    """
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return None
    try:
        import base64
        import requests
        parts = [{"text": prompt}]
        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            parts.append({
                "inline_data": {
                    "mime_type": mime_type or "image/jpeg",
                    "data": b64,
                }
            })
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            }
        }
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            text_out = data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text_out)
    except Exception:
        pass
    return None


# ==============================================================================
# 1. AUDIT AUTOMATICO ORE, PAGHE E ANOMALIE ("AI REVISORE ORE")
# ==============================================================================

def _calcola_ore_previste_assegnazione(assign):
    """Calcola le ore previste per un'AssegnazioneTurno (da contratto o da fascia oraria)."""
    if assign.ore_previste_contratto and assign.ore_previste_contratto > 0:
        return round(float(assign.ore_previste_contratto), 2)
    if assign.orario_inizio_previsto and assign.orario_fine_previsto:
        d = date.today()
        dt_start = datetime.combine(d, assign.orario_inizio_previsto)
        dt_end = datetime.combine(d, assign.orario_fine_previsto)
        if dt_end < dt_start:
            dt_end += timedelta(days=1)
        diff = (dt_end - dt_start).total_seconds() / 3600.0
        if diff > 0:
            return round(diff, 2)
    return 0.0


def analizza_anomalie_ore(data_inizio=None, data_fine=None, auto_valida=False, dipendente_id=None):
    """
    Analizza tutti i record di TimeTracking e AssegnazioneTurno nel periodo (filtrabile per singolo dipendente):
    - Confronta ore dichiarate con ore previste da contratto/turno
    - Verifica passaggi GPS in ProximityLog
    - Controlla superamento tetto settimanale Part-Time
    - Segnala turni passati privi di compilazione ore
    - Restituisce l'elenco individuale delle ore in attesa di validazione (auto_validabili_items)
    - Se auto_valida=True, valida automaticamente (is_validated=True) i turni regolari privi di anomalie.
    """
    from .models import AssegnazioneTurno, TimeTracking, ProximityLog, Assenza, RichiestaSostituzione

    today = timezone.now().date()
    if not data_fine:
        data_fine = today
    if not data_inizio:
        data_inizio = data_fine - timedelta(days=30)

    filter_dip_id = None
    if dipendente_id and str(dipendente_id).isdigit():
        filter_dip_id = int(dipendente_id)

    assegnazioni = list(
        AssegnazioneTurno.objects.filter(
            turno__data__gte=data_inizio,
            turno__data__lte=data_fine,
        )
        .select_related('cliente', 'turno', 'turno__squadra', 'turno__squadra__caposquadra', 'programmazione_feriale')
        .prefetch_related('timetracks__dipendente', 'dipendenti_esclusi', 'turno__squadra__componenti')
        .order_by('-turno__data', 'orario_inizio_previsto')
    )

    # Pre-carica sostituzioni nel periodo per associare correttamente il sostituto confermato ai turni
    sost_by_assign = {}
    for rs in RichiestaSostituzione.objects.filter(
        assegnazione_originale__turno__data__gte=data_inizio,
        assegnazione_originale__turno__data__lte=data_fine,
        stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA', 'ACCETTATA', 'COMPLETATA', 'NON_SOSTITUITO']
    ).select_related('sostituto', 'dipendente_assente'):
        sost_by_assign.setdefault(rs.assegnazione_originale_id, []).append(rs)

    # Pre-carica log GPS nel periodo per controllo incrociato (1 query)
    prox_map = {}
    for pl in ProximityLog.objects.filter(entered_at__date__gte=data_inizio, entered_at__date__lte=data_fine):
        prox_map[(pl.dipendente_id, pl.cliente_id, pl.entered_at.date())] = pl

    # Pre-carica assenze approvate sull'intera giornata nel periodo (1 query invece di N query nel loop)
    assenze_approvate_periodo = list(
        Assenza.objects.filter(
            data_inizio__lte=data_fine,
            data_fine__gte=data_inizio,
            stato_approvazione='APPROVATA',
            ora_inizio__isnull=True,
        )
    )
    assenze_per_dip = {}
    for ass in assenze_approvate_periodo:
        assenze_per_dip.setdefault(ass.dipendente_id, []).append(ass)

    # Calcolo ore settimanali per dipendenti part-time direttamente in memoria dai timetracks pre-caricati
    ore_settimanali_dip = {}
    for assign in assegnazioni:
        if not assign.turno:
            continue
        iso_y, iso_w, _ = assign.turno.data.isocalendar()
        for tt in assign.timetracks.all():
            if not tt.dipendente_id:
                continue
            key = (tt.dipendente_id, iso_y, iso_w)
            ore_settimanali_dip[key] = ore_settimanali_dip.get(key, 0.0) + float(tt.durata_ore or 0)

    anomalie = []
    turni_regolari_ids = []
    timetracks_auto_validabili_ids = []
    auto_validabili_items = []
    totale_turni_analizzati = 0
    totale_ore_dichiarate = 0.0
    totale_ore_previste = 0.0

    for assign in assegnazioni:
        data_turno = assign.turno.data
        ore_prev_unitarie = _calcola_ore_previste_assegnazione(assign)
        presenti = assign.dipendenti_presenti
        sost_list = sost_by_assign.get(assign.id, [])
        sost_confermati_ids = {r.sostituto_id for r in sost_list if r.stato in ('ACCETTATA', 'COMPLETATA') and r.sostituto_id}

        tts_all = list(assign.timetracks.all())
        if filter_dip_id:
            presenti_ids = {d.id for d in presenti} | sost_confermati_ids | {t.dipendente_id for t in tts_all}
            if filter_dip_id not in presenti_ids:
                continue
            tts = [t for t in tts_all if t.dipendente_id == filter_dip_id]
            n_pres = 1
        else:
            tts = tts_all
            n_pres = max(len(presenti), 1)

        totale_turni_analizzati += 1
        totale_ore_previste += ore_prev_unitarie * n_pres

        if not tts:
            # Se tutti i componenti del turno sono in assenza e il turno è NON_SOSTITUITO, non è un'anomalia di ore mancanti
            if sost_list and all(r.stato == 'NON_SOSTITUITO' for r in sost_list):
                continue
            # Se stiamo filtrando per un dipendente che in quel giorno è in assenza approvata, salta
            if filter_dip_id and any(a.data_inizio <= data_turno <= a.data_fine for a in assenze_per_dip.get(filter_dip_id, ())):
                continue
            if data_turno < today:
                ora_ini_s = assign.orario_inizio_previsto.strftime('%H:%M') if assign.orario_inizio_previsto else 'N/D'
                ora_fin_s = assign.orario_fine_previsto.strftime('%H:%M') if assign.orario_fine_previsto else 'N/D'
                nome_sq = assign.turno.squadra.nome if (assign.turno and assign.turno.squadra) else 'Squadra Storica'
                sost_attivi = [r for r in sost_list if r.stato in ('ACCETTATA', 'COMPLETATA') and r.sostituto]
                if sost_attivi:
                    dip_manc_lbl = f"{sost_attivi[0].sostituto.cognome} {sost_attivi[0].sostituto.nome} (Sostituto)"
                    dip_manc_id = sost_attivi[0].sostituto_id
                elif len(presenti) == 1:
                    dip_manc_lbl = f"{presenti[0].cognome} {presenti[0].nome}"
                    dip_manc_id = presenti[0].id
                else:
                    dip_manc_lbl = f"Squadra {nome_sq}"
                    dip_manc_id = filter_dip_id
                mot_manc = (
                    f"Turno del {data_turno.strftime('%d/%m/%Y')} ({ora_ini_s}-"
                    f"{ora_fin_s}) non ancora compilato."
                )
                sug_manc = "Registra e valida le ore direttamente col pulsante qui a fianco oppure dal Calendario."
                anomalie.append({
                    'tipo': 'ORE_MANCANTI',
                    'severita': 'ATTENZIONE',
                    'gravita': 'MEDIA',
                    'badge': '🟠 Ore Non Compilate',
                    'data': data_turno,
                    'cliente': assign.cliente.ragione_sociale if assign.cliente else 'N/D',
                    'cliente_nome': assign.cliente.ragione_sociale if assign.cliente else 'N/D',
                    'dipendente': dip_manc_lbl,
                    'dipendente_nome': dip_manc_lbl,
                    'dipendente_id': dip_manc_id,
                    'assegnazione_id': assign.id,
                    'timetracking_id': None,
                    'ore_previste': ore_prev_unitarie,
                    'ore_dichiarate': 0.0,
                    'scostamento': -ore_prev_unitarie,
                    'is_validated': False,
                    'motivo': mot_manc,
                    'motivi': [mot_manc],
                    'azione_consigliata': sug_manc,
                    'suggerimento': sug_manc,
                })
            continue

        assign_has_anomaly = False
        for tt in tts:
            dip = tt.dipendente
            ore_dich = round(float(tt.durata_ore or 0), 2)
            totale_ore_dichiarate += ore_dich
            diff = round(ore_dich - ore_prev_unitarie, 2)
            motivi_tt = []
            severita_tt = 'INFO'

            # 1. Scostamento rispetto all'orario previsto (> 0.5h)
            if ore_prev_unitarie > 0 and abs(diff) >= 0.5:
                segno = "+" if diff > 0 else ""
                motivi_tt.append(
                    f"Scostamento di {segno}{diff}h rispetto alle {ore_prev_unitarie}h previste "
                    f"(dichiarate: {ore_dich}h)."
                )
                severita_tt = 'CRITICA' if abs(diff) >= 2.0 else 'ATTENZIONE'

            # 2. Controllo Part-Time settimanale
            if dip and dip.is_part_time and dip.ore_settimanali_part_time:
                iso_y, iso_w, _ = data_turno.isocalendar()
                tot_sett = round(ore_settimanali_dip.get((dip.id, iso_y, iso_w), 0.0), 1)
                tetto_pt = float(dip.ore_settimanali_part_time)
                if tot_sett > tetto_pt + 0.5:
                    motivi_tt.append(
                        f"Superamento tetto Part-Time ({dip.get_tipo_part_time_display() or 'PT'}): "
                        f"{tot_sett}h nella settimana {iso_w} su {tetto_pt}h contrattuali."
                    )
                    if severita_tt != 'CRITICA':
                        severita_tt = 'ATTENZIONE'

            # 3. Controllo GPS ProximityLog (se presente log per quel dipendente/cliente/data)
            pl = prox_map.get((dip.id if dip else None, assign.cliente_id, data_turno))
            if pl and pl.entered_at and pl.exited_at:
                perm_ore = round((pl.exited_at - pl.entered_at).total_seconds() / 3600.0, 2)
                if ore_dich - perm_ore >= 1.0:
                    motivi_tt.append(
                        f"Permanenza GPS rilevata ({perm_ore}h) inferiore di {round(ore_dich - perm_ore, 1)}h "
                        f"rispetto alle ore dichiarate ({ore_dich}h)."
                    )
                    severita_tt = 'CRITICA'

            # 4. Verifica sovrapposizione con Assenza approvata nello stesso giorno (in memoria)
            if dip:
                ass_conflitto = None
                for ass_item in assenze_per_dip.get(dip.id, ()):
                    if ass_item.data_inizio <= data_turno <= ass_item.data_fine:
                        ass_conflitto = ass_item
                        break
                if ass_conflitto:
                    motivi_tt.append(
                        f"Conflitto: il dipendente risulta in {ass_conflitto.tipo} approvata sull'intera giornata "
                        f"ma ha {ore_dich}h lavorate registrate."
                    )
                    severita_tt = 'CRITICA'

            if motivi_tt:
                assign_has_anomaly = True
                badge_map = {
                    'CRITICA': '🔴 Anomalia Critica',
                    'ATTENZIONE': '🟠 Da Verificare',
                    'INFO': '🔵 Nota IA',
                }
                az_cons = (
                    "Controlla le note del dipendente o rettifica dal Report Cedolini Paghe."
                    if severita_tt == 'CRITICA'
                    else "Verifica scostamento prima della validazione."
                )
                dip_lbl = f"{dip.cognome} {dip.nome}" if dip else 'N/D'
                cli_lbl = assign.cliente.ragione_sociale if assign.cliente else 'N/D'
                anomalie.append({
                    'tipo': 'SCOSTAMENTO_ORE',
                    'severita': severita_tt,
                    'gravita': 'ALTA' if severita_tt == 'CRITICA' else 'MEDIA',
                    'badge': badge_map.get(severita_tt, '🟠 Da Verificare'),
                    'data': data_turno,
                    'cliente': cli_lbl,
                    'cliente_nome': cli_lbl,
                    'dipendente': dip_lbl,
                    'dipendente_nome': dip_lbl,
                    'dipendente_id': dip.id if dip else None,
                    'assegnazione_id': assign.id,
                    'timetracking_id': tt.id,
                    'ore_previste': ore_prev_unitarie,
                    'ore_dichiarate': ore_dich,
                    'scostamento': diff,
                    'is_validated': tt.is_validated,
                    'note_dipendente': tt.note or '',
                    'motivo': " ".join(motivi_tt),
                    'motivi': motivi_tt,
                    'azione_consigliata': az_cons,
                    'suggerimento': az_cons,
                })
            else:
                if not tt.is_validated and ore_dich > 0:
                    timetracks_auto_validabili_ids.append(tt.id)
                    dip_lbl = f"{dip.cognome} {dip.nome}" if dip else 'N/D'
                    cli_lbl = assign.cliente.ragione_sociale if assign.cliente else 'N/D'
                    auto_validabili_items.append({
                        'timetracking_id': tt.id,
                        'assegnazione_id': assign.id,
                        'data': data_turno,
                        'dipendente_id': dip.id if dip else None,
                        'dipendente_nome': dip_lbl,
                        'cliente_nome': cli_lbl,
                        'ore_dichiarate': ore_dich,
                        'ore_previste': ore_prev_unitarie,
                        'note': tt.note or '',
                    })

        if not assign_has_anomaly:
            turni_regolari_ids.append(assign.id)

    auto_validati_count = 0
    if auto_valida and timetracks_auto_validabili_ids:
        auto_validati_count = TimeTracking.objects.filter(
            id__in=timetracks_auto_validabili_ids,
            is_validated=False,
        ).update(is_validated=True)

    # Ordina anomalie: prima CRITICA, poi ATTENZIONE, poi per data decrescente
    ordine_sev = {'CRITICA': 0, 'ATTENZIONE': 1, 'INFO': 2}
    anomalie.sort(key=lambda x: (ordine_sev.get(x['severita'], 9), -x['data'].toordinal()))

    num_critiche = sum(1 for a in anomalie if a['severita'] == 'CRITICA')
    num_attenzione = sum(1 for a in anomalie if a['severita'] == 'ATTENZIONE')

    return {
        'data_inizio': data_inizio,
        'data_fine': data_fine,
        'totale_turni_analizzati': totale_turni_analizzati,
        'totale_ore_previste': round(totale_ore_previste, 1),
        'totale_ore_dichiarate': round(totale_ore_dichiarate, 1),
        'num_anomalie': len(anomalie),
        'num_critiche': num_critiche,
        'num_attenzione': num_attenzione,
        'num_auto_validabili': len(timetracks_auto_validabili_ids),
        'auto_validabili_ids': timetracks_auto_validabili_ids,
        'auto_validabili_items': auto_validabili_items,
        'auto_validati_count': auto_validati_count,
        'anomalie': anomalie,
        'riepilogo': {
            'totale_analizzati': totale_turni_analizzati,
            'anomalie_count': len(anomalie),
            'critiche_count': num_critiche,
            'auto_validabili_count': len(timetracks_auto_validabili_ids),
        },
    }


# ==============================================================================
# 2. NLP CONVERSAZIONALE, ANALISI CERTIFICATI/FOTO & TRIAGE SEGNALAZIONI
# ==============================================================================

CATEGORIE_SEGNALAZIONE = [
    (
        'SICUREZZA',
        'CRITICA',
        '🚨 Sicurezza / Infortunio',
        ['infortun', 'incidente', 'ferit', 'sangue', 'ambulanza', 'cadut', 'scivolat', 'ospedale', 'emergenza', 'pericolo', 'fumo', 'incendio', 'allagament', 'scossa', 'scintill'],
        "Contattare immediatamente il dipendente e il Responsabile Sicurezza/Titolare.",
    ),
    (
        'GUASTO_MEZZO',
        'ALTA',
        '🚐 Guasto / Problema Mezzo',
        ['furgone', 'mezzo', 'auto', 'camion', 'gomma', 'bucata', 'batteria', 'motore', 'spia', 'freni', 'non parte', 'incidente stradale', 'targa', 'carrozzeria', 'meccanico', 'gasolio', 'revisione'],
        "Verificare disponibilità mezzo sostitutivo e impostare il mezzo in stato MANUTENZIONE.",
    ),
    (
        'ACCESSO_CHIAVI',
        'ALTA',
        '🔑 Accesso Cantiere / Chiavi / Allarme',
        ['chiav', 'cancello', 'chiuso', 'allarme', 'codice', 'portone', 'entrare', 'bloccato fuori', 'serratura', 'badge'],
        "Contattare il referente del cliente o fornire le chiavi di scorta alla squadra.",
    ),
    (
        'MATERIALI_SCORTE',
        'NORMALE',
        '🧴 Materiali / Prodotti / Attrezzature',
        ['prodott', 'detergente', 'finit', 'manca', 'sacchett', 'stracci', 'aspirapolvere', 'lavapavimenti', 'scopa', 'guanti', 'carta', 'sapone', 'candeggina', 'materiale'],
        "Programmare rifornimento materiali per il cantiere al prossimo turno.",
    ),
]


def classifica_segnalazione(testo, dipendente=None, mezzi_list=None):
    """
    Analizza il testo di una Segnalazione inviata da un dipendente (via Telegram o Web App),
    determina Categoria, Urgenza (CRITICA, ALTA, NORMALE), eventuale Mezzo coinvolto
    e l'azione consigliata per l'amministrazione.
    """
    from .models import Mezzo

    clean = (testo or '').lower().strip()
    categoria = 'OPERATIVA'
    urgenza = 'NORMALE'
    etichetta = '📋 Segnalazione Operativa'
    azione = "Verificare la segnalazione e aggiornare lo stato in pannello."

    for cat_code, urg, label, keywords, act in CATEGORIE_SEGNALAZIONE:
        if any(kw in clean for kw in keywords):
            categoria = cat_code
            urgenza = urg
            etichetta = label
            azione = act
            break

    # Verifica se nel testo è citata la targa o il modello di un mezzo aziendale
    mezzo_rilevato = None
    try:
        elenco_mezzi = mezzi_list if mezzi_list is not None else list(Mezzo.objects.all())
        for m in elenco_mezzi:
            targa_low = (m.targa or '').lower().strip()
            mod_low = (m.modello or '').lower().strip()
            if (targa_low and targa_low in clean) or (mod_low and len(mod_low) > 3 and mod_low in clean):
                mezzo_rilevato = m
                if categoria == 'OPERATIVA':
                    categoria = 'GUASTO_MEZZO'
                    urgenza = 'ALTA'
                    etichetta = '🚐 Guasto / Problema Mezzo'
                azione = f"Valutare messa in MANUTENZIONE del mezzo {m.modello} ({m.targa})."
                break
    except Exception:
        pass

    return {
        'categoria': categoria,
        'urgenza': urgenza,
        'etichetta': etichetta,
        'azione_consigliata': azione,
        'mezzo_id': mezzo_rilevato.id if mezzo_rilevato else None,
        'mezzo_nome': str(mezzo_rilevato) if mezzo_rilevato else None,
        'sintesi_admin': f"[IA Triage: {urgenza} — {etichetta}] Azione consigliata: {azione}",
    }


def _estrai_date_naturali(testo, today=None):
    """Estrae data_inizio e data_fine da espressioni in italiano ('oggi', 'ieri', 'domani', 'lunedì', '15/10', 'dal 12 al 15')."""
    if not today:
        today = timezone.now().date()
    low = (testo or '').lower()

    # 1. Cerca date esplicite DD/MM(/YYYY)
    matches = re.findall(r'(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?', low)
    explicit_dates = []
    for d_s, m_s, y_s in matches:
        day_i, month_i = int(d_s), int(m_s)
        if 1 <= day_i <= 31 and 1 <= month_i <= 12:
            year_i = int(y_s) if y_s else today.year
            if year_i < 100:
                year_i += 2000
            try:
                explicit_dates.append(date(year_i, month_i, day_i))
            except ValueError:
                pass
    if explicit_dates:
        d1 = explicit_dates[0]
        d2 = explicit_dates[-1]
        if d2 < d1:
            d1, d2 = d2, d1
        return d1, d2

    # 2. Parole relative ('dopodomani', 'domani', 'ieri', 'oggi')
    if 'dopodomani' in low:
        d = today + timedelta(days=2)
        return d, d
    if 'domani' in low:
        d = today + timedelta(days=1)
        return d, d
    if 'l\'altro ieri' in low or 'altroieri' in low:
        d = today - timedelta(days=2)
        return d, d
    if 'ieri' in low:
        d = today - timedelta(days=1)
        return d, d
    if 'oggi' in low or 'stamattina' in low or 'stasera' in low:
        return today, today

    # 3. Giorni della settimana ('lunedì', 'martedì', ecc.)
    giorni_map = {
        'luned': 0, 'marted': 1, 'mercoled': 2, 'gioved': 3,
        'venerd': 4, 'sabat': 5, 'domenic': 6
    }
    for rad, wd in giorni_map.items():
        if rad in low:
            delta = (wd - today.weekday()) % 7
            if delta == 0 and ('scorso' in low or 'passato' in low):
                delta = -7
            elif 'scorso' in low:
                delta = delta - 7
            target = today + timedelta(days=delta)
            return target, target

    return today, today


def _estrai_ore_lavorate_naturali(testo):
    """
    Estrae il numero di ore lavorate da espressioni naturali:
    es. '3 ore e mezza' -> 3.5, '2 ore e 15' -> 2.25, '4,5 ore' -> 4.5, '3h' -> 3.0
    """
    low = (testo or '').lower()

    # Pattern 'X ore e mezza' / 'X ora e mezzo'
    m_mezza = re.search(r'(\d+)\s*(?:or[ae]|h)\s*e\s*mezz[ao]', low)
    if m_mezza:
        return float(m_mezza.group(1)) + 0.5

    if 'mezz\'ora' in low or 'mezza ora' in low:
        return 0.5

    # Pattern 'X ore e Y minuti' / 'X ore e 30'
    m_min = re.search(r'(\d+)\s*(?:or[ae]|h)\s*e\s*(\d{1,2})\b', low)
    if m_min:
        h = int(m_min.group(1))
        mins = int(m_min.group(2))
        if mins < 60:
            return round(h + mins / 60.0, 2)

    # Pattern 'X,5 ore' / 'X.5 h' / 'X ore'
    m_std = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:or[ae]|h\b)', low)
    if m_std:
        return float(m_std.group(1).replace(',', '.'))

    return None


def interpreta_messaggio_libero(dipendente, testo):
    """
    Analizza una frase in linguaggio naturale scritta o dettata dal dipendente
    (su Telegram o nella Web App /app/) e restituisce un'azione strutturata:
    - REGISTRA_ORE (con assegnazione turno, cliente, ore, data, note)
    - RICHIESTA_ASSENZA (con tipo FERIE/MALATTIA/PERMESSO/104, data_inizio, data_fine, ora_inizio, ora_fine)
    - SEGNALAZIONE (con classificazione d'urgenza e categoria)
    - SCONOSCIUTO (se è una normale conversazione da inoltrare alla chat ufficio)
    """
    from .models import Cliente, AssegnazioneTurno, RichiestaSostituzione

    raw = (testo or '').strip()
    if not raw:
        return {'intent': 'SCONOSCIUTO'}

    low = raw.lower()
    today = timezone.now().date()

    # 1. RICONOSCIMENTO INTENTO ASSENZA (Malattia, Ferie, Permesso, Legge 104)
    tipo_assenza = None
    if any(k in low for k in ['malattia', 'malato', 'mutua', 'febbre', 'influenza', 'certificato medico']):
        tipo_assenza = 'MALATTIA'
    elif any(k in low for k in ['104', 'legge 104']):
        tipo_assenza = '104'
    elif any(k in low for k in ['ferie', 'vacanza', 'giorni di ferie']):
        tipo_assenza = 'FERIE'
    elif any(k in low for k in ['permesso', 'uscire prima', 'entrare dopo', 'assente dalle']):
        tipo_assenza = 'PERMESSO'

    if tipo_assenza:
        d_inizio, d_fine = _estrai_date_naturali(raw, today=today)
        ora_inizio = None
        ora_fine = None
        # Cerca fascia oraria es. "dalle 9 alle 11:30" o "09:00 - 12:00"
        m_orario = re.search(
            r'(?:dalle\s+|ore\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(?:alle|-|fino\s+alle)\s*(\d{1,2})(?:[:.](\d{2}))?',
            low
        )
        if m_orario:
            try:
                h1 = int(m_orario.group(1))
                m1 = int(m_orario.group(2) or 0)
                h2 = int(m_orario.group(3))
                m2 = int(m_orario.group(4) or 0)
                if 0 <= h1 <= 23 and 0 <= h2 <= 23:
                    ora_inizio = time(h1, m1)
                    ora_fine = time(h2, m2)
                    if not tipo_assenza:
                        tipo_assenza = 'PERMESSO'
            except ValueError:
                pass

        riepilogo = f"{tipo_assenza} dal {d_inizio.strftime('%d/%m/%Y')} al {d_fine.strftime('%d/%m/%Y')}"
        if ora_inizio and ora_fine:
            riepilogo += f" ({ora_inizio.strftime('%H:%M')} - {ora_fine.strftime('%H:%M')})"

        return {
            'intent': 'ASSENZA',
            'tipo_assenza': tipo_assenza,
            'data_inizio': d_inizio,
            'data_fine': d_fine,
            'ora_inizio': ora_inizio,
            'ora_fine': ora_fine,
            'note': raw,
            'riepilogo': riepilogo,
        }

    # 2. RICONOSCIMENTO INTENTO REGISTRAZIONE ORE (es. "Oggi da Rossi ho fatto 3 ore e mezza")
    ore_estr = _estrai_ore_lavorate_naturali(raw)
    if ore_estr and 0 < ore_estr <= 24:
        d_turno, _ = _estrai_date_naturali(raw, today=today)

        # Cerca i turni del dipendente in quella data
        sost_ids = set(
            RichiestaSostituzione.objects.filter(
                sostituto=dipendente,
                stato__in=['ACCETTATA', 'COMPLETATA'],
                assegnazione_originale__turno__data=d_turno,
            ).values_list('assegnazione_originale_id', flat=True)
        ) if dipendente else set()

        turni_dip = []
        if dipendente:
            turni_dip = list(
                AssegnazioneTurno.objects.filter(turno__data=d_turno)
                .filter(
                    Q(turno__squadra__componenti=dipendente)
                    | Q(turno__squadra__caposquadra=dipendente)
                    | Q(id__in=sost_ids)
                )
                .select_related('cliente', 'turno', 'turno__squadra')
                .distinct()
            )

        best_assign = None
        best_score = 0.0
        for a in turni_dip:
            c_nome = (a.cliente.ragione_sociale or '').lower()
            parole_cliente = [p for p in re.split(r'\W+', c_nome) if len(p) >= 3 and p not in ('srl', 'spa', 'snc', 'sas', 'condominio', 'via', 'del', 'della')]
            for p in parole_cliente:
                if p in low:
                    score = len(p) / max(len(c_nome), 1)
                    if score > best_score:
                        best_score = score
                        best_assign = a

        # Se non ha specificato il nome ma ha un solo turno oggi, usa quello!
        if not best_assign and len(turni_dip) == 1:
            best_assign = turni_dip[0]

        # Se ha scritto il nome di un cliente ma non era nei turni_dip di quel giorno, cerca su tutti i turni degli ultimi 7gg
        if not best_assign and dipendente:
            turni_7gg = list(
                AssegnazioneTurno.objects.filter(
                    turno__data__gte=today - timedelta(days=7),
                    turno__data__lte=today,
                )
                .filter(
                    Q(turno__squadra__componenti=dipendente)
                    | Q(turno__squadra__caposquadra=dipendente)
                )
                .select_related('cliente', 'turno')
                .order_by('-turno__data')
                .distinct()
            )
            for a in turni_7gg:
                c_nome = (a.cliente.ragione_sociale or '').lower()
                parole_cliente = [p for p in re.split(r'\W+', c_nome) if len(p) >= 3 and p not in ('srl', 'spa', 'snc', 'sas', 'condominio')]
                if any(p in low for p in parole_cliente):
                    best_assign = a
                    d_turno = a.turno.data
                    break

        if best_assign:
            return {
                'intent': 'REGISTRA_ORE',
                'assegnazione': best_assign,
                'assegnazione_id': best_assign.id,
                'cliente_nome': best_assign.cliente.ragione_sociale,
                'data': best_assign.turno.data,
                'ore': ore_estr,
                'note': raw,
                'riepilogo': f"{ore_estr:g}h presso {best_assign.cliente.ragione_sociale} ({best_assign.turno.data.strftime('%d/%m/%Y')})",
            }

    # 3. RICONOSCIMENTO INTENTO SEGNALAZIONE CRITICA / GUASTO
    triage = classifica_segnalazione(raw, dipendente=dipendente)
    if triage['categoria'] != 'OPERATIVA':
        return {
            'intent': 'SEGNALAZIONE',
            'triage': triage,
            'testo': raw,
            'riepilogo': f"{triage['etichetta']} (Urgenza: {triage['urgenza']})",
        }

    # 4. FALLBACK OPZIONALE GEMINI API (se configurata)
    if is_gemini_configured():
        prompt = (
            f"Data odierna: {today.strftime('%Y-%m-%d')}. "
            f"Analizza questo messaggio del dipendente: \"{raw}\". "
            "Rispondi in JSON con chiave 'intent' tra: 'RICHIESTA_ASSENZA', 'SEGNALAZIONE', 'SCONOSCIUTO'. "
            "Se RICHIESTA_ASSENZA includi 'tipo_assenza' (FERIE, MALATTIA, PERMESSO, 104), 'data_inizio' (YYYY-MM-DD), 'data_fine' (YYYY-MM-DD)."
        )
        gem_res = call_gemini_json(prompt)
        if gem_res and gem_res.get('intent') in ('RICHIESTA_ASSENZA', 'SEGNALAZIONE'):
            return gem_res

    return {'intent': 'SCONOSCIUTO'}


def analizza_documento_o_certificato(dipendente=None, testo_o_nomefile='', image_bytes=None, mime_type='image/jpeg',
                                     testo_o_caption=None, filename='', file_bytes=None):
    """
    Analizza un certificato medico o un attestato di formazione inviato via Telegram o Web App:
    - Estrae numero protocollo PUC (9-15 cifre), date di prognosi o tipo di corso di formazione
    - Se GEMINI_API_KEY è attiva e viene fornita un'immagine, esegue l'OCR visuale automatico.
    Supporta sia chiamata posizionale con stringa sia chiamata con dipendente + testo/file.
    """
    today = timezone.now().date()
    if isinstance(dipendente, str) and not testo_o_nomefile and not testo_o_caption:
        testo_o_nomefile = dipendente
        dipendente = None

    parts_txt = [p for p in (testo_o_nomefile, testo_o_caption, filename) if p]
    combined_text = " ".join(parts_txt).strip()
    img_data = image_bytes or file_bytes

    # Se è presente un'immagine e Gemini Free Tier è attivo, usa Vision OCR
    if img_data and is_gemini_configured():
        prompt = (
            f"Data di oggi: {today.strftime('%Y-%m-%d')}. "
            "Leggi questo documento/certificato del dipendente. "
            "Restituisci un JSON con: "
            "'tipo_documento' ('CERTIFICATO_MALATTIA', 'ATTESTATO_CORSO', 'ALTRO'), "
            "'protocollo_puc' (stringa se presente), "
            "'data_inizio' (YYYY-MM-DD se presente), "
            "'data_fine' (YYYY-MM-DD se presente), "
            "'nome_corso' (se è un attestato corso), "
            "'sintesi' (breve descrizione in italiano)."
        )
        ocr_data = call_gemini_json(prompt, image_bytes=img_data, mime_type=mime_type)
        if ocr_data and ocr_data.get('tipo_documento') in ('CERTIFICATO_MALATTIA', 'ATTESTATO_CORSO'):
            ocr_data.setdefault('corso_nome', ocr_data.get('nome_corso'))
            ocr_data.setdefault('codice_puc', ocr_data.get('protocollo_puc'))
            ocr_data.setdefault('data_rilevata', ocr_data.get('data_inizio'))
            ocr_data.setdefault('data_fine_rilevata', ocr_data.get('data_fine'))
            return ocr_data

    low = combined_text.lower()
    # Estrazione protocollo PUC (tipicamente 9-15 cifre)
    m_puc = re.search(r'\b(\d{9,15})\b', low)
    puc = m_puc.group(1) if m_puc else None
    d_inizio, d_fine = _estrai_date_naturali(combined_text, today=today)

    if any(k in low for k in ['malattia', 'certificato', 'inps', 'prognosi', 'medico', 'mutua']) or puc:
        return {
            'tipo_documento': 'CERTIFICATO_MALATTIA',
            'protocollo_puc': puc,
            'codice_puc': puc,
            'corso_nome': None,
            'nome_corso': None,
            'data_inizio': d_inizio.strftime('%Y-%m-%d'),
            'data_fine': d_fine.strftime('%Y-%m-%d'),
            'data_rilevata': d_inizio.strftime('%d/%m/%Y'),
            'data_fine_rilevata': d_fine.strftime('%d/%m/%Y'),
            'sintesi': f"Certificato di Malattia rilevato ({d_inizio.strftime('%d/%m/%Y')} - {d_fine.strftime('%d/%m/%Y')})" + (f" - PUC: {puc}" if puc else ""),
        }

    corsi_keywords = {
        'sicurezza generale': 'Corso sicurezza generale',
        'basso rischio': 'Corso Specifico Basso Rischio',
        'carichi': 'Corso Movimentazione manuale carichi',
        'quota': 'Corso DPI 3 lavori in quota',
        'dpi': 'Corso DPI 3 lavori in quota',
        'rls': 'Corso RLS',
        'preposto': 'Corso preposto',
        'primo soccorso': 'Corso primo soccorso',
        'piattaform': 'Corso piattaforme mobili con o senza stabilizzatori',
        'haccp': 'Corso HACCP',
        'antincendio': 'Corso antincendio livello 2',
    }
    for kw, nome_ufficiale in corsi_keywords.items():
        if kw in low:
            return {
                'tipo_documento': 'ATTESTATO_CORSO',
                'nome_corso': nome_ufficiale,
                'corso_nome': nome_ufficiale,
                'codice_puc': None,
                'protocollo_puc': None,
                'data_esecuzione': d_inizio.strftime('%Y-%m-%d'),
                'data_rilevata': d_inizio.strftime('%d/%m/%Y'),
                'data_fine_rilevata': None,
                'sintesi': f"Attestato rilevato: {nome_ufficiale} (Data: {d_inizio.strftime('%d/%m/%Y')})",
            }

    return {
        'tipo_documento': 'ALTRO',
        'corso_nome': None,
        'nome_corso': None,
        'codice_puc': None,
        'protocollo_puc': None,
        'data_rilevata': None,
        'data_fine_rilevata': None,
        'sintesi': 'Documento allegato ricevuto',
    }


# ==============================================================================
# 3. OTTIMIZZAZIONE TURNI E "SMART SOSTITUZIONI" (RANKING PREDITTIVO 0-100)
# ==============================================================================

def calcola_smart_score_sostituto(dipendente, cliente, data_turno, distanza_km, qualifica_compatibile,
                                  presenze_cliente=0, ore_settimana=0.0, tasso_accettazione=None,
                                  conformita_ok=True, motivi_non_conformita=None):
    """
    Calcola un punteggio predittivo da 0 a 100 per un candidato sostituto combinando:
    1. Esperienza pregressa presso lo specifico Cliente (fino a +30 pt)
    2. Vicinanza geografica casa-cantiere (fino a +25 pt)
    3. Compatibilità qualifica e conformità sicurezza/visita medica (fino a +20 pt)
    4. Equilibrio carico orario settimanale rispetto al contratto (fino a +15 pt)
    5. Affidabilità e rapidità storica nelle sostituzioni (fino a +10 pt)
    """
    score = 0
    badges = []

    # 1. Esperienza sul cliente (0 - 30 pt)
    if presenze_cliente >= 10:
        score += 30
        badges.append(f"⭐ Esperto del cantiere ({presenze_cliente} turni svolti)")
    elif presenze_cliente >= 3:
        score += 22
        badges.append(f"🏢 Conosce il cantiere ({presenze_cliente} turni)")
    elif presenze_cliente >= 1:
        score += 14
        badges.append(f"🏢 Già stato dal cliente ({presenze_cliente}x)")

    # 2. Distanza geografica (0 - 25 pt)
    if distanza_km != float('inf') and distanza_km is not None:
        if distanza_km <= 3.0:
            score += 25
            badges.append(f"📍 Vicinissimo ({distanza_km:.1f} km)")
        elif distanza_km <= 8.0:
            score += 20
            badges.append(f"📍 Vicino ({distanza_km:.1f} km)")
        elif distanza_km <= 15.0:
            score += 12
        elif distanza_km <= 30.0:
            score += 5

    # 3. Qualifica e Conformità Sicurezza (0 - 20 pt)
    if qualifica_compatibile:
        score += 10
    if conformita_ok:
        score += 10
        badges.append("🛡️ Visita e corsi in regola")
    else:
        score -= 15
        if motivi_non_conformita:
            badges.append(f"⚠️ {motivi_non_conformita[0]}")

    # 4. Carico settimanale (0 - 15 pt)
    tetto = float(dipendente.ore_settimanali_part_time) if (dipendente.is_part_time and dipendente.ore_settimanali_part_time) else 40.0
    if ore_settimana < tetto * 0.7:
        score += 15
        badges.append(f"⚖️ Monte ore libero ({ore_settimana:.1f}h/{tetto:g}h sett.)")
    elif ore_settimana < tetto:
        score += 8
    else:
        score -= 10
        badges.append(f"⚠️ Monte ore settimanale pieno ({ore_settimana:.1f}h)")

    # 5. Storico risposte sostituzioni (0 - 10 pt)
    if tasso_accettazione is not None:
        if tasso_accettazione >= 0.75:
            score += 10
            badges.append("⚡ Alta risposta sostituzioni")
        elif tasso_accettazione >= 0.4:
            score += 5
    else:
        score += 5  # Neutro se non ha ancora storico

    score = max(0, min(100, int(round(score))))
    return score, badges


# ==============================================================================
# 4. CONTROLLO CONFORMITÀ, SICUREZZA E SCADENZE ("COMPLIANCE GUARDIAN")
# ==============================================================================

REGOLE_CORSI_MANSIONE = [
    (['quota', ' tetto', 'ponteggi', 'imbracatur', 'vetrate alte'], 'Corso DPI 3 lavori in quota', 'Lavori in Quota (DPI III)'),
    (['piattaform', 'cestello', 'ple ', 'autoscala'], 'Corso piattaforme mobili con o senza stabilizzatori', 'Piattaforme Mobili (PLE)'),
    (['haccp', 'mensa', 'cucina', 'alimentar', 'ristorante', 'bar '], 'Corso HACCP', 'Igiene Alimentare (HACCP)'),
    (['antincendio'], 'Corso antincendio livello 2', 'Antincendio Livello 2'),
]


def verifica_idoneita_dipendente_per_cliente(dipendente, cliente, data_riferimento=None, mansione_extra='', corsi_dip_map=None):
    """
    Verifica se un singolo dipendente ha visita medica e corsi obbligatori validi alla data_riferimento
    per lavorare presso lo specifico cliente.
    Restituisce (is_ok, lista_problemi).
    """
    from .models import CorsoDipendente

    if not data_riferimento:
        data_riferimento = timezone.now().date()

    problemi = []

    # 1. Visita medica (in Kandor data_ultima_visita_medica indica la prossima scadenza visita medica)
    if dipendente.data_ultima_visita_medica and dipendente.data_ultima_visita_medica < data_riferimento:
        problemi.append(f"Visita medica scaduta il {dipendente.data_ultima_visita_medica.strftime('%d/%m/%Y')}")

    # 2. Controllo corsi specifici richiesti dalle note del cliente o dalla mansione del turno
    testo_cantiere = f"{getattr(cliente, 'note_mansioni', '') or ''} {mansione_extra or ''}".lower()
    mappa_corsi_richiesti = [
        (keywords, nome_corso, label_breve)
        for keywords, nome_corso, label_breve in REGOLE_CORSI_MANSIONE
        if any(kw in testo_cantiere for kw in keywords)
    ]

    if mappa_corsi_richiesti:
        if corsi_dip_map is not None:
            corsi_dip = corsi_dip_map.get(dipendente.id, {})
        else:
            corsi_dip = {
                cd.corso.nome: cd
                for cd in CorsoDipendente.objects.filter(dipendente=dipendente).select_related('corso')
            }

        for _, nome_corso, label_breve in mappa_corsi_richiesti:
            cd = corsi_dip.get(nome_corso)
            if not cd or cd.stato != 'FATTO':
                problemi.append(f"Manca {label_breve} richiesto dal cantiere")
            elif cd.data_scadenza and cd.data_scadenza < data_riferimento:
                problemi.append(f"{label_breve} scaduto il {cd.data_scadenza.strftime('%d/%m/%Y')}")

    return (len(problemi) == 0), problemi


def verifica_conformita_turni(data_inizio=None, data_fine=None, giorni=None):
    """
    Controlla tutti i turni pianificati nel periodo (default: da oggi ai prossimi 14 giorni)
    segnalando preventivamente blocchi normativi o operativi:
    - Cantiere in Città Alta (Bergamo) con mezzo privo di Permesso Città Alta valido
    - Mezzo in Manutenzione/Riparazione o con Revisione/Polizza scaduta alla data del turno
    - Componenti della squadra con Visita Medica scaduta o Corsi specifici mancanti/scaduti
    """
    from .models import AssegnazioneTurno, CorsoDipendente

    today = timezone.now().date()
    if not data_inizio:
        data_inizio = today
    if not data_fine:
        days_span = int(giorni) if giorni is not None else 14
        data_fine = data_inizio + timedelta(days=days_span)

    assegnazioni = list(
        AssegnazioneTurno.objects.filter(
            turno__data__gte=data_inizio,
            turno__data__lte=data_fine,
        )
        .select_related('cliente', 'turno', 'turno__squadra', 'turno__squadra__caposquadra', 'turno__mezzo')
        .prefetch_related('dipendenti_esclusi', 'turno__squadra__componenti', 'timetracks__dipendente')
        .order_by('turno__data', 'orario_inizio_previsto')
    )

    # Pre-carica tutti i corsi dei dipendenti in 1 sola query invece di N query nel loop
    corsi_dip_map = {}
    for cd in CorsoDipendente.objects.select_related('corso').all():
        corsi_dip_map.setdefault(cd.dipendente_id, {})[cd.corso.nome] = cd

    alert_conformita = []

    for a in assegnazioni:
        d_turno = a.turno.data
        cliente = a.cliente
        mezzo = a.turno.mezzo if a.turno else None
        squadra = a.turno.squadra if a.turno else None

        # A. CONTROLLI SUL MEZZO ASSEGNATO
        if mezzo:
            if mezzo.stato in ('MANUTENZIONE', 'RIPARAZIONE'):
                desc_m = f"Il mezzo {mezzo} assegnato al turno del {d_turno.strftime('%d/%m/%Y')} è attualmente in stato '{mezzo.get_stato_display()}'."
                sol_m = "Assegna un mezzo alternativo disponibile al turno."
                alert_conformita.append({
                    'severita': 'CRITICA',
                    'gravita': 'CRITICA',
                    'tipo': 'MEZZO_INDISPONIBILE',
                    'categoria': 'MEZZO_INDISPONIBILE',
                    'badge': '🔴 Mezzo Non Disponibile',
                    'titolo': '🔴 Mezzo Non Disponibile',
                    'data': d_turno,
                    'cliente': cliente.ragione_sociale if cliente else 'N/D',
                    'squadra': squadra.nome if squadra else 'N/D',
                    'risorsa': str(mezzo),
                    'mezzo_id': mezzo.id,
                    'descrizione': desc_m,
                    'dettaglio': desc_m,
                    'soluzione': sol_m,
                    'azione_rapida': sol_m,
                })
            if mezzo.scadenza_revisione and mezzo.scadenza_revisione < d_turno:
                desc_rev = f"Il mezzo {mezzo} ha la revisione scaduta ({mezzo.scadenza_revisione.strftime('%d/%m/%Y')}) per il turno del {d_turno.strftime('%d/%m/%Y')}."
                sol_rev = "Sostituisci il mezzo sul turno o aggiorna la data di revisione."
                alert_conformita.append({
                    'severita': 'CRITICA',
                    'gravita': 'CRITICA',
                    'tipo': 'REVISIONE_SCADUTA',
                    'categoria': 'REVISIONE_SCADUTA',
                    'badge': '🔴 Revisione Mezzo Scaduta',
                    'titolo': '🔴 Revisione Mezzo Scaduta',
                    'data': d_turno,
                    'cliente': cliente.ragione_sociale if cliente else 'N/D',
                    'squadra': squadra.nome if squadra else 'N/D',
                    'risorsa': str(mezzo),
                    'mezzo_id': mezzo.id,
                    'descrizione': desc_rev,
                    'dettaglio': desc_rev,
                    'soluzione': sol_rev,
                    'azione_rapida': sol_rev,
                })
            if mezzo.scadenza_polizza and mezzo.scadenza_polizza < d_turno:
                desc_pol = f"Il mezzo {mezzo} ha la polizza assicurativa scaduta ({mezzo.scadenza_polizza.strftime('%d/%m/%Y')})."
                sol_pol = "Rinnova la polizza o assegna un altro mezzo."
                alert_conformita.append({
                    'severita': 'CRITICA',
                    'gravita': 'CRITICA',
                    'tipo': 'POLIZZA_SCADUTA',
                    'categoria': 'POLIZZA_SCADUTA',
                    'badge': '🔴 Polizza Mezzo Scaduta',
                    'titolo': '🔴 Polizza Mezzo Scaduta',
                    'data': d_turno,
                    'cliente': cliente.ragione_sociale if cliente else 'N/D',
                    'squadra': squadra.nome if squadra else 'N/D',
                    'risorsa': str(mezzo),
                    'mezzo_id': mezzo.id,
                    'descrizione': desc_pol,
                    'dettaglio': desc_pol,
                    'soluzione': sol_pol,
                    'azione_rapida': sol_pol,
                })

            # Controllo specifico Permesso Città Alta (Bergamo)
            testo_luogo = f"{cliente.ragione_sociale if cliente else ''} {cliente.indirizzo_sede if cliente else ''} {cliente.note_mansioni if cliente else ''}".lower()
            if any(k in testo_luogo for k in ['città alta', 'citta alta', 'ztl città alta', 'bergamo alta', 'colle aperto', 'via gombito', 'piazza vecchia']):
                if not mezzo.scadenza_permesso_citta_alta or mezzo.scadenza_permesso_citta_alta < d_turno:
                    stato_perm = f"scaduto il {mezzo.scadenza_permesso_citta_alta.strftime('%d/%m/%Y')}" if mezzo.scadenza_permesso_citta_alta else "non presente"
                    desc_ztl = f"Cantiere in zona Città Alta ma il mezzo {mezzo} ha il Permesso Città Alta {stato_perm}."
                    sol_ztl = "Assegna un mezzo dotato di Permesso Città Alta attivo per evitare sanzioni ZTL."
                    alert_conformita.append({
                        'severita': 'CRITICA',
                        'gravita': 'CRITICA',
                        'tipo': 'PERMESSO_CITTA_ALTA',
                        'categoria': 'ZTL_CITTA_ALTA',
                        'badge': '🚧 ZTL Città Alta (BG)',
                        'titolo': '🚧 Permesso ZTL Città Alta Scaduto o Assente',
                        'data': d_turno,
                        'cliente': cliente.ragione_sociale if cliente else 'N/D',
                        'squadra': squadra.nome if squadra else 'N/D',
                        'risorsa': str(mezzo),
                        'mezzo_id': mezzo.id,
                        'descrizione': desc_ztl,
                        'dettaglio': desc_ztl,
                        'soluzione': sol_ztl,
                        'azione_rapida': sol_ztl,
                    })

        # B. CONTROLLI SUI COMPONENTI DELLA SQUADRA
        for dip in a.dipendenti_presenti:
            ok, probs = verifica_idoneita_dipendente_per_cliente(
                dip, cliente, data_riferimento=d_turno, mansione_extra=a.mansione_svolta, corsi_dip_map=corsi_dip_map
            )
            if not ok:
                desc_dip = f"Turno del {d_turno.strftime('%d/%m/%Y')}: {', '.join(probs)}."
                sol_dip = "Aggiorna l'attestato/visita in scheda Dipendente o assegna un operatore abilitato."
                alert_conformita.append({
                    'severita': 'ATTENZIONE',
                    'gravita': 'ALTA',
                    'tipo': 'IDONEITA_DIPENDENTE',
                    'categoria': 'IDONEITA_DIPENDENTE',
                    'badge': '🛡️ Conformità Sicurezza/Medica',
                    'titolo': f"🛡️ {dip.cognome} {dip.nome}: Conformità Sicurezza/Medica",
                    'data': d_turno,
                    'cliente': cliente.ragione_sociale if cliente else 'N/D',
                    'squadra': squadra.nome if squadra else 'N/D',
                    'risorsa': f"{dip.cognome} {dip.nome}",
                    'mezzo_id': None,
                    'descrizione': desc_dip,
                    'dettaglio': desc_dip,
                    'soluzione': sol_dip,
                    'azione_rapida': sol_dip,
                })

    num_critici = sum(1 for x in alert_conformita if x['severita'] == 'CRITICA')
    return {
        'data_inizio': data_inizio,
        'data_fine': data_fine,
        'num_alert': len(alert_conformita),
        'totale_alert': len(alert_conformita),
        'num_critici': num_critici,
        'critici_count': num_critici,
        'alerts': alert_conformita,
    }


# ==============================================================================
# 5. CONTROLLO MARGINALITÀ, BURN-RATE E LAVORI EXTRA CANTIERI
# ==============================================================================

PAROLE_CHIAVE_LAVORI_EXTRA = [
    'extra', 'straordinari', 'in più', 'in piu', 'fuori contratto', 'richiesto dal cliente',
    'sgombero', 'allagament', 'cantiere fine lavori', 'vetri extra', 'cortile extra',
    'disinfestazione', 'emergenza', 'urgenza', 'pulizia profonda', 'sanificazione'
]


def analizza_marginalita_e_budget_clienti(mese=None, anno=None):
    """
    Analizza tutti i Clienti nel mese selezionato:
    - Confronta ore lavorate/dichiarate, ore pianificate e ore_mensili_contratto
    - Calcola la proiezione di fine mese (burn-rate) per prevenire sforamenti
    - Calcola la tariffa oraria effettiva (€/ora reale vs €/ora contrattuale)
    - Scansiona le note dei dipendenti alla ricerca di 'Lavori Extra' svolti fuori dalle Richieste Straordinarie
      per suggerire all'amministrazione cosa fatturare a parte.
    """
    from .models import Cliente, AssegnazioneTurno, TimeTracking

    today = timezone.now().date()
    mese = int(mese or today.month)
    anno = int(anno or today.year)

    _, num_giorni_mese = calendar.monthrange(anno, mese)
    inizio_mese = date(anno, mese, 1)
    fine_mese = date(anno, mese, num_giorni_mese)

    if anno == today.year and mese == today.month:
        giorni_trascorsi = max(today.day, 1)
    elif fine_mese < today:
        giorni_trascorsi = num_giorni_mese
    else:
        giorni_trascorsi = 1

    clienti = list(Cliente.objects.all().order_by('ragione_sociale'))
    report_clienti = []
    lavori_extra_rilevati = []

    # Carica tutte le assegnazioni del mese per tutti i clienti in 1 sola query invece di N query nel loop
    tutte_assegnazioni_mese = list(
        AssegnazioneTurno.objects.filter(
            turno__data__gte=inizio_mese,
            turno__data__lte=fine_mese,
        )
        .select_related('turno', 'turno__squadra', 'turno__squadra__caposquadra', 'richiesta_straordinaria')
        .prefetch_related('timetracks__dipendente', 'dipendenti_esclusi', 'turno__squadra__componenti')
    )
    assegnazioni_per_cliente = {}
    for a_item in tutte_assegnazioni_mese:
        assegnazioni_per_cliente.setdefault(a_item.cliente_id, []).append(a_item)

    for cliente in clienti:
        ore_contratto = float(cliente.ore_mensili_contratto or 0)
        importo_contratto = float(cliente.importo_mensile_contratto or 0)

        assegnazioni_mese = assegnazioni_per_cliente.get(cliente.id, ())

        ore_pianificate_ordinarie = 0.0
        ore_lavorate_ordinarie = 0.0
        ore_lavorate_straordinarie = 0.0

        for a in assegnazioni_mese:
            is_straord = bool(a.richiesta_straordinaria_id)
            ore_unit = _calcola_ore_previste_assegnazione(a)
            n_pres = max(len(a.dipendenti_presenti), 1)
            if not is_straord:
                ore_pianificate_ordinarie += ore_unit * n_pres

            for tt in a.timetracks.all():
                h_tt = float(tt.durata_ore or 0)
                if is_straord:
                    ore_lavorate_straordinarie += h_tt
                else:
                    ore_lavorate_ordinarie += h_tt

                # Scansione NLP delle note del dipendente per intercettare lavori extra non fatturati
                nota_low = (tt.note or '').lower()
                if not is_straord and nota_low:
                    kw_trovate = [kw for kw in PAROLE_CHIAVE_LAVORI_EXTRA if kw in nota_low]
                    if kw_trovate:
                        dip_lbl = f"{tt.dipendente.cognome} {tt.dipendente.nome}" if tt.dipendente else 'N/D'
                        lavori_extra_rilevati.append({
                            'data': a.turno.data,
                            'cliente': cliente.ragione_sociale,
                            'cliente_nome': cliente.ragione_sociale,
                            'cliente_id': cliente.id,
                            'dipendente': dip_lbl,
                            'dipendente_nome': dip_lbl,
                            'ore_dichiarate': round(h_tt, 1),
                            'ore': round(h_tt, 1),
                            'ore_previste': round(ore_unit, 1),
                            'nota': tt.note,
                            'parole_chiave': kw_trovate,
                            'keyword': kw_trovate[0],
                            'suggerimento': "Lavoro extra segnalato nelle note su turno ordinario: verifica se da fatturare come Richiesta Straordinaria.",
                        })

        # Se non ci sono ancora timetracking ma ci sono turni passati/pianificati, calcola proiezione
        base_proiezione = ore_lavorate_ordinarie if ore_lavorate_ordinarie > 0 else ore_pianificate_ordinarie
        if anno == today.year and mese == today.month and ore_lavorate_ordinarie > 0:
            proiezione_fine_mese = round((ore_lavorate_ordinarie / giorni_trascorsi) * num_giorni_mese, 1)
            # Se la programmazione fissa è maggiore della proiezione lineare, usa il massimo prudenziale
            proiezione_fine_mese = max(proiezione_fine_mese, round(ore_lavorate_ordinarie, 1))
        else:
            proiezione_fine_mese = round(base_proiezione, 1)

        scostamento_contratto = round(ore_lavorate_ordinarie - ore_contratto, 1) if ore_contratto > 0 else 0.0
        scostamento_proiezione = round(proiezione_fine_mese - ore_contratto, 1) if ore_contratto > 0 else 0.0

        tariffa_contratto = round(importo_contratto / ore_contratto, 2) if ore_contratto > 0 else 0.0
        ore_effettive_ref = ore_lavorate_ordinarie if ore_lavorate_ordinarie > 0 else ore_pianificate_ordinarie
        tariffa_reale = round(importo_contratto / ore_effettive_ref, 2) if (importo_contratto > 0 and ore_effettive_ref > 0) else tariffa_contratto

        stato_budget = 'REGOLARE'
        badge_budget = '🟢 In Budget'
        messaggio_ia = "Andamento ore allineato al contratto."

        if ore_contratto > 0:
            perc_usata = round((ore_lavorate_ordinarie / ore_contratto) * 100, 1)
            perc_proiettata = round((proiezione_fine_mese / ore_contratto) * 100, 1)
            if ore_lavorate_ordinarie > ore_contratto * 1.10 and (ore_lavorate_ordinarie - ore_contratto) >= 2.0:
                stato_budget = 'SFORAMENTO'
                badge_budget = '🔴 Sforamento Ore'
                messaggio_ia = (
                    f"Sforamento di +{scostamento_contratto}h rispetto alle {ore_contratto:g}h contrattuali "
                    f"(tariffa reale scesa a {tariffa_reale:.2f} €/h)."
                )
            elif proiezione_fine_mese > ore_contratto * 1.15 and (proiezione_fine_mese - ore_contratto) >= 3.0:
                stato_budget = 'RISCHIO_SFORAMENTO'
                badge_budget = '🟠 Rischio Sforamento a Fine Mese'
                messaggio_ia = (
                    f"Al ritmo attuale la proiezione a fine mese è di {proiezione_fine_mese}h "
                    f"(+{scostamento_proiezione}h rispetto al contratto di {ore_contratto:g}h)."
                )
            elif fine_mese <= today and ore_lavorate_ordinarie < ore_contratto * 0.75 and (ore_contratto - ore_lavorate_ordinarie) >= 4.0:
                stato_budget = 'SOTTOUTILIZZO'
                badge_budget = '🔵 Sotto Monte Ore'
                messaggio_ia = (
                    f"Erogate {ore_lavorate_ordinarie:g}h su {ore_contratto:g}h previste ({perc_usata}%): "
                    f"verifica eventuali turni non compilati dai dipendenti."
                )
        else:
            perc_usata = 0.0
            perc_proiettata = 0.0

        if ore_contratto > 0 or ore_lavorate_ordinarie > 0 or ore_pianificate_ordinarie > 0:
            report_clienti.append({
                'cliente': cliente,
                'cliente_nome': cliente.ragione_sociale,
                'ore_contratto': round(ore_contratto, 1),
                'importo_contratto': round(importo_contratto, 2),
                'ore_pianificate': round(ore_pianificate_ordinarie, 1),
                'ore_lavorate': round(ore_lavorate_ordinarie, 1),
                'ore_lavorate_ad_oggi': round(ore_lavorate_ordinarie, 1),
                'ore_straordinarie': round(ore_lavorate_straordinarie, 1),
                'proiezione_fine_mese': proiezione_fine_mese,
                'ore_proiettate_fine_mese': proiezione_fine_mese,
                'scostamento_contratto': scostamento_contratto,
                'scostamento_proiettato': scostamento_proiezione,
                'perc_usata': perc_usata,
                'percentuale_attuale': perc_usata,
                'percentuale_proiettata': perc_proiettata,
                'tariffa_contratto': tariffa_contratto,
                'tariffa_reale': tariffa_reale,
                'tariffa_effettiva_proiettata': tariffa_reale,
                'stato_budget': stato_budget,
                'badge_budget': badge_budget,
                'messaggio_ia': messaggio_ia,
            })

    ordine_stato = {'SFORAMENTO': 0, 'RISCHIO_SFORAMENTO': 1, 'SOTTOUTILIZZO': 2, 'REGOLARE': 3}
    report_clienti.sort(key=lambda x: (ordine_stato.get(x['stato_budget'], 9), -abs(x['scostamento_contratto'])))

    num_sforamento = sum(1 for c in report_clienti if c['stato_budget'] in ('SFORAMENTO', 'RISCHIO_SFORAMENTO'))
    return {
        'mese': mese,
        'anno': anno,
        'clienti': report_clienti,
        'num_sforamento': num_sforamento,
        'sforamenti_count': num_sforamento,
        'num_sottoutilizzo': sum(1 for c in report_clienti if c['stato_budget'] == 'SOTTOUTILIZZO'),
        'lavori_extra_rilevati': lavori_extra_rilevati,
        'lavori_extra': lavori_extra_rilevati,
    }


# ==============================================================================
# BRIEFING GIORNALIERO / SETTIMANALE IA PER TITOLARE E AMMINISTRAZIONE
# ==============================================================================

def genera_briefing_mattutino(invia_telegram=False, data_riferimento=None, conformita=None, budget=None, mezzi_list=None):
    """
    Compone il Briefing Direzionale IA giornaliero/settimanale per Titolari e Responsabili Area:
    - Turni di oggi e richieste di sostituzione aperte/in attesa
    - Avanzamento delle Procedure Operative aperte (es. Disdetta contratto: punti fatti e punti mancanti)
    - Assenze in attesa di avvallo amministrazione
    - Segnalazioni critiche aperte (con Triage IA)
    - Allarmi di conformità (Mezzi, Permessi Città Alta, Visite Mediche, Corsi)
    - Cantieri in sforamento budget mensile
    Se invia_telegram=True, invia il riepilogo su Telegram ai Titolari attivi.
    """
    from .models import (
        AssegnazioneTurno, RichiestaSostituzione, Assenza, Segnalazione, Mezzo, ProceduraAvviata
    )
    from .services import notifica_titolari

    today = data_riferimento or timezone.now().date()
    turni_oggi_count = AssegnazioneTurno.objects.filter(turno__data=today).count()
    sost_in_stallo = list(
        RichiestaSostituzione.objects.filter(
            stato__in=['APERTA', 'APPROVATA_RA', 'INVIATA'],
            assegnazione_originale__turno__data__gte=today,
        ).select_related('dipendente_assente', 'assegnazione_originale__cliente', 'assegnazione_originale__turno')
    )

    assenze_da_avvallare = list(
        Assenza.objects.filter(
            stato_approvazione='IN_ATTESA'
        ).select_related('dipendente')
    )

    segnalazioni_aperte = list(
        Segnalazione.objects.filter(risolto=False).select_related('dipendente').order_by('-data_inserimento')[:10]
    )

    procedure_aperte_qs = list(
        ProceduraAvviata.objects.filter(stato='IN_CORSO')
        .select_related('modello', 'cliente', 'dipendente')
        .prefetch_related('passaggi')
        .order_by('data_scadenza', '-data_avvio', '-id')
    )

    if conformita is None:
        conformita = verifica_conformita_turni(data_inizio=today, data_fine=today + timedelta(days=7))
    if budget is None:
        budget = analizza_marginalita_e_budget_clienti(mese=today.month, anno=today.year)

    lines = [
        f"🤖 <b>BRIEFING DIREZIONALE IA — {today.strftime('%d/%m/%Y')}</b>",
        "",
        f"📅 <b>Operatività Oggi:</b> {turni_oggi_count} turni in programma",
    ]

    if sost_in_stallo:
        lines.append(f"🚨 <b>Sostituzioni da coprire ({len(sost_in_stallo)}):</b>")
        for s in sost_in_stallo[:5]:
            d_str = s.assegnazione_originale.turno.data.strftime('%d/%m')
            lines.append(f"  • {d_str} — {s.assegnazione_originale.cliente.ragione_sociale} (Assente: {s.dipendente_assente})")
    else:
        lines.append("✅ <b>Sostituzioni:</b> Nessun turno scoperto")

    # SEZIONE AVANZAMENTO PROCEDURE OPERATIVE APERTE
    procedure_riepilogo = []
    if procedure_aperte_qs:
        lines.append(f"\n📋 <b>Procedure Operative in Corso ({len(procedure_aperte_qs)}):</b>")
        for proc in procedure_aperte_qs[:8]:
            passaggi = list(proc.passaggi.all().order_by('ordine', 'id'))
            tot_p = len(passaggi)
            fatti_p = [p for p in passaggi if p.completato]
            mancanti_p = [p for p in passaggi if not p.completato]
            comp_p = len(fatti_p)
            perc_p = int(round((comp_p / tot_p) * 100)) if tot_p > 0 else 0

            filled_blocks = int(round((perc_p / 100) * 6))
            bar_str = "🟩" * filled_blocks + "⬜" * (6 - filled_blocks)

            meta_extra = []
            if proc.cliente and proc.cliente.ragione_sociale.lower() not in (proc.titolo or '').lower():
                meta_extra.append(f"Cliente: {proc.cliente.ragione_sociale}")
            if proc.dipendente:
                meta_extra.append(f"Incaricato: {proc.dipendente.cognome} {proc.dipendente.nome}")
            if proc.data_scadenza:
                scad_prefix = "⚠️ Scad." if proc.data_scadenza <= today else "Scad."
                meta_extra.append(f"{scad_prefix} {proc.data_scadenza.strftime('%d/%m/%Y')}")
            meta_str = f" ({' | '.join(meta_extra)})" if meta_extra else ""

            lines.append(
                f"  • <b>{proc.titolo}</b>{meta_str}\n"
                f"    {bar_str} <b>{comp_p}/{tot_p} punti ({perc_p}%)</b>"
            )
            if fatti_p:
                fatti_str = ", ".join(f"{p.ordine}) {p.titolo}" for p in fatti_p)
                lines.append(f"    ✅ Completati: {fatti_str}")
            if mancanti_p:
                prossimo = mancanti_p[0]
                altri_mancanti = ", ".join(f"{p.ordine}) {p.titolo}" for p in mancanti_p[1:4])
                if altri_mancanti:
                    lines.append(f"    👉 Prossimo: <b>{prossimo.ordine}) {prossimo.titolo}</b> (poi: {altri_mancanti})")
                else:
                    lines.append(f"    👉 Da completare: <b>{prossimo.ordine}) {prossimo.titolo}</b>")

            procedure_riepilogo.append({
                'id': proc.id,
                'titolo': proc.titolo,
                'cliente': proc.cliente.ragione_sociale if proc.cliente else '',
                'dipendente': f"{proc.dipendente.cognome} {proc.dipendente.nome}" if proc.dipendente else '',
                'completati': comp_p,
                'totale': tot_p,
                'percentuale': perc_p,
                'prossimo_passo': f"{mancanti_p[0].ordine}) {mancanti_p[0].titolo}" if mancanti_p else 'Tutti i punti completati',
            })
    else:
        lines.append("\n📋 <b>Procedure Operative:</b> Nessuna procedura aperta in corso")

    if assenze_da_avvallare:
        lines.append(f"\n⏳ <b>Assenze in attesa di avvallo ({len(assenze_da_avvallare)}):</b>")
        for ass in assenze_da_avvallare[:5]:
            lines.append(f"  • {ass.dipendente} ({ass.tipo}: {ass.data_inizio.strftime('%d/%m')})")

    if conformita['num_alert'] > 0:
        lines.append(f"\n🛡️ <b>Alert Conformità & Scadenze prossimi 7gg ({conformita['num_alert']}):</b>")
        for al in conformita['alerts'][:5]:
            lines.append(f"  • {al['badge']}: {al['risorsa']} su {al['cliente']} ({al['data'].strftime('%d/%m')})")

    if budget['num_sforamento'] > 0:
        lines.append(f"\n💰 <b>Cantieri in Sforamento/Rischio Ore ({budget['num_sforamento']}):</b>")
        for c in budget['clienti'][:4]:
            if c['stato_budget'] in ('SFORAMENTO', 'RISCHIO_SFORAMENTO'):
                lines.append(f"  • {c['cliente'].ragione_sociale}: {c['ore_lavorate']}h lav. / {c['ore_contratto']}h contr. (Proiez: {c['proiezione_fine_mese']}h)")

    if segnalazioni_aperte:
        elenco_mezzi = mezzi_list if mezzi_list is not None else list(Mezzo.objects.all())
        lines.append(f"\n🔧 <b>Segnalazioni aperte ({len(segnalazioni_aperte)}):</b>")
        for seg in segnalazioni_aperte[:4]:
            tr = classifica_segnalazione(seg.testo, seg.dipendente, mezzi_list=elenco_mezzi)
            lines.append(f"  • [{tr['urgenza']}] {seg.dipendente}: {seg.testo[:60]}")

    testo_html = "\n".join(lines)
    testo_plain = re.sub(r'</?b>', '', testo_html)

    if invia_telegram:
        notifica_titolari(testo_html, solo_attivi=True)

    return {
        'data': today,
        'testo_telegram_html': testo_html,
        'testo_telegram': testo_plain,
        'turni_oggi_count': turni_oggi_count,
        'sostituzioni_stallo_count': len(sost_in_stallo),
        'procedure_aperte_count': len(procedure_aperte_qs),
        'procedure_aperte': procedure_riepilogo,
        'assenze_da_avvallare_count': len(assenze_da_avvallare),
        'alert_conformita_count': conformita['num_alert'],
        'cantieri_sforamento_count': budget['num_sforamento'],
        'lavori_extra_count': len(budget['lavori_extra_rilevati']),
    }
