"""
Viste e API per le 5 Migliorie Enterprise di Kandor ERP:
1. Contabilità Industriale per Cantiere (Marginalità Reale MOL = Ricavi − Costo Orario − Prodotti − Mezzi)
2. Gestione Magazzino Prodotti, Attrezzature, Dotazioni Cantiere e Consegne (con richieste da App/Telegram)
3. Modulo Qualità, Ispezioni & SLA Cliente (Verbali di Sopralluogo 1-5 stelle, PDF cortesia e QR Code Geofence)
4. Modulo Preventivazione Rapida (CRM Commerciale) & Conversione "1-Click" in Cliente Attivo
5. Pre-Fatturazione Attiva e Riconciliazione Automatica dei Lavori Extra/Straordinari
"""

import calendar
import io
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import quote

from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import (
    AssegnazioneTurno,
    Cliente,
    ConsegnaRichiestaMateriale,
    Dipendente,
    DotazioneCantiere,
    IspezioneQualitaCantiere,
    Mezzo,
    ModelloProcedura,
    PreventivoCommerciale,
    ProceduraAvviata,
    ProdottoMagazzino,
    ProgrammazioneRicorrente,
    ProximityLog,
    RichiestaStraordinaria,
    Squadra,
    TimeTracking,
    Turno,
    VoceAmbientePreventivo,
    ensure_default_procedure,
    ensure_default_prodotti_magazzino,
)
from .views import staff_or_titolare_api_required, staff_or_titolare_required

MESI_NOMI = {
    1: 'Gennaio', 2: 'Febbraio', 3: 'Marzo', 4: 'Aprile',
    5: 'Maggio', 6: 'Giugno', 7: 'Luglio', 8: 'Agosto',
    9: 'Settembre', 10: 'Ottobre', 11: 'Novembre', 12: 'Dicembre'
}

TARIFFA_COSTO_ORARIO_LIVELLO_DEFAULT = {
    'TIROCINANTE': 9.50,
    '1_LIVELLO': 15.20,
    '2_LIVELLO': 16.50,
    '3_LIVELLO': 18.20,
    '4_LIVELLO': 20.50,
    '5_LIVELLO': 23.50,
}


def get_costo_orario_dipendente(dipendente, data_turno=None, is_straordinario=False):
    """
    Restituisce il costo orario aziendale reale del dipendente (Lordo + TFR + INAIL/INPS).
    Applica automaticamente la maggiorazione se il turno cade di domenica/festivo (+30%) o straordinario (+25%).
    """
    base = 16.50
    if dipendente:
        val_db = float(getattr(dipendente, 'costo_orario_aziendale', 0) or 0)
        if val_db > 0:
            base = val_db
        else:
            liv = getattr(dipendente, 'livello_contrattuale', '2_LIVELLO') or '2_LIVELLO'
            base = TARIFFA_COSTO_ORARIO_LIVELLO_DEFAULT.get(liv, 16.50)

    moltiplicatore = 1.0
    if data_turno and data_turno.weekday() == 6:  # Domenica / Festivo
        moltiplicatore = 1.30
    elif is_straordinario:
        moltiplicatore = 1.20
    return round(base * moltiplicatore, 2)


# ==============================================================================
# 1. CALCOLO CONTABILITÀ INDUSTRIALE & MOL PER CANTIERE
# ==============================================================================

