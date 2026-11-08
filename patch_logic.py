import re

with open('core/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Processa TimeTracking in report_paghe_view
old_tt = '''        if ore > 0:
            report_data[dip_id]['giorni_lavorati_set'].add(data_turno)

            if cl_nome not in report_data[dip_id]['clienti_dict']:
                report_data[dip_id]['clienti_dict'][cl_nome] = 0.0
            report_data[dip_id]['clienti_dict'][cl_nome] += ore'''
new_tt = '''        if ore > 0:
            report_data[dip_id]['giorni_lavorati_set'].add(data_turno)

            if cl_nome not in report_data[dip_id]['clienti_dict']:
                report_data[dip_id]['clienti_dict'][cl_nome] = 0.0
            report_data[dip_id]['clienti_dict'][cl_nome] += ore
            report_data[dip_id]['ore_per_giorno'][data_turno] = report_data[dip_id]['ore_per_giorno'].get(data_turno, 0.0) + ore'''
content = content.replace(old_tt, new_tt)


# Fix Processa Assenze in report_paghe_view
old_ass = '''    # Processa Assenze
    for assenza in assenze_qs:
        dip_id = assenza.dipendente_id
        if dip_id not in report_data:
            continue

        inizio_eff = max(assenza.data_inizio, data_inizio)
        fine_eff = min(assenza.data_fine, data_fine)
        giorni = (fine_eff - inizio_eff).days + 1'''
new_ass = '''    # Processa Assenze
    from datetime import timedelta
    for assenza in assenze_qs:
        dip_id = assenza.dipendente_id
        if dip_id not in report_data:
            continue

        inizio_eff = max(assenza.data_inizio, data_inizio)
        fine_eff = min(assenza.data_fine, data_fine)
        
        curr_d = inizio_eff
        while curr_d <= fine_eff:
            report_data[dip_id]['assenze_per_giorno'].setdefault(curr_d, []).append(assenza.tipo)
            curr_d += timedelta(days=1)
            
        giorni = (fine_eff - inizio_eff).days + 1'''
content = content.replace(old_ass, new_ass)

with open('core/views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Logic patched!")
