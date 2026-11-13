"""
Genera i 3 manuali ufficiali di KANDOR ERP in formato Microsoft Word (.docx) completamente
modificabile (con stili, tabelle formattate e screenshot incorporati) per la Console Programmatore:
1. MANUALE_PROGRAMMATORE_KANDOR.docx (Manuale Tecnico & Super-Admin per Gian Carlo Serra)
2. MANUALE_UTENTE_KANDOR.docx (Manuale Completo Amministrazione, Titolari & Responsabili)
3. MANUALE_DIPENDENTE_KANDOR.docx (Guida Operativa Dipendente — Web App Mobile & Bot Telegram)
"""
import os
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def set_cell_background(cell, fill_hex):
    """Imposta il colore di sfondo di una cella Word (es. '1E3A8A')."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_formatted_runs(paragraph, text, default_color=None, default_size=Pt(10.5)):
    """Analizza **grassetto**, *corsivo* e `codice` inline aggiungendo i run Word."""
    # Pulisci link markdown [testo](url) -> testo (url)
    text = re.sub(r'(?<!!)\[(.*?)\]\((.*?)\)', r'\1 (\2)', text)
    tokens = re.split(r'(\*\*.*?\*\*|`.*?`|\*[^*]+?\*)', text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith('**') and tok.endswith('**') and len(tok) > 4:
            run = paragraph.add_run(tok[2:-2])
            run.bold = True
        elif tok.startswith('`') and tok.endswith('`') and len(tok) > 2:
            run = paragraph.add_run(tok[1:-1])
            run.font.name = 'Consolas'
            run.font.color.rgb = RGBColor(15, 23, 42)
            run.bold = True
        elif tok.startswith('*') and tok.endswith('*') and len(tok) > 2:
            run = paragraph.add_run(tok[1:-1])
            run.italic = True
        else:
            run = paragraph.add_run(tok)
        if default_size:
            run.font.size = default_size
        if default_color:
            run.font.color.rgb = default_color


def parse_md_table(lines, start_idx):
    headers = []
    rows = []
    i = start_idx
    if i < len(lines) and '|' in lines[i]:
        headers = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        i += 1
    if i < len(lines) and '---' in lines[i]:
        i += 1
    while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
        row_cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
        rows.append(row_cells)
        i += 1
    return headers, rows, i


def configure_document_styles(doc):
    """Imposta margini di pagina e font predefiniti puliti."""
    for section in doc.sections:
        section.top_margin = Inches(0.85)
        section.bottom_margin = Inches(0.85)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = RGBColor(30, 41, 59)


def add_cover_page(doc, main_title, subtitle, version_line, role_description):
    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(60)

    p_badge = doc.add_paragraph()
    p_badge.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_b = p_badge.add_run("DOCUMENTAZIONE UFFICIALE MODIFICABILE — STUDIO SERRA")
    r_b.bold = True
    r_b.font.size = Pt(10)
    r_b.font.color.rgb = RGBColor(37, 99, 235)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(6)
    r_t = p_title.add_run(main_title)
    r_t.bold = True
    r_t.font.size = Pt(28)
    r_t.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(18)
    r_s = p_sub.add_run(subtitle)
    r_s.bold = True
    r_s.font.size = Pt(14)
    r_s.font.color.rgb = RGBColor(29, 78, 216)

    p_ver = doc.add_paragraph()
    p_ver.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ver.paragraph_format.space_after = Pt(16)
    r_v = p_ver.add_run(version_line)
    r_v.italic = True
    r_v.font.size = Pt(11)
    r_v.font.color.rgb = RGBColor(100, 116, 139)

    p_desc = doc.add_paragraph()
    p_desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_desc.paragraph_format.space_before = Pt(14)
    p_desc.paragraph_format.space_after = Pt(30)
    r_d = p_desc.add_run(role_description)
    r_d.font.size = Pt(11)
    r_d.font.color.rgb = RGBColor(51, 65, 85)

    # Box riepilogo URL
    tbl = doc.add_table(rows=6, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = 'Table Grid'
    urls_info = [
        ("Portale Amministrazione & Dashboard", "https://kandor.187.126.30.207.sslip.io/admin/"),
        ("Console Programmatore (Accessi & Manuali)", "https://kandor.187.126.30.207.sslip.io/gestione-accessi/"),
        ("Buste Paga Automatiche & Procedure", "https://kandor.187.126.30.207.sslip.io/buste-paga/  |  /procedure/"),
        ("Suite Direzionale ERP (MOL, Magazzino, SLA, CRM)", "/analisi-contratti/ | /magazzino-dotazioni/ | /qualita-ispezioni/ | /preventivi-crm/"),
        ("Centro IA & Pre-Fatturazione", "https://kandor.187.126.30.207.sslip.io/ia-hub/  |  /pre-fatturazione/"),
        ("Web App Mobile Dipendenti & Bot Telegram", "https://kandor.187.126.30.207.sslip.io/app/  |  @kandor_gestionale_bot"),
    ]
    for idx, (k, v) in enumerate(urls_info):
        c0 = tbl.rows[idx].cells[0]
        c1 = tbl.rows[idx].cells[1]
        set_cell_background(c0, "EFF6FF")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, 80, 80, 120, 120)
        set_cell_margins(c1, 80, 80, 120, 120)
        r0 = c0.paragraphs[0].add_run(k)
        r0.bold = True
        r0.font.size = Pt(9.5)
        r0.font.color.rgb = RGBColor(30, 58, 138)
        r1 = c1.paragraphs[0].add_run(v)
        r1.font.name = 'Consolas'
        r1.font.size = Pt(9)
        r1.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_page_break()


def render_markdown_to_docx(doc, md_text, skip_first_h1=True):
    lines = md_text.splitlines()
    i = 0
    in_code_block = False
    code_buffer = []

    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith('```'):
            if in_code_block:
                p_code = doc.add_paragraph()
                p_code.paragraph_format.left_indent = Inches(0.25)
                p_code.paragraph_format.space_before = Pt(4)
                p_code.paragraph_format.space_after = Pt(6)
                r_c = p_code.add_run('\n'.join(code_buffer))
                r_c.font.name = 'Consolas'
                r_c.font.size = Pt(9)
                r_c.font.color.rgb = RGBColor(15, 23, 42)
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        if not line.strip():
            i += 1
            continue

        if line.strip().startswith('---'):
            i += 1
            continue

        # Immagini ![didascalia](percorso)
        img_match = re.match(r'^!\[(.*?)\]\((.*?)\)', line.strip())
        if img_match:
            caption, img_rel = img_match.groups()
            img_path = os.path.normpath(os.path.join(BASE_DIR, img_rel))
            if os.path.exists(img_path):
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(8)
                p_img.paragraph_format.space_after = Pt(2)
                p_img.paragraph_format.keep_with_next = True
                run_img = p_img.add_run()
                run_img.add_picture(img_path, width=Inches(6.2))
                if caption:
                    p_cap = doc.add_paragraph()
                    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_cap.paragraph_format.space_after = Pt(10)
                    r_cap = p_cap.add_run(f"Figura: {caption}")
                    r_cap.italic = True
                    r_cap.font.size = Pt(9)
                    r_cap.font.color.rgb = RGBColor(100, 116, 139)
            i += 1
            continue

        # H1
        if line.startswith('# ') and not line.startswith('##'):
            if skip_first_h1:
                skip_first_h1 = False
                i += 1
                continue
            h1 = doc.add_heading(level=1)
            h1.paragraph_format.space_before = Pt(18)
            h1.paragraph_format.space_after = Pt(6)
            h1.paragraph_format.keep_with_next = True
            r = h1.add_run(line[2:].strip().replace('**', ''))
            r.bold = True
            r.font.size = Pt(18)
            r.font.color.rgb = RGBColor(26, 82, 118)
            i += 1
            continue

        # H2
        if line.startswith('## '):
            title_txt = line[3:].strip().replace('**', '')
            # Ogni nuovo capitolo numerato (es. "1. ", "2. ", "PARTE ") inizia con spazio extra e keep_with_next
            h2 = doc.add_heading(level=2)
            h2.paragraph_format.space_before = Pt(16)
            h2.paragraph_format.space_after = Pt(6)
            h2.paragraph_format.keep_with_next = True
            r = h2.add_run(title_txt)
            r.bold = True
            r.font.size = Pt(14)
            r.font.color.rgb = RGBColor(30, 64, 175)
            i += 1
            continue

        # H3
        if line.startswith('### '):
            h3 = doc.add_heading(level=3)
            h3.paragraph_format.space_before = Pt(12)
            h3.paragraph_format.space_after = Pt(4)
            h3.paragraph_format.keep_with_next = True
            r = h3.add_run(line[4:].strip().replace('**', ''))
            r.bold = True
            r.font.size = Pt(12)
            r.font.color.rgb = RGBColor(5, 150, 105)
            i += 1
            continue

        # H4
        if line.startswith('#### '):
            h4 = doc.add_heading(level=4)
            h4.paragraph_format.space_before = Pt(10)
            h4.paragraph_format.space_after = Pt(3)
            h4.paragraph_format.keep_with_next = True
            r = h4.add_run(line[5:].strip().replace('**', ''))
            r.bold = True
            r.font.size = Pt(11)
            r.font.color.rgb = RGBColor(109, 40, 217)
            i += 1
            continue

        # Tabelle Markdown
        if '|' in line and i + 1 < len(lines) and '---' in lines[i + 1]:
            headers, rows, end_idx = parse_md_table(lines, i)
            if headers and rows:
                num_cols = len(headers)
                tbl = doc.add_table(rows=1 + len(rows), cols=num_cols)
                tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                tbl.style = 'Table Grid'
                # Header row
                hdr_cells = tbl.rows[0].cells
                for j, h_text in enumerate(headers):
                    if j < num_cols:
                        set_cell_background(hdr_cells[j], "1E3A8A")
                        set_cell_margins(hdr_cells[j], 90, 90, 120, 120)
                        p_cell = hdr_cells[j].paragraphs[0]
                        r_h = p_cell.add_run(re.sub(r'[*`]', '', h_text))
                        r_h.bold = True
                        r_h.font.size = Pt(9.5)
                        r_h.font.color.rgb = RGBColor(255, 255, 255)
                # Body rows
                for r_idx, row_data in enumerate(rows):
                    row_cells = tbl.rows[r_idx + 1].cells
                    bg_hex = "F8FAFC" if r_idx % 2 == 0 else "FFFFFF"
                    for j in range(num_cols):
                        val = row_data[j] if j < len(row_data) else ""
                        set_cell_background(row_cells[j], bg_hex)
                        set_cell_margins(row_cells[j], 80, 80, 120, 120)
                        p_cell = row_cells[j].paragraphs[0]
                        add_formatted_runs(p_cell, val, default_color=RGBColor(30, 41, 59), default_size=Pt(9.5))
                p_after = doc.add_paragraph()
                p_after.paragraph_format.space_after = Pt(4)
            i = end_idx
            continue

        # Blockquote
        if line.startswith('>'):
            quote_txt = line.lstrip('> ').strip()
            p_q = doc.add_paragraph()
            p_q.paragraph_format.left_indent = Inches(0.3)
            p_q.paragraph_format.right_indent = Inches(0.2)
            p_q.paragraph_format.space_before = Pt(6)
            p_q.paragraph_format.space_after = Pt(6)
            add_formatted_runs(p_q, quote_txt, default_color=RGBColor(146, 64, 14), default_size=Pt(10))
            i += 1
            continue

        # Elenchi puntati (anche indentati)
        m_bul = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if m_bul:
            indent_spaces = len(m_bul.group(1))
            item_txt = m_bul.group(2).strip()
            p_li = doc.add_paragraph(style='List Bullet')
            if indent_spaces >= 2:
                p_li.paragraph_format.left_indent = Inches(0.55)
            p_li.paragraph_format.space_before = Pt(1.5)
            p_li.paragraph_format.space_after = Pt(2.5)
            add_formatted_runs(p_li, item_txt)
            i += 1
            continue

        # Elenchi numerati
        m_num = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        if m_num:
            indent_spaces = len(m_num.group(1))
            num_str = m_num.group(2)
            item_txt = m_num.group(3).strip()
            p_num = doc.add_paragraph()
            p_num.paragraph_format.left_indent = Inches(0.3 if indent_spaces < 2 else 0.55)
            p_num.paragraph_format.space_before = Pt(2)
            p_num.paragraph_format.space_after = Pt(3)
            r_n = p_num.add_run(f"{num_str}. ")
            r_n.bold = True
            r_n.font.color.rgb = RGBColor(30, 64, 175)
            add_formatted_runs(p_num, item_txt)
            i += 1
            continue

        # Formula LaTeX $$...$$
        if line.strip().startswith('$$') and line.strip().endswith('$$'):
            formula = line.strip().strip('$').replace(r'\text{', '').replace('}', '')
            p_f = doc.add_paragraph()
            p_f.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r_f = p_f.add_run(formula)
            r_f.bold = True
            r_f.italic = True
            r_f.font.color.rgb = RGBColor(30, 58, 138)
            i += 1
            continue

        # Paragrafo normale
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(5)
        add_formatted_runs(p, line.strip())
        i += 1


def build_manuale_programmatore_markdown(content_main):
    """Costruisce il markdown specifico per il Manuale 1 (Programmatore & Super-Admin)."""
    intro_prog = """# KANDOR ERP - Manuale Programmatore & Super-Admin