def calcola_contabilita_industriale_mese(mese=None, anno=None, soglia_oraria=15.0, costo_mezzo_per_uscita=3.50):
    """
    Calcola per ogni Cliente/Gruppo P.IVA nel mese selezionato:
    - Ricavi Totali = Canone Mensile Contratto + Lavori Straordinari FATTURATI / DA_FATTURARE nel mese
    - Ore Lavorate Effettive (da TimeTracking.durata_ore; fallback sulle ore pianificate se il mese è in corso)
    - Costo Personale Effettivo = Somma (Ore singolo dipendente × Costo Orario Aziendale effettivo del dipendente)
    - Costo Materiali Consegnati = Somma ConsegnaRichiestaMateriale (CONSEGNATO o IN_CONSEGNA nel mese)
    - Costo Mezzi / Trasferte = N° uscite con mezzo aziendale × costo_mezzo_per_uscita
    - MOL (€) = Ricavi Totali − Costo Personale − Costo Materiali − Costo Mezzi
    - MOL (%) = (MOL / Ricavi Totali) * 100
    - Semaforo Direzionale:
        🔴 PERDITA (MOL < 0 € o MOL % < 5%)
        🟠 EROSIONE (5% <= MOL % < 18% oppure tariffa oraria sotto soglia)
        🟢 OTTIMO (MOL % >= 18%)
    """
    today = timezone.now().date()
    mese = int(mese or today.month)
    anno = int(anno or today.year)
    _, last_day = calendar.monthrange(anno, mese)
    inizio_mese = date(anno, mese, 1)
    fine_mese = date(anno, mese, last_day)

    clienti_qs = list(Cliente.objects.prefetch_related('storico_contratti').order_by('ragione_sociale'))

    # Pre-carica TimeTracking del mese
    tt_qs = list(
        TimeTracking.objects.filter(
            assegnazione__turno__data__gte=inizio_mese,
            assegnazione__turno__data__lte=fine_mese,
        ).select_related(
            'dipendente',
            'assegnazione__cliente',
            'assegnazione__turno',
            'assegnazione__turno__mezzo',
            'assegnazione__richiesta_straordinaria',
        )
    )

    # Pre-carica Assegnazioni del mese (per contare uscite mezzi e fallback ore pianificate)
    assign_qs = list(
        AssegnazioneTurno.objects.filter(
            turno__data__gte=inizio_mese,
            turno__data__lte=fine_mese,
        ).select_related(
            'cliente',
            'turno',
            'turno__mezzo',
            'turno__squadra',
            'turno__squadra__caposquadra',
            'richiesta_straordinaria',
        ).prefetch_related('turno__squadra__componenti', 'dipendenti_esclusi')
    )

    # Pre-carica Consegne Materiali del mese
    consegne_qs = list(
        ConsegnaRichiestaMateriale.objects.filter(
            Q(data_consegna__gte=inizio_mese, data_consegna__lte=fine_mese)
            | Q(data_consegna__isnull=True, data_richiesta__gte=inizio_mese, data_richiesta__lte=fine_mese),
        ).exclude(stato='ANNULLATO').select_related('cliente', 'prodotto')
    )

    # Pre-carica Richieste Straordinarie del mese
    straord_qs = list(
        RichiestaStraordinaria.objects.filter(
            data_inizio__gte=inizio_mese,
            data_inizio__lte=fine_mese,
        ).select_related('cliente')
    )

    # Raggruppa per Cliente / Partita IVA
    grouped = {}
    for c in clienti_qs:
        ore_c_mese, imp_c_mese = c.get_condizioni_contrattuali_mese(anno, mese)
        if ore_c_mese <= 0 and imp_c_mese <= 0:
            # Includi comunque se ha lavorazioni o consegne nel mese
            has_act = any(t.assegnazione.cliente_id == c.id for t in tt_qs) or any(m.cliente_id == c.id for m in consegne_qs)
            if not has_act:
                continue
        piva = (c.partita_iva or '').strip().upper()
        key = f"PIVA_{piva}" if piva else f"PK_{c.pk}"
        if key not in grouped:
            grouped[key] = {'piva': piva, 'clienti': []}
        grouped[key]['clienti'].append(c)

    righe = []
    cantieri_perdita = []
    cantieri_erosione = []
    cantieri_ottimi = []

    tot_ricavi = 0.0
    tot_canoni = 0.0
    tot_extra = 0.0
    tot_costo_personale = 0.0
    tot_costo_materiali = 0.0
    tot_costo_mezzi = 0.0
    tot_mol = 0.0
    tot_ore_contratto = 0.0
    tot_ore_lavorate = 0.0
    tariffe_orarie_list = []

    for key, grp in grouped.items():
        cl_list = grp['clienti']
        cl_ids = {c.id for c in cl_list}

        canone_mensile = 0.0
        ore_contratto = 0.0
        for c in cl_list:
            ore_c_m, imp_c_m = c.get_condizioni_contrattuali_mese(anno, mese)
            ore_contratto += float(ore_c_m)
            canone_mensile += float(imp_c_m)

        # Ricavi Extra da RichiestaStraordinaria (DA_FATTURARE o FATTURATO)
        ricavi_extra = sum(
            float(s.prezzo_concordato or 0)
            for s in straord_qs
            if s.cliente_id in cl_ids and s.stato_fatturazione in ('DA_FATTURARE', 'FATTURATO')
        )
        ricavi_totali = round(canone_mensile + ricavi_extra, 2)

        piva_str = grp['piva']
        if len(cl_list) > 1 and piva_str:
            nome_base = cl_list[0].ragione_sociale.split('-')[0].strip()
            ragione_display = f"{nome_base} ({len(cl_list)} Sedi - P.IVA {piva_str})"
        else:
            ragione_display = cl_list[0].ragione_sociale

        # Calcolo Ore Lavorate e Costo Personale reale dai TimeTracking
        tts_cl = [t for t in tt_qs if t.assegnazione.cliente_id in cl_ids]
        ore_lavorate = 0.0
        costo_personale = 0.0
        dettaglio_livelli = set()

        for tt in tts_cl:
            h = float(tt.durata_ore or 0)
            if h <= 0:
                continue
            ore_lavorate += h
            is_str = bool(tt.assegnazione.richiesta_straordinaria_id)
            costo_h = get_costo_orario_dipendente(tt.dipendente, data_turno=tt.assegnazione.turno.data, is_straordinario=is_str)
            costo_personale += h * costo_h
            if tt.dipendente:
                dettaglio_livelli.add(f"{tt.dipendente.cognome} (€{costo_h:.2f}/h)")

        # Se nel mese non ci sono ancora timetracking registrati ma ci sono turni pianificati o ore contratto,
        # stimiamo il costo personale previsto dalle squadre assegnate per dare subito visibilità al MOL previsionale
        assigns_cl = [a for a in assign_qs if a.cliente_id in cl_ids]
        is_stima_previsionale = False
        if ore_lavorate == 0 and ore_contratto > 0:
            is_stima_previsionale = True
            ore_lavorate = ore_contratto
            # Calcola costo orario medio della squadra abituale del cantiere
            costi_sq = []
            for a in assigns_cl:
                for d in a.dipendenti_presenti:
                    costi_sq.append(get_costo_orario_dipendente(d))
            costo_medio_stimato = (sum(costi_sq) / len(costi_sq)) if costi_sq else 16.50
            costo_personale = ore_lavorate * costo_medio_stimato

        ore_lavorate = round(ore_lavorate, 1)
        costo_personale = round(costo_personale, 2)
        costo_orario_medio_personale = round(costo_personale / ore_lavorate, 2) if ore_lavorate > 0 else 16.50

        # Costo Materiali Consegnati nel mese
        consegne_cl = [m for m in consegne_qs if m.cliente_id in cl_ids]
        costo_materiali = round(sum(float(m.costo_totale or 0) for m in consegne_cl), 2)

        # Costo Mezzi (uscite con mezzo aziendale assegnato)
        uscite_con_mezzo = sum(1 for a in assigns_cl if a.turno and a.turno.mezzo_id)
        costo_mezzi = round(uscite_con_mezzo * float(costo_mezzo_per_uscita), 2)

        costo_totale_industriale = round(costo_personale + costo_materiali + costo_mezzi, 2)
        mol_euro = round(ricavi_totali - costo_totale_industriale, 2)
        mol_perc = round((mol_euro / ricavi_totali) * 100.0, 1) if ricavi_totali > 0 else (-100.0 if costo_totale_industriale > 0 else 0.0)

        importo_orario_contratto = round(canone_mensile / ore_contratto, 2) if ore_contratto > 0 else 0.0
        ricavo_orario_effettivo = round(ricavi_totali / ore_lavorate, 2) if ore_lavorate > 0 else importo_orario_contratto
        diff_ore = round(ore_lavorate - ore_contratto, 1)

        is_sotto_soglia = (importo_orario_contratto < soglia_oraria and canone_mensile > 0) or (
            ricavo_orario_effettivo > 0 and ricavo_orario_effettivo < soglia_oraria
        )

        # Semaforo Direzionale MOL
        if mol_euro < 0 or mol_perc < 5.0:
            semaforo = 'ROSSO'
            semaforo_badge = '🔴 IN PERDITA'
            semaforo_color = '#DC2626'
            semaforo_bg = '#FEF2F2'
        elif mol_perc < 18.0 or is_sotto_soglia:
            semaforo = 'GIALLO'
            semaforo_badge = '🟠 EROSIONE MARGINE'
            semaforo_color = '#D97706'
            semaforo_bg = '#FFFBEB'
        else:
            semaforo = 'VERDE'
            semaforo_badge = '🟢 MARGINALITÀ OK'
            semaforo_color = '#059669'
            semaforo_bg = '#ECFDF5'

        if diff_ore > 0:
            diff_ore_display = f'<span style="color: #D97706; font-weight: 700;">+{diff_ore}h</span>'
        elif diff_ore < 0:
            diff_ore_display = f'<span style="color: #2563EB; font-weight: 600;">{diff_ore}h</span>'
        else:
            diff_ore_display = '<span style="color: #059669;">0h</span>'

        stato_display = (
            f'<span style="background:{semaforo_bg}; color:{semaforo_color}; border:1px solid {semaforo_color}40; '
            f'padding:4px 10px; border-radius:999px; font-size:11px; font-weight:800; white-space:nowrap;">{semaforo_badge}</span>'
        )

        row = {
            'cliente': ragione_display,
            'cliente_id': cl_list[0].pk,
            'canone_mensile_val': canone_mensile,
            'ricavi_extra_val': ricavi_extra,
            'ricavi_totali_val': ricavi_totali,
            'importo_mensile': f"&euro;{canone_mensile:,.2f}",
            'ricavi_extra_fmt': f"+&euro;{ricavi_extra:,.2f}" if ricavi_extra > 0 else "—",
            'ricavi_totali_fmt': f"&euro;{ricavi_totali:,.2f}",
            'ore_contratto_val': ore_contratto,
            'ore_contratto': f"{ore_contratto:g}h",
            'importo_orario_val': importo_orario_contratto,
            'importo_orario': f"&euro;{importo_orario_contratto:.2f}",
            'ore_lavorate_val': ore_lavorate,
            'ore_lavorate': f"{ore_lavorate:g}h" + (" *" if is_stima_previsionale else ""),
            'is_stima_previsionale': is_stima_previsionale,
            'costo_orario_medio_personale': costo_orario_medio_personale,
            'costo_personale_val': costo_personale,
            'costo_personale_fmt': f"&euro;{costo_personale:,.2f}",
            'costo_materiali_val': costo_materiali,
            'costo_materiali_fmt': f"&euro;{costo_materiali:,.2f}",
            'costo_mezzi_val': costo_mezzi,
            'costo_mezzi_fmt': f"&euro;{costo_mezzi:,.2f}",
            'uscite_con_mezzo': uscite_con_mezzo,
            'costo_totale_industriale_val': costo_totale_industriale,
            'costo_totale_industriale_fmt': f"&euro;{costo_totale_industriale:,.2f}",
            'mol_euro_val': mol_euro,
            'mol_euro_fmt': f"{'+' if mol_euro > 0 else ''}&euro;{mol_euro:,.2f}",
            'mol_perc_val': mol_perc,
            'mol_perc_fmt': f"{mol_perc:.1f}%",
            'costo_effettivo_display': f"&euro;{ricavo_orario_effettivo:.2f}/h" if ricavo_orario_effettivo else "&mdash;",
            'diff_ore_display': diff_ore_display,
            'stato_display': stato_display,
            'semaforo': semaforo,
            'semaforo_badge': semaforo_badge,
            'semaforo_color': semaforo_color,
            'semaforo_bg': semaforo_bg,
            'sotto_soglia': is_sotto_soglia or semaforo == 'ROSSO',
        }
        righe.append(row)

        if semaforo == 'ROSSO':
            cantieri_perdita.append(row)
        elif semaforo == 'GIALLO':
            cantieri_erosione.append(row)
        else:
            cantieri_ottimi.append(row)

        tot_canoni += canone_mensile
        tot_extra += ricavi_extra
        tot_ricavi += ricavi_totali
        tot_costo_personale += costo_personale
        tot_costo_materiali += costo_materiali
        tot_costo_mezzi += costo_mezzi
        tot_mol += mol_euro
        tot_ore_contratto += ore_contratto
        tot_ore_lavorate += ore_lavorate
        if importo_orario_contratto > 0:
            tariffe_orarie_list.append(importo_orario_contratto)

    # Ordina mostrando prima i cantieri in perdita/erosione per azione immediata dei Titolari
    ordine_sem = {'ROSSO': 0, 'GIALLO': 1, 'VERDE': 2}
    righe.sort(key=lambda r: (ordine_sem.get(r['semaforo'], 9), r['mol_euro_val']))

    mol_tot_perc = round((tot_mol / tot_ricavi) * 100.0, 1) if tot_ricavi > 0 else 0.0
    media_oraria = round(sum(tariffe_orarie_list) / len(tariffe_orarie_list), 2) if tariffe_orarie_list else 0.0

    return {
        'mese': mese,
        'anno': anno,
        'mese_nome': MESI_NOMI.get(mese, ''),
        'soglia': soglia_oraria,
        'analisi': righe,
        'cantieri_perdita': cantieri_perdita,
        'cantieri_erosione': cantieri_erosione,
        'cantieri_ottimi': cantieri_ottimi,
        'sotto_soglia': cantieri_perdita + cantieri_erosione,
        'totale_contratti': len(righe),
        'totale_canoni_val': round(tot_canoni, 2),
        'totale_extra_val': round(tot_extra, 2),
        'totale_ricavi_val': round(tot_ricavi, 2),
        'totale_fatturato': f"&euro;{tot_ricavi:,.2f}",
        'totale_costo_personale_val': round(tot_costo_personale, 2),
        'totale_costo_personale_fmt': f"&euro;{tot_costo_personale:,.2f}",
        'totale_costo_materiali_val': round(tot_costo_materiali, 2),
        'totale_costo_materiali_fmt': f"&euro;{tot_costo_materiali:,.2f}",
        'totale_costo_mezzi_val': round(tot_costo_mezzi, 2),
        'totale_costo_mezzi_fmt': f"&euro;{tot_costo_mezzi:,.2f}",
        'totale_mol_val': round(tot_mol, 2),
        'totale_mol_fmt': f"&euro;{tot_mol:,.2f}",
        'totale_mol_perc': mol_tot_perc,
        'media_oraria': f"&euro;{media_oraria:.2f}",
    }


