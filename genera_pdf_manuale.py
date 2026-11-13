"""Genera il PDF del manuale utente KANDOR completo e senza alcuna troncatura di testo."""
import re
import os
from fpdf import FPDF

class ManualePDF(FPDF):
    def __init__(self):
        super().__init__()
    
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, 'KANDOR ERP - Manuale d\'Uso Completo e Guida Operativa', align='C')
            self.ln(4)
            self.set_draw_color(41, 128, 185)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(6)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Pagina {self.page_no()}/{{nb}}', align='C')

    def cover_page(self):
        self.add_page()
        self.ln(50)
        # Logo/Titolo
        self.set_font('Helvetica', 'B', 40)
        self.set_text_color(26, 82, 118)
        self.cell(0, 18, 'KANDOR ERP', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        # Sottotitolo
        self.set_font('Helvetica', '', 16)
        self.set_text_color(41, 128, 185)
        self.cell(0, 10, "Manuale d'Uso Completo e Guida Operativa", align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        # Linea decorativa
        self.set_draw_color(41, 128, 185)
        self.set_line_width(1)
        self.line(50, self.get_y(), 160, self.get_y())
        self.ln(15)
        # Info
        self.set_font('Helvetica', '', 11)
        self.set_text_color(100, 100, 100)
        self.cell(0, 7, 'Versione 3.3 - 13 Novembre 2026', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, 'Manuale Operativo Passo-Passo: Accessi, Procedure, Buste Paga, MOL, Magazzino, SLA, CRM & IA', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.cell(0, 7, 'URL Gestionale (VPS 24/7): https://kandor.187.126.30.207.sslip.io', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, 'Buste Paga Automatiche: https://kandor.187.126.30.207.sslip.io/buste-paga/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, 'Procedure & Avvalli: https://kandor.187.126.30.207.sslip.io/procedure/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, 'Centro IA & Automazioni: https://kandor.187.126.30.207.sslip.io/ia-hub/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, 'Web App Dipendenti: https://kandor.187.126.30.207.sslip.io/app/', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(30)
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 7, 'Sviluppato per Studio Serra - (c) 2026', align='C', new_x="LMARGIN", new_y="NEXT")

def clean_text(text):
    """Rimuove markup markdown e caratteri non-latin1 dal testo."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)  # Italic
    text = re.sub(r'`(.*?)`', r'\1', text)  # Code
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # Links
    # Emoji e caratteri speciali -> ASCII
    replacements = {
        '\u2014': '-', '\u2013': '-', '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"', '\u2026': '...',
        '\u2022': '-', '\u2192': '->', '\u2190': '<-',
        '\u2713': '[OK]', '\u2717': '[NO]',
        '\u2705': '[OK]', '\u274c': '[NO]', '\u26a0\ufe0f': '[!]', '\u26a0': '[!]',
        '⚠️': '[!]', '📘': '', '🚨': '[!]', '🟢': '[V]', '🟡': '[A]', '🔴': '[R]', '⚪': '[ ]',
        '\U0001f389': '', '\U0001f91e': '', '\U0001f680': '',
        '\U0001f4d8': '', '\U0001f4c5': '', '\U0001f4f1': '',
        '\U0001f697': '', '\U0001f382': '', '\U0001f4ac': '',
        '\U0001f7e2': '[V]', '\U0001f7e0': '[A]', '\U0001f534': '[R]',
        '\U0001f912': '', '\U0001f3d6\ufe0f': '', '\U0001f4dd': '',
        '\U0001f6ab': '[X]', '\u23f3': '[...]', '\U0001f44b': '',
        '\U0001f464': '', '\U0001f511': '', '\U0001f449': '>',
        '\U0001f5d1\ufe0f': '', '\u270f\ufe0f': '', '\U0001f440': '',
        '\u26a1': '', '\u2190': '<', '\u2192': '>',
        '\u2714': '[OK]', '\u23f1': '[...]', '\u23f3': '[...]',
        '⏳': '[...]', '✔': '[OK]', '✅': '[OK]', '🗓️': '', '👥': '', '🏢': '', '📦': '', '📄': '',
        '🎯': '', '🚀': '', '🔘': '', '⏱': '', '📋': '', '🤒': '', '🏖️': '', '📝': '', '🏖': '',
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
        cells = [c.strip() for c in lines[i].split('|') if c.strip()]
        headers = [clean_text(c) for c in cells]
        i += 1
    if i < len(lines) and '---' in lines[i]:
        i += 1
    while i < len(lines) and '|' in lines[i]:
        cells = [c.strip() for c in lines[i].split('|') if c.strip()]
        rows.append([clean_text(c) for c in cells])
        i += 1
    return headers, rows, i

def render_markdown_content(pdf, lines, skip_first_h1=False):
    i = 0
    in_code_block = False
    
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Code blocks
        if line.startswith('```'):
            in_code_block = not in_code_block
            i += 1
            continue
        
        if in_code_block:
            clean_l = clean_text(line)
            pdf.set_font('Courier', '', 9)
            pdf.set_fill_color(240, 243, 244)
            pdf.set_text_color(44, 62, 80)
            pdf.multi_cell(0, 5, f'  {clean_l}', fill=True)
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue
        
        # Empty lines
        if not line:
            pdf.ln(2)
            i += 1
            continue
        
        # Horizontal rules
        if line.startswith('---'):
            pdf.ln(3)
            pdf.set_draw_color(189, 195, 199)
            pdf.set_line_width(0.3)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            i += 1
            continue
        
        # Images ![caption](path)
        img_match = re.match(r'^!\[(.*?)\]\((.*?)\)', line)
        if img_match:
            caption, img_path = img_match.groups()
            full_img_path = os.path.normpath(os.path.join(os.path.dirname(__file__), img_path))
            if os.path.exists(full_img_path):
                pdf.ln(4)
                if pdf.get_y() > 160:
                    pdf.add_page()
                pdf.image(full_img_path, w=175)
                if caption:
                    pdf.set_font('Helvetica', 'I', 9)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(0, 6, clean_text(caption), align='C', new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)
            i += 1
            continue

        # H1
        if line.startswith('# ') and not line.startswith('##'):
            title = clean_text(line[2:])
            if skip_first_h1:
                skip_first_h1 = False
                i += 1
                continue
            pdf.ln(8)
            pdf.set_font('Helvetica', 'B', 20)
            pdf.set_text_color(26, 82, 118)
            pdf.cell(0, 11, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(41, 128, 185)
            pdf.set_line_width(0.8)
            pdf.line(10, pdf.get_y()+1, 200, pdf.get_y()+1)
            pdf.ln(5)
            i += 1
            continue
        
        # H2
        if line.startswith('## '):
            title = clean_text(line[3:])
            pdf.ln(6)
            pdf.set_font('Helvetica', 'B', 15)
            pdf.set_text_color(41, 128, 185)
            pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(189, 195, 199)
            pdf.set_line_width(0.3)
            pdf.line(10, pdf.get_y(), 140, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue
        
        # H3
        if line.startswith('### '):
            title = clean_text(line[4:])
            pdf.ln(4)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(39, 174, 96)
            pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue
        
        # H4
        if line.startswith('#### '):
            title = clean_text(line[5:])
            pdf.ln(3)
            pdf.set_font('Helvetica', 'B', 10.5)
            pdf.set_text_color(142, 68, 173)
            pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue
        
        # Tables
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers, rows, end_idx = parse_table(lines, i)
            if headers and rows:
                pdf.ln(3)
                num_cols = len(headers)
                available_width = 190
                col_widths = [available_width / num_cols] * num_cols
                if num_cols == 2:
                    col_widths = [60, 130]
                elif num_cols == 3:
                    col_widths = [50, 30, 110]
                
                # Header
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_fill_color(41, 128, 185)
                pdf.set_text_color(255, 255, 255)
                for j, h in enumerate(headers):
                    w = col_widths[j] if j < len(col_widths) else col_widths[-1]
                    pdf.cell(w, 7, h, border=1, fill=True, align='C')
                pdf.ln()
                
                # Rows
                pdf.set_font('Helvetica', '', 8.5)
                for row_idx, row in enumerate(rows):
                    if row_idx % 2 == 0:
                        pdf.set_fill_color(248, 249, 250)
                    else:
                        pdf.set_fill_color(255, 255, 255)
                    pdf.set_text_color(44, 62, 80)
                    
                    for j, cell in enumerate(row):
                        w = col_widths[j] if j < len(col_widths) else col_widths[-1]
                        pdf.cell(w, 6, cell, border=1, fill=True)
                    pdf.ln()
                pdf.ln(3)
            i = end_idx
            continue
        
        # Blockquotes
        if line.startswith('>'):
            text = clean_text(line.lstrip('> '))
            if text:
                pdf.set_font('Helvetica', 'I', 9.5)
                pdf.set_text_color(125, 102, 8)
                pdf.set_fill_color(254, 249, 231)
                pdf.set_draw_color(243, 156, 18)
                pdf.multi_cell(0, 5.5, f"  {text}", fill=True, border=1)
                pdf.ln(2)
            i += 1
            continue
        
        # List items - NO TRUNCATION
        if line.startswith('- ') or line.startswith('* '):
            text = clean_text(line[2:])
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(6, 5.5, '-', new_x="RIGHT", new_y="TOP")
            pdf.multi_cell(0, 5.5, text)
            pdf.ln(1)
            i += 1
            continue
        
        # Numbered list - NO TRUNCATION
        if re.match(r'^\d+\. ', line):
            m = re.match(r'^(\d+)\. (.*)', line)
            num = m.group(1) if m else "1"
            text = clean_text(m.group(2)) if m else clean_text(line)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(8, 5.5, f"{num}.", new_x="RIGHT", new_y="TOP")
            pdf.multi_cell(0, 5.5, text)
            pdf.ln(1)
            i += 1
            continue
        
        # Normal text 
        text = clean_text(line)
        if text:
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.multi_cell(0, 5.5, text)
            pdf.ln(1.5)
        
        i += 1

def main():
    # Read both MANUALE_UTENTE.md and MANUALE_DIPENDENTE_TELEGRAM.md
    with open('MANUALE_UTENTE.md', 'r', encoding='utf-8') as f:
        content_main = f.read()
    
    with open('MANUALE_DIPENDENTE_TELEGRAM.md', 'r', encoding='utf-8') as f:
        content_telegram = f.read()
    
    pdf = ManualePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # Copertina
    pdf.cover_page()
    
    # Parte I: Manuale Amministrazione ed ERP
    pdf.add_page()
    render_markdown_content(pdf, content_main.split('\n'), skip_first_h1=True)
    
    # Parte II: Guida Operativa per il Dipendente - Web App Mobile & Bot Telegram
    pdf.add_page()
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 24)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 15, 'PARTE II: GUIDA OPERATIVA DIPENDENTE', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font('Helvetica', 'I', 14)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 10, 'Web App Mobile (/app/) & Bot Telegram (@kandor_gestionale_bot)', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(10)
    pdf.set_draw_color(41, 128, 185)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)
    
    render_markdown_content(pdf, content_telegram.split('\n'), skip_first_h1=True)
    
    output = 'MANUALE_UTENTE_KANDOR.pdf'
    pdf.output(output)
    print(f"PDF generato con successo: {output}")
    print(f"Pagine totali: {pdf.page_no()}")

    import shutil
    for extra_pdf in ['Manuale di utilizzo del portale Kandor.pdf', 'Kandor_Portal_Operational_Guide.pdf']:
        shutil.copyfile(output, extra_pdf)
        print(f"PDF aggiornato e sostituito: {extra_pdf} ({pdf.page_no()} pagine)")

    # Genera anche il PDF autonomo per il Dipendente (Web App + Telegram)
    pdf_dip = ManualePDF()
    pdf_dip.alias_nb_pages()
    pdf_dip.set_auto_page_break(auto=True, margin=20)
    pdf_dip.add_page()
    pdf_dip.ln(10)
    pdf_dip.set_font('Helvetica', 'B', 22)
    pdf_dip.set_text_color(26, 82, 118)
    pdf_dip.cell(0, 14, 'KANDOR - GUIDA OPERATIVA DIPENDENTE', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf_dip.set_font('Helvetica', 'I', 13)
    pdf_dip.set_text_color(41, 128, 185)
    pdf_dip.cell(0, 9, 'Web App Mobile (https://kandor.187.126.30.207.sslip.io/app/) & Bot Telegram', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf_dip.ln(6)
    pdf_dip.set_draw_color(41, 128, 185)
    pdf_dip.set_line_width(0.8)
    pdf_dip.line(10, pdf_dip.get_y(), 200, pdf_dip.get_y())
    pdf_dip.ln(8)
    render_markdown_content(pdf_dip, content_telegram.split('\n'), skip_first_h1=True)
    output_dip = 'MANUALE_DIPENDENTE_KANDOR.pdf'
    pdf_dip.output(output_dip)
    print(f"PDF Dipendente generato con successo: {output_dip} ({pdf_dip.page_no()} pagine)")

if __name__ == '__main__':
    main()
