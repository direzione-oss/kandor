import pandas as pd
import io
import xlsxwriter
import datetime
from .models import Dipendente, Cliente, Mezzo, Qualifica

# Definiamo le colonne per ogni modello
COLUMNS_MAP = {
    'dipendente': [
        'nome', 'cognome', 'codice_fiscale', 'data_nascita', 'stato',
        'email', 'telefono', 'indirizzo_residenza', 
        'qualifiche_nomi', 'telegram_chat_id'
    ],
    'cliente': [
        'ragione_sociale', 'partita_iva', 'codice_fiscale', 'indirizzo_sede',
        'referente_nome', 'referente_ruolo', 'referente_data_nascita',
        'ore_mensili_contratto', 'importo_mensile_contratto', 'note_mansioni'
    ],
    'mezzo': [
        'targa', 'modello', 'scadenza_assicurazione', 'scadenza_revisione', 'scadenza_permesso_citta_alta'
    ]
}

def generate_excel_template(model_name):
    """
    Genera un file Excel vuoto (solo header) per il modello specificato.
    Ritorna un oggetto BytesIO.
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    
    cols = COLUMNS_MAP.get(model_name, [])
    
    # Header format
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#D7E4BC',
        'border': 1
    })
    
    for i, col in enumerate(cols):
        worksheet.write(0, i, col, header_format)
        worksheet.set_column(i, i, 20) # Width
        
    # Aggiunge una riga di esempio
    if model_name == 'dipendente':
        example_format = workbook.add_format({'italic': True, 'color': 'gray'})
        worksheet.write(1, 0, "Mario", example_format)
        worksheet.write(1, 1, "Rossi", example_format)
        worksheet.write(1, 2, "RSSMRA80A01H501U", example_format)
        worksheet.write(1, 3, "01/01/1980", example_format) # Data Nascita
        worksheet.write(1, 4, "ATTIVO", example_format) # Stato
        worksheet.write(1, 5, "mario.rossi@email.it", example_format) # Email
        worksheet.write(1, 6, "3331234567", example_format) # Telefono
        worksheet.write(1, 7, "Via Roma 1, Milano", example_format) # Indirizzo
        worksheet.write(1, 8, "Addetto Pulizie, Caposquadra", example_format)
        worksheet.write(1, 9, "123456789", example_format) # Telegram ID
    
    workbook.close()
    output.seek(0)
    return output

def import_from_excel(model_name, file_obj, mode='UPDATE'):
    """
    Legge un file Excel e crea/aggiorna i record.
    Ritorna (success_count, errors_list).
    mode: 'UPDATE' (sovrascrive se esiste), 'ADD_ONLY' (salta se esiste)
    """
    try:
        df = pd.read_excel(file_obj)
    except Exception as e:
        return 0, [f"Errore lettura file: {str(e)}"]
    
    cols = COLUMNS_MAP.get(model_name)
    if not cols:
        return 0, ["Modello non supportato"]
        
    success_count = 0
    errors = []
    
    # Mappa per normalizzare lo stato (da input utente a chiave modello db)
    stato_mapping = {
        'ATTIVO': 'ATTIVO', 'ATTIVA': 'ATTIVO',
        'MALATTIA': 'MALATTIA', 'IN MALATTIA': 'MALATTIA',
        'FERIE': 'FERIE', 'IN FERIE': 'FERIE',
        'PERMESSO': 'PERMESSO', 'IN PERMESSO': 'PERMESSO',
        'LEGGE 104': '104', '104': '104',
        'INATTIVO': 'INATTIVO', 'LICENZIATO': 'INATTIVO'
    }

    for index, row in df.iterrows():
        try:
            # Skip example row if it looks like the example
            if model_name == 'dipendente' and str(row.get('nome')) == 'Mario' and str(row.get('codice_fiscale')) == 'RSSMRA80A01H501U':
                 continue

            if models_validation_check(row, model_name):
                 # Skip invalid rows or empty ones
                 if pd.isna(row.get(cols[0])): # Check if primary identifier col is empty roughly
                     continue

            if model_name == 'dipendente':
                cf = row.get('codice_fiscale')
                if pd.isna(cf): 
                    errors.append(f"Riga {index+2}: Codice Fiscale mancante")
                    continue
                
                # Check Mode ADD_ONLY
                if mode == 'ADD_ONLY':
                    if Dipendente.objects.filter(codice_fiscale=cf).exists():
                        continue # Skip existing
                
                # Campi obbligatori
                if pd.isna(row.get('nome')) or pd.isna(row.get('cognome')):
                    continue
                
                # Parsing Data Nascita (Flexible)
                data_nascita = row.get('data_nascita')
                dt_nascita = None
                if not pd.isna(data_nascita):
                    try:
                        dt_nascita = pd.to_datetime(data_nascita).date()
                    except:
                        # Se la data è invalida, la ignoriamo (dato che è opzionale ora)
                        # errors.append(f"Riga {index+2}: Formato Data Nascita non valido. Salvato come vuoto.")
                        pass

                # Parsing Stato
                raw_stato = str(row.get('stato', 'ATTIVO')).upper().strip()
                stato_val = stato_mapping.get(raw_stato, 'ATTIVO')

                raw_tg = str(row.get('telegram_chat_id', '')).replace('.0', '').strip() if not pd.isna(row.get('telegram_chat_id')) else ''
                if raw_tg:
                    conflitto_tg = Dipendente.objects.filter(telegram_chat_id=raw_tg).exclude(codice_fiscale__iexact=cf).first()
                    if conflitto_tg:
                        errors.append(
                            f"Riga {index + 2}: ID Telegram '{raw_tg}' ignorato perché già associato a {conflitto_tg.cognome} {conflitto_tg.nome}."
                        )
                        raw_tg = None
                else:
                    raw_tg = None

                # Preparazione defaults
                defaults = {
                    'nome': row['nome'],
                    'cognome': row['cognome'],
                    'data_nascita': dt_nascita,
                    'email': row.get('email', '') if not pd.isna(row.get('email')) else '',
                    'telefono': row.get('telefono', '') if not pd.isna(row.get('telefono')) else '',
                    'indirizzo_residenza': row.get('indirizzo_residenza', '') if not pd.isna(row.get('indirizzo_residenza')) else '',
                    'stato': stato_val,
                    'telegram_chat_id': raw_tg
                }
                
                obj, created = Dipendente.objects.update_or_create(
                    codice_fiscale=cf,
                    defaults=defaults
                )
                
                # Handle qualifiche (Many-to-Many)
                q_names = row.get('qualifiche_nomi')
                if q_names and not pd.isna(q_names):
                    names = [n.strip() for n in str(q_names).split(',')]
                    pts = []
                    for n in names:
                        if n: # avoid empty strings
                            q_obj, _ = Qualifica.objects.get_or_create(nome=n)
                            pts.append(q_obj)
                    obj.qualifiche.set(pts)
                    
                success_count += 1

            elif model_name == 'cliente':
                rs = row.get('ragione_sociale')
                if pd.isna(rs): continue
                
                defaults = {
                    'partita_iva': row.get('partita_iva', '') if not pd.isna(row.get('partita_iva')) else '',
                    'codice_fiscale': row.get('codice_fiscale', '') if not pd.isna(row.get('codice_fiscale')) else '',
                    'indirizzo_sede': row.get('indirizzo_sede', '') if not pd.isna(row.get('indirizzo_sede')) else '',
                    'referente_nome': row.get('referente_nome', '') if not pd.isna(row.get('referente_nome')) else '',
                    'referente_ruolo': row.get('referente_ruolo', '') if not pd.isna(row.get('referente_ruolo')) else '',
                    'note_mansioni': row.get('note_mansioni', '') if not pd.isna(row.get('note_mansioni')) else '',
                }
                
                # Ore mensili contratto
                ore = row.get('ore_mensili_contratto')
                if not pd.isna(ore):
                    try: defaults['ore_mensili_contratto'] = float(ore)
                    except: pass
                
                # Importo mensile contratto
                importo = row.get('importo_mensile_contratto')
                if not pd.isna(importo):
                    try: defaults['importo_mensile_contratto'] = float(importo)
                    except: pass
                
                # Data nascita referente
                ref_nascita = row.get('referente_data_nascita')
                if not pd.isna(ref_nascita):
                    try: defaults['referente_data_nascita'] = pd.to_datetime(ref_nascita).date()
                    except: pass

                obj, created = Cliente.objects.update_or_create(
                    ragione_sociale=rs,
                    defaults=defaults
                )
                success_count += 1
                
            elif model_name == 'mezzo':
                targa = row.get('targa')
                if pd.isna(targa): continue
                
                defaults = {'modello': row.get('modello', '')}
                scad_ass = row.get('scadenza_assicurazione')
                if not pd.isna(scad_ass):
                    try: defaults['scadenza_polizza'] = pd.to_datetime(scad_ass).date()
                    except: pass
                scad_revisione = row.get('scadenza_revisione')
                if not pd.isna(scad_revisione):
                     try: defaults['scadenza_revisione'] = pd.to_datetime(scad_revisione).date()
                     except: pass
                scad_permesso_ca = row.get('scadenza_permesso_citta_alta')
                if not pd.isna(scad_permesso_ca):
                     try: defaults['scadenza_permesso_citta_alta'] = pd.to_datetime(scad_permesso_ca).date()
                     except: pass
                
                obj, created = Mezzo.objects.update_or_create(
                    targa=targa,
                    defaults=defaults
                )
                success_count += 1

        except Exception as e:
            errors.append(f"Riga {index+2}: {str(e)}")
            
    return success_count, errors

def models_validation_check(row, model_name):
    return True


def export_data_excel(model_name):
    """
    Esporta tutti i dati esistenti di un modello in un file Excel.
    Usa le stesse colonne di COLUMNS_MAP per compatibilità con l'import.
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    
    cols = COLUMNS_MAP.get(model_name, [])
    
    # Header format
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#4472C4',
        'font_color': 'white',
        'border': 1
    })
    
    for i, col in enumerate(cols):
        worksheet.write(0, i, col, header_format)
        worksheet.set_column(i, i, 22)
    
    row_num = 1
    
    if model_name == 'dipendente':
        for dip in Dipendente.objects.all().order_by('cognome', 'nome'):
            worksheet.write(row_num, 0, dip.nome or '')
            worksheet.write(row_num, 1, dip.cognome or '')
            worksheet.write(row_num, 2, dip.codice_fiscale or '')
            worksheet.write(row_num, 3, dip.data_nascita.strftime('%d/%m/%Y') if dip.data_nascita else '')
            worksheet.write(row_num, 4, dip.stato or 'ATTIVO')
            worksheet.write(row_num, 5, dip.email or '')
            worksheet.write(row_num, 6, dip.telefono or '')
            worksheet.write(row_num, 7, dip.indirizzo_residenza or '')
            qualifiche = ', '.join([q.nome for q in dip.qualifiche.all()])
            worksheet.write(row_num, 8, qualifiche)
            worksheet.write(row_num, 9, dip.telegram_chat_id or '')
            row_num += 1
    
    elif model_name == 'cliente':
        for cli in Cliente.objects.all().order_by('ragione_sociale'):
            worksheet.write(row_num, 0, cli.ragione_sociale or '')
            worksheet.write(row_num, 1, cli.partita_iva or '')
            worksheet.write(row_num, 2, cli.codice_fiscale or '')
            worksheet.write(row_num, 3, cli.indirizzo_sede or '')
            worksheet.write(row_num, 4, cli.referente_nome or '')
            worksheet.write(row_num, 5, cli.referente_ruolo or '')
            worksheet.write(row_num, 6, cli.referente_data_nascita.strftime('%d/%m/%Y') if cli.referente_data_nascita else '')
            worksheet.write(row_num, 7, float(cli.ore_mensili_contratto) if cli.ore_mensili_contratto else 0)
            worksheet.write(row_num, 8, float(cli.importo_mensile_contratto) if cli.importo_mensile_contratto else 0)
            worksheet.write(row_num, 9, cli.note_mansioni or '')
            row_num += 1
    
    elif model_name == 'mezzo':
        for mezzo in Mezzo.objects.all().order_by('targa'):
            worksheet.write(row_num, 0, mezzo.targa or '')
            worksheet.write(row_num, 1, mezzo.modello or '')
            worksheet.write(row_num, 2, mezzo.scadenza_polizza.strftime('%d/%m/%Y') if mezzo.scadenza_polizza else '')
            worksheet.write(row_num, 3, mezzo.scadenza_revisione.strftime('%d/%m/%Y') if mezzo.scadenza_revisione else '')
            worksheet.write(row_num, 4, mezzo.scadenza_permesso_citta_alta.strftime('%d/%m/%Y') if mezzo.scadenza_permesso_citta_alta else '')
            row_num += 1
    
    workbook.close()
    output.seek(0)
    return output


