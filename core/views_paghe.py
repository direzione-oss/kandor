"""
Viste dedicate a Paghe, Cedolini, Verifica Ore Mensili, Riconciliazione e Analisi Contratti.
Tutte le viste delegano i calcoli a `core.paghe_service` (Single Source of Truth).
"""
import csv
import io
import json
from datetime import date, timedelta, time
from xml.sax.saxutils import escape as xml_escape

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Cliente, Dipendente, TimeTracking, ModificaCedolino, to_decimal, Assenza, Turno, AssegnazioneTurno
from .utils_ore import parse_ore_input, format_ore_hhmm, format_ore_estese
from .paghe_service import (
    MESI_NOMI,
    calcola_ore_lavorate_record,
    calcola_dataset_paghe,
    calcola_verifica_ore_mensile,
    calcola_analisi_contratti,
    genera_pdf_calendario_dipendente,
    invia_pdf_calendario_telegram,
)
from .views import staff_or_titolare_required, staff_or_titolare_api_required


@staff_or_titolare_required
def reconciliation_view(request):
    mesi = [(num, nome) for num, nome in MESI_NOMI.items()]

    today = timezone.now().date()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    report_data = []
    clienti = Cliente.objects.prefetch_related('storico_contratti').all()

    for cliente in clienti:
        timetracks = TimeTracking.objects.filter(
            assegnazione__cliente=cliente
        ).filter(
            Q(assegnazione__turno__data__year=selected_year, assegnazione__turno__data__month=selected_month)
            | Q(check_in__year=selected_year, check_in__month=selected_month)
        ).distinct()

        ore_reali = round(sum(calcola_ore_lavorate_record(t) for t in timetracks), 2)
        ore_previste_dec, _ = cliente.get_condizioni_contrattuali_mese(selected_year, selected_month)
        ore_previste = float(ore_previste_dec)
        diff = round(ore_reali - ore_previste, 2)

        status = 'OK'
        if diff < -5:
            status = 'ALARM'
        elif diff > 5:
            status = 'WARNING'

        report_data.append({
            'cliente': cliente,
            'ore_previste': ore_previste,
            'ore_reali': ore_reali,
            'diff': diff,
            'status': status,
        })

    return render(request, 'core/reconciliation.html', {
        'mesi': mesi,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'report_data': report_data,
    })


def _resolve_soglia_and_periodo(request):
    today = timezone.now().date()
    soglia_param = request.GET.get('soglia', None)
    if soglia_param:
        try:
            soglia = float(soglia_param)
            request.session['analisi_soglia'] = soglia
        except (ValueError, TypeError):
            soglia = request.session.get('analisi_soglia', 15.0)
    else:
        soglia = request.session.get('analisi_soglia', 15.0)

    try:
        mese = int(request.GET.get('mese', today.month))
    except (ValueError, TypeError):
        mese = today.month

    try:
        anno = int(request.GET.get('anno', today.year))
    except (ValueError, TypeError):
        anno = today.year

    return soglia, mese, anno, today


@staff_or_titolare_required
def analisi_contratti_view(request):
    """Analisi economica & Contabilità Industriale dei contratti: MOL reale, costo personale per livello, materiali, mezzi e semaforo direzionale."""
    from .views_erp_pro import calcola_contabilita_industriale_mese
    from .models import DotazioneCantiere

    soglia, mese, anno, _ = _resolve_soglia_and_periodo(request)
    filtro_semaforo = (request.GET.get('semaforo') or '').strip().upper()

    dati = calcola_contabilita_industriale_mese(anno=anno, mese=mese, soglia_oraria=soglia)

    dot_counts = {}
    for d in DotazioneCantiere.objects.filter(stato__in=['IN_CANTIERE', 'DA_RITIRARE']):
        dot_counts[d.cliente_id] = dot_counts.get(d.cliente_id, 0) + d.quantita

    righe_tutte = dati['analisi']
    analisi = []
    for r in righe_tutte:
        r['dotazioni_attive'] = dot_counts.get(r['cliente_id'], 0)
        if filtro_semaforo and r['semaforo'] != filtro_semaforo:
            continue
        analisi.append(r)

    mesi_list = [
        {
            'value': num,
            'nome': nome,
            'selected': 'selected' if num == mese else '',
        }
        for num, nome in MESI_NOMI.items()
    ]

    sotto_soglia = dati['sotto_soglia']
    sotto_soglia_html = ''
    if sotto_soglia:
        badges = [
            f'<span style="background: {c["semaforo_color"]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 12.5px;">'
            f'{c["cliente"]} &mdash; MOL {c["mol_euro_fmt"]} ({c["mol_perc_fmt"]})</span>'
            for c in sotto_soglia
        ]
        sotto_soglia_html = ' '.join(badges)

    context = {
        'analisi': analisi,
        'contabilita': dati,
        'filtro_semaforo': filtro_semaforo,
        'sotto_soglia': sotto_soglia,
        'sotto_soglia_html': sotto_soglia_html,
        'soglia': soglia,
        'mese': mese,
        'mesi': mesi_list,
        'mese_nome': dati['mese_nome'],
        'anno': anno,
        'ore_header': f'Ore Lavorate<br><small>{dati["mese_nome"]} {anno}</small>',
        'totale_contratti': len(analisi),
        'totale_fatturato': dati['totale_fatturato'],
        'media_oraria': dati['media_oraria'],
    }
    return render(request, 'core/analisi_contratti.html', context)