# ==============================================================================
# 2. VISTA & API MAGAZZINO PRODOTTI, DOTAZIONI CANTIERE & CONSEGNE
# ==============================================================================

@staff_or_titolare_required
def magazzino_dotazioni_view(request):
    ensure_default_prodotti_magazzino()
    cliente_id = request.GET.get('cliente_id', '')
    stato_filter = request.GET.get('stato', '')

    prodotti = list(ProdottoMagazzino.objects.filter(attivo=True).order_by('categoria', 'nome'))
    prodotti_sotto_scorta = [p for p in prodotti if p.sotto_scorta]

    dotazioni_qs = DotazioneCantiere.objects.select_related('cliente').order_by('cliente__ragione_sociale', 'tipo')
    consegne_qs = ConsegnaRichiestaMateriale.objects.select_related('cliente', 'prodotto', 'richiesto_da', 'consegnato_da').order_by('-data_richiesta', '-id')

    if cliente_id and str(cliente_id).isdigit():
        dotazioni_qs = dotazioni_qs.filter(cliente_id=int(cliente_id))
        consegne_qs = consegne_qs.filter(cliente_id=int(cliente_id))

    if stato_filter:
        consegne_qs = consegne_qs.filter(stato=stato_filter)

    dotazioni = list(dotazioni_qs[:200])
    consegne = list(consegne_qs[:150])

    richieste_aperte = ConsegnaRichiestaMateriale.objects.filter(stato__in=['RICHIESTA', 'IN_CONSEGNA']).count()
    dotazioni_da_ritirare = DotazioneCantiere.objects.filter(stato='DA_RITIRARE').select_related('cliente')

    today = timezone.now().date()
    inizio_mese = today.replace(day=1)
    spesa_mese_materiali = ConsegnaRichiestaMateriale.objects.filter(
        stato='CONSEGNATO',
        data_consegna__gte=inizio_mese,
    ).aggregate(tot=Sum('costo_totale'))['tot'] or Decimal('0.00')

    clienti = list(Cliente.objects.all().order_by('ragione_sociale'))
    dipendenti = list(Dipendente.objects.filter(stato='ATTIVO').order_by('cognome', 'nome'))

    return render(request, 'core/magazzino_dotazioni.html', {
        'prodotti': prodotti,
        'prodotti_sotto_scorta': prodotti_sotto_scorta,
        'dotazioni': dotazioni,
        'dotazioni_da_ritirare': dotazioni_da_ritirare,
        'consegne': consegne,
        'richieste_aperte': richieste_aperte,
        'spesa_mese_materiali': spesa_mese_materiali,
        'clienti': clienti,
        'dipendenti': dipendenti,
        'cliente_id_selected': int(cliente_id) if (cliente_id and str(cliente_id).isdigit()) else None,
        'stato_selected': stato_filter,
        'today_iso': today.strftime('%Y-%m-%d'),
    })