def export_dipendenti_to_excel(queryset):
    """
    Esporta un queryset di Dipendente (filtrato dai filtri admin o completo)
    in un file Excel (.xlsx) con formattazione professionale, larghezza colonne automatica,
    blocco riga intestazioni e autofiltro.
    """
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Dipendenti')

    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#1E293B',
        'font_color': '#FFFFFF',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Arial',
        'font_size': 10,
    })

    cell_left = workbook.add_format({
        'border': 1,
        'align': 'left',
        'valign': 'vcenter',
        'font_name': 'Arial',
        'font_size': 9.5,
    })
    cell_center = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Arial',
        'font_size': 9.5,
    })
    cell_date = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'num_format': 'dd/mm/yyyy',
        'font_name': 'Arial',
        'font_size': 9.5,
    })
    cell_currency = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '€ #,##0.00',
        'font_name': 'Arial',
        'font_size': 9.5,
    })
    cell_decimal = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter',
        'num_format': '#,##0.0',
        'font_name': 'Arial',
        'font_size': 9.5,
    })

    from .services import get_dipendenti_con_turni_futuri_ids
    turni_futuri_ids = get_dipendenti_con_turni_futuri_ids()

    headers = [
        'ID',
        'Cognome',
        'Nome',
        'Codice Fiscale',
        'Stato',
        'Turni Futuri Programmati',
        'Data Nascita',
        'Data Assunzione',
        'Data Licenziamento',
        'Livello Contrattuale',
        'Costo Orario Aziendale',
        'Part-Time',
        'Tipo Part-Time',
        'Ore Settimana Part-Time',
        'Sostituto Disponibile',
        'Jolly',
        'Categoria Protetta',
        'Legge 104',
        'Riceve Notifiche Resp.',
        'Qualifiche / Mansioni',
        'Telefono',
        'Email',
        'Indirizzo Residenza',
        'Scadenza Visita Medica',
        'Privacy Accettata',
        'PIN Accesso App',
        'Telegram Chat ID',
    ]

    worksheet.set_row(0, 26)
    for col_idx, h in enumerate(headers):
        worksheet.write(0, col_idx, h, header_format)

    col_widths = [len(h) + 4 for h in headers]

    row_idx = 1
    for dip in queryset:
        qualifiche_str = ', '.join([q.nome for q in dip.qualifiche.all()])

        data_row = [
            (dip.id, cell_center),
            (dip.cognome or '', cell_left),
            (dip.nome or '', cell_left),
            (dip.codice_fiscale or '', cell_center),
            (dip.get_stato_display() if hasattr(dip, 'get_stato_display') else (dip.stato or ''), cell_center),
            ('Sì' if dip.id in turni_futuri_ids else 'No', cell_center),
            (dip.data_nascita.strftime('%d/%m/%Y') if dip.data_nascita else '', cell_date if dip.data_nascita else cell_center),
            (dip.data_assunzione.strftime('%d/%m/%Y') if dip.data_assunzione else '', cell_date if dip.data_assunzione else cell_center),
            (dip.data_licenziamento.strftime('%d/%m/%Y') if dip.data_licenziamento else '', cell_date if dip.data_licenziamento else cell_center),
            (dip.get_livello_contrattuale_display() if hasattr(dip, 'get_livello_contrattuale_display') else (dip.livello_contrattuale or ''), cell_center),
            (float(dip.costo_orario_aziendale) if dip.costo_orario_aziendale is not None else '', cell_currency if dip.costo_orario_aziendale is not None else cell_center),
            ('Sì' if dip.is_part_time else 'No', cell_center),
            (dip.get_tipo_part_time_display() if hasattr(dip, 'get_tipo_part_time_display') else (dip.tipo_part_time or ''), cell_center),
            (float(dip.ore_settimanali_part_time) if dip.ore_settimanali_part_time is not None else '', cell_decimal if dip.ore_settimanali_part_time is not None else cell_center),
            ('Sì' if dip.is_sostituto else 'No', cell_center),
            ('Sì' if dip.is_jolly else 'No', cell_center),
            ('Sì' if dip.categoria_protetta else 'No', cell_center),
            ('Sì' if dip.usufruisce_104 else 'No', cell_center),
            ('Sì' if dip.riceve_notifiche_messaggi else 'No', cell_center),
            (qualifiche_str, cell_left),
            (dip.telefono or '', cell_center),
            (dip.email or '', cell_left),
            (dip.indirizzo_residenza or '', cell_left),
            (dip.data_ultima_visita_medica.strftime('%d/%m/%Y') if dip.data_ultima_visita_medica else '', cell_date if dip.data_ultima_visita_medica else cell_center),
            ('Sì' if dip.privacy_accettata else 'No', cell_center),
            (dip.pin_accesso or '', cell_center),
            (dip.telegram_chat_id or '', cell_center),
        ]

        worksheet.set_row(row_idx, 20)
        for c_idx, (val, fmt) in enumerate(data_row):
            worksheet.write(row_idx, c_idx, val, fmt)
            s_val = str(val or '')
            if len(s_val) + 3 > col_widths[c_idx]:
                col_widths[c_idx] = min(len(s_val) + 3, 40)

        row_idx += 1

    for c_idx, w in enumerate(col_widths):
        worksheet.set_column(c_idx, c_idx, max(w, 12))

    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max(row_idx - 1, 1), len(headers) - 1)

    workbook.close()
    output.seek(0)
    return output