## Guida Tecnico-Direzionale per Gian Carlo Serra — Governance Accessi, Manuali, Suite ERP & Architettura

**Versione 3.3 — 13 Novembre 2026**

---

## SEZIONE SPECIALE PROGRAMMATORE: CONSOLE ACCESSI, GESTIONE DEI 3 MANUALI E ARCHITETTURA

### A.1 Il Ruolo dell'Account Programmatore (`serra` — Gian Carlo Serra)
L'account **Programmatore (`serra`)** e il profilo **Super-Admin** di KANDOR ERP e gode di tre prerogative esclusive:
1. **Visibilita Permanente 38/38 Sezioni**: qualsiasi nuova sezione, modulo direzionale o tabella di sistema e automaticamente e permanentemente visibile all'account `serra`.
2. **Governo Granulare delle Sezioni dei Responsabili (`/gestione-accessi/`)**: tramite la Console Programmatore puoi abilitare o nascondere con 1 clic ciascuna delle **38 sezioni** per ogni singolo Responsabile (*Simone Cortinovis*, *Roberta Gamba*, *Giorgio Gamba*, *Sonia Cavalera*, *Consuelo Pina*, *Carla Bordoni*), modificare i loro username/password e verificare l'effetto esatto con la modalita **`Simula Vista Responsabile`**.
3. **Gestione Diretta dei 3 Manuali del Portale (Download `.DOCX` Modificabili & Upload `.PDF`)**:
   - Direttamente dentro `/gestione-accessi/` trovi il pannello **Gestione dei 3 Manuali Ufficiali** (*1. Manuale Programmatore*, *2. Manuale Responsabili / Admin*, *3. Manuale Dipendenti*);
   - Per ciascuno dei 3 manuali puoi **scaricare il file Word (`.docx`) modificabile**, aprirlo in Microsoft Word per personalizzare testi, immagini o impaginazione, esportarlo in PDF e **ricaricare il PDF finito** direttamente dal pannello di upload;
   - Il PDF caricato viene salvato nel volume persistente della VPS (`/data/kandor/media/manuali/`) e aggiorna all'istante tutti i pulsanti di download del portale, della Web App e di Telegram.

