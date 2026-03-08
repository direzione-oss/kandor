"""Genera il PDF dello Stack Tecnologico KANDOR."""
import re
from fpdf import FPDF

class StackPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, 'KANDOR - Stack Tecnologico', align='C')
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

def clean(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    return text.strip()

def main():
    with open(r'C:\Users\serra\.gemini\antigravity\brain\21bb526e-3ece-4160-9dd8-92412bdee577\stack_tecnologico.md', 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
    
    pdf = StackPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    
    # Copertina
    pdf.add_page()
    pdf.ln(60)
    pdf.set_font('Helvetica', 'B', 38)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 20, 'KANDOR', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font('Helvetica', '', 18)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(0, 12, 'Stack Tecnologico Completo', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_draw_color(41, 128, 185)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(15)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, 'Architettura, Servizi e Tecnologie', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, 'Marzo 2026', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(50)
    pdf.set_font('Helvetica', 'I', 10)
    pdf.cell(0, 8, 'Sviluppato per Studio Serra', align='C', new_x="LMARGIN", new_y="NEXT")
    
    # Contenuto
    pdf.add_page()
    i = 0
    in_code = False
    skip_first_h1 = True
    
    while i < len(lines):
        line = lines[i].rstrip()
        
        if line.startswith('```'):
            in_code = not in_code
            if in_code:
                pdf.ln(2)
            else:
                pdf.ln(3)
            i += 1
            continue
        
        if in_code:
            pdf.set_font('Courier', '', 8)
            pdf.set_fill_color(44, 62, 80)
            pdf.set_text_color(236, 240, 241)
            t = clean(line) if line.strip() else ' '
            pdf.cell(0, 4.5, f'  {t}', fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue
        
        if not line:
            i += 1
            continue
        
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
            if skip_first_h1:
                skip_first_h1 = False
                i += 1
                continue
            title = clean(line[2:])
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
            title = clean(line[3:])
            pdf.ln(6)
            pdf.set_font('Helvetica', 'B', 15)
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
            title = clean(line[4:])
            pdf.ln(4)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(39, 174, 96)
            pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            i += 1
            continue
        
        # Tables
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers = [clean(c) for c in line.split('|') if c.strip()]
            i += 2  # skip separator
            rows = []
            while i < len(lines) and '|' in lines[i]:
                cells = [clean(c) for c in lines[i].split('|') if c.strip()]
                rows.append(cells)
                i += 1
            
            if headers and rows:
                pdf.ln(2)
                num_cols = len(headers)
                col_widths = [190 / num_cols] * num_cols
                if num_cols == 2:
                    col_widths = [60, 130]
                elif num_cols == 3:
                    col_widths = [55, 90, 45]
                
                pdf.set_font('Helvetica', 'B', 9)
                pdf.set_fill_color(41, 128, 185)
                pdf.set_text_color(255, 255, 255)
                for j, h in enumerate(headers):
                    w = col_widths[j] if j < len(col_widths) else col_widths[-1]
                    pdf.cell(w, 7, h[:35], border=1, fill=True, align='C')
                pdf.ln()
                
                pdf.set_font('Helvetica', '', 9)
                for ri, row in enumerate(rows):
                    pdf.set_fill_color(248, 249, 250) if ri % 2 == 0 else pdf.set_fill_color(255, 255, 255)
                    pdf.set_text_color(44, 62, 80)
                    for j, cell in enumerate(row):
                        w = col_widths[j] if j < len(col_widths) else col_widths[-1]
                        pdf.cell(w, 6, cell[:55], border=1, fill=True)
                    pdf.ln()
                pdf.ln(3)
            continue
        
        # Blockquotes
        if line.startswith('>'):
            text = clean(line.lstrip('> '))
            if text:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(125, 102, 8)
                pdf.set_fill_color(254, 249, 231)
                y = pdf.get_y()
                pdf.rect(10, y, 190, 8, style='F')
                pdf.set_draw_color(243, 156, 18)
                pdf.set_line_width(0.8)
                pdf.line(10, y, 10, y + 8)
                pdf.set_xy(14, y)
                pdf.cell(186, 8, text[:100])
                pdf.ln(9)
                pdf.set_text_color(0, 0, 0)
            i += 1
            continue
        
        # Lists
        if line.startswith('- ') or line.startswith('* '):
            text = clean(line[2:])
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(0, 5.5, f'  - {text[:130]}', new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue
        
        # Numbered
        if re.match(r'^\d+\. ', line):
            text = clean(re.sub(r'^\d+\. ', '', line))
            num = re.match(r'^(\d+)\. ', line).group(1)
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.cell(8, 5.5, f'{num}.')
            pdf.cell(0, 5.5, text[:120], new_x="LMARGIN", new_y="NEXT")
            i += 1
            continue
        
        # Normal text
        text = clean(line)
        if text:
            pdf.set_font('Helvetica', '', 10)
            pdf.set_text_color(44, 62, 80)
            pdf.multi_cell(0, 5.5, text)
            pdf.ln(1)
        i += 1
    
    output = r'C:\Users\serra\.gemini\antigravity\playground\phantom-ionosphere\STACK_TECNOLOGICO_KANDOR.pdf'
    pdf.output(output)
    print(f"PDF generato: {output}")
    print(f"Pagine: {pdf.page_no()}")

if __name__ == '__main__':
    main()