@staff_or_titolare_required
def pdf_contratti_sotto_soglia(request):
    """Genera PDF Contabilità Industriale & Contratti Sotto Soglia / In Perdita."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from .views_erp_pro import calcola_contabilita_industriale_mese

    soglia, mese, anno, today = _resolve_soglia_and_periodo(request)
    dati = calcola_contabilita_industriale_mese(anno=anno, mese=mese, soglia_oraria=soglia)
    solo_critici = request.GET.get('tutti') != '1'
    righe_pdf = dati['sotto_soglia'] if solo_critici else dati['analisi']
    if not righe_pdf:
        righe_pdf = dati['analisi']
    mese_nome = dati['mese_nome']

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=16, textColor=colors.HexColor('#1a5276'))
    elements.append(Paragraph('Contabilità Industriale Cantieri & Analisi Marginalità (MOL)', title_style))
    elements.append(Spacer(1, 4 * mm))

    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#555'))
    elements.append(Paragraph(
        f'Periodo: {mese_nome} {anno} | Soglia Oraria: {soglia:.2f} EUR/h | '
        f'Ricavi Tot: {dati["totale_ricavi_val"]:,.2f} EUR | '
        f'MOL Aziendale: {dati["totale_mol_val"]:,.2f} EUR ({dati["totale_mol_perc"]:.1f}%)',
        info_style
    ))
    elements.append(Spacer(1, 6 * mm))

    if righe_pdf:
        data = [['Cliente / Cantiere', 'Ricavi Tot.', 'Ore (Lav/Ctr)', 'Costo Pers.', 'Materiali', 'Mezzi', 'MOL EUR', 'MOL %', 'Semaforo']]
        for row in righe_pdf:
            data.append([
                row['cliente'][:38],
                f"{row['ricavi_totali_val']:,.2f} EUR",
                f"{row['ore_lavorate_val']:g}h / {row['ore_contratto_val']:g}h",
                f"{row['costo_personale_val']:,.2f} EUR",
                f"{row['costo_materiali_val']:,.2f} EUR",
                f"{row['costo_mezzi_val']:,.2f} EUR",
                f"{row['mol_euro_val']:,.2f} EUR",
                f"{row['mol_perc_val']:.1f}%",
                row['semaforo'],
            ])

        table = Table(data, colWidths=[72 * mm, 26 * mm, 28 * mm, 26 * mm, 24 * mm, 22 * mm, 26 * mm, 20 * mm, 23 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 8.5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('TOPPADDING', (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('FONTNAME', (6, 1), (7, -1), 'Helvetica-Bold'),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph('Nessun contratto presente per i criteri selezionati.', styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    nome_file = f'contabilita_industriale_cantieri_{mese_nome}{anno}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{nome_file}"'
    return response


@csrf_exempt
@staff_or_titolare_required
def verifica_ore_view(request):
    """Dashboard verifica ore mensili: confronto ore lavorate vs contrattuali."""
    now = timezone.now()
    mese = int(request.GET.get('mese', now.month))
    anno = int(request.GET.get('anno', now.year))

    dati = calcola_verifica_ore_mensile(mese=mese, anno=anno)

    mesi_options = [
        {'numero': m, 'nome': MESI_NOMI[m], 'selected': m == mese}
        for m in range(1, 13)
    ]
    anni_options = list(range(anno - 2, anno + 2))

    context = {
        'clienti_list': dati['clienti_list'],
        'totale_clienti': dati['totale_clienti'],
        'squadre_list': dati['squadre_list'],
        'assenze_list': dati['assenze_list'],
        'totale_assenze': dati['totale_assenze'],
        'mese': mese,
        'anno': anno,
        'mese_nome': dati['mese_nome'],
        'mesi_options': mesi_options,
        'anni_options': anni_options,
    }
    return render(request, 'admin/verifica_ore.html', context)


@csrf_exempt
@staff_or_titolare_required
def pdf_verifica_ore(request):
    """Genera PDF report verifica ore mensili usando `calcola_verifica_ore_mensile`."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    now = timezone.now()
    mese = int(request.GET.get('mese', now.month))
    anno = int(request.GET.get('anno', now.year))

    dati = calcola_verifica_ore_mensile(mese=mese, anno=anno)
    mese_nome = dati['mese_nome']
    clienti_list = dati['clienti_list']
    squadre_list = dati['squadre_list']
    assenze_list = dati['assenze_list']
    totale_assenze = dati['totale_assenze']

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=15 * mm,
        bottomMargin=12 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#417690'), spaceAfter=6 * mm)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor('#417690'), spaceAfter=4 * mm, spaceBefore=6 * mm)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8)

    elements.append(Paragraph(f"Report Verifica Ore — {mese_nome} {anno}", title_style))
    elements.append(Paragraph(f"Generato il {now.strftime('%d/%m/%Y %H:%M')}", small_style))
    elements.append(Spacer(1, 6 * mm))

    # === TABELLA CLIENTI ===
    elements.append(Paragraph("Riepilogo per Cliente", subtitle_style))
    cl_header = ['Cliente', 'Ore Contratto', 'Ore Lavorate', 'Ore Validate', 'Differenza', '€ Contratto', '€ Calcolato']
    cl_rows = [cl_header]

    for c in clienti_list:
        diff_str = f"+{c['diff']}" if c['diff'] > 0 else str(c['diff'])
        cl_rows.append([
            c['ragione_sociale'],
            f"{c['ore_contratto']:.1f}",
            f"{c['ore_lavorate']:.1f}",
            f"{c['ore_validate']:.1f}",
            diff_str,
            f"€{c['importo_contratto']:.2f}",
            f"€{c['importo_calcolato']:.2f}",
        ])

    tc = dati['totale_clienti']
    diff_tot_str = f"+{tc['diff']}" if tc['diff'] > 0 else str(tc['diff'])
    cl_rows.append([
        'TOTALE',
        f"{tc['ore_contratto']:.1f}",
        f"{tc['ore_lavorate']:.1f}",
        f"{tc['ore_validate']:.1f}",
        diff_tot_str,
        f"€{tc['importo_contratto']:.2f}",
        f"€{tc['importo_calcolato']:.2f}",
    ])

    cl_table = Table(cl_rows, colWidths=[160, 80, 80, 80, 70, 90, 90])
    cl_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#417690')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f0f5')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]
    for i, c in enumerate(clienti_list, start=1):
        if c['diff'] < 0:
            cl_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#e74c3c')))
        elif c['diff'] > 0:
            cl_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#27ae60')))

    cl_table.setStyle(TableStyle(cl_style))
    elements.append(cl_table)
    elements.append(Spacer(1, 8 * mm))

    # === TABELLA SQUADRE/DIPENDENTI ===
    elements.append(Paragraph("Riepilogo per Squadra e Dipendente", subtitle_style))
    sq_rows = [['Squadra / Dipendente', 'Ore Totali', 'Dettaglio Clienti']]
    for sq in squadre_list:
        sq_rows.append([f"▸ {sq['nome']}", f"{sq['ore_totali']}h", ''])
        for d in sq['dipendenti_list']:
            sq_rows.append([f"    {d['nome']}", f"{d['ore_totali']}h", Paragraph(d['clienti_str'], small_style)])

    sq_table = Table(sq_rows, colWidths=[180, 80, 420])
    sq_style_rules = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#417690')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    row_idx = 1
    for sq in squadre_list:
        sq_style_rules.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#e8f0f5')))
        sq_style_rules.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
        row_idx += 1 + len(sq['dipendenti_list'])

    sq_table.setStyle(TableStyle(sq_style_rules))
    elements.append(sq_table)
    elements.append(Spacer(1, 8 * mm))

    # === TABELLA ASSENZE ===
    if assenze_list:
        elements.append(Paragraph("Riepilogo Assenze del Mese", subtitle_style))
        ass_rows = [['Dipendente', 'Malattia', 'Ferie', 'Permesso', 'L.104', 'Altro', 'Totale gg', 'Dettaglio']]
        for a in assenze_list:
            det_str = '; '.join(a['dettagli_pdf'])
            ass_rows.append([
                a['nome'],
                str(a['MALATTIA']) if a['MALATTIA'] else '-',
                str(a['FERIE']) if a['FERIE'] else '-',
                str(a['PERMESSO']) if a['PERMESSO'] else '-',
                str(a['104']) if a['104'] else '-',
                str(a['ALTRO']) if a['ALTRO'] else '-',
                str(a['totale_giorni']),
                Paragraph(det_str, small_style),
            ])
        ass_rows.append([
            'TOTALE',
            str(totale_assenze['MALATTIA']),
            str(totale_assenze['FERIE']),
            str(totale_assenze['PERMESSO']),
            str(totale_assenze['104']),
            str(totale_assenze['ALTRO']),
            str(totale_assenze['totale_giorni']),
            '',
        ])

        ass_table = Table(ass_rows, colWidths=[130, 55, 55, 55, 45, 45, 55, 240])
        ass_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e65100')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (6, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fef3e8')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fce4cc')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(ass_table)

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    nome_file = f'verifica_ore_{mese_nome}_{anno}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{nome_file}"'
    return response