### A.2 Architettura di Produzione sulla VPS SerraStudio (`187.126.30.207`)
- **Dominio HTTPS Ufficiale**: `https://kandor.187.126.30.207.sslip.io`
- **Container Orchestration**: Coolify (Application UUID: `kandor000000000000000001`)
- **Database Centrale**: PostgreSQL 16 (`kandor` su container `msdjhpmobh6gcfqg5pxmf7pq:5432`)
- **Storage Persistente Media & Manuali**: volume host `/data/kandor/media` montato su `/app/media` (contiene fotocamere cantiere, cedolini buste paga PDF divisi per C.F. e i manuali PDF/DOCX caricati dal Programmatore).
- **Webhook Bot Telegram**: attivo su `https://kandor.187.126.30.207.sslip.io/telegram-webhook/` con stato conversazionale persistente su database (`TelegramConversationState`) e cache condivisa multi-worker.

---
"""
    return intro_prog + "\n" + content_main


def genera_tutti_i_docx(output_dir=None):
    target_dir = output_dir or BASE_DIR
    os.makedirs(target_dir, exist_ok=True)

    with open(os.path.join(BASE_DIR, 'MANUALE_UTENTE.md'), 'r', encoding='utf-8') as f:
        content_main = f.read()

    with open(os.path.join(BASE_DIR, 'MANUALE_DIPENDENTE_TELEGRAM.md'), 'r', encoding='utf-8') as f:
        content_dip = f.read()

    content_prog = build_manuale_programmatore_markdown(content_main)

    # 1. MANUALE PROGRAMMATORE (.docx)
    doc_prog = Document()
    configure_document_styles(doc_prog)
    add_cover_page(
        doc_prog,
        "KANDOR ERP — MANUALE PROGRAMMATORE",
        "Guida Completa Super-Admin, Console Accessi & Architettura Completa (38 Sezioni)",
        "Versione 3.3 — 13 Novembre 2026 (File Word .DOCX Modificabile)",
        "Documento riservato al Programmatore (Gian Carlo Serra). Modificabile liberamente in Microsoft Word per personalizzare l'impaginazione prima dell'esportazione e del caricamento in PDF nella Console Programmatore (/gestione-accessi/).",
    )
    render_markdown_to_docx(doc_prog, content_prog, skip_first_h1=True)
    path_prog = os.path.join(target_dir, 'MANUALE_PROGRAMMATORE_KANDOR.docx')
    doc_prog.save(path_prog)

    # 2. MANUALE AMMINISTRAZIONE / RESPONSABILI (.docx)
    doc_admin = Document()
    configure_document_styles(doc_admin)
    add_cover_page(
        doc_admin,
        "KANDOR ERP — MANUALE RESPONSABILI & ADMIN",
        "Introduzione Esaustiva alle Funzioni del Programma e Guida Operativa Passo-Passo",
        "Versione 3.3 — 13 Novembre 2026 (File Word .DOCX Modificabile)",
        "Manuale operativo completo per Titolari, Amministrazione e Responsabili d'Area. Modificabile in Microsoft Word e ricaricabile in formato PDF dalla Console Programmatore (/gestione-accessi/).",
    )
    render_markdown_to_docx(doc_admin, content_main, skip_first_h1=True)
    path_admin = os.path.join(target_dir, 'MANUALE_UTENTE_KANDOR.docx')
    doc_admin.save(path_admin)

    # 3. MANUALE DIPENDENTE — WEB APP & TELEGRAM (.docx)
    doc_dip = Document()
    configure_document_styles(doc_dip)
    add_cover_page(
        doc_dip,
        "KANDOR — GUIDA OPERATIVA DIPENDENTE",
        "Manuale Passo-Passo per Web App Mobile (/app/) & Bot Telegram (@kandor_gestionale_bot)",
        "Versione 3.3 — 13 Novembre 2026 (File Word .DOCX Modificabile)",
        "Guida pratica illustrata per tutti i lavoratori Kandor: primo accesso, registrazione ore, motivazione scostamenti, recupero turni 31 giorni, timbratura GPS/QR, assenze, richiesta materiali e scarico Buste Paga PDF.",
    )
    render_markdown_to_docx(doc_dip, content_dip, skip_first_h1=True)
    path_dip = os.path.join(target_dir, 'MANUALE_DIPENDENTE_KANDOR.docx')
    doc_dip.save(path_dip)

    return {
        'programmatore': path_prog,
        'admin': path_admin,
        'dipendente': path_dip,
    }


if __name__ == '__main__':
    paths = genera_tutti_i_docx()
    for k, p in paths.items():
        print(f"DOCX generato [{k}]: {p} ({os.path.getsize(p):,} bytes)")
