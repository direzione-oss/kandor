"""Genera i 3 PDF ufficiali dei manuali KANDOR ERP con tabelle multi-riga e impaginazione controllata."""
import re
import os
import shutil
from fpdf import FPDF
from genera_docx_manuali import build_manuale_programmatore_markdown


class ManualePDF(FPDF):
    def __init__(self, header_label='KANDOR ERP - Manuale d\'Uso Completo e Guida Operativa'):
        super().__init__()
        self.header_label = header_label

    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(120, 130, 140)
            self.cell(0, 7, self.header_label, align='C')
            self.ln(3.5)
            self.set_draw_color(41, 128, 185)
            self.set_line_width(0.4)
            self.line(12, self.get_y(), 198, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-14)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(120, 130, 140)
        self.cell(0, 8, f'Pagina {self.page_no()}/{{nb}}', align='C')

    def cover_page(self, title='KANDOR ERP', subtitle="Manuale d'Uso Completo e Guida Operativa"):
        self.add_page()
        self.ln(42)
        self.set_font('Helvetica', 'B', 36)
        self.set_text_color(26, 82, 118)
        self.multi_cell(0, 15, title, align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(41, 128, 185)
        self.multi_cell(0, 8, subtitle, align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_draw_color(41, 128, 185)
        self.set_line_width(1)
        self.line(45, self.get_y(), 165, self.get_y())
        self.ln(14)
        self.set_font('Helvetica', '', 10.5)
        self.set_text_color(90, 100, 110)
        self.cell(0, 7, 'Versione 3.3 - 13 Novembre 2026', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, 'Manuale Operativo Passo-Passo: Accessi, Procedure, Buste Paga, MOL, Magazzino, SLA, CRM & IA', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.cell(0, 6.5, 'URL Gestionale (VPS 24/7): https://kandor.187.126.30.207.sslip.io/admin/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6.5, 'Console Programmatore & Manuali: https://kandor.187.126.30.207.sslip.io/gestione-accessi/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6.5, 'Buste Paga Automatiche: https://kandor.187.126.30.207.sslip.io/buste-paga/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6.5, 'Procedure & Avvalli: https://kandor.187.126.30.207.sslip.io/procedure/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6.5, 'Suite ERP (MOL, Magazzino, SLA, CRM, Fatture): /analisi-contratti/ | /magazzino-dotazioni/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6.5, 'Centro IA & Automazioni: https://kandor.187.126.30.207.sslip.io/ia-hub/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6.5, 'Web App Dipendenti: https://kandor.187.126.30.207.sslip.io/app/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(22)
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 7, 'Sviluppato per Studio Serra - (c) 2026', align='C', new_x="LMARGIN", new_y="NEXT")


def clean_text(text):
    """Rimuove markup markdown e converte caratteri non-latin1 in equivalenti leggibili."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'(?<!!)\[(.*?)\]\((.*?)\)', r'\1', text)
    replacements = {
        '\u2014': '-', '\u2013': '-', '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"', '\u2026': '...',
        '\u2022': '-', '\u2192': '->', '\u2190': '<-',
        '\u2212': '-', '\u00f7': '/', '\u20ac': 'EUR',
        '\u2713': '[OK]', '\u2717': '[NO]',
        '\u2705': '[OK]', '\u274c': '[NO]', '\u26a0\ufe0f': '[!]', '\u26a0': '[!]',
        '⚠️': '[!]', '📘': '', '🚨': '[!]', '🟢': '[V]', '🟡': '[G]', '🔴': '[R]', '⚪': '[ ]',
        '⏳': '[...]', '✔': '[OK]', '✅': '[OK]', '★': '*', '⋮': ':',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.encode('latin-1', errors='ignore').decode('latin-1')
    return text.strip()


def parse_table(lines, start_idx):
    headers = []
    rows = []
    i = start_idx
    if i < len(lines) and '|' in lines[i]:
        cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        headers = [clean_text(c) for c in cells]
        i += 1
    if i < len(lines) and '---' in lines[i]:
        i += 1
    while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
        cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        rows.append([clean_text(c) for c in cells])
        i += 1
    return headers, rows, i


def render_table_multiline(pdf, headers, rows):
    """Disegna una tabella con celle multi-riga che vanno a capo automaticamente senza mai sbordare."""
    num_cols = len(headers)
    if num_cols == 0:
        return
    if pdf.get_y() > 235:
        pdf.add_page()

    avail_w = 186.0
    if num_cols == 2:
        col_widths = [58.0, 128.0]
    elif num_cols == 3:
        col_widths = [54.0, 48.0, 84.0]
    elif num_cols == 4:
        col_widths = [46.0, 44.0, 36.0, 60.0]
    else:
        col_widths = [avail_w / num_cols] * num_cols

    def draw_row(cells_text, is_header=False, fill_rgb=(255, 255, 255)):
        pdf.set_font('Helvetica', 'B' if is_header else '', 8.5)
        line_h = 4.8
        wrapped_cols = []
        max_lines = 1
        for j in range(num_cols):
            w = col_widths[j]
            txt = cells_text[j] if j < len(cells_text) else ''
            lines_c = pdf.multi_cell(w - 3, line_h, txt, dry_run=True, output="LINES")
            if not lines_c:
                lines_c = ['']
            wrapped_cols.append(lines_c)
            if len(lines_c) > max_lines:
                max_lines = len(lines_c)

        row_h = max_lines * line_h + 3.0
        if pdf.get_y() + row_h > 272:
            pdf.add_page()

        x_start = pdf.get_x()
        y_start = pdf.get_y()
        pdf.set_fill_color(*fill_rgb)
        pdf.set_draw_color(203, 213, 225)
        pdf.set_line_width(0.25)

        cur_x = x_start
        for j in range(num_cols):
            w = col_widths[j]
            pdf.rect(cur_x, y_start, w, row_h, style='DF')
            pdf.set_text_color(255, 255, 255) if is_header else pdf.set_text_color(30, 41, 59)
            for l_idx, line_str in enumerate(wrapped_cols[j]):
                pdf.set_xy(cur_x + 1.5, y_start + 1.5 + l_idx * line_h)
                pdf.cell(w - 3, line_h, line_str, align='L')
            cur_x += w
        pdf.set_xy(x_start, y_start + row_h)

    pdf.ln(2)
    draw_row(headers, is_header=True, fill_rgb=(30, 58, 138))
    for r_idx, row in enumerate(rows):
        bg = (248, 250, 252) if r_idx % 2 == 0 else (255, 255, 255)
        draw_row(row, is_header=False, fill_rgb=bg)
    pdf.ln(3)


def render_markdown_content(pdf, lines, skip_first_h1=False):
    i = 0
    in_code_block = False

    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith('```'):
            in_code_block = not in_code_block
            i += 1
            continue

        if in_code_block:
            clean_l = clean_text(line)
            pdf.set_font('Courier', '', 8.5)
            pdf.set_fill_color(241, 245, 249)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5, f'  {clean_l}', fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        if not line.strip():
            pdf.ln(1.5)
            i += 1
            continue

        if line.strip().startswith('---'):
            if pdf.get_y() < 260:
                pdf.ln(2)
                pdf.set_draw_color(203, 213, 225)
                pdf.set_line_width(0.3)
                pdf.line(12, pdf.get_y(), 198, pdf.get_y())
                pdf.ln(3)
            i += 1
            continue

        # Immagini ![caption](path)
        img_match = re.match(r'^!\[(.*?)\]\((.*?)\)', line.strip())
        if img_match:
            caption, img_path = img_match.groups()
            full_img_path = os.path.normpath(os.path.join(os.path.dirname(__file__), img_path))
            if os.path.exists(full_img_path):
                if pdf.get_y() > 165:
                    pdf.add_page()
                pdf.ln(3)
                pdf.image(full_img_path, x=15, w=180)
                if caption:
                    pdf.set_font('Helvetica', 'I', 8.5)
                    pdf.set_text_color(100, 116, 139)
                    pdf.cell(0, 5.5, clean_text(f"Figura: {caption}"), align='C', new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)
            i += 1
            continue

        # H1
        if line.startswith('# ') and not line.startswith('##'):
            title = clean_text(line[2:])
            if skip_first_h1:
                skip_first_h1 = False
                i += 1
                continue
            if pdf.get_y() > 225:
                pdf.add_page()
            pdf.ln(6)
            pdf.set_font('Helvetica', 'B', 17)
            pdf.set_text_color(26, 82, 118)
            pdf.multi_cell(0, 8.5, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(41, 128, 185)
            pdf.set_line_width(0.7)
            pdf.line(12, pdf.get_y() + 1, 198, pdf.get_y() + 1)
            pdf.ln(4)
            i += 1
            continue

        # H2 (Evita titoli orfani a fine pagina)
        if line.startswith('## '):
            title = clean_text(line[3:])
            if pdf.get_y() > 232:
                pdf.add_page()
            else:
                pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 13.5)
            pdf.set_text_color(30, 64, 175)
            pdf.multi_cell(0, 7.5, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(203, 213, 225)
            pdf.set_line_width(0.3)
            pdf.line(12, pdf.get_y(), 170, pdf.get_y())
            pdf.ln(3)
            i += 1
            continue

        # H3 (Evita titoli orfani a fine pagina)
        if line.startswith('### '):
            title = clean_text(line[4:])
            if pdf.get_y() > 245:
                pdf.add_page()
            else:
                pdf.ln(3.5)
            pdf.set_font('Helvetica', 'B', 11.5)
            pdf.set_text_color(5, 150, 105)
            pdf.multi_cell(0, 6.5, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            i += 1
            continue

        # H4
        if line.startswith('#### '):
            title = clean_text(line[5:])
            if pdf.get_y() > 250:
                pdf.add_page()
            else:
                pdf.ln(2.5)
            pdf.set_font('Helvetica', 'B', 10.5)
            pdf.set_text_color(109, 40, 217)
            pdf.multi_cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            i += 1
            continue

        # Tabelle
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers, rows, end_idx = parse_table(lines, i)
            if headers and rows:
                render_table_multiline(pdf, headers, rows)
            i = end_idx
            continue

        # Blockquotes
        if line.startswith('>'):
            text = clean_text(line.lstrip('> '))
            if text:
                if pdf.get_y() > 255:
                    pdf.add_page()
                pdf.set_font('Helvetica', 'I', 9.5)
                pdf.set_text_color(120, 53, 15)
                pdf.set_fill_color(254, 249, 195)
                pdf.set_draw_color(245, 158, 11)
                pdf.multi_cell(0, 5.2, f"  {text}", fill=True, border=1, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            i += 1
            continue

        # Formule $$...$$
        if line.strip().startswith('$$') and line.strip().endswith('$$'):
            formula = clean_text(line.strip().strip('$').replace(r'\text{', '').replace('}', ''))
            pdf.set_font('Helvetica', 'BI', 10)
            pdf.set_text_color(30, 58, 138)
            pdf.cell(0, 6, formula, align='C', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
            i += 1
            continue

        # Elenchi puntati (anche indentati)
        m_bul = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if m_bul:
            indent = min(12, len(m_bul.group(1)) * 2)
            text = clean_text(m_bul.group(2))
            if pdf.get_y() > 265:
                pdf.add_page()
            pdf.set_font('Helvetica', '', 9.8)
            pdf.set_text_color(30, 41, 59)
            if indent > 0:
                pdf.cell(indent, 5.2, '')
            pdf.cell(5, 5.2, '-', new_x="RIGHT", new_y="TOP")
            pdf.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.8)
            i += 1
            continue

        # Elenchi numerati
        m_num = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        if m_num:
            indent = min(12, len(m_num.group(1)) * 2)
            num = m_num.group(2)
            text = clean_text(m_num.group(3))
            if pdf.get_y() > 265:
                pdf.add_page()
            pdf.set_font('Helvetica', 'B', 9.8)
            pdf.set_text_color(30, 64, 175)
            if indent > 0:
                pdf.cell(indent, 5.2, '')
            pdf.cell(7, 5.2, f"{num}.", new_x="RIGHT", new_y="TOP")
            pdf.set_font('Helvetica', '', 9.8)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.8)
            i += 1
            continue

        # Testo normale
        text = clean_text(line)
        if text:
            pdf.set_font('Helvetica', '', 9.8)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.2)

        i += 1


def main():
    with open('MANUALE_UTENTE.md', 'r', encoding='utf-8') as f:
        content_main = f.read()

    with open('MANUALE_DIPENDENTE_TELEGRAM.md', 'r', encoding='utf-8') as f:
        content_telegram = f.read()

    content_prog = build_manuale_programmatore_markdown(content_main)

    # 1. MANUALE PROGRAMMATORE PDF
    pdf_prog = ManualePDF(header_label='KANDOR ERP - Manuale Programmatore & Super-Admin')
    pdf_prog.set_margins(12, 14, 12)
    pdf_prog.alias_nb_pages()
    pdf_prog.set_auto_page_break(auto=True, margin=18)
    pdf_prog.cover_page(
        title='KANDOR ERP\nMANUALE PROGRAMMATORE',
        subtitle='Governance Accessi, Gestione Manuali, Architettura VPS & Suite Direzionale (38 Sezioni)',
    )
    pdf_prog.add_page()
    render_markdown_content(pdf_prog, content_prog.split('\n'), skip_first_h1=True)
    out_prog = 'MANUALE_PROGRAMMATORE_KANDOR.pdf'
    pdf_prog.output(out_prog)
    print(f"PDF Programmatore generato: {out_prog} ({pdf_prog.page_no()} pagine)")

    # 2. MANUALE RESPONSABILI / ADMIN PDF
    pdf = ManualePDF(header_label='KANDOR ERP - Manuale Responsabili & Amministrazione')
    pdf.set_margins(12, 14, 12)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.cover_page(
        title='KANDOR ERP',
        subtitle="Manuale d'Uso Completo e Guida Operativa per Responsabili & Amministrazione",
    )
    pdf.add_page()
    render_markdown_content(pdf, content_main.split('\n'), skip_first_h1=True)
    pdf.add_page()
    pdf.ln(8)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 12, 'APPENDICE: GUIDA OPERATIVA DIPENDENTE', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font('Helvetica', 'I', 12)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 8, 'Web App Mobile (/app/) & Bot Telegram (@kandor_gestionale_bot)', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(6)
    render_markdown_content(pdf, content_telegram.split('\n'), skip_first_h1=True)

    output = 'MANUALE_UTENTE_KANDOR.pdf'
    pdf.output(output)
    print(f"PDF Admin/Responsabili generato: {output} ({pdf.page_no()} pagine)")

    for extra_pdf in ['Manuale di utilizzo del portale Kandor.pdf', 'Kandor_Portal_Operational_Guide.pdf']:
        shutil.copyfile(output, extra_pdf)

    # 3. MANUALE DIPENDENTE PDF
    pdf_dip = ManualePDF(header_label='KANDOR - Guida Operativa Dipendente (Web App & Bot Telegram)')
    pdf_dip.set_margins(12, 14, 12)
    pdf_dip.alias_nb_pages()
    pdf_dip.set_auto_page_break(auto=True, margin=18)
    pdf_dip.cover_page(
        title='KANDOR\nGUIDA DIPENDENTE',
        subtitle='Manuale Passo-Passo Web App Mobile (/app/) & Bot Telegram (@kandor_gestionale_bot)',
    )
    pdf_dip.add_page()
    render_markdown_content(pdf_dip, content_telegram.split('\n'), skip_first_h1=True)
    output_dip = 'MANUALE_DIPENDENTE_KANDOR.pdf'
    pdf_dip.output(output_dip)
    print(f"PDF Dipendente generato: {output_dip} ({pdf_dip.page_no()} pagine)")


if __name__ == '__main__':
    main()