# ==============================================================================
# REPORT CEDOLINI PAGHE (WEB, PDF, CSV, AJAX RETTIFICA)
# ==============================================================================

@staff_or_titolare_required
def report_paghe_view(request):
    """
    Report Elaborazione Cedolini Paghe da Data Inizio a Data Fine.
    Usa `calcola_dataset_paghe` come unica fonte di verità.
    Supporta filtri per escludere chi non ha ore e per stato validazione ore.
    """
    solo_con_ore_param = request.GET.get('solo_con_ore', '')
    stato_validazione_param = request.GET.get('stato_validazione', '')

    dataset = calcola_dataset_paghe(
        str_inizio=request.GET.get('data_inizio', ''),
        str_fine=request.GET.get('data_fine', ''),
        dipendente_id=request.GET.get('dipendente_id', ''),
        build_calendar=True,
        solo_con_ore=solo_con_ore_param,
        stato_validazione=stato_validazione_param,
    )
    data_inizio = dataset['data_inizio']
    data_fine = dataset['data_fine']

    context = {
        'report_list': dataset['report_list'],
        'totale_generale': dataset['totale_generale'],
        'data_inizio': data_inizio.strftime('%Y-%m-%d'),
        'data_fine': data_fine.strftime('%Y-%m-%d'),
        'data_inizio_formatted': data_inizio.strftime('%d/%m/%Y'),
        'data_fine_formatted': data_fine.strftime('%d/%m/%Y'),
        'dipendente_id': dataset['dipendente_id_int'],
        'all_dipendenti': dataset['all_dipendenti'],
        'solo_con_ore': dataset['solo_con_ore'],
        'stato_validazione': dataset['stato_validazione'],
    }
    return render(request, 'admin/report_paghe.html', context)