@csrf_exempt
@staff_or_titolare_api_required
def magazzino_dotazioni_api(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    except Exception:
        data = request.POST

    action = (data.get('action') or '').strip()

    if action == 'aggiungi_prodotto':
        nome = (data.get('nome') or '').strip()
        if not nome:
            return JsonResponse({'ok': False, 'error': 'Inserisci il nome del prodotto.'}, status=400)
        categoria = (data.get('categoria') or 'DETERGENTE').strip()
        unita = (data.get('unita_misura') or 'pz').strip()
        costo = Decimal(str(data.get('costo_unitario') or '0').replace(',', '.'))
        giacenza = Decimal(str(data.get('giacenza_attuale') or '0').replace(',', '.'))
        scorta_min = Decimal(str(data.get('scorta_minima') or '5').replace(',', '.'))
        fornitore = (data.get('fornitore_abituale') or '').strip()

        prod, created = ProdottoMagazzino.objects.update_or_create(
            nome=nome,
            defaults={
                'categoria': categoria,
                'unita_misura': unita,
                'costo_unitario': costo,
                'giacenza_attuale': giacenza,
                'scorta_minima': scorta_min,
                'fornitore_abituale': fornitore,
                'attivo': True,
            }
        )
        return JsonResponse({'ok': True, 'message': f'Prodotto "{prod.nome}" salvato in catalogo.', 'id': prod.id})

    elif action == 'carica_scorta':
        prod_id = data.get('prodotto_id')
        qta = Decimal(str(data.get('quantita') or '0').replace(',', '.'))
        prod = get_object_or_404(ProdottoMagazzino, pk=prod_id)
        prod.giacenza_attuale = (prod.giacenza_attuale or Decimal('0')) + qta
        if data.get('nuovo_costo'):
            prod.costo_unitario = Decimal(str(data.get('nuovo_costo')).replace(',', '.'))
        prod.save()
        return JsonResponse({'ok': True, 'message': f'Giacenza di "{prod.nome}" aggiornata a {prod.giacenza_attuale:g} {prod.unita_misura}.'})

    elif action == 'aggiungi_dotazione':
        cliente_id = data.get('cliente_id')
        descrizione = (data.get('descrizione') or '').strip()
        if not cliente_id or not descrizione:
            return JsonResponse({'ok': False, 'error': 'Seleziona il cliente e inserisci la descrizione della dotazione.'}, status=400)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        dot = DotazioneCantiere.objects.create(
            cliente=cliente,
            tipo=(data.get('tipo') or 'MACCHINARIO').strip(),
            descrizione=descrizione,
            matricola_codice=(data.get('matricola_codice') or '').strip(),
            quantita=int(data.get('quantita') or 1),
            valore_stimato=Decimal(str(data.get('valore_stimato') or '0').replace(',', '.')),
            data_consegna=timezone.now().date(),
            stato=(data.get('stato') or 'IN_CANTIERE').strip(),
            note=(data.get('note') or '').strip(),
        )
        return JsonResponse({'ok': True, 'message': f'Dotazione "{dot.descrizione}" assegnata a {cliente.ragione_sociale}.', 'id': dot.id})

    elif action == 'cambia_stato_dotazione':
        dot_id = data.get('dotazione_id')
        nuovo_stato = (data.get('stato') or 'IN_CANTIERE').strip()
        dot = get_object_or_404(DotazioneCantiere, pk=dot_id)
        dot.stato = nuovo_stato
        if nuovo_stato == 'RITIRATO' and not dot.data_ritiro:
            dot.data_ritiro = timezone.now().date()
        dot.save()
        return JsonResponse({'ok': True, 'message': f'Stato dotazione aggiornato a {dot.get_stato_display()}.'})

    elif action == 'registra_consegna':
        cliente_id = data.get('cliente_id')
        prodotto_id = data.get('prodotto_id')
        descrizione_libera = (data.get('descrizione_libera') or '').strip()
        if not cliente_id or (not prodotto_id and not descrizione_libera):
            return JsonResponse({'ok': False, 'error': 'Seleziona il cliente e il prodotto da consegnare.'}, status=400)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        prodotto = ProdottoMagazzino.objects.filter(pk=prodotto_id).first() if prodotto_id else None
        qta = Decimal(str(data.get('quantita') or '1').replace(',', '.'))
        costo_u = Decimal(str(data.get('costo_unitario') or (prodotto.costo_unitario if prodotto else '0')).replace(',', '.'))
        stato = (data.get('stato') or 'CONSEGNATO').strip()
        dip_id = data.get('dipendente_id')
        dip = Dipendente.objects.filter(pk=dip_id).first() if dip_id else None

        item = ConsegnaRichiestaMateriale.objects.create(
            cliente=cliente,
            prodotto=prodotto,
            descrizione_libera=descrizione_libera or (prodotto.nome if prodotto else ''),
            quantita=qta,
            costo_unitario_applicato=costo_u,
            stato=stato,
            urgenza=(data.get('urgenza') or 'NORMALE').strip(),
            richiesto_da=dip if stato == 'RICHIESTA' else None,
            consegnato_da=dip if stato == 'CONSEGNATO' else None,
            data_richiesta=timezone.now().date(),
            data_consegna=timezone.now().date() if stato == 'CONSEGNATO' else None,
            note=(data.get('note') or '').strip(),
        )
        return JsonResponse({
            'ok': True,
            'message': f'Registrato: {item.descrizione_libera} (x{item.quantita:g}) per {cliente.ragione_sociale} — €{item.costo_totale:.2f}.',
            'id': item.id,
        })

    elif action == 'aggiorna_stato_consegna':
        consegna_id = data.get('consegna_id')
        nuovo_stato = (data.get('stato') or 'CONSEGNATO').strip()
        item = get_object_or_404(ConsegnaRichiestaMateriale, pk=consegna_id)
        item.stato = nuovo_stato
        if nuovo_stato == 'CONSEGNATO' and not item.data_consegna:
            item.data_consegna = timezone.now().date()
        item.save()
        return JsonResponse({
            'ok': True,
            'message': f'Consegna #{item.id} impostata come "{item.get_stato_display()}" (€{item.costo_totale:.2f}).',
        })

    return JsonResponse({'ok': False, 'error': f'Azione non riconosciuta: {action}'}, status=400)


# ==============================================================================
# 3. QUALITÀ, ISPEZIONI CANTIERE (SLA CLIENTE) & QR CODE GEOFENCE
# ==============================================================================

@staff_or_titolare_required
def qualita_ispezioni_view(request):
    cliente_id = request.GET.get('cliente_id', '')
    ispezioni_qs = IspezioneQualitaCantiere.objects.select_related('cliente', 'ispettore', 'squadra_valutata').order_by('-data_ispezione', '-id')
    if cliente_id and str(cliente_id).isdigit():
        ispezioni_qs = ispezioni_qs.filter(cliente_id=int(cliente_id))

    ispezioni = list(ispezioni_qs[:100])
    clienti = list(Cliente.objects.all().order_by('ragione_sociale'))
    squadre = list(Squadra.objects.all().order_by('nome'))
    dipendenti = list(Dipendente.objects.filter(stato='ATTIVO').order_by('cognome', 'nome'))

    # Log prossimità / timbrature GPS recenti
    proximity_logs = list(
        ProximityLog.objects.select_related('dipendente', 'cliente').order_by('-last_updated')[:40]
    )

    media_globale = 5.0
    if ispezioni:
        media_globale = round(sum(float(i.media_voto or 5) for i in ispezioni) / len(ispezioni), 2)

    non_conformi_count = sum(1 for i in ispezioni if i.esito in ('DA_MIGLIORARE', 'NON_CONFORME'))

    return render(request, 'core/qualita_ispezioni.html', {
        'ispezioni': ispezioni,
        'clienti': clienti,
        'squadre': squadre,
        'dipendenti': dipendenti,
        'proximity_logs': proximity_logs,
        'media_globale': media_globale,
        'non_conformi_count': non_conformi_count,
        'cliente_id_selected': int(cliente_id) if (cliente_id and str(cliente_id).isdigit()) else None,
    })


@csrf_exempt
@staff_or_titolare_api_required
def qualita_ispezioni_api(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.POST
    else:
        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
        except Exception:
            data = request.POST

    action = (data.get('action') or 'crea_ispezione').strip()

    if action == 'crea_ispezione':
        cliente_id = data.get('cliente_id')
        if not cliente_id:
            return JsonResponse({'ok': False, 'error': 'Seleziona il Cliente / Cantiere ispezionato.'}, status=400)
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        ispettore_id = data.get('ispettore_id')
        squadra_id = data.get('squadra_id')
        ispettore = Dipendente.objects.filter(pk=ispettore_id).first() if ispettore_id else None
        squadra = Squadra.objects.filter(pk=squadra_id).first() if squadra_id else None

        # Se non specificata la squadra, proponi la squadra abituale del cantiere
        if not squadra:
            prog = cliente.programmazione_ricorrente.filter(squadra_abituale__isnull=False).first()
            if prog:
                squadra = prog.squadra_abituale

        isp = IspezioneQualitaCantiere(
            cliente=cliente,
            ispettore=ispettore,
            squadra_valutata=squadra,
            data_ispezione=timezone.now(),
            voto_ingressi_scale=min(max(int(data.get('voto_ingressi_scale') or 5), 1), 5),
            voto_uffici_postazioni=min(max(int(data.get('voto_uffici_postazioni') or 5), 1), 5),
            voto_bagni_sanitari=min(max(int(data.get('voto_bagni_sanitari') or 5), 1), 5),
            voto_vetrate_infissi=min(max(int(data.get('voto_vetrate_infissi') or 5), 1), 5),
            voto_riordino_dotazioni=min(max(int(data.get('voto_riordino_dotazioni') or 5), 1), 5),
            note_interne_squadra=(data.get('note_interne_squadra') or '').strip(),
            messaggio_cortesia_cliente=(data.get('messaggio_cortesia_cliente') or '').strip(),
            firma_referente_cliente=(data.get('firma_referente_cliente') or '').strip(),
        )
        if request.FILES.get('foto_1'):
            isp.foto_1 = request.FILES['foto_1']
        if request.FILES.get('foto_2'):
            isp.foto_2 = request.FILES['foto_2']
        isp.save()

        return JsonResponse({
            'ok': True,
            'message': f'Verbale Ispezione salvato per {cliente.ragione_sociale} (Media: ⭐ {isp.media_voto}/5 — {isp.get_esito_display()}).',
            'ispezione_id': isp.id,
            'pdf_url': f'/qualita-ispezioni/pdf/{isp.id}/',
        })

    elif action == 'segna_inviato_cliente':
        isp_id = data.get('ispezione_id')
        isp = get_object_or_404(IspezioneQualitaCantiere, pk=isp_id)
        isp.inviato_al_cliente = True
        isp.save(update_fields=['inviato_al_cliente'])
        return JsonResponse({'ok': True, 'message': 'Verbale segnato come inviato al cliente.'})

    return JsonResponse({'ok': False, 'error': f'Azione non valida: {action}'}, status=400)


def pdf_verbale_ispezione_view(request, ispezione_id):
    """
    Genera il Report PDF di Cortesia per il Cliente ("Certificato di Controllo Qualità & SLA")
    con punteggi per ambiente, note di cortesia, data/ora del sopralluogo e firma del Responsabile.
    Accessibile sia da Admin sia tramite token pubblico per invio diretto via WhatsApp/Email al cliente.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    isp = get_object_or_404(
        IspezioneQualitaCantiere.objects.select_related('cliente', 'ispettore', 'squadra_valutata'),
        pk=ispezione_id,
    )
    token_q = (request.GET.get('token') or '').strip()
    from .views import _is_staff_or_titolare
    if not _is_staff_or_titolare(request) and (not token_q or token_q != isp.token_pubblico):
        return HttpResponseRedirect(f'/admin/login/?next={request.path}')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18*mm, bottomMargin=18*mm, leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()
    elements = []

    title_st = ParagraphStyle('T', parent=styles['Title'], fontSize=17, textColor=colors.HexColor('#0F172A'), alignment=0, spaceAfter=2*mm)
    sub_st = ParagraphStyle('S', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#475569'), spaceAfter=6*mm)
    h2_st = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1E293B'), spaceBefore=5*mm, spaceAfter=3*mm)
    body_st = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#1E293B'))

    elements.append(Paragraph("KANDOR — CERTIFICATO DI CONTROLLO QUALITÀ SERVIZIO", title_st))
    elements.append(Paragraph(
        f"Verbale di Sopralluogo Tecnico #{isp.id} del {timezone.localtime(isp.data_ispezione).strftime('%d/%m/%Y ore %H:%M')}",
        sub_st
    ))

    # Box Dati Cliente
    ispettore_str = f"{isp.ispettore.nome} {isp.ispettore.cognome}" if isp.ispettore else "Responsabile Qualità Kandor"
    squadra_str = isp.squadra_valutata.nome if isp.squadra_valutata else "Squadra Operativa Assegnata"
    info_data = [
        ['Cliente / Sede:', isp.cliente.ragione_sociale, 'Data Verifica:', timezone.localtime(isp.data_ispezione).strftime('%d/%m/%Y %H:%M')],
        ['Indirizzo Cantiere:', isp.cliente.indirizzo_sede or '—', 'Responsabile Area:', ispettore_str],
        ['Squadra Operativa:', squadra_str, 'Esito SLA Complessivo:', f"{isp.media_voto}/5.00 ({isp.get_esito_display()})"],
    ]
    t_info = Table(info_data, colWidths=[38*mm, 62*mm, 38*mm, 36*mm])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0F172A')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("Gentile Cliente, oggi il nostro Responsabile d'Area ha effettuato un sopralluogo di controllo qualità presso la Vostra sede per verificare il pieno rispetto degli standard di pulizia concordati (SLA).", body_st))
    elements.append(Spacer(1, 4*mm))

    # Tabella Checklist Ambienti
    elements.append(Paragraph("Valutazione Analitica per Ambiente", h2_st))

    def _stars(n):
        n = int(n or 5)
        return "★" * n + "☆" * (5 - n) + f"  ({n}/5)"

    rows = [
        ['Area / Ambiente Verificato', 'Valutazione Qualità', 'Conformità SLA'],
        ['1. Ingressi, Scale, Ascensori e Parti Comuni', _stars(isp.voto_ingressi_scale), 'Conforme' if isp.voto_ingressi_scale >= 3 else 'In revisione'],
        ['2. Uffici, Postazioni di Lavoro e Pavimentazioni', _stars(isp.voto_uffici_postazioni), 'Conforme' if isp.voto_uffici_postazioni >= 3 else 'In revisione'],
        ['3. Servizi Igienici, Sanitari e Disinfezione', _stars(isp.voto_bagni_sanitari), 'Conforme' if isp.voto_bagni_sanitari >= 3 else 'In revisione'],
        ['4. Vetrate, Specchi, Porte e Infissi', _stars(isp.voto_vetrate_infissi), 'Conforme' if isp.voto_vetrate_infissi >= 3 else 'In revisione'],
        ['5. Locale Tecnico, Riordino Prodotti e Attrezzature', _stars(isp.voto_riordino_dotazioni), 'Conforme' if isp.voto_riordino_dotazioni >= 3 else 'In revisione'],
        ['PUNTEGGIO MEDIO COMPLESSIVO', f"{isp.media_voto} / 5.00", isp.get_esito_display()],
    ]
    t_voti = Table(rows, colWidths=[90*mm, 44*mm, 40*mm])
    t_voti.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECFDF5')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.append(t_voti)

    if isp.messaggio_cortesia_cliente:
        elements.append(Spacer(1, 5*mm))
        elements.append(Paragraph("Osservazioni e Note per il Cliente", h2_st))
        elements.append(Paragraph(isp.messaggio_cortesia_cliente, body_st))

    elements.append(Spacer(1, 10*mm))
    firma_ref = isp.firma_referente_cliente or "Per presa visione"
    firme_table = Table([
        ['Il Responsabile Qualità Kandor', 'Referente Cliente'],
        [ispettore_str, firma_ref],
    ], colWidths=[87*mm, 87*mm])
    firme_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('LINEABOVE', (0, 1), (0, 1), 0.8, colors.HexColor('#94A3B8')),
        ('LINEABOVE', (1, 1), (1, 1), 0.8, colors.HexColor('#94A3B8')),
        ('TOPPADDING', (0, 1), (-1, 1), 8),
    ]))
    elements.append(firme_table)

    doc.build(elements)
    buffer.seek(0)
    resp = HttpResponse(buffer, content_type='application/pdf')
    nome_clean = isp.cliente.ragione_sociale.replace(' ', '_')[:25]
    resp['Content-Disposition'] = f'inline; filename="Verbale_Qualita_{nome_clean}_{isp.id}.pdf"'
    return resp


@staff_or_titolare_required
def qr_code_cantiere_view(request, cliente_id):
    """
    Pagina stampabile con il QR Code Cantiere da affiggere nel locale tecnico/sgabuzzino del cliente:
    inquadrandolo col cellulare apre l'App Dipendenti Kandor pre-impostata sul cantiere per
    Check-in / Check-out GPS istantaneo o Richiesta Rapida Materiali.
    """
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    host = request.get_host()
    scheme = 'https' if request.is_secure() or 'sslip.io' in host else 'http'
    checkin_url = f"{scheme}://{host}/app/?qr_cliente_id={cliente.id}&tab=home"

    return render(request, 'core/qr_cantiere_print.html', {
        'cliente': cliente,
        'checkin_url': checkin_url,
        'checkin_url_encoded': quote(checkin_url),
    })


# ==============================================================================
# 4. MODULO PREVENTIVAZIONE RAPIDA (CRM COMMERCIALE) & CONVERSIONE 1-CLICK
# ==============================================================================

RESE_STANDARD_CATALOGO = [
    {'label': '🏢 Uffici direzionali / operativi arredati', 'resa': 150, 'freq': 2, 'amb': 'Uffici e Postazioni Lavoro'},
    {'label': '🚽 Bagni, Sanitari e Spogliatoi', 'resa': 60, 'freq': 5, 'amb': 'Servizi Igienici e Sanitari'},
    {'label': '🏢 Scale Condominiali + Ascensore + Atrio', 'resa': 120, 'freq': 1, 'amb': 'Scale Condominiali e Parti Comuni'},
    {'label': '🪟 Vetrate, Ingressi e Porte a Vetro', 'resa': 90, 'freq': 1, 'amb': 'Vetrate e Infissi'},
    {'label': '🏭 Corridoi / Open Space / Magazzino libero', 'resa': 350, 'freq': 1, 'amb': 'Corridoi / Magazzino'},
    {'label': '🚗 Corsello Box / Cortile Esterno', 'resa': 450, 'freq': 0.5, 'amb': 'Cortile / Corsello Box'},
]


@staff_or_titolare_required
def preventivi_crm_view(request):
    prev_id = request.GET.get('prev_id', '')
    preventivi = list(
        PreventivoCommerciale.objects.select_related('cliente_convertito', 'squadra_prevista')
        .prefetch_related('voci_ambienti')
        .order_by('-created_at')
    )
    selected_prev = None
    if prev_id and str(prev_id).isdigit():
        selected_prev = PreventivoCommerciale.objects.prefetch_related('voci_ambienti').filter(pk=int(prev_id)).first()
    elif preventivi:
        selected_prev = preventivi[0]

    squadre = list(Squadra.objects.all().order_by('nome'))

    return render(request, 'core/preventivi_crm.html', {
        'preventivi': preventivi,
        'selected_prev': selected_prev,
        'squadre': squadre,
        'rese_standard': RESE_STANDARD_CATALOGO,
        'today_iso': timezone.now().date().strftime('%Y-%m-%d'),
    })


@csrf_exempt
@staff_or_titolare_api_required
def preventivi_crm_api(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    except Exception:
        data = request.POST

    action = (data.get('action') or '').strip()

    if action == 'salva_preventivo':
        prev_id = data.get('preventivo_id')
        ragione = (data.get('ragione_sociale_prospect') or '').strip()
        if not ragione:
            return JsonResponse({'ok': False, 'error': 'Inserisci la Ragione Sociale o il nome del Condominio.'}, status=400)

        with transaction.atomic():
            if prev_id and str(prev_id).isdigit():
                prev = get_object_or_404(PreventivoCommerciale, pk=int(prev_id))
            else:
                prev = PreventivoCommerciale(data_emissione=timezone.now().date())

            prev.ragione_sociale_prospect = ragione
            prev.partita_iva = (data.get('partita_iva') or '').strip()
            prev.codice_fiscale = (data.get('codice_fiscale') or '').strip().upper()
            prev.indirizzo_cantiere = (data.get('indirizzo_cantiere') or '').strip()
            prev.referente_nome = (data.get('referente_nome') or '').strip()
            prev.referente_contatto = (data.get('referente_contatto') or '').strip()
            prev.costo_orario_applicato = Decimal(str(data.get('costo_orario_applicato') or '16.50').replace(',', '.'))
            prev.incidenza_prodotti_perc = Decimal(str(data.get('incidenza_prodotti_perc') or '6.00').replace(',', '.'))
            prev.quota_fissa_mezzi_mensile = Decimal(str(data.get('quota_fissa_mezzi_mensile') or '25.00').replace(',', '.'))
            prev.margine_target_perc = Decimal(str(data.get('margine_target_perc') or '28.00').replace(',', '.'))
            prev.importo_una_tantum_sgrosso = Decimal(str(data.get('importo_una_tantum_sgrosso') or '0.00').replace(',', '.'))
            prev.note_capitolato = (data.get('note_capitolato') or '').strip()

            canone_override = data.get('canone_finale_offerto')
            if canone_override is not None and str(canone_override).strip() != '':
                prev.canone_finale_offerto = Decimal(str(canone_override).replace(',', '.'))
            else:
                prev.canone_finale_offerto = Decimal('0.00')

            sq_id = data.get('squadra_prevista_id')
            prev.squadra_prevista = Squadra.objects.filter(pk=sq_id).first() if sq_id else None
            prev.save()

            ambienti = data.get('ambienti')
            if isinstance(ambienti, list):
                prev.voci_ambienti.all().delete()
                for amb in ambienti:
                    nome_amb = (amb.get('nome_ambiente') or '').strip()
                    if not nome_amb:
                        continue
                    mq = Decimal(str(amb.get('metri_quadri') or '100').replace(',', '.'))
                    resa = Decimal(str(amb.get('resa_oraria_mq') or '150').replace(',', '.'))
                    pass_sett = Decimal(str(amb.get('passaggi_settimanali') or '1').replace(',', '.'))
                    giorni = (amb.get('giorni_preferiti') or '0').strip()
                    ora_ini = (amb.get('ora_inizio_suggerita') or '07:00').strip()
                    VoceAmbientePreventivo.objects.create(
                        preventivo=prev,
                        nome_ambiente=nome_amb,
                        metri_quadri=mq,
                        resa_oraria_mq=resa,
                        passaggi_settimanali=pass_sett,
                        giorni_preferiti=giorni,
                        ora_inizio_suggerita=ora_ini,
                    )
            prev.ricalcola_totali()

        return JsonResponse({
            'ok': True,
            'message': f'Preventivo {prev.numero_preventivo} salvato! Monte ore: {prev.ore_mensili_stimate}h/mese — Canone consigliato: €{prev.canone_consigliato_mensile}/mese.',
            'preventivo_id': prev.id,
        })

    elif action == 'converti_in_cliente_1click':
        prev_id = data.get('preventivo_id')
        prev = get_object_or_404(PreventivoCommerciale.objects.prefetch_related('voci_ambienti'), pk=prev_id)

        if prev.cliente_convertito_id:
            return JsonResponse({
                'ok': True,
                'message': f'Questo preventivo è già collegato al cliente attivo "{prev.cliente_convertito.ragione_sociale}".',
                'cliente_id': prev.cliente_convertito_id,
            })

        with transaction.atomic():
            canone = prev.canone_finale_offerto if prev.canone_finale_offerto > 0 else prev.canone_consigliato_mensile
            riepilogo_ambienti = "; ".join(
                f"{v.nome_ambiente} ({v.metri_quadri:g} m², {v.passaggi_settimanali:g}x/sett)"
                for v in prev.voci_ambienti.all()
            )
            note_complete = prev.note_capitolato
            if riepilogo_ambienti:
                note_complete = f"[Da Preventivo {prev.numero_preventivo}] Ambienti: {riepilogo_ambienti}.\n{note_complete}".strip()

            cliente = Cliente.objects.create(
                ragione_sociale=prev.ragione_sociale_prospect,
                partita_iva=prev.partita_iva or None,
                codice_fiscale=prev.codice_fiscale or None,
                indirizzo_sede=prev.indirizzo_cantiere,
                referente_nome=prev.referente_nome,
                referente_ruolo=prev.referente_contatto,
                ore_mensili_contratto=prev.ore_mensili_stimate,
                importo_mensile_contratto=canone,
                note_mansioni=note_complete,
            )

            # Genera automaticamente le ProgrammazioneRicorrente in base agli ambienti o al monte ore settimanale
            oggi = timezone.now().date()
            ore_sett = float(prev.ore_settimanali_stimate or 2.0)
            voci = list(prev.voci_ambienti.all())
            max_freq = max([float(v.passaggi_settimanali or 1) for v in voci], default=1.0)

            if max_freq >= 5:
                giorni_target = [0, 1, 2, 3, 4]  # Lun-Ven
            elif max_freq >= 3:
                giorni_target = [0, 2, 4]        # Lun-Mer-Ven
            elif max_freq >= 2:
                giorni_target = [0, 3]           # Lun-Gio
            else:
                giorni_target = [0]              # Lunedì

            durata_per_uscita = round(max(ore_sett / len(giorni_target), 0.5), 2)
            for wd in giorni_target:
                ProgrammazioneRicorrente.objects.create(
                    cliente=cliente,
                    tipo_ripetizione='SETTIMANALE',
                    giorno_settimana=wd,
                    ora_inizio=time(7, 0),
                    durata=Decimal(str(durata_per_uscita)),
                    squadra_abituale=prev.squadra_prevista,
                    data_inizio_contratto=oggi,
                )

            # Se era previsto uno Sgrosso Iniziale Una Tantum, crea già la RichiestaStraordinaria DA_FATTURARE
            if prev.importo_una_tantum_sgrosso and prev.importo_una_tantum_sgrosso > 0:
                RichiestaStraordinaria.objects.create(
                    cliente=cliente,
                    data_inizio=oggi,
                    ora_inizio=time(8, 0),
                    ora_fine=time(12, 0),
                    descrizione=f"Sgrosso / Pulizia di primo impianto da Preventivo {prev.numero_preventivo}",
                    completata=False,
                    stato_fatturazione='DA_FATTURARE',
                    prezzo_concordato=prev.importo_una_tantum_sgrosso,
                )

            # Avvia automaticamente la procedura operativa "Attivazione Nuovo Cantiere"
            ensure_default_procedure()
            mod_attivazione = ModelloProcedura.objects.filter(nome__icontains='Attivazione Nuovo Cantiere').first()
            pratica_id = None
            if mod_attivazione:
                pratica = ProceduraAvviata.objects.create(
                    modello=mod_attivazione,
                    cliente=cliente,
                    titolo=f"Attivazione Nuovo Cantiere — {cliente.ragione_sociale}",
                    data_avvio=oggi,
                    data_scadenza=oggi + timedelta(days=7),
                    stato='IN_CORSO',
                    note=f"Generata automaticamente dalla conversione 1-Click del Preventivo {prev.numero_preventivo}.",
                )
                pratica.copia_passaggi_da_modello()
                pratica_id = pratica.id

            prev.stato = 'ACCETTATO'
            prev.cliente_convertito = cliente
            prev.save(update_fields=['stato', 'cliente_convertito'])

        return JsonResponse({
            'ok': True,
            'message': (
                f'🎉 Conversione 1-Click completata! Creato Cliente "{cliente.ragione_sociale}", '
                f'{len(giorni_target)} programmazioni settimanali e avviata la procedura "Attivazione Nuovo Cantiere".'
            ),
            'cliente_id': cliente.id,
            'pratica_id': pratica_id,
        })

    return JsonResponse({'ok': False, 'error': f'Azione non riconosciuta: {action}'}, status=400)


@staff_or_titolare_required
def pdf_preventivo_commerciale_view(request, prev_id):
    """Genera il PDF professionale dell'offerta commerciale per il potenziale cliente."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    prev = get_object_or_404(PreventivoCommerciale.objects.prefetch_related('voci_ambienti'), pk=prev_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18*mm, bottomMargin=18*mm, leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()
    elements = []

    title_st = ParagraphStyle('T', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#0F172A'), alignment=0, spaceAfter=2*mm)
    sub_st = ParagraphStyle('S', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#475569'), spaceAfter=6*mm)
    h2_st = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1E293B'), spaceBefore=5*mm, spaceAfter=3*mm)
    body_st = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#1E293B'))

    elements.append(Paragraph(f"OFFERTA COMMERCIALE SERVIZI DI PULIZIA — {prev.numero_preventivo}", title_st))
    elements.append(Paragraph(f"Data emissione: {prev.data_emissione.strftime('%d/%m/%Y')} — Validità offerta: {prev.validita_giorni} giorni", sub_st))

    info_rows = [
        ['Spett.le Cliente:', prev.ragione_sociale_prospect, 'P.IVA / C.F.:', prev.partita_iva or prev.codice_fiscale or '—'],
        ['Ubicazione Cantiere:', prev.indirizzo_cantiere, 'Referente:', f"{prev.referente_nome} ({prev.referente_contatto})".strip(' ()') or '—'],
    ]
    t_info = Table(info_rows, colWidths=[35*mm, 65*mm, 28*mm, 46*mm])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 5*mm))

    elements.append(Paragraph("Prospetto Tecnico degli Ambienti e Frequenze d'Intervento", h2_st))
    amb_rows = [['Ambiente / Zona', 'Superficie (m²)', 'Frequenza Settimanale', 'Ore / Intervento', 'Ore / Settimana']]
    for v in prev.voci_ambienti.all():
        freq_lbl = f"{v.passaggi_settimanali:g} passaggi/sett." if v.passaggi_settimanali >= 1 else "Quindicinale / Mensile"
        amb_rows.append([
            v.nome_ambiente,
            f"{v.metri_quadri:g} m²",
            freq_lbl,
            f"{v.ore_per_intervento:g} h",
            f"{v.ore_settimanali_ambiente:g} h/sett",
        ])
    amb_rows.append([
        'TOTALE MONTE ORE PREVISTO',
        f"{prev.totale_mq:g} m²",
        f"{prev.ore_settimanali_stimate:g} h/settimana",
        '—',
        f"{prev.ore_mensili_stimate:g} h/mese",
    ])
    t_amb = Table(amb_rows, colWidths=[66*mm, 28*mm, 34*mm, 23*mm, 23*mm])
    t_amb.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EFF6FF')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_amb)

    if prev.note_capitolato:
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph("Capitolato Operativo e Prodotti Inclusi", h2_st))
        elements.append(Paragraph(prev.note_capitolato.replace('\n', '<br/>'), body_st))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("Condizioni Economiche Riservate (IVA Esclusa)", h2_st))
    canone_off = prev.canone_finale_offerto if prev.canone_finale_offerto > 0 else prev.canone_consigliato_mensile
    econ_rows = [
        ['Descrizione Voce', 'Importo Netto'],
        [f'Canone Mensile Onnicomprensivo (personale qualificato, prodotti professionali, attrezzature e assicurazione RCT)', f"€ {canone_off:,.2f} / mese"],
    ]
    if prev.importo_una_tantum_sgrosso and prev.importo_una_tantum_sgrosso > 0:
        econ_rows.append(['Intervento iniziale Una Tantum di sgrosso / primo impianto', f"€ {prev.importo_una_tantum_sgrosso:,.2f}"])

    t_econ = Table(econ_rows, colWidths=[134*mm, 40*mm])
    t_econ.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#A7F3D0')),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_econ)

    elements.append(Spacer(1, 12*mm))
    firme = Table([
        ['Per Kandor S.r.l.', 'Per Accettazione del Cliente (Timbro e Firma)'],
        ['La Direzione Commerciale', '_______________________________________'],
    ], colWidths=[87*mm, 87*mm])
    firme.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
    ]))
    elements.append(firme)

    doc.build(elements)
    buffer.seek(0)
    resp = HttpResponse(buffer, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{prev.numero_preventivo}_{prev.ragione_sociale_prospect[:20]}.pdf"'
    return resp


# ==============================================================================
# 5. PRE-FATTURAZIONE ATTIVA E RICONCILIAZIONE LAVORI EXTRA / STRAORDINARI
# ==============================================================================

@staff_or_titolare_required
def pre_fatturazione_view(request):
    from .ai_engine import analizza_marginalita_e_budget_clienti

    today = timezone.now().date()
    mese = int(request.GET.get('mese', today.month))
    anno = int(request.GET.get('anno', today.year))
    _, last_day = calendar.monthrange(anno, mese)
    inizio_mese = date(anno, mese, 1)
    fine_mese = date(anno, mese, last_day)

    # 1. Lavori Straordinari del mese
    straordinari = list(
        RichiestaStraordinaria.objects.filter(
            data_inizio__gte=inizio_mese,
            data_inizio__lte=fine_mese,
        ).select_related('cliente').order_by('-data_inizio')
    )

    # 2. Lavori Extra intercettati da ai_engine nelle note dei dipendenti su turni ordinari
    ia_budget = analizza_marginalita_e_budget_clienti(mese=mese, anno=anno)
    lavori_extra_ia = ia_budget.get('lavori_extra_rilevati', [])

    # 3. Costruisci il Prospetto Mensile di Pre-Fatturazione per ogni Cliente attivo
    clienti_qs = list(Cliente.objects.prefetch_related('storico_contratti').order_by('ragione_sociale'))
    tt_mese = list(
        TimeTracking.objects.filter(
            assegnazione__turno__data__gte=inizio_mese,
            assegnazione__turno__data__lte=fine_mese,
        ).select_related('assegnazione__cliente')
    )
    ore_per_cl = {}
    for tt in tt_mese:
        cid = tt.assegnazione.cliente_id
        ore_per_cl[cid] = ore_per_cl.get(cid, 0.0) + float(tt.durata_ore or 0)

    straord_per_cl = {}
    for s in straordinari:
        straord_per_cl.setdefault(s.cliente_id, []).append(s)

    prospetto_clienti = []
    tot_canoni_fissi = 0.0
    tot_straordinari_da_fatturare = 0.0
    tot_straordinari_fatturati = 0.0
    tot_conguagli_ore = 0.0
    tot_generale_fatturabile = 0.0

    for c in clienti_qs:
        canone = float(c.importo_mensile_contratto or 0)
        ore_contr = float(c.ore_mensili_contratto or 0)
        ore_lav = round(ore_per_cl.get(c.id, 0.0), 1)
        str_list = straord_per_cl.get(c.id, [])

        if canone <= 0 and not str_list and ore_lav <= 0:
            continue

        da_fatt_val = sum(float(s.prezzo_concordato or 0) for s in str_list if s.stato_fatturazione == 'DA_FATTURARE')
        fatt_val = sum(float(s.prezzo_concordato or 0) for s in str_list if s.stato_fatturazione == 'FATTURATO')
        inclusi_cnt = sum(1 for s in str_list if s.stato_fatturazione == 'INCLUSO_NEL_CANONE')

        scostamento_ore = round(ore_lav - ore_contr, 1) if ore_contr > 0 else 0.0
        tariffa_h = c.importo_orario or 18.0
        conguaglio_consigliato = round(scostamento_ore * tariffa_h, 2) if scostamento_ore >= 3.0 else 0.0

        totale_riga = round(canone + da_fatt_val + fatt_val, 2)

        prospetto_clienti.append({
            'cliente': c,
            'canone_fisso': canone,
            'ore_contratto': ore_contr,
            'ore_lavorate': ore_lav,
            'scostamento_ore': scostamento_ore,
            'straordinari': str_list,
            'straordinari_da_fatturare': round(da_fatt_val, 2),
            'straordinari_fatturati': round(fatt_val, 2),
            'straordinari_inclusi_cnt': inclusi_cnt,
            'conguaglio_consigliato': conguaglio_consigliato,
            'totale_fatturabile': totale_riga,
        })

        tot_canoni_fissi += canone
        tot_straordinari_da_fatturare += da_fatt_val
        tot_straordinari_fatturati += fatt_val
        tot_conguagli_ore += conguaglio_consigliato
        tot_generale_fatturabile += totale_riga

    mesi_options = [{'num': m, 'nome': MESI_NOMI[m], 'selected': m == mese} for m in range(1, 13)]

    return render(request, 'core/pre_fatturazione.html', {
        'mese': mese,
        'anno': anno,
        'mese_nome': MESI_NOMI.get(mese, ''),
        'mesi_options': mesi_options,
        'straordinari': straordinari,
        'lavori_extra_ia': lavori_extra_ia,
        'prospetto_clienti': prospetto_clienti,
        'clienti_tutti': clienti_qs,
        'tot_canoni_fissi': round(tot_canoni_fissi, 2),
        'tot_straordinari_da_fatturare': round(tot_straordinari_da_fatturare, 2),
        'tot_straordinari_fatturati': round(tot_straordinari_fatturati, 2),
        'tot_conguagli_ore': round(tot_conguagli_ore, 2),
        'tot_generale_fatturabile': round(tot_generale_fatturabile, 2),
        'today_iso': today.strftime('%Y-%m-%d'),
    })


@csrf_exempt
@staff_or_titolare_api_required
def pre_fatturazione_api(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo non consentito'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else request.POST
    except Exception:
        data = request.POST

    action = (data.get('action') or '').strip()

    if action == 'aggiorna_straordinario':
        str_id = data.get('straordinario_id')
        item = get_object_or_404(RichiestaStraordinaria, pk=str_id)
        if 'stato_fatturazione' in data:
            item.stato_fatturazione = data['stato_fatturazione']
        if 'prezzo_concordato' in data and str(data['prezzo_concordato']).strip() != '':
            item.prezzo_concordato = Decimal(str(data['prezzo_concordato']).replace(',', '.'))
        if 'numero_fattura_rif' in data:
            item.numero_fattura_rif = (data['numero_fattura_rif'] or '').strip()
        if 'completata' in data:
            item.completata = bool(data['completata'])
        item.save()
        return JsonResponse({
            'ok': True,
            'message': f'Straordinario #{item.id} ({item.cliente.ragione_sociale}) aggiornato: {item.get_stato_fatturazione_display()} — €{item.prezzo_concordato:.2f}.',
        })

    elif action == 'crea_straordinario_da_extra_ia':
        cliente_id = data.get('cliente_id')
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        data_str = (data.get('data') or timezone.now().date().strftime('%Y-%m-%d')).strip()
        try:
            d_ini = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            d_ini = timezone.now().date()
        descrizione = (data.get('descrizione') or 'Lavoro extra rilevato da note turno').strip()
        prezzo = Decimal(str(data.get('prezzo_concordato') or '0').replace(',', '.'))
        stato_fatt = (data.get('stato_fatturazione') or 'DA_FATTURARE').strip()

        nuovo = RichiestaStraordinaria.objects.create(
            cliente=cliente,
            data_inizio=d_ini,
            ora_inizio=time(8, 0),
            ora_fine=time(12, 0),
            descrizione=descrizione,
            completata=True,
            stato_fatturazione=stato_fatt,
            prezzo_concordato=prezzo,
        )
        return JsonResponse({
            'ok': True,
            'message': f'Creata voce straordinaria da fatturare per {cliente.ragione_sociale} (€{nuovo.prezzo_concordato:.2f}).',
            'id': nuovo.id,
        })

    return JsonResponse({'ok': False, 'error': f'Azione non riconosciuta: {action}'}, status=400)


@staff_or_titolare_required
def export_pre_fatturazione_csv(request):
    """Esporta il prospetto mensile di Pre-Fatturazione in formato CSV/Excel per il Commercialista."""
    import csv

    today = timezone.now().date()
    mese = int(request.GET.get('mese', today.month))
    anno = int(request.GET.get('anno', today.year))
    _, last_day = calendar.monthrange(anno, mese)
    inizio_mese = date(anno, mese, 1)
    fine_mese = date(anno, mese, last_day)

    straordinari = list(
        RichiestaStraordinaria.objects.filter(
            data_inizio__gte=inizio_mese,
            data_inizio__lte=fine_mese,
        ).select_related('cliente')
    )
    straord_per_cl = {}
    for s in straordinari:
        straord_per_cl.setdefault(s.cliente_id, []).append(s)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="pre_fatturazione_{MESI_NOMI.get(mese, mese)}_{anno}.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Ragione Sociale', 'Partita IVA', 'Codice Fiscale',
        'Canone Mensile Fisso (EUR)', 'Straordinari Da Fatturare (EUR)',
        'Straordinari Gia Fatturati (EUR)', 'Totale Imponibile Mese (EUR)',
        'Dettaglio Lavori Straordinari / Note Fattura'
    ])

    for c in Cliente.objects.all().order_by('ragione_sociale'):
        canone = float(c.importo_mensile_contratto or 0)
        str_list = straord_per_cl.get(c.id, [])
        if canone <= 0 and not str_list:
            continue
        da_fatt = sum(float(s.prezzo_concordato or 0) for s in str_list if s.stato_fatturazione == 'DA_FATTURARE')
        gia_fatt = sum(float(s.prezzo_concordato or 0) for s in str_list if s.stato_fatturazione == 'FATTURATO')
        tot = round(canone + da_fatt + gia_fatt, 2)
        dettagli = " | ".join(
            f"{s.data_inizio.strftime('%d/%m')}: {s.descrizione} (€{s.prezzo_concordato:.2f} - {s.get_stato_fatturazione_display()})"
            for s in str_list
        )
        writer.writerow([
            c.ragione_sociale,
            c.partita_iva or '',
            c.codice_fiscale or '',
            f"{canone:.2f}".replace('.', ','),
            f"{da_fatt:.2f}".replace('.', ','),
            f"{gia_fatt:.2f}".replace('.', ','),
            f"{tot:.2f}".replace('.', ','),
            dettagli,
        ])

    return response
