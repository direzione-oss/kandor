"""
Viste dedicate a Paghe, Cedolini, Verifica Ore Mensili, Riconciliazione e Analisi Contratti.
Tutte le viste delegano i calcoli a `core.paghe_service` (Single Source of Truth).
"""
import csv
import io
import json
from datetime import date, timedelta
from xml.sax.saxutils import escape as xml_escape

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Cliente, Dipendente, TimeTracking, ModificaCedolino
from .paghe_service import (
    MESI_NOMI,
    calcola_ore_lavorate_record,
    calcola_dataset_paghe,
    calcola_verifica_ore_mensile,
    calcola_analisi_contratti,
)
from .views import staff_or_titolare_required, staff_or_titolare_api_required


@staff_or_titolare_required
def reconciliation_view(request):
    mesi = [(num, nome) for num, nome in MESI_NOMI.items()]

    today = timezone.now().date()
    selected_month = int(request.GET.get('month', today.month))
    selected_year = int(request.GET.get('year', today.year))

    report_data = []
    clienti = Cliente.objects.all()

    for cliente in clienti:
        timetracks = TimeTracking.objects.filter(
            assegnazione__cliente=cliente
        ).filter(
            Q(assegnazione__turno__data__year=selected_year, assegnazione__turno__data__month=selected_month)
            | Q(check_in__year=selected_year, check_in__month=selected_month)
        ).distinct()

        ore_reali = round(sum(calcola_ore_lavorate_record(t) for t in timetracks), 2)
        ore_previste = float(cliente.ore_mensili_contratto)
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
    """Analisi economica dei contratti: importo orario, soglia, costi effettivi."""
    soglia, mese, anno, _ = _resolve_soglia_and_periodo(request)
    dati = calcola_analisi_contratti(mese=mese, anno=anno, soglia=soglia)

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
            f'<span style="background: #e74c3c; color: white; padding: 4px 12px; border-radius: 15px; font-size: 13px;">'
            f'{c["cliente"]} &mdash; {c["importo_orario"]}/h</span>'
            for c in sotto_soglia
        ]
        sotto_soglia_html = ' '.join(badges)

    context = {
        'analisi': dati['analisi'],
        'sotto_soglia': sotto_soglia,
        'sotto_soglia_html': sotto_soglia_html,
        'soglia': soglia,
        'mese': mese,
        'mesi': mesi_list,
        'mese_nome': dati['mese_nome'],
        'anno': anno,
        'ore_header': f'Ore Lavorate<br><small>{dati["mese_nome"]} {anno}</small>',
        'totale_contratti': len(dati['analisi']),
        'totale_fatturato': f"&euro;{dati['totale_fatturato']:,.2f}",
        'media_oraria': f"&euro;{dati['media_oraria']:.2f}",
    }
    return render(request, 'core/analisi_contratti.html', context)


@staff_or_titolare_required
def pdf_contratti_sotto_soglia(request):
    """Genera PDF con elenco contratti sotto soglia usando `calcola_analisi_contratti`."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    soglia, mese, anno, today = _resolve_soglia_and_periodo(request)
    dati = calcola_analisi_contratti(mese=mese, anno=anno, soglia=soglia)
    sotto_soglia = dati['sotto_soglia']
    mese_nome = dati['mese_nome']

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#1a5276'))
    elements.append(Paragraph('Report Contratti Sotto Soglia', title_style))
    elements.append(Spacer(1, 5 * mm))

    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555'))
    elements.append(Paragraph(f'Soglia: {soglia:.2f} EUR/ora | Periodo: {mese_nome} {anno}', info_style))
    elements.append(Paragraph(f'Data generazione: {today.strftime("%d/%m/%Y")} | Contratti sotto soglia: {len(sotto_soglia)}', info_style))
    elements.append(Spacer(1, 8 * mm))

    if sotto_soglia:
        data = [['Cliente', 'Importo Mensile', 'Ore Contratto', 'EUR/Ora', 'Ore Lavorate', 'Costo Effettivo/Ora']]
        for row in sotto_soglia:
            data.append([
                row['cliente'],
                f"{row['importo_num']:,.2f} EUR",
                f"{row['ore_contratto_num']}h",
                f"{row['importo_orario_num']:.2f} EUR",
                f"{row['ore_lavorate_num']}h",
                f"{row['costo_effettivo_num']:.2f} EUR" if row['costo_effettivo_num'] else '-',
            ])

        table = Table(data, colWidths=[95 * mm, 35 * mm, 30 * mm, 25 * mm, 30 * mm, 35 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TEXTCOLOR', (3, 1), (3, -1), colors.HexColor('#e74c3c')),
            ('FONTNAME', (3, 1), (3, -1), 'Helvetica-Bold'),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph('Nessun contratto sotto la soglia impostata.', styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    nome_file = f'contratti_sotto_soglia_{mese_nome}{anno}.pdf'
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
    """
    dataset = calcola_dataset_paghe(
        str_inizio=request.GET.get('data_inizio', ''),
        str_fine=request.GET.get('data_fine', ''),
        dipendente_id=request.GET.get('dipendente_id', ''),
        build_calendar=True,
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

        def parse_optional_float(val):
            if val is not None and str(val).strip() != '':
                try:
                    return float(str(val).replace(',', '.'))
                except ValueError:
                    pass
            return None

        giorni_lavorati = parse_optional_int(data.get('giorni_lavorati_override'))
        ore_lavorate = parse_optional_float(data.get('ore_lavorate_override'))
        ore_validate = parse_optional_float(data.get('ore_validate_override'))
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