@csrf_exempt
@staff_or_titolare_required
def pdf_report_paghe(request):
    """Genera report PDF per la consulenza paghe usando `calcola_dataset_paghe`."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    now = timezone.now().date()
    dataset = calcola_dataset_paghe(
        str_inizio=request.GET.get('data_inizio', ''),
        str_fine=request.GET.get('data_fine', ''),
        dipendente_id=request.GET.get('dipendente_id', ''),
        build_calendar=False,
    )
    data_inizio = dataset['data_inizio']
    data_fine = dataset['data_fine']
    report_list = dataset['report_list']
    totale_generale = dataset['totale_generale']

    response = HttpResponse(content_type='application/pdf')
    filename = f"report_cedolini_paghe_{data_inizio.strftime('%d%m%Y')}_{data_fine.strftime('%d%m%Y')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12,
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold',
    )

    story = []
    story.append(Paragraph("KANDOR — REPORT ELABORAZIONE CEDOLINI PAGHE", title_style))
    periodo_str = f"Periodo dal <b>{data_inizio.strftime('%d/%m/%Y')}</b> al <b>{data_fine.strftime('%d/%m/%Y')}</b> — Generato il {now.strftime('%d/%m/%Y')}"
    story.append(Paragraph(periodo_str, sub_style))

    table_data = [
        [
            Paragraph("Dipendente", cell_bold),
            Paragraph("Codice Fiscale", cell_bold),
            Paragraph("G. Lav.", cell_bold),
            Paragraph("Ore Totali", cell_bold),
            Paragraph("Ore Valid.", cell_bold),
            Paragraph("Ferie", cell_bold),
            Paragraph("Perm.", cell_bold),
            Paragraph("Malatt.", cell_bold),
            Paragraph("Altri/104", cell_bold),
            Paragraph("Dettaglio Cantieri", cell_bold),
        ]
    ]

    for item in report_list:
        nome_disp = f"{item['cognome_nome']} *" if item['is_rettificato'] else item['cognome_nome']
        cantieri_p = item['clienti_raw'] or "---"

        table_data.append([
            Paragraph(nome_disp, cell_bold),
            Paragraph(item['codice_fiscale'], cell_style),
            Paragraph(str(item['giorni_lavorati']), cell_style),
            Paragraph(f"{round(item['ore_lavorate'], 1)}h", cell_style),
            Paragraph(f"{round(item['ore_validate'], 1)}h", cell_style),
            Paragraph(f"{item['assenze_dict']['FERIE']}gg", cell_style),
            Paragraph(f"{item['assenze_dict']['PERMESSO']}gg", cell_style),
            Paragraph(f"{item['assenze_dict']['MALATTIA']}gg", cell_style),
            Paragraph(f"{item['altri_e_104']}gg", cell_style),
            Paragraph(cantieri_p, cell_style),
        ])

    table_data.append([
        Paragraph("<b>TOTALE GENERALE</b>", cell_bold),
        Paragraph("", cell_style),
        Paragraph(f"<b>{totale_generale['giorni_lavorati_totali']}</b>", cell_bold),
        Paragraph(f"<b>{round(totale_generale['ore_lavorate_totali'], 1)}h</b>", cell_bold),
        Paragraph(f"<b>{round(totale_generale['ore_validate_totali'], 1)}h</b>", cell_bold),
        Paragraph(f"<b>{totale_generale['ferie_totali']}gg</b>", cell_bold),
        Paragraph(f"<b>{totale_generale['permessi_totali']}gg</b>", cell_bold),
        Paragraph(f"<b>{totale_generale['malattia_totale']}gg</b>", cell_bold),
        Paragraph(f"<b>{totale_generale['altri_e_104_totali']}gg</b>", cell_bold),
        Paragraph("", cell_style),
    ])

    col_widths = [110, 100, 45, 55, 55, 40, 40, 45, 45, 230]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEF2F2')),
    ]))

    story.append(t)
    if dataset['ha_rettifiche']:
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "<i>* Note: I dipendenti contrassegnati con (*) presentano modifiche/rettifiche manuali apportate dall'Amministrazione.</i>",
            cell_style,
        ))

    day_style = ParagraphStyle('day', fontSize=8, textColor=colors.gray, alignment=2)
    mid_style = ParagraphStyle('mid', fontSize=14, alignment=1)

    cal_style = TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 4),
    ])

    for item in report_list:
        story.append(PageBreak())
        story.append(Paragraph(f"Dettaglio Mensile - {item['cognome_nome']}", title_style))
        story.append(Paragraph(f"Periodo: {data_inizio.strftime('%d/%m/%Y')} - {data_fine.strftime('%d/%m/%Y')}", sub_style))

        cal_data = [['LUN', 'MAR', 'MER', 'GIO', 'VEN', 'SAB', 'DOM']]
        row = ['', '', '', '', '', '', '']

        curr_d = data_inizio
        while curr_d <= data_fine:
            wd = curr_d.weekday()
            cell_flowables = [Paragraph(str(curr_d.day), day_style)]

            ore = item['ore_per_giorno'].get(curr_d, 0.0)
            assenze = item['assenze_per_giorno'].get(curr_d, [])
            note_giorno = item['note_per_giorno'].get(curr_d, [])

            middle = ""
            if ore > 0:
                middle += f"<b>{round(ore, 1)}</b>"
            if assenze:
                if middle:
                    middle += "<br/>"
                middle += f"<font size=8>{'+'.join(assenze)}</font>"
            if note_giorno:
                note_escaped = xml_escape(" | ".join(note_giorno))
                if middle:
                    middle += "<br/>"
                middle += f"<font size=6.5 color='#1e40af'><i>{note_escaped}</i></font>"

            if middle:
                cell_flowables.append(Spacer(1, 8))
                cell_flowables.append(Paragraph(middle, mid_style))
            else:
                cell_flowables.append(Spacer(1, 25))

            row[wd] = cell_flowables

            if wd == 6 or curr_d == data_fine:
                cal_data.append(row)
                row = ['', '', '', '', '', '', '']

            curr_d += timedelta(days=1)

        t_cal = Table(cal_data, colWidths=[110] * 7)
        t_cal.setStyle(cal_style)
        story.append(t_cal)

    doc.build(story)
    return response


@csrf_exempt
@staff_or_titolare_required
def export_paghe_csv(request):
    """Esporta i dati elaborazione paghe in formato CSV con codifica UTF-8 BOM per Excel."""
    dataset = calcola_dataset_paghe(
        str_inizio=request.GET.get('data_inizio', ''),
        str_fine=request.GET.get('data_fine', ''),
        dipendente_id=request.GET.get('dipendente_id', ''),
        build_calendar=False,
    )
    data_inizio = dataset['data_inizio']
    data_fine = dataset['data_fine']

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"export_cedolini_paghe_{data_inizio.strftime('%Y%m%d')}_{data_fine.strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    response.write('\ufeff')  # BOM per Microsoft Excel UTF-8
    writer = csv.writer(response, delimiter=';')

    writer.writerow([
        'ID Dipendente', 'Cognome', 'Nome', 'Codice Fiscale',
        'Data Inizio', 'Data Fine',
        'Giorni Lavorati', 'Ore Lavorate Totali', 'Ore Validate', 'Ore Non Validate',
        'Giorni Ferie', 'Giorni Permesso', 'Giorni Malattia', 'Giorni Infortunio', 'Giorni 104', 'Altri Giorni Assenza',
        'Rettificato Admin', 'Note Rettifica',
        'Dettaglio Cantieri / Clienti'
    ])

    for item in dataset['report_list']:
        ore_lav = item['ore_lavorate']
        ore_val = item['ore_validate']
        ore_non_val = round(ore_lav - ore_val, 2)
        ass = item['assenze_dict']

        writer.writerow([
            item['dip_id'],
            item['cognome'],
            item['nome'],
            item['cf_raw'],
            data_inizio.strftime('%d/%m/%Y'),
            data_fine.strftime('%d/%m/%Y'),
            item['giorni_lavorati'],
            str(round(ore_lav, 2)).replace('.', ','),
            str(round(ore_val, 2)).replace('.', ','),
            str(ore_non_val).replace('.', ','),
            ass['FERIE'],
            ass['PERMESSO'],
            ass['MALATTIA'],
            ass['INFORTUNIO'],
            ass['104'],
            ass['ALTRO'],
            "SÌ" if item['is_rettificato'] else "NO",
            item['modifica_note'],
            item['clienti_raw'],
        ])

    return response


@csrf_exempt
@staff_or_titolare_required
def pdf_calendario_dipendente_view(request, dipendente_id):
    """
    Genera e visualizza/scarica il PDF del prospetto analitico calendario
    per un singolo dipendente nel periodo selezionato.
    """
    str_inizio = request.GET.get('data_inizio', '')
    str_fine = request.GET.get('data_fine', '')

    dataset = calcola_dataset_paghe(
        str_inizio=str_inizio,
        str_fine=str_fine,
        dipendente_id=dipendente_id,
        build_calendar=True,
    )
    if not dataset['report_list']:
        return HttpResponse("Nessun dato trovato per questo dipendente nel periodo specificato.", status=404)

    item = dataset['report_list'][0]
    data_inizio = dataset['data_inizio']
    data_fine = dataset['data_fine']

    pdf_bytes = genera_pdf_calendario_dipendente(item, data_inizio, data_fine)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    cf = item.get('cf_raw') or f"ID{dipendente_id}"
    filename = f"calendario_ore_{data_inizio.strftime('%Y%m')}_{cf}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@csrf_exempt
@staff_or_titolare_api_required
def invia_calendario_telegram_singolo_api(request):
    """
    Invia il PDF calendario al singolo dipendente via Bot Telegram.
    REGOLA FERREA:
    Blocca categoricamente l'invio se ci sono ore non convalidate nel periodo selezionato.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo POST richiesto.'}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        dipendente_id = data.get('dipendente_id')
        str_inizio = data.get('data_inizio', '')
        str_fine = data.get('data_fine', '')

        if not dipendente_id:
            return JsonResponse({'ok': False, 'error': 'Parametro dipendente_id mancante.'}, status=400)

        dipendente = Dipendente.objects.filter(pk=int(dipendente_id)).first()
        if not dipendente:
            return JsonResponse({'ok': False, 'error': 'Dipendente non trovato.'}, status=404)

        dataset = calcola_dataset_paghe(
            str_inizio=str_inizio,
            str_fine=str_fine,
            dipendente_id=dipendente_id,
            build_calendar=True,
        )
        if not dataset['report_list']:
            return JsonResponse({'ok': False, 'error': 'Nessun record presente per questo dipendente nel periodo.'}, status=404)

        item = dataset['report_list'][0]
        data_inizio = dataset['data_inizio']
        data_fine = dataset['data_fine']

        # CONTROLLO BLOCCANTE RIGOROSO: ore non convalidate
        ore_non_val = item.get('ore_non_validate', 0.0)
        if ore_non_val > 0.0:
            return JsonResponse({
                'ok': False,
                'error': f"Impossibile inviare il documento: sono presenti {ore_non_val} ore non convalidate per {item['cognome_nome']}. Tutte le ore devono essere prima validate dall'Amministrazione!"
            })

        if not item.get('ha_telegram'):
            return JsonResponse({
                'ok': False,
                'error': f"{item['cognome_nome']} non ha collegato il Bot Telegram (@kandor_gestionale_bot). Invio non disponibile."
            })

        pdf_bytes = genera_pdf_calendario_dipendente(item, data_inizio, data_fine)
        result = invia_pdf_calendario_telegram(dipendente, data_inizio, data_fine, pdf_bytes, item=item)
        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@staff_or_titolare_api_required
