"""
Servizio centralizzato (Single Source of Truth) per l'elaborazione di:
- Cedolini Paghe (Report Web, PDF e CSV)
- Verifica Ore Mensili (Dashboard e PDF)
- Analisi Economica Contratti e Contratti Sotto Soglia (Dashboard e PDF)
- Riconciliazione Ore Clienti
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone

from .models import Dipendente, Cliente, TimeTracking, Assenza, ModificaCedolino, to_decimal


MESI_NOMI = {
    1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
    5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
    9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
}


def calcola_ore_lavorate_record(tt):
    """
    Restituisce le ore lavorate per un record TimeTracking:
    1) Usa `ore_dichiarate` se valorizzato e > 0 (modalità principale Kandor).
    2) Usa `(check_out - check_in)` in ore come fallback se presenti i timestamp.
    """
    if tt.ore_dichiarate is not None and float(tt.ore_dichiarate) > 0:
        return float(tt.ore_dichiarate)
    if tt.check_in and tt.check_out:
        delta = (tt.check_out - tt.check_in).total_seconds() / 3600.0
        return max(0.0, delta)
    return 0.0


def parse_periodo_paghe(str_inizio='', str_fine=''):
    """Risolve data_inizio e data_fine con fallback al primo/ultimo giorno del mese corrente."""
    now = timezone.now().date()
    try:
        data_inizio = date.fromisoformat(str_inizio) if str_inizio else now.replace(day=1)
    except Exception:
        data_inizio = now.replace(day=1)

    try:
        if str_fine:
            data_fine = date.fromisoformat(str_fine)
        else:
            last_day = calendar.monthrange(now.year, now.month)[1]
            data_fine = now.replace(day=last_day)
    except Exception:
        last_day = calendar.monthrange(now.year, now.month)[1]
        data_fine = now.replace(day=last_day)

    return data_inizio, data_fine


def calcola_dataset_paghe(str_inizio='', str_fine='', dipendente_id='', build_calendar=True, solo_con_ore=False, stato_validazione=''):
    """
    Unica fonte di verità per l'elaborazione dei cedolini paghe (usata da HTML, PDF e CSV).
    Restituisce un dizionario completo con:
    - data_inizio, data_fine
    - report_list (lista ordinata per cognome e nome dei dipendenti con tutti i dati e rettifiche applicate)
    - totale_generale (totali aggregati)
    - all_dipendenti (QuerySet di tutti i dipendenti selezionabili nel filtro)
    - dipendente_id_int (int o '')
    - ha_rettifiche (bool)
    - solo_con_ore (bool)
    - stato_validazione (str: '' | 'non_validate' | 'validate')
    """
    data_inizio, data_fine = parse_periodo_paghe(str_inizio, str_fine)

    dip_ids_con_storico = (
        set(TimeTracking.objects.filter(
            assegnazione__turno__data__gte=data_inizio,
            assegnazione__turno__data__lte=data_fine,
            ore_dichiarate__gt=0,
        ).values_list('dipendente_id', flat=True))
        | set(Assenza.objects.filter(
            Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio)
        ).exclude(stato_approvazione='RIFIUTATA').values_list('dipendente_id', flat=True))
        | set(ModificaCedolino.objects.filter(
            data_inizio=data_inizio,
            data_fine=data_fine,
        ).values_list('dipendente_id', flat=True))
    )

    dip_qs = Dipendente.objects.filter(
        Q(stato='ATTIVO')
        | (Q(data_licenziamento__gte=data_inizio) & (Q(data_assunzione__isnull=True) | Q(data_assunzione__lte=data_fine)))
        | Q(pk__in=dip_ids_con_storico)
    ).distinct()

    all_dipendenti = dip_qs.order_by('cognome', 'nome')
    dip_id_str = str(dipendente_id or '').strip()
    if dip_id_str.isdigit():
        dip_qs = dip_qs.filter(pk=int(dip_id_str))

    dipendenti_map = {d.pk: d for d in dip_qs.order_by('cognome', 'nome')}

    tt_qs = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=data_inizio,
        assegnazione__turno__data__lte=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    ).select_related('dipendente', 'assegnazione__cliente', 'assegnazione__turno__squadra')

    assenze_qs = Assenza.objects.filter(
        Q(data_inizio__lte=data_fine) & Q(data_fine__gte=data_inizio),
        dipendente_id__in=dipendenti_map.keys()
    ).exclude(stato_approvazione='RIFIUTATA').select_related('dipendente')

    modifiche_qs = ModificaCedolino.objects.filter(
        data_inizio=data_inizio,
        data_fine=data_fine,
        dipendente_id__in=dipendenti_map.keys()
    )
    modifiche_map = {m.dipendente_id: m for m in modifiche_qs}

    report_data = {}
    for d_id, dip in dipendenti_map.items():
        report_data[d_id] = {
            'dip_id': d_id,
            'dipendente': dip,
            'cognome': dip.cognome,
            'nome': dip.nome,
            'cognome_nome': f"{dip.cognome} {dip.nome}",
            'codice_fiscale': dip.codice_fiscale or '---',
            'cf_raw': dip.codice_fiscale or '',
            'ruolo': ('Part-Time' if getattr(dip, 'is_part_time', False) else 'Full-Time'),
            'ore_lavorate': 0.0,
            'ore_validate': 0.0,
            'giorni_lavorati_set': set(),
            'clienti_dict': {},
            'assenze_dict': {
                'MALATTIA': 0,
                'FERIE': 0,
                'PERMESSO': 0,
                '104': 0,
                'INFORTUNIO': 0,
                'ALTRO': 0,
            },
            'giorni_assenza_totali': 0,
            'ore_permesso_totali': 0.0,
            'dettaglio_assenze': [],
            'ore_per_giorno': {},
            'ore_validate_per_giorno': {},
            'assenze_per_giorno': {},
            'note_per_giorno': {},
            'note_dettaglio_per_giorno': {},
        }

    # Processa TimeTracking
    for tt in tt_qs:
        d_id = tt.dipendente_id
        if d_id not in report_data:
            continue

        ore = calcola_ore_lavorate_record(tt)
        data_turno = tt.assegnazione.turno.data
        cliente = tt.assegnazione.cliente
        cl_nome = cliente.ragione_sociale if cliente else 'Senza Cliente'

        nota_tt = (tt.note or '').strip()
        if nota_tt:
            note_day_list = report_data[d_id]['note_per_giorno'].setdefault(data_turno, [])
            if nota_tt not in note_day_list:
                note_day_list.append(nota_tt)
            det_str = f"{cl_nome}: {nota_tt}" if cl_nome and cl_nome != 'Senza Cliente' else nota_tt
            det_day_list = report_data[d_id]['note_dettaglio_per_giorno'].setdefault(data_turno, [])
            if det_str not in det_day_list:
                det_day_list.append(det_str)

        report_data[d_id]['ore_lavorate'] += ore
        if tt.is_validated:
            report_data[d_id]['ore_validate'] += ore
            report_data[d_id]['ore_validate_per_giorno'][data_turno] = report_data[d_id]['ore_validate_per_giorno'].get(data_turno, 0.0) + ore

        if ore > 0:
            report_data[d_id]['giorni_lavorati_set'].add(data_turno)
            report_data[d_id]['clienti_dict'][cl_nome] = report_data[d_id]['clienti_dict'].get(cl_nome, 0.0) + ore
            report_data[d_id]['ore_per_giorno'][data_turno] = report_data[d_id]['ore_per_giorno'].get(data_turno, 0.0) + ore

    # Processa Assenze
    for assenza in assenze_qs:
        d_id = assenza.dipendente_id
        if d_id not in report_data:
            continue

        inizio_eff = max(assenza.data_inizio, data_inizio)
        fine_eff = min(assenza.data_fine, data_fine)

        curr_d = inizio_eff
        while curr_d <= fine_eff:
            report_data[d_id]['assenze_per_giorno'].setdefault(curr_d, []).append(assenza.tipo)
            curr_d += timedelta(days=1)

        giorni = (fine_eff - inizio_eff).days + 1
        tipo = assenza.tipo if assenza.tipo in report_data[d_id]['assenze_dict'] else 'ALTRO'
        report_data[d_id]['assenze_dict'][tipo] += giorni
        report_data[d_id]['giorni_assenza_totali'] += giorni

        if assenza.tipo == 'PERMESSO' and assenza.ore_permesso:
            report_data[d_id]['ore_permesso_totali'] += float(assenza.ore_permesso)

        report_data[d_id]['dettaglio_assenze'].append({
            'tipo': assenza.tipo,
            'inizio': assenza.data_inizio.strftime('%d/%m/%Y'),
            'fine': assenza.data_fine.strftime('%d/%m/%Y'),
            'orario': assenza.get_orario_display(),
            'ore': assenza.ore_permesso or 0.0,
            'giorni': giorni,
            'note': (assenza.note or '') + (f" [{assenza.get_orario_display()}]" if assenza.ora_inizio else ""),
        })

    report_list = []
    ha_rettifiche = False

    for d_id, item in report_data.items():
        giorni_orig = len(item['giorni_lavorati_set'])
        ore_lav_orig = round(item['ore_lavorate'], 2)
        ore_val_orig = round(item['ore_validate'], 2)

        item['giorni_lavorati_orig'] = giorni_orig
        item['ore_lavorate_orig'] = ore_lav_orig
        item['ore_validate_orig'] = ore_val_orig
        item['ferie_orig'] = item['assenze_dict']['FERIE']
        item['permessi_orig'] = item['assenze_dict']['PERMESSO']
        item['malattia_orig'] = item['assenze_dict']['MALATTIA']
        item['l104_orig'] = item['assenze_dict']['104']

        modifica = modifiche_map.get(d_id)
        if modifica:
            ha_rettifiche = True
            item['is_rettificato'] = True
            item['modifica_note'] = modifica.note or ''
            item['modifica_id'] = modifica.pk
            item['giorni_lavorati_override'] = modifica.giorni_lavorati_override
            item['ore_lavorate_override'] = float(to_decimal(modifica.ore_lavorate_override)) if modifica.ore_lavorate_override is not None else None
            item['ore_validate_override'] = float(to_decimal(modifica.ore_validate_override)) if modifica.ore_validate_override is not None else None
            item['giorni_ferie_override'] = modifica.giorni_ferie_override
            item['giorni_permesso_override'] = modifica.giorni_permesso_override
            item['giorni_malattia_override'] = modifica.giorni_malattia_override
            item['giorni_104_override'] = modifica.giorni_104_override

            item['giorni_lavorati'] = modifica.giorni_lavorati_override if modifica.giorni_lavorati_override is not None else giorni_orig
            item['ore_lavorate'] = float(to_decimal(modifica.ore_lavorate_override)) if modifica.ore_lavorate_override is not None else ore_lav_orig
            item['ore_validate'] = float(to_decimal(modifica.ore_validate_override)) if modifica.ore_validate_override is not None else ore_val_orig

            if modifica.giorni_ferie_override is not None:
                item['assenze_dict']['FERIE'] = modifica.giorni_ferie_override
            if modifica.giorni_permesso_override is not None:
                item['assenze_dict']['PERMESSO'] = modifica.giorni_permesso_override
            if modifica.giorni_malattia_override is not None:
                item['assenze_dict']['MALATTIA'] = modifica.giorni_malattia_override
            if modifica.giorni_104_override is not None:
                item['assenze_dict']['104'] = modifica.giorni_104_override
        else:
            item['is_rettificato'] = False
            item['modifica_note'] = ''
            item['modifica_id'] = None
            item['giorni_lavorati_override'] = None
            item['ore_lavorate_override'] = None
            item['ore_validate_override'] = None
            item['giorni_ferie_override'] = None
            item['giorni_permesso_override'] = None
            item['giorni_malattia_override'] = None
            item['giorni_104_override'] = None
            item['giorni_lavorati'] = giorni_orig
            item['ore_lavorate'] = ore_lav_orig
            item['ore_validate'] = ore_val_orig

        item['ore_non_validate'] = max(0.0, round(item['ore_lavorate'] - item['ore_validate'], 2))
        item['is_completamente_validato'] = bool(item['ore_lavorate'] > 0 and item['ore_non_validate'] <= 0.0)
        telegram_cid = str(getattr(item['dipendente'], 'telegram_chat_id', '') or '').strip()
        item['ha_telegram'] = bool(telegram_cid)
        item['telegram_chat_id'] = telegram_cid
        item['altri_e_104'] = (
            item['assenze_dict']['104']
            + item['assenze_dict']['INFORTUNIO']
            + item['assenze_dict']['ALTRO']
        )

        clienti_raw = ", ".join([f"{n} ({round(o, 1)}h)" for n, o in sorted(item['clienti_dict'].items())])
        item['clienti_raw'] = clienti_raw
        item['clienti_str'] = clienti_raw or "Nessun cantiere"

        if build_calendar:
            calendario_weeks = []
            curr_d = data_inizio
            row = [{'date': None, 'day': '', 'ore': None, 'assenze': [], 'note': '', 'note_dettaglio': ''} for _ in range(7)]
            while curr_d <= data_fine:
                wd = curr_d.weekday()
                ore_g = item['ore_per_giorno'].get(curr_d, 0.0)
                ore_val_g = item['ore_validate_per_giorno'].get(curr_d, 0.0)
                assenze_g = item['assenze_per_giorno'].get(curr_d, [])
                note_list = item['note_per_giorno'].get(curr_d, [])
                note_det_list = item['note_dettaglio_per_giorno'].get(curr_d, [])
                row[wd] = {
                    'date': curr_d.isoformat(),
                    'day': curr_d.day,
                    'ore': round(ore_g, 1) if ore_g > 0 else None,
                    'ore_val': round(ore_val_g, 1) if ore_val_g > 0 else None,
                    'is_validated': (ore_g > 0 and ore_val_g >= ore_g),
                    'has_pending': (ore_g > 0 and ore_val_g < ore_g),
                    'assenze': assenze_g,
                    'note': " | ".join(note_list),
                    'note_dettaglio': " • ".join(note_det_list),
                }
                if wd == 6 or curr_d == data_fine:
                    calendario_weeks.append(row)
                    row = [{'date': None, 'day': '', 'ore': None, 'assenze': [], 'note': '', 'note_dettaglio': ''} for _ in range(7)]
                curr_d += timedelta(days=1)
            item['calendario_weeks'] = calendario_weeks
            item['note_calendario_count'] = sum(len(v) for v in item['note_per_giorno'].values())

        report_list.append(item)

    report_list.sort(key=lambda x: (x['cognome'], x['nome']))

    # Filtri aggiuntivi per pulizia elenco e stato validazione
    solo_con_ore_bool = (solo_con_ore is True or str(solo_con_ore).strip() in ('1', 'true', 'True'))
    if solo_con_ore_bool:
        report_list = [x for x in report_list if x['ore_lavorate'] > 0 or x['giorni_lavorati'] > 0]

    stato_val_str = str(stato_validazione or '').strip().lower()
    if stato_val_str in ('non_validate', 'da_validare', 'pending'):
        report_list = [x for x in report_list if x['ore_non_validate'] > 0]
    elif stato_val_str in ('validate', 'completate', 'ok'):
        report_list = [x for x in report_list if x['is_completamente_validato']]

    totale_generale = {
        'dipendenti_count': len(report_list),
        'giorni_lavorati_totali': sum(x['giorni_lavorati'] for x in report_list),
        'ore_lavorate_totali': round(sum(x['ore_lavorate'] for x in report_list), 2),
        'ore_validate_totali': round(sum(x['ore_validate'] for x in report_list), 2),
        'ore_non_validate_totali': round(sum(x['ore_non_validate'] for x in report_list), 2),
        'giorni_assenza_totali': sum(x['giorni_assenza_totali'] for x in report_list),
        'ferie_totali': sum(x['assenze_dict']['FERIE'] for x in report_list),
        'permessi_totali': sum(x['assenze_dict']['PERMESSO'] for x in report_list),
        'malattia_totale': sum(x['assenze_dict']['MALATTIA'] for x in report_list),
        'infortunio_totale': sum(x['assenze_dict']['INFORTUNIO'] for x in report_list),
        'l104_totale': sum(x['assenze_dict']['104'] for x in report_list),
        'altri_totale': sum(x['assenze_dict']['ALTRO'] for x in report_list),
        'altri_e_104_totali': sum(x['altri_e_104'] for x in report_list),
        'pronti_invio_count': sum(1 for x in report_list if x['is_completamente_validato'] and x['ha_telegram']),
        'da_validare_count': sum(1 for x in report_list if x['ore_non_validate'] > 0),
        'senza_telegram_count': sum(1 for x in report_list if not x['ha_telegram'] and x['ore_lavorate'] > 0),
    }

    return {
        'data_inizio': data_inizio,
        'data_fine': data_fine,
        'report_list': report_list,
        'totale_generale': totale_generale,
        'all_dipendenti': all_dipendenti,
        'dipendente_id_int': int(dip_id_str) if dip_id_str.isdigit() else '',
        'ha_rettifiche': ha_rettifiche,
        'solo_con_ore': solo_con_ore_bool,
        'stato_validazione': stato_val_str,
    }


def calcola_verifica_ore_mensile(mese=None, anno=None):
    """
    Calcola i dati mensili per la dashboard e il PDF di Verifica Ore:
    - Riepilogo per Cliente (raggruppato per Partita IVA)
    - Riepilogo per Squadra e Dipendente
    - Riepilogo Assenze del mese
    """
    now = timezone.now()
    mese = int(mese) if mese else now.month
    anno = int(anno) if anno else now.year

    primo_giorno = date(anno, mese, 1)
    ultimo_giorno_num = calendar.monthrange(anno, mese)[1]
    ultimo_giorno = date(anno, mese, ultimo_giorno_num)
    mese_nome = MESI_NOMI.get(mese, '')

    tt_mese = TimeTracking.objects.filter(
        assegnazione__turno__data__gte=primo_giorno,
        assegnazione__turno__data__lte=ultimo_giorno
    ).select_related('assegnazione__cliente', 'dipendente', 'assegnazione__turno__squadra')

    # Pre-carica tutti i clienti con lo storico contrattuale in 2 query complessive (zero N+1)
    tutti_clienti = list(Cliente.objects.prefetch_related('storico_contratti'))
    clienti_by_pk = {c.pk: c for c in tutti_clienti}

    # === 1. SEZIONE PER CLIENTE (Raggruppato per Partita IVA) ===
    clienti_data = {}
    for tt in tt_mese:
        raw_cl = tt.assegnazione.cliente
        if not raw_cl:
            continue
        cliente = clienti_by_pk.get(raw_cl.pk, raw_cl)
        piva = (cliente.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{cliente.pk}"

        if key not in clienti_data:
            clienti_data[key] = {
                'key': key,
                'piva': piva,
                'clienti': set(),
                'ore_lavorate': 0.0,
                'ore_validate': 0.0,
            }
        clienti_data[key]['clienti'].add(cliente)

        ore = calcola_ore_lavorate_record(tt)
        clienti_data[key]['ore_lavorate'] += ore
        if tt.is_validated:
            clienti_data[key]['ore_validate'] += ore

    for cl in tutti_clienti:
        ore_storiche, _ = cl.get_condizioni_contrattuali_mese(anno, mese)
        if ore_storiche <= Decimal('0.00'):
            continue
        piva = (cl.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{cl.pk}"

        if key not in clienti_data:
            clienti_data[key] = {
                'key': key,
                'piva': piva,
                'clienti': set(),
                'ore_lavorate': 0.0,
                'ore_validate': 0.0,
            }
        clienti_data[key]['clienti'].add(cl)

    for cd in clienti_data.values():
        clienti_list_sorted = sorted(list(cd['clienti']), key=lambda x: x.ragione_sociale)
        cd['cliente'] = clienti_list_sorted[0]
        ore_contratto_dec = Decimal('0.00')
        imp_contratto_dec = Decimal('0.00')
        for c in clienti_list_sorted:
            ore_c, imp_c = c.get_condizioni_contrattuali_mese(anno, mese)
            ore_contratto_dec += ore_c
            imp_contratto_dec += imp_c
        cd['ore_contratto'] = float(ore_contratto_dec)
        cd['importo_contratto'] = float(imp_contratto_dec)
        cd['importo_orario'] = (
            float(to_decimal(imp_contratto_dec / ore_contratto_dec, places=2))
            if ore_contratto_dec > Decimal('0.00')
            else 0
        )

        piva_str = cd['piva']
        if len(clienti_list_sorted) > 1 and piva_str:
            nome_base = clienti_list_sorted[0].ragione_sociale.split('-')[0].strip()
            cd['ragione_sociale'] = f"{nome_base} ({len(clienti_list_sorted)} Sedi - P.IVA {piva_str})"
        else:
            cd['ragione_sociale'] = clienti_list_sorted[0].ragione_sociale

        cd['ore_lavorate'] = round(cd['ore_lavorate'], 1)
        cd['ore_validate'] = round(cd['ore_validate'], 1)
        cd['diff'] = round(cd['ore_lavorate'] - cd['ore_contratto'], 1)
        cd['importo_calcolato'] = round(cd['ore_validate'] * cd['importo_orario'], 2) if cd['importo_orario'] else 0
        cd['ore_non_validate'] = round(cd['ore_lavorate'] - cd['ore_validate'], 1)

    clienti_list = sorted(clienti_data.values(), key=lambda x: x['ragione_sociale'])

    totale_clienti = {
        'ore_contratto': sum(c['ore_contratto'] for c in clienti_list),
        'ore_lavorate': sum(c['ore_lavorate'] for c in clienti_list),
        'ore_validate': sum(c['ore_validate'] for c in clienti_list),
        'importo_contratto': sum(c['importo_contratto'] for c in clienti_list),
        'importo_calcolato': sum(c['importo_calcolato'] for c in clienti_list),
    }
    totale_clienti['diff'] = round(totale_clienti['ore_lavorate'] - totale_clienti['ore_contratto'], 1)

    # === 2. SEZIONE PER SQUADRA / DIPENDENTE ===
    squadre_data = {}
    for tt in tt_mese:
        dip = tt.dipendente
        squadra = tt.assegnazione.turno.squadra
        cliente = tt.assegnazione.cliente
        ore = calcola_ore_lavorate_record(tt)
        if ore <= 0:
            continue

        sq_nome = squadra.nome if squadra else tt.assegnazione.turno.nome_squadra
        sq_id = squadra.pk if squadra else f"hist_{sq_nome}"

        if sq_id not in squadre_data:
            squadre_data[sq_id] = {
                'nome': sq_nome,
                'dipendenti': {},
                'ore_totali': 0.0,
            }

        dip_id = dip.pk
        if dip_id not in squadre_data[sq_id]['dipendenti']:
            squadre_data[sq_id]['dipendenti'][dip_id] = {
                'nome': str(dip),
                'ore_totali': 0.0,
                'clienti': {},
            }

        squadre_data[sq_id]['dipendenti'][dip_id]['ore_totali'] += ore
        squadre_data[sq_id]['ore_totali'] += ore

        cl_nome = cliente.ragione_sociale if cliente else 'N/D'
        squadre_data[sq_id]['dipendenti'][dip_id]['clienti'][cl_nome] = (
            squadre_data[sq_id]['dipendenti'][dip_id]['clienti'].get(cl_nome, 0.0) + ore
        )

    squadre_list = []
    for sq in sorted(squadre_data.values(), key=lambda x: x['nome']):
        dip_list = []
        for d in sorted(sq['dipendenti'].values(), key=lambda x: x['nome']):
            d['ore_totali'] = round(d['ore_totali'], 1)
            d['clienti_str'] = ', '.join(f"{n} ({round(o, 1)}h)" for n, o in sorted(d['clienti'].items()))
            dip_list.append(d)
        sq['dipendenti_list'] = dip_list
        sq['ore_totali'] = round(sq['ore_totali'], 1)
        squadre_list.append(sq)

    # === 3. SEZIONE ASSENZE DEL MESE ===
    assenze_mese = Assenza.objects.filter(
        Q(data_inizio__lte=ultimo_giorno) & Q(data_fine__gte=primo_giorno),
    ).exclude(stato_approvazione='RIFIUTATA').select_related('dipendente')

    assenze_per_dip = {}
    for assenza in assenze_mese:
        dip_id = assenza.dipendente.pk
        if dip_id not in assenze_per_dip:
            assenze_per_dip[dip_id] = {
                'dipendente': assenza.dipendente,
                'nome': f"{assenza.dipendente.cognome} {assenza.dipendente.nome}",
                'MALATTIA': 0, 'FERIE': 0, 'PERMESSO': 0, '104': 0, 'ALTRO': 0,
                'totale_giorni': 0,
                'dettagli': [],
                'dettagli_pdf': [],
            }

        inizio_eff = max(assenza.data_inizio, primo_giorno)
        fine_eff = min(assenza.data_fine, ultimo_giorno)
        giorni = (fine_eff - inizio_eff).days + 1

        tipo = assenza.tipo if assenza.tipo in assenze_per_dip[dip_id] else 'ALTRO'
        assenze_per_dip[dip_id][tipo] += giorni
        assenze_per_dip[dip_id]['totale_giorni'] += giorni
        assenze_per_dip[dip_id]['dettagli'].append({
            'tipo': assenza.tipo,
            'inizio': assenza.data_inizio.strftime('%d/%m'),
            'fine': assenza.data_fine.strftime('%d/%m'),
            'giorni': giorni,
            'note': assenza.note,
        })
        assenze_per_dip[dip_id]['dettagli_pdf'].append(
            f"{assenza.tipo}: {assenza.data_inizio.strftime('%d/%m')}-{assenza.data_fine.strftime('%d/%m')} ({giorni}gg)"
        )

    assenze_list = sorted(assenze_per_dip.values(), key=lambda x: x['nome'])

    totale_assenze = {
        'MALATTIA': sum(a['MALATTIA'] for a in assenze_list),
        'FERIE': sum(a['FERIE'] for a in assenze_list),
        'PERMESSO': sum(a['PERMESSO'] for a in assenze_list),
        '104': sum(a['104'] for a in assenze_list),
        'ALTRO': sum(a['ALTRO'] for a in assenze_list),
        'totale_giorni': sum(a['totale_giorni'] for a in assenze_list),
    }

    return {
        'mese': mese,
        'anno': anno,
        'mese_nome': mese_nome,
        'primo_giorno': primo_giorno,
        'ultimo_giorno': ultimo_giorno,
        'clienti_list': clienti_list,
        'totale_clienti': totale_clienti,
        'squadre_list': squadre_list,
        'assenze_list': assenze_list,
        'totale_assenze': totale_assenze,
    }


def calcola_analisi_contratti(mese=None, anno=None, soglia=15.0):
    """
    Calcola l'analisi economica dei contratti (raggruppati per Partita IVA)
    e identifica i contratti sotto soglia. Condivisa tra vista HTML e report PDF.
    Supporta sia le ore dichiarate sul turno sia i timestamp check_in/check_out.
    """
    today = timezone.now().date()
    mese = int(mese) if mese else today.month
    anno = int(anno) if anno else today.year
    soglia = float(soglia) if soglia is not None else 15.0

    clienti_qs = Cliente.objects.prefetch_related('storico_contratti').order_by('ragione_sociale')

    grouped_clienti = {}
    for c in clienti_qs:
        ore_c, _ = c.get_condizioni_contrattuali_mese(anno, mese)
        if ore_c <= Decimal('0.00'):
            continue
        piva = (c.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{c.pk}"
        if key not in grouped_clienti:
            grouped_clienti[key] = {'piva': piva, 'clienti': []}
        grouped_clienti[key]['clienti'].append(c)

    analisi = []
    sotto_soglia = []
    totale_fatturato = Decimal('0')
    somma_orari = []

    for key, grp in grouped_clienti.items():
        clienti_list = grp['clienti']
        ore_contratto_dec = Decimal('0.00')
        importo_dec = Decimal('0.00')
        for c in clienti_list:
            ore_c, imp_c = c.get_condizioni_contrattuali_mese(anno, mese)
            ore_contratto_dec += ore_c
            importo_dec += imp_c
        importo = float(importo_dec)
        ore_contratto = float(ore_contratto_dec)
        importo_orario = (
            float(to_decimal(importo_dec / ore_contratto_dec, places=2))
            if ore_contratto_dec > Decimal('0.00')
            else 0
        )

        piva_str = grp['piva']
        if len(clienti_list) > 1 and piva_str:
            nome_base = clienti_list[0].ragione_sociale.split('-')[0].strip()
            ragione_display = f"{nome_base} ({len(clienti_list)} Sedi - P.IVA {piva_str})"
        else:
            ragione_display = clienti_list[0].ragione_sociale

        tt_records = TimeTracking.objects.filter(
            assegnazione__cliente__in=clienti_list
        ).filter(
            Q(assegnazione__turno__data__year=anno, assegnazione__turno__data__month=mese)
            | Q(check_out__year=anno, check_out__month=mese)
        ).distinct()

        ore_lavorate = sum(calcola_ore_lavorate_record(tt) for tt in tt_records)
        ore_lavorate = round(ore_lavorate, 1)

        costo_effettivo = round(importo / ore_lavorate, 2) if ore_lavorate > 0 else None
        diff_ore = round(ore_lavorate - ore_contratto, 1)

        is_sotto_soglia = importo_orario < soglia and importo > 0
        costo_effettivo_alert = costo_effettivo is not None and costo_effettivo < soglia

        if diff_ore > 0:
            diff_ore_display = f'<span style="color: #e67e22; font-weight: 600;">+{diff_ore}h</span>'
        elif diff_ore < 0:
            diff_ore_display = f'<span style="color: #e74c3c; font-weight: 600;">{diff_ore}h</span>'
        else:
            diff_ore_display = '<span style="color: #27ae60;">0h</span>'

        if is_sotto_soglia:
            stato_display = '<span style="background: #e74c3c; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">SOTTO SOGLIA</span>'
        elif costo_effettivo_alert:
            stato_display = '<span style="background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">DA VERIFICARE</span>'
        else:
            stato_display = '<span style="background: #27ae60; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">OK</span>'

        costo_eff_display = f"&euro;{costo_effettivo}" if costo_effettivo else "&mdash;"

        row = {
            'cliente': ragione_display,
            'cliente_id': clienti_list[0].pk,
            'importo_num': importo,
            'ore_contratto_num': ore_contratto,
            'importo_orario_num': importo_orario,
            'ore_lavorate_num': ore_lavorate,
            'costo_effettivo_num': costo_effettivo,
            'importo_mensile': f"&euro;{importo:,.2f}",
            'ore_contratto': f"{ore_contratto}h",
            'importo_orario': f"&euro;{importo_orario:.2f}",
            'ore_lavorate': f"{ore_lavorate}h",
            'costo_effettivo_display': costo_eff_display,
            'diff_ore_display': diff_ore_display,
            'stato_display': stato_display,
            'sotto_soglia': is_sotto_soglia,
        }
        analisi.append(row)

        if is_sotto_soglia:
            sotto_soglia.append(row)

        totale_fatturato += Decimal(str(importo))
        if importo_orario > 0:
            somma_orari.append(importo_orario)

    media_oraria = round(sum(somma_orari) / len(somma_orari), 2) if somma_orari else 0

    return {
        'mese': mese,
        'anno': anno,
        'mese_nome': MESI_NOMI.get(mese, ''),
        'soglia': soglia,
        'analisi': analisi,
        'sotto_soglia': sotto_soglia,
        'totale_fatturato': totale_fatturato,
        'media_oraria': media_oraria,
    }


def genera_pdf_calendario_dipendente(item, data_inizio, data_fine):
    """
    Genera il prospetto analitico mensile e calendario presenze in formato PDF per il singolo dipendente.
    Include:
    - Intestazione ufficiale Kandor
    - Scheda riassuntiva lavoratore e KPI (ore lavorate, convalidate, assenze, cantieri)
    - Griglia calendario mensile dettagliata giorno per giorno
    - Firme di accettazione con timbro aziendale ufficiale Kandor
    Restituisce: bytes del PDF.
    """
    import io
    import os
    from xml.sax.saxutils import escape as xml_escape
    from django.conf import settings
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()

    title_main = ParagraphStyle(
        'DocTitleMain',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2,
    )
    sub_head = ParagraphStyle(
        'DocSubHead',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#475569'),
    )
    title_right = ParagraphStyle(
        'DocTitleRight',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=2,
    )
    sub_right = ParagraphStyle(
        'DocSubRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#64748B'),
        alignment=2,
    )
    card_label = ParagraphStyle(
        'CardLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#475569'),
    )
    card_val = ParagraphStyle(
        'CardVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A'),
    )
    card_val_bold = ParagraphStyle(
        'CardValBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A'),
    )
    day_num_style = ParagraphStyle(
        'DayNum',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=9,
        textColor=colors.HexColor('#64748B'),
        alignment=2,
    )
    cal_mid_style = ParagraphStyle(
        'CalMid',
        parent=styles['Normal'],
        fontSize=11,
        leading=13,
        alignment=1,
    )
    cal_note_style = ParagraphStyle(
        'CalNote',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#1E40AF'),
        alignment=1,
    )
    sign_label = ParagraphStyle(
        'SignLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A'),
    )
    sign_note = ParagraphStyle(
        'SignNote',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#64748B'),
    )

    story = []

    # 1. HEADER KANDOR & TITOLO DOCUMENTO
    header_left = [
        Paragraph("<b>KANDOR SOCIETÀ COOPERATIVA</b>", title_main),
        Paragraph("Impresa di Pulizie e Servizi Integrati • P.IVA 04182710162 • C.C.I.A.A. BG n°442382", sub_head),
        Paragraph("Via Martiri di Cefalonia 2, 24031 Almenno San Bartolomeo (BG) • Tel/Fax 035 643033", sub_head),
    ]
    header_right = [
        Paragraph("PROSPETTO ANALITICO PRESENZE", title_right),
        Paragraph(f"Periodo: <b>{data_inizio.strftime('%d/%m/%Y')} — {data_fine.strftime('%d/%m/%Y')}</b>", sub_right),
        Paragraph(f"Emesso il {timezone.now().strftime('%d/%m/%Y %H:%M')}", sub_right),
    ]
    header_table = Table([[header_left, header_right]], colWidths=[430, 330])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    # 2. SCHEDA DIPENDENTE & KPI
    nome_dip = item.get('cognome_nome', '')
    cf_dip = item.get('codice_fiscale', '---')
    ruolo_dip = item.get('ruolo', 'Dipendente')
    ore_lav = item.get('ore_lavorate', 0.0)
    ore_val = item.get('ore_validate', 0.0)
    ore_non_val = item.get('ore_non_validate', 0.0)
    gg_lav = item.get('giorni_lavorati', 0)
    ferie = item.get('assenze_dict', {}).get('FERIE', 0)
    perm = item.get('assenze_dict', {}).get('PERMESSO', 0)
    mal = item.get('assenze_dict', {}).get('MALATTIA', 0)
    altri_104 = item.get('altri_e_104', 0)
    cantieri_str = item.get('clienti_str', 'Nessun cantiere registrato')

    if ore_non_val <= 0 and ore_lav > 0:
        val_status_txt = f"<font color='#059669'><b>{ore_val} h</b> (Tutte Validate ✅)</font>"
    elif ore_non_val > 0:
        val_status_txt = f"<font color='#DC2626'><b>{ore_val} h</b> ({ore_non_val}h in attesa ⚠️)</font>"
    else:
        val_status_txt = "<b>0.0 h</b>"

    assenze_summary = []
    if ferie: assenze_summary.append(f"Ferie: {ferie}gg")
    if perm: assenze_summary.append(f"Permessi: {perm}gg")
    if mal: assenze_summary.append(f"Malattia: {mal}gg")
    if altri_104: assenze_summary.append(f"104/Altri: {altri_104}gg")
    assenze_txt = " • ".join(assenze_summary) if assenze_summary else "Nessuna assenza"

    kpi_data = [
        [
            Paragraph("Lavoratore:", card_label),
            Paragraph(f"<b>{xml_escape(nome_dip)}</b>", card_val_bold),
            Paragraph("Codice Fiscale:", card_label),
            Paragraph(f"<code>{xml_escape(cf_dip)}</code>", card_val),
            Paragraph("Inquadramento:", card_label),
            Paragraph(xml_escape(ruolo_dip), card_val),
        ],
        [
            Paragraph("Giorni Lavorati:", card_label),
            Paragraph(f"<b>{gg_lav} gg</b>", card_val),
            Paragraph("Ore Totali Lavorate:", card_label),
            Paragraph(f"<b>{ore_lav} h</b>", card_val_bold),
            Paragraph("Ore Convalidate:", card_label),
            Paragraph(val_status_txt, card_val),
        ],
        [
            Paragraph("Riepilogo Assenze:", card_label),
            Paragraph(xml_escape(assenze_txt), card_val),
            Paragraph("Cantieri & Clienti:", card_label),
            Paragraph(xml_escape(cantieri_str), card_val),
            Paragraph("", card_label),
            Paragraph("", card_val),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[90, 165, 95, 175, 85, 150])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('SPAN', (3, 2), (5, 2)),  # Cantieri allargati sulle ultime 3 colonne della riga 3
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 4 * mm))

    # 3. GRIGLIA CALENDARIO MENSILE (7 COLONNE: LUN-DOM)
    cal_style = TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('LEFTPADDING', (0, 1), (-1, -1), 3),
        ('RIGHTPADDING', (0, 1), (-1, -1), 3),
        ('TOPPADDING', (0, 1), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
    ])

    cal_data = [['LUNEDÌ', 'MARTEDÌ', 'MERCOLEDÌ', 'GIOVEDÌ', 'VENERDÌ', 'SABATO', 'DOMENICA']]
    empty_cell = [Spacer(1, 28)]
    row = [list(empty_cell) for _ in range(7)]

    curr_d = data_inizio
    while curr_d <= data_fine:
        wd = curr_d.weekday()
        flowables = [Paragraph(str(curr_d.day), day_num_style)]

        ore = item.get('ore_per_giorno', {}).get(curr_d, 0.0)
        ore_val_g = item.get('ore_validate_per_giorno', {}).get(curr_d, 0.0)
        assenze = item.get('assenze_per_giorno', {}).get(curr_d, [])
        note_giorno = item.get('note_per_giorno', {}).get(curr_d, [])

        mid_parts = []
        if ore > 0:
            if ore_val_g >= ore:
                mid_parts.append(f"<font color='#059669'><b>{round(ore, 1)} h</b></font>")
                mid_parts.append("<font size=6 color='#059669'>[Validato]</font>")
            else:
                mid_parts.append(f"<font color='#DC2626'><b>{round(ore, 1)} h</b></font>")
                mid_parts.append("<font size=6 color='#DC2626'>[In attesa]</font>")

        if assenze:
            mid_parts.append(f"<font size=7 color='#2563EB'><b>{'+'.join(assenze)}</b></font>")

        if mid_parts:
            flowables.append(Spacer(1, 1))
            flowables.append(Paragraph("<br/>".join(mid_parts), cal_mid_style))

        if note_giorno:
            clean_note = " • ".join(note_giorno)
            flowables.append(Spacer(1, 1))
            flowables.append(Paragraph(xml_escape(clean_note[:75]), cal_note_style))

        if not ore and not assenze and not note_giorno:
            flowables.append(Spacer(1, 18))

        row[wd] = flowables

        if wd == 6 or curr_d == data_fine:
            cal_data.append(row)
            row = [list(empty_cell) for _ in range(7)]

        curr_d += timedelta(days=1)

    col_w = 760.0 / 7.0  # ~108.57 pt ciascuna
    t_cal = Table(cal_data, colWidths=[col_w] * 7)
    t_cal.setStyle(cal_style)
    story.append(t_cal)
    story.append(Spacer(1, 5 * mm))

    # 4. SEZIONE FIRME E TIMBRO KANDOR
    timbro_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'core', 'img', 'timbro_kandor.jpg')
    timbro_elements = [
        Paragraph("Per <b>KANDOR Società Cooperativa</b>:", sign_label),
        Spacer(1, 1 * mm),
    ]
    if os.path.exists(timbro_path):
        try:
            # Immagine del timbro aziendale Kandor ufficiale
            timbro_elements.append(Image(timbro_path, width=140, height=48))
        except Exception:
            timbro_elements.append(Paragraph("<i>(Timbro e Firma Kandor)</i>", sign_note))
    else:
        timbro_elements.append(Spacer(1, 12 * mm))
        timbro_elements.append(Paragraph("________________________________________", sign_note))

    firma_dip_elements = [
        Paragraph("Firma del Lavoratore per presa visione e accettazione:", sign_label),
        Spacer(1, 8 * mm),
        Paragraph("____________________________________________________", sign_label),
        Spacer(1, 1 * mm),
        Paragraph(f"Firma per esteso: {xml_escape(nome_dip)}", sign_note),
    ]

    firme_table = Table([[timbro_elements, firma_dip_elements]], colWidths=[380, 380])
    firme_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))

    story.append(KeepTogether(firme_table))

    doc.build(story)
    return buffer.getvalue()


def invia_pdf_calendario_telegram(dipendente, data_inizio, data_fine, pdf_bytes, item=None):
    """
    Invia via Bot Telegram il PDF del calendario / prospetto analitico ore al dipendente.
    REQUISITO CRITICO:
    - Se ci sono ore non convalidate per il periodo (`ore_non_validate > 0`), l'invio è RIGOROSAMENTE BLOCCATO.
    - Se il dipendente non ha Telegram collegato, ritorna errore esplicito.
    - Registra il messaggio e l'allegato anche nella chat interna dell'App dipendente.
    """
    import os
    import requests
    from django.conf import settings
    from .models import MessaggioChat

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return {'ok': False, 'error': 'TELEGRAM_BOT_TOKEN non configurato sul server'}

    chat_id = str(getattr(dipendente, 'telegram_chat_id', '') or '').strip()
    if not chat_id:
        return {'ok': False, 'error': f"{dipendente.nome} {dipendente.cognome} non ha collegato il Bot Telegram (@kandor_gestionale_bot)"}

    # CONTROLLO BLOCCANTE ORE NON CONVALIDATE
    ore_non_val = item.get('ore_non_validate', 0.0) if item else 0.0
    if ore_non_val > 0.0:
        return {
            'ok': False,
            'error': f"Invio bloccato: sono presenti {ore_non_val} ore non convalidate nel periodo per {dipendente.nome} {dipendente.cognome}. Tutte le ore devono essere validate prima dell'invio!"
        }

    periodo_str = f"{data_inizio.strftime('%d/%m/%Y')} - {data_fine.strftime('%d/%m/%Y')}"
    mese_anno_tag = data_inizio.strftime('%m_%Y')
    cf_tag = dipendente.codice_fiscale or f"ID{dipendente.pk}"
    safe_filename = f"Prospetto_Ore_{mese_anno_tag}_{cf_tag}.pdf"

    ore_tot = item.get('ore_lavorate', 0.0) if item else 0.0
    gg_lav = item.get('giorni_lavorati', 0) if item else 0
    ferie = item.get('assenze_dict', {}).get('FERIE', 0) if item else 0
    perm = item.get('assenze_dict', {}).get('PERMESSO', 0) if item else 0
    mal = item.get('assenze_dict', {}).get('MALATTIA', 0) if item else 0

    caption = (
        f"📅 PROSPETTO ANALITICO ORE & CALENDARIO\n"
        f"Periodo: {periodo_str}\n\n"
        f"👤 Gentile {dipendente.nome} {dipendente.cognome},\n"
        f"in allegato trovi il documento PDF del tuo prospetto analitico con il calendario presenze e le ore validate.\n\n"
        f"⏱️ Ore Lavorate: {ore_tot}h (Tutte convalidate ✅)\n"
        f"🗓️ Giorni Lavorati: {gg_lav} gg\n"
    )
    if ferie or perm or mal:
        caption += f"🏖️ Assenze: {ferie}gg Ferie | {perm}gg Permessi | {mal}gg Malattia\n"
    caption += "\n📲 Puoi verificare le tue timbrature anche sull'App Kandor."

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            data={
                'chat_id': chat_id,
                'caption': caption,
            },
            files={
                'document': (safe_filename, pdf_bytes, 'application/pdf'),
            },
            timeout=30,
        )
        data_json = resp.json() if resp.status_code == 200 else {}
        if resp.status_code == 200 and data_json.get('ok'):
            # Registrazione opzionale nello storico chat WebApp Dipendente
            try:
                MessaggioChat.objects.create(
                    dipendente=dipendente,
                    testo=f"📅 Prospetto Ore & Calendario ({periodo_str}) — {ore_tot}h validate",
                    allegato_nome=safe_filename,
                    direzione='OUT',
                    letto=True,
                )
            except Exception:
                pass
            return {'ok': True, 'dipendente': f"{dipendente.cognome} {dipendente.nome}"}
        else:
            err_desc = data_json.get('description', f"HTTP {resp.status_code}")
            return {'ok': False, 'error': f"Errore Telegram: {err_desc}"}
    except Exception as e:
        return {'ok': False, 'error': f"Errore di connessione Telegram: {e}"}
