"""Genera il PDF del manuale utente KANDOR da MANUALE_UTENTE.md"""
import re
import os
from fpdf import FPDF

# Percorso font DejaVuSans (supporta Unicode)
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
os.makedirs(FONT_DIR, exist_ok=True)

class ManualePDF(FPDF):
    def __init__(self):
        super().__init__()
        # Usa font built-in con encoding che supporta caratteri base
        # Useremo - come bullet al posto di unicode bullet
    
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, 'KANDOR - Manuale d\'Uso Completo', align='C')
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
        self.ln(60)
        # Logo/Titolo
        self.set_font('Helvetica', 'B', 42)
        self.set_text_color(26, 82, 118)
        self.cell(0, 20, 'KANDOR', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        # Sottotitolo
        self.set_font('Helvetica', '', 18)
        self.set_text_color(41, 128, 185)
        self.cell(0, 12, "Manuale d'Uso Completo", align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        # Linea decorativa
        self.set_draw_color(41, 128, 185)
        self.set_line_width(1)
        self.line(60, self.get_y(), 150, self.get_y())
        self.ln(15)
        # Info
        self.set_font('Helvetica', '', 12)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, 'Versione 1.0 - Marzo 2026', align='C', new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 8, 'Sistema ERP per la Gestione Operativa Aziendale', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.cell(0, 8, 'URL: kandor.onrender.com', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(40)
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 8, 'Sviluppato per Studio Serra', align='C', new_x="LMARGIN", new_y="NEXT")

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
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Rimuovi qualsiasi carattere non-latin1 rimanente convertendolo
    text = text.encode('latin-1', errors='ignore').decode('latin-1')
    return text.strip()

def parse_table(lines, start_idx):
    """Parsa una tabella markdown e ritorna (headers, rows, end_idx)."""
    headers = []
    rows = []
    i = start_idx
    
    # Header row
    if i < len(lines) and '|' in lines[i]:
        cells = [c.strip() for c in lines[i].split('|') if c.strip()]
        headers = [clean_text(c) for c in cells]
        i += 1
    
    # Separator row
    if i < len(lines) and '---' in lines[i]:
        i += 1
    
    # Data rows
    while i < len(lines) and '|' in lines[i]:
        cells = [c.strip() for c in lines[i].split('|') if c.strip()]
        rows.append([clean_text(c) for c in cells])
        i += 1
    
    return headers, rows, i

def main():
    # Leggi il file markdown
    with open('MANUALE_UTENTE.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # Crea PDF
    pdf = ManualePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # Pagina copertina
    pdf.cover_page()
    
    # Processa le linee
    pdf.add_page()
    i = 0
    in_code_block = False
    in_blockquote = False
    skip_first_h1 = True
    
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Skip sommario section lines that are just links
        if line.startswith('1. [') or (line.startswith('2') and line.startswith('2. [')):
            # Skip TOC entries
            if re.match(r'^\d+\. \[', line):
                i += 1
                continue
        
        # Code blocks
        if line.startswith('```'):
            in_code_block = not in_code_block
            i += 1
            continue
        
        if in_code_block:
            clean_l = clean_text(line)
            pdf.set_font('Courier', '', 9)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(236, 240, 241)
            pdf.cell(0, 5, f'  {clean_l}', fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue
        
        # Empty lines
        if not line:
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
        
        # H1
        if line.startswith('# ') and not line.startswith('##'):
            title = clean_text(line[2:])
            if skip_first_h1:
                skip_first_h1 = False
                i += 1
                continue
            pdf.ln(8)
            pdf.set_font('Helvetica', 'B', 22)
            pdf.set_text_color(26, 82, 118)
            pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(41, 128, 185)
            pdf.set_line_width(0.8)
            pdf.line(10, pdf.get_y()+1, 200, pdf.get_y()+1)
            pdf.ln(6)
            i += 1
            continue
        
        # H2
        if line.startswith('## '):
            title = clean_text(line[3:])
            pdf.ln(6)
            pdf.set_font('Helvetica', 'B', 16)
            pdf.set_text_color(41, 128, 185)
            pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
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
            pdf.set_font('Helvetica', 'B', 13)
            pdf.set_text_color(39, 174, 96)
            pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue
        
        # H4
        if line.startswith('#### '):
            title = clean_text(line[5:])
            pdf.ln(3)
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(142, 68, 173)
            pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue
        
        # Tables
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers, rows, end_idx = parse_table(lines, i)
            
            if headers and rows:
                pdf.ln(3)
                # Calculate column widths
                num_cols = len(headers)
                available_width = 190
                col_widths = [available_width / num_cols] * num_cols
                
                # Adjust for common patterns
                if num_cols == 2:
                    col_widths = [70, 120]
                elif num_cols == 3:
                    col_widths = [55, 90, 45]
                
                # Header
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_fill_color(41, 128, 185)
                pdf.set_text_color(255, 255, 255)
                for j, h in enumerate(headers):
                    w = col_widths[j] if j < len(col_widths) else col_widths[-1]
                    pdf.cell(w, 7, h[:30], border=1, fill=True, align='C')
                pdf.ln()
                
                # Rows
                pdf.set_font('Helvetica', '', 9)
                for row_idx, row in enumerate(rows):
                    if row_idx % 2 == 0:
                        pdf.set_fill_color(248, 249, 250)
                    else:
                        pdf.set_fill_color(255, 255, 255)
                    pdf.set_text_color(44, 62, 80)
                    
                    for j, cell in enumerate(row):
                        w = col_widths[j] if j < len(col_widths) else col_widths[-1]
                        pdf.cell(w, 6, cell[:50], border=1, fill=True)
                    pdf.ln()
                
                pdf.ln(3)
            
            i = end_idx
            continue
        
        # Blockquotes
        if line.startswith('>'):
            text = clean_text(line.lstrip('> '))
            if text:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(125, 102, 8)
                pdf.set_fill_color(254, 249, 231)
                pdf.set_draw_color(243, 156, 18)
                x = pdf.get_x()
                y = pdf.get_y()
                pdf.rect(10, y, 190, 8, style='F')
                pdf.set_line_width(0.8)
                pdf.line(10, y, 10, y + 8)
                pdf.set_xy(14, y)
                pdf.cell(186, 8, text[:100])
                pdf.ln(9)
                pdf.set_text_color(0, 0, 0)
            i += 1
            continue
        
        # List items
        if line.startswith('- ') or line.startswith('* '):
            text = clean_text(line[2:])
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(8, 6, '-')  # bullet
            pdf.cell(0, 6, text[:120], new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue
        
        # Numbered list
        if re.match(r'^\d+\. ', line):
            text = clean_text(re.sub(r'^\d+\. ', '', line))
            num = re.match(r'^(\d+)\. ', line).group(1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(8, 6, f'{num}.')
            pdf.cell(0, 6, text[:120], new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue
        
        # Normal text 
        text = clean_text(line)
        if text:
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.multi_cell(0, 5.5, text)
            pdf.ln(1)
        
        i += 1
    
    # Salva
    output = 'MANUALE_UTENTE_KANDOR.pdf'
    pdf.output(output)
    print(f"PDF generato con successo: {output}")
    print(f"Pagine: {pdf.page_no()}")

if __name__ == '__main__':
    main()