def invia_calendari_telegram_massivo_api(request):
    """
    Invia massivamente il PDF calendario a TUTTI i dipendenti che risultano:
    - con ore lavorate > 0
    - COMPLETAMENTE VALIDATI (0 ore non validate)
    - con Bot Telegram collegato
    Salta ed elenca tutti gli esclusi (non validati o senza bot).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Metodo POST richiesto.'}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        str_inizio = data.get('data_inizio', '')
        str_fine = data.get('data_fine', '')
        solo_con_ore = data.get('solo_con_ore', True)

        dataset = calcola_dataset_paghe(
            str_inizio=str_inizio,
            str_fine=str_fine,
            build_calendar=True,
            solo_con_ore=solo_con_ore,
        )

        data_inizio = dataset['data_inizio']
        data_fine = dataset['data_fine']
        report_list = dataset['report_list']

        inviati = 0
        saltati_non_validati = []
        saltati_senza_telegram = []
        errori = []

        for item in report_list:
            nome = item.get('cognome_nome', 'Dipendente')
            ore_lav = item.get('ore_lavorate', 0.0)
            ore_non_val = item.get('ore_non_validate', 0.0)
            ha_telegram = item.get('ha_telegram', False)
            dip = item.get('dipendente')

            # Salta chi non ha ore
            if ore_lav <= 0.0 and item.get('giorni_lavorati', 0) <= 0:
                continue

            # CONTROLLO BLOCCANTE VALIDAZIONE: esclude categoricamente chi ha ore non validate
            if ore_non_val > 0.0:
                saltati_non_validati.append({
                    'id': item['dip_id'],
                    'nome': nome,
                    'ore_non_validate': ore_non_val,
                })
                continue

            # CONTROLLO BOT TELEGRAM: esclude chi non ha la chat telegram collegata
            if not ha_telegram:
                saltati_senza_telegram.append({
                    'id': item['dip_id'],
                    'nome': nome,
                })
                continue

            # Tutti i requisiti soddisfatti: generazione e invio
            try:
                pdf_bytes = genera_pdf_calendario_dipendente(item, data_inizio, data_fine)
                res = invia_pdf_calendario_telegram(dip, data_inizio, data_fine, pdf_bytes, item=item)
                if res.get('ok'):
                    inviati += 1
                else:
                    errori.append(f"{nome}: {res.get('error')}")
            except Exception as e_send:
                errori.append(f"{nome}: {str(e_send)}")

        return JsonResponse({
            'ok': True,
            'inviati': inviati,
            'saltati_non_validati': saltati_non_validati,
            'saltati_senza_telegram': saltati_senza_telegram,
            'errori': errori,
            'totale_esaminati': len(report_list),
        })

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@staff_or_titolare_api_required
def salva_modifica_cedolino_ajax(request):
    """
    Endpoint AJAX per l'amministrazione per salvare o resettare
    le rettifiche manuali del cedolino paghe (ore e giornate).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Metodo non consentito.'}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        dipendente_id = data.get('dipendente_id')
        str_inizio = data.get('data_inizio')
        str_fine = data.get('data_fine')
        reset = data.get('reset')

        if not dipendente_id or not str_inizio or not str_fine:
            return JsonResponse({'success': False, 'error': 'Parametri mancanti.'}, status=400)

        data_inizio = date.fromisoformat(str_inizio)
        data_fine = date.fromisoformat(str_fine)
        dipendente = Dipendente.objects.get(pk=int(dipendente_id))

        if reset in (True, 'true', '1', 1):
            ModificaCedolino.objects.filter(
                dipendente=dipendente,
                data_inizio=data_inizio,
                data_fine=data_fine
            ).delete()
            return JsonResponse({
                'success': True,
                'message': f'Rettifica per {dipendente.cognome} {dipendente.nome} eliminata. Ripristinati i valori automatici.'
            })

        def parse_optional_int(val):
            if val is not None and str(val).strip() != '':
                try:
                    return int(val)
                except ValueError:
                    pass
            return None

        def parse_optional_decimal(val):
            if val is not None and str(val).strip() != '':
                try:
                    from .utils_ore import parse_ore_input
                    return parse_ore_input(val)
                except Exception:
                    try:
                        return to_decimal(val, places=2)
                    except (ValueError, TypeError):
                        pass
            return None

        giorni_lavorati = parse_optional_int(data.get('giorni_lavorati_override'))
        ore_lavorate = parse_optional_decimal(data.get('ore_lavorate_override'))
        ore_validate = parse_optional_decimal(data.get('ore_validate_override'))
        giorni_ferie = parse_optional_int(data.get('giorni_ferie_override'))
        giorni_permesso = parse_optional_int(data.get('giorni_permesso_override'))
        giorni_malattia = parse_optional_int(data.get('giorni_malattia_override'))
        giorni_104 = parse_optional_int(data.get('giorni_104_override'))
        note = data.get('note', '').strip()

        ModificaCedolino.objects.update_or_create(
            dipendente=dipendente,
            data_inizio=data_inizio,
            data_fine=data_fine,
            defaults={
                'giorni_lavorati_override': giorni_lavorati,
                'ore_lavorate_override': ore_lavorate,
                'ore_validate_override': ore_validate,
                'giorni_ferie_override': giorni_ferie,
                'giorni_permesso_override': giorni_permesso,
                'giorni_malattia_override': giorni_malattia,
                'giorni_104_override': giorni_104,
                'note': note,
                'modificato_da': request.user if request.user.is_authenticated else None,
            }
        )

        return JsonResponse({
            'success': True,
            'message': f'Rettifica cedolino per {dipendente.cognome} {dipendente.nome} salvata con successo.'
        })

    except Dipendente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Dipendente non trovato.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@staff_or_titolare_api_required
