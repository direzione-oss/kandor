from django.urls import path
from .views import (
    find_jolly_view, reconciliation_view, generate_shifts_view,
    data_management_view, download_template_view, import_data_view,
    export_data_view, backup_db_view, restore_db_view, manuale_view, manuale_pdf_view, manuale_dipendente_pdf_view, manuale_screenshot_view, manuale_dipendente_view,
    chat_simulator_view, telegram_webhook_view, toggle_telegram_status,
    extend_contract_view, analisi_contratti_view, pdf_contratti_sotto_soglia,
    add_turno_ajax, edit_turno_ajax, delete_turno_ajax, get_squadre_clienti_json,
    copy_move_turno_ajax, get_assegnazione_componenti_json, assegna_sostituto_turno_ajax,
    validate_ore_ajax, verifica_ore_view, pdf_verifica_ore,
    report_paghe_view, pdf_report_paghe, export_paghe_csv, salva_modifica_cedolino_ajax,
    richiesta_sostituzione_api, risposta_sostituto_api, trova_sostituti_api,
    get_sostituti_richiesta_api, invia_notifiche_sostituti_api,
    valida_assenza_api, conferma_sostituto_ufficio_api,
    titolari_dashboard_view, titolari_riepilogo_view,
    settimana_pdf_view,
    dev_tools_view, dev_tools_pull, dev_tools_push, dev_tools_push_status, dev_tools_backup, dev_tools_publish_code,
    installa_locale_view, installa_locale_download, debug_db_view,
    ia_hub_view, ia_auto_valida_ore_api, ia_invia_briefing_api, ia_mezzo_manutenzione_api, ia_analizza_documento_api,
    gestione_procedure_view, gestione_procedure_api,
)
from .views_webapp import (
    dipendente_app_view,
    dipendente_app_login_view,
    dipendente_app_logout_view,
    dipendente_app_action_view,
    dipendente_app_manifest_view,
    dipendente_app_sw_view,
    dipendente_app_icon_view,
)
from .views_buste_paga import (
    buste_paga_view,
    buste_paga_api_view,
    scarica_busta_paga_token_view,
)
from .views_accessi import (
    gestione_accessi_view,
    gestione_accessi_api_view,
    scarica_manuale_docx_view,
    manuale_programmatore_pdf_view,
)
from .views_erp_pro import (
    magazzino_dotazioni_view,
    magazzino_dotazioni_api,
    qualita_ispezioni_view,
    qualita_ispezioni_api,
    pdf_verbale_ispezione_view,
    qr_code_cantiere_view,
    preventivi_crm_view,
    preventivi_crm_api,
    pdf_preventivo_commerciale_view,
    pre_fatturazione_view,
    pre_fatturazione_api,
    export_pre_fatturazione_csv,
)
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)), # Redirect root to admin
    path('debug-db/', debug_db_view, name='debug_db'),
    path('find-jolly/', find_jolly_view, name='find_jolly'),
    path('reconciliation/', reconciliation_view, name='reconciliation'),
    path('manuale/', manuale_view, name='manuale_utente'),
    path('manuale/pdf/', manuale_pdf_view, name='manuale_pdf'),
    path('manuale/screenshots/<str:filename>', manuale_screenshot_view, name='manuale_screenshot'),
    path('screenshots/<str:filename>', manuale_screenshot_view, name='root_screenshot'),
    path('manuale-dipendente/', manuale_dipendente_view, name='manuale_dipendente'),
    path('manuale-dipendente/pdf/', manuale_dipendente_pdf_view, name='manuale_dipendente_pdf'),
    path('generate-shifts/', generate_shifts_view, name='generate_shifts'),
    
    # Data Management
    path('data-management/', data_management_view, name='data_management'),
    path('data-management/download/<str:model_name>/', download_template_view, name='download_template'),
    path('data-management/export/<str:model_name>/', export_data_view, name='export_data'),
    path('data-management/import/', import_data_view, name='import_data'),
    path('data-management/backup/', backup_db_view, name='backup_db'),
    path('data-management/restore/', restore_db_view, name='restore_db'),
    
    # Chat & Telegram
    path('chat-simulator/', chat_simulator_view, name='chat_simulator'),
    path('telegram-webhook/', telegram_webhook_view, name='telegram_webhook'),
    path('telegram-toggle/<str:model_name>/<int:item_id>/', toggle_telegram_status, name='toggle_telegram_status'),
    
    # Proroga Contratti
    path('extend-contract/<int:prog_id>/', extend_contract_view, name='extend_contract'),
    
    # Analisi Economica
    path('analisi-contratti/', analisi_contratti_view, name='analisi_contratti'),
    path('analisi-contratti/pdf/', pdf_contratti_sotto_soglia, name='pdf_contratti_sotto_soglia'),
    
    # Calendario Turni AJAX
    path('api/add-turno/', add_turno_ajax, name='add_turno_ajax'),
    path('api/edit-turno/<int:assign_id>/', edit_turno_ajax, name='edit_turno_ajax'),
    path('api/delete-turno/<int:assign_id>/', delete_turno_ajax, name='delete_turno_ajax'),
    path('api/squadre-clienti/', get_squadre_clienti_json, name='get_squadre_clienti'),
    path('api/validate-ore/<int:assign_id>/', validate_ore_ajax, name='validate_ore_ajax'),
    path('api/copy-move-turno/<int:assign_id>/', copy_move_turno_ajax, name='copy_move_turno_ajax'),
    path('api/assegnazione-componenti/<int:assign_id>/', get_assegnazione_componenti_json, name='get_assegnazione_componenti'),
    path('api/assegna-sostituto-turno/<int:assign_id>/', assegna_sostituto_turno_ajax, name='assegna_sostituto_turno_ajax'),
    path('verifica-ore/', verifica_ore_view, name='verifica_ore'),
    path('report-paghe/', report_paghe_view, name='report_paghe'),
    path('report-paghe/pdf/', pdf_report_paghe, name='pdf_report_paghe'),
    path('report-paghe/csv/', export_paghe_csv, name='export_paghe_csv'),
    path('report-paghe/salva-modifica/', salva_modifica_cedolino_ajax, name='salva_modifica_cedolino'),
    path('pdf-verifica-ore/', pdf_verifica_ore, name='pdf_verifica_ore'),
    path('settimana-pdf/', settimana_pdf_view, name='settimana_pdf'),
    
    # Gestione Sostituti
    path('api/richiesta-sostituzione/', richiesta_sostituzione_api, name='richiesta_sostituzione'),
    path('api/risposta-sostituto/<int:richiesta_id>/', risposta_sostituto_api, name='risposta_sostituto'),
    path('api/trova-sostituti/', trova_sostituti_api, name='trova_sostituti'),
    path('api/sostituti-disponibili/<int:richiesta_id>/', get_sostituti_richiesta_api, name='get_sostituti_richiesta_api'),
    path('api/invia-notifiche-sostituti/', invia_notifiche_sostituti_api, name='invia_notifiche_sostituti_api'),
    path('api/valida-assenza/<int:assenza_id>/', valida_assenza_api, name='valida_assenza_api'),
    path('api/conferma-sostituto-ufficio/', conferma_sostituto_ufficio_api, name='conferma_sostituto_ufficio_api'),

    # Dashboard Titolari
    path('titolari/', titolari_dashboard_view, name='titolari_dashboard'),
    path('titolari/riepilogo/', titolari_riepilogo_view, name='titolari_riepilogo'),

    # Dev Tools (solo LOCAL_DEV)
    path('dev-tools/', dev_tools_view, name='dev_tools'),
    path('dev-tools/pull/', dev_tools_pull, name='dev_tools_pull'),
    path('dev-tools/push/', dev_tools_push, name='dev_tools_push'),
    path('dev-tools/push-status/<str:job_id>/', dev_tools_push_status, name='dev_tools_push_status'),
    path('dev-tools/backup/', dev_tools_backup, name='dev_tools_backup'),
    path('dev-tools/publish-code/', dev_tools_publish_code, name='dev_tools_publish_code'),

    # Installa Locale (accessibile da Render per scaricare i file)
    path('installa-locale/', installa_locale_view, name='installa_locale'),
    path('installa-locale/download/<str:file_type>/', installa_locale_download, name='installa_locale_download'),

    # Web App Mobile Dipendenti (PWA)
    path('app/', dipendente_app_view, name='dipendente_app'),
    path('app/login/', dipendente_app_login_view, name='dipendente_app_login'),
    path('app/logout/', dipendente_app_logout_view, name='dipendente_app_logout'),
    path('app/action/', dipendente_app_action_view, name='dipendente_app_action'),
    path('app/manifest.json', dipendente_app_manifest_view, name='dipendente_app_manifest'),
    path('app/sw.js', dipendente_app_sw_view, name='dipendente_app_sw'),
    path('app/icon.svg', dipendente_app_icon_view, name='dipendente_app_icon'),

    # Centro IA & Automazioni Zero-Cost
    path('ia-hub/', ia_hub_view, name='ia_hub'),
    path('api/ia/auto-valida-ore/', ia_auto_valida_ore_api, name='ia_auto_valida_ore_api'),
    path('api/ia/invia-briefing/', ia_invia_briefing_api, name='ia_invia_briefing_api'),
    path('api/ia/mezzo-manutenzione/', ia_mezzo_manutenzione_api, name='ia_mezzo_manutenzione_api'),
    path('api/ia/analizza-documento/', ia_analizza_documento_api, name='ia_analizza_documento_api'),

    # Gestione Procedure Operative (es. Disdetta Contratto, Checklist personalizzabili)
    path('procedure/', gestione_procedure_view, name='gestione_procedure'),
    path('api/procedure/action/', gestione_procedure_api, name='gestione_procedure_api'),

    # Buste Paga Automatiche (Split PDF per Codice Fiscale + Invio Telegram / WhatsApp)
    path('buste-paga/', buste_paga_view, name='buste_paga'),
    path('api/buste-paga/action/', buste_paga_api_view, name='buste_paga_api'),
    path('buste-paga/scarica/<str:token>/', scarica_busta_paga_token_view, name='scarica_busta_paga_token'),

    # Console Programmatore (Serra Gian Carlo) — Gestione Accessi & Sezioni Responsabili
    path('gestione-accessi/', gestione_accessi_view, name='gestione_accessi'),
    path('api/gestione-accessi/action/', gestione_accessi_api_view, name='gestione_accessi_api'),
    path('gestione-accessi/manuale/<str:tipo>/docx/', scarica_manuale_docx_view, name='scarica_manuale_docx'),
    path('manuale-programmatore/pdf/', manuale_programmatore_pdf_view, name='manuale_programmatore_pdf'),

    # 1-5 Migliorie ERP PRO (Magazzino & Dotazioni, Qualità & SLA, Preventivi CRM, Pre-Fatturazione)
    path('magazzino-dotazioni/', magazzino_dotazioni_view, name='magazzino_dotazioni'),
    path('api/magazzino-dotazioni/action/', magazzino_dotazioni_api, name='magazzino_dotazioni_api'),
    path('qualita-ispezioni/', qualita_ispezioni_view, name='qualita_ispezioni'),
    path('api/qualita-ispezioni/action/', qualita_ispezioni_api, name='qualita_ispezioni_api'),
    path('qualita-ispezioni/pdf/<int:ispezione_id>/', pdf_verbale_ispezione_view, name='pdf_verbale_ispezione'),
    path('qualita-ispezioni/qr/<int:cliente_id>/', qr_code_cantiere_view, name='qr_code_cantiere'),
    path('preventivi-crm/', preventivi_crm_view, name='preventivi_crm'),
    path('api/preventivi-crm/action/', preventivi_crm_api, name='preventivi_crm_api'),
    path('preventivi-crm/pdf/<int:prev_id>/', pdf_preventivo_commerciale_view, name='pdf_preventivo_commerciale'),
    path('pre-fatturazione/', pre_fatturazione_view, name='pre_fatturazione'),
    path('api/pre-fatturazione/action/', pre_fatturazione_api, name='pre_fatturazione_api'),
    path('pre-fatturazione/csv/', export_pre_fatturazione_csv, name='export_pre_fatturazione_csv'),
]