def dettaglio_ore_giorno_ajax(request):
    """
    Restituisce in formato JSON il dettaglio delle ore registrate (TimeTracking),
    le assenze e l'elenco dei clienti per un dipendente in una data specifica,
    per consentire la modifica direttamente dalla vista calendario dei cedolini paghe.
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Metodo GET richiesto.'}, status=405)

    dip_id = request.GET.get('dipendente_id')
    data_str = request.GET.get('data')

    if not dip_id or not data_str:
        return JsonResponse({'success': False, 'error': 'Parametri dipendente_id e data obbligatori.'}, status=400)

    try:
        dipendente = Dipendente.objects.get(pk=int(dip_id))
        data_giorno = date.fromisoformat(data_str)
    except (Dipendente.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'error': 'Dipendente o data non validi.'}, status=400)

    # TimeTracking esistenti per il dipendente in questa data
    tt_qs = TimeTracking.objects.filter(
        dipendente=dipendente,
        assegnazione__turno__data=data_giorno
    ).select_related('assegnazione__cliente', 'assegnazione__turno__squadra').order_by('id')

    records = []
    totale_ore = 0.0
    for tt in tt_qs:
        ore = calcola_ore_lavorate_record(tt)
        totale_ore += ore
        cliente = tt.assegnazione.cliente if tt.assegnazione else None
        squadra = tt.assegnazione.turno.squadra if (tt.assegnazione and tt.assegnazione.turno) else None
        records.append({
            'id': tt.id,
            'cliente_id': cliente.id if cliente else None,
            'cliente_nome': cliente.ragione_sociale if cliente else 'Senza Cliente',
            'squadra_nome': squadra.nome if squadra else (tt.assegnazione.turno.nome_squadra if tt.assegnazione and tt.assegnazione.turno else 'Senza Squadra'),
            'ore': round(ore, 2),
            'ore_hhmm': format_ore_hhmm(ore, include_zero=False),
            'is_validated': bool(tt.is_validated),
            'note': tt.note or '',
            'source': tt.source or 'MANUAL',
        })

    # Assenze registrate in questa data
    assenze_qs = Assenza.objects.filter(
        dipendente=dipendente,
        data_inizio__lte=data_giorno,
        data_fine__gte=data_giorno
    ).exclude(stato_approvazione='RIFIUTATA')
    assenze_list = [f"{a.get_tipo_display()}{' (' + a.get_orario_display() + ')' if a.tipo == 'PERMESSO' and a.ora_inizio else ''}" for a in assenze_qs]

    # Clienti disponibili per eventuale assegnazione/aggiunta ore
    clienti_qs = Cliente.objects.all().order_by('ragione_sociale')
    clienti_list = [{'id': c.id, 'nome': c.ragione_sociale} for c in clienti_qs]

    giorni_nomi = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    giorno_sett = giorni_nomi[data_giorno.weekday()]

    return JsonResponse({
        'success': True,
        'dipendente_id': dipendente.id,
        'dipendente_nome': f"{dipendente.cognome} {dipendente.nome}",
        'data': data_giorno.isoformat(),
        'data_formatted': data_giorno.strftime('%d/%m/%Y'),
        'giorno_settimana': giorno_sett,
        'totale_ore': round(totale_ore, 2),
        'records': records,
        'assenze': assenze_list,
        'clienti': clienti_list,
    })


@csrf_exempt
@staff_or_titolare_api_required
def salva_ore_giorno_ajax(request):
    """
    Salva le modifiche alle ore registrate giornalmente per un dipendente (TimeTracking).
    Supporta:
    - Modifica di ore, validazione e note per i record TimeTracking esistenti della data.
    - Eliminazione di record esistenti (se ore <= 0 o elimina=True).
    - Creazione di un nuovo record di ore per la data (Turno + AssegnazioneTurno + TimeTracking).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Metodo POST richiesto.'}, status=405)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST

        dip_id = data.get('dipendente_id')
        data_str = data.get('data')

        if not dip_id or not data_str:
            return JsonResponse({'success': False, 'error': 'Parametri dipendente_id e data mancanti.'}, status=400)

        dipendente = Dipendente.objects.get(pk=int(dip_id))
        data_giorno = date.fromisoformat(data_str)

        records_mod = data.get('records', [])
        nuovo_rec = data.get('nuovo_record')

        with transaction.atomic():
            # 1. Aggiorna o elimina record esistenti
            for r in records_mod:
                rec_id = r.get('id')
                if not rec_id:
                    continue
                try:
                    tt = TimeTracking.objects.get(
                        pk=int(rec_id),
                        dipendente=dipendente,
                        assegnazione__turno__data=data_giorno
                    )
                except TimeTracking.DoesNotExist:
                    continue

                elimina = r.get('elimina', False)
                ore_raw = r.get('ore')

                if elimina:
                    tt.delete()
                    continue

                if ore_raw is not None and str(ore_raw).strip() != '':
                    ore_dec = parse_ore_input(ore_raw)
                    if ore_dec is not None:
                        if ore_dec <= 0:
                            tt.delete()
                            continue
                        tt.ore_dichiarate = ore_dec
                
                if 'is_validated' in r:
                    tt.is_validated = bool(r.get('is_validated'))
                if 'note' in r:
                    tt.note = (r.get('note') or '').strip()

                tt.save()

            # 2. Crea nuovo record se specificato
            if nuovo_rec and isinstance(nuovo_rec, dict):
                ore_nuove_raw = nuovo_rec.get('ore')
                if ore_nuove_raw is not None and str(ore_nuove_raw).strip() != '':
                    ore_nuove_dec = parse_ore_input(ore_nuove_raw)
                    if ore_nuove_dec is not None and ore_nuove_dec > 0:
                        cliente_id = nuovo_rec.get('cliente_id')
                        cliente = None
                        if cliente_id:
                            cliente = Cliente.objects.filter(pk=int(cliente_id)).first()
                        if not cliente:
                            # Prendi l'ultimo cliente del dipendente o il primo attivo
                            last_tt = TimeTracking.objects.filter(dipendente=dipendente, assegnazione__cliente__isnull=False).order_by('-id').first()
                            if last_tt and last_tt.assegnazione and last_tt.assegnazione.cliente:
                                cliente = last_tt.assegnazione.cliente
                            else:
                                cliente = Cliente.objects.all().order_by('ragione_sociale').first()

                        if not cliente:
                            return JsonResponse({'success': False, 'error': 'Nessun cliente/cantiere disponibile.'}, status=400)

                        squadra = dipendente.squadre_appartenenza.first() or dipendente.squadre_capitanate.first()
                        turno, _ = Turno.objects.get_or_create(
                            data=data_giorno,
                            squadra=squadra
                        )

                        assign = AssegnazioneTurno.objects.filter(turno=turno, cliente=cliente).first()
                        if not assign:
                            assign = AssegnazioneTurno.objects.create(
                                turno=turno,
                                cliente=cliente,
                                orario_inizio_previsto=time(8, 0),
                                orario_fine_previsto=time(17, 0),
                                mansione_svolta="Turno inserito da Amministrazione (Report Cedolini Paghe)"
                            )

                        is_val = bool(nuovo_rec.get('is_validated', True))
                        nota_nuova = (nuovo_rec.get('note') or '').strip()
                        if not nota_nuova:
                            nota_nuova = "Ore inserite da calendario cedolini"

                        TimeTracking.objects.create(
                            dipendente=dipendente,
                            assegnazione=assign,
                            ore_dichiarate=ore_nuove_dec,
                            is_validated=is_val,
                            note=nota_nuova,
                            source='ADMIN'
                        )

        return JsonResponse({
            'success': True,
            'message': f"Ore del {data_giorno.strftime('%d/%m/%Y')} per {dipendente.cognome} {dipendente.nome} aggiornate con successo."
        })

    except Dipendente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Dipendente non trovato.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
