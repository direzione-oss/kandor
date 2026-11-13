"""
Servizio di gestione dell'Account Programmatore (Serra Gian Carlo) e della
visibilità personalizzata delle sezioni del Portale Kandor per ciascun Responsabile.
"""
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q


CATALOGO_SEZIONI_PORTALE = [
    # --- GRUPPO 1: OPERAZIONI FREQUENTI & MODULI SPECIALI ---
    {
        'codice': 'jolly',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '🏥',
        'titolo': 'Jolly (Trova Sostituto)',
        'descrizione': 'Ricerca rapida sostituti per turni scoperti con Smart Score IA',
        'default_responsabile': True,
    },
    {
        'codice': 'report_ore',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📊',
        'titolo': 'Report Ore (Verifica Ore)',
        'descrizione': 'Verifica e convalida ore mensili e consuntivi cantiere',
        'default_responsabile': True,
    },
    {
        'codice': 'cedolini_paghe',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📋',
        'titolo': 'Cedolini Paghe (Elabora Paghe)',
        'descrizione': 'Prospetto mensile ore ed assenze per studio consulenza del lavoro',
        'default_responsabile': True,
    },
    {
        'codice': 'buste_paga',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📄',
        'titolo': 'Buste Paga (Split PDF & Invio)',
        'descrizione': 'Divisione PDF unico commercialista per C.F. e invio Telegram/WhatsApp',
        'default_responsabile': True,
    },
    {
        'codice': 'chat_telegram',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '💬',
        'titolo': 'Chat & Telegram',
        'descrizione': 'Centro messaggi diretto con dipendenti su Telegram e Web App',
        'default_responsabile': True,
    },
    {
        'codice': 'app_dipendenti',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📲',
        'titolo': 'App Dipendenti (Web App)',
        'descrizione': 'Collegamento rapido alla Web App Mobile per cellulare (/app/)',
        'default_responsabile': True,
    },
    {
        'codice': 'analisi_contratti',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '💰',
        'titolo': 'Contabilità Industriale & MOL (/analisi-contratti/)',
        'descrizione': 'Marginalità reale per cantiere (Ricavi − Costo Orario − Prodotti − Mezzi) e semaforo MOL',
        'default_responsabile': False,
    },
    {
        'codice': 'magazzino_dotazioni',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📦',
        'titolo': 'Magazzino, Dotazioni & Consegne (/magazzino-dotazioni/)',
        'descrizione': 'Inventario prodotti, macchinari in cantiere, consegne e richieste materiali da App/Telegram',
        'default_responsabile': True,
    },
    {
        'codice': 'qualita_ispezioni',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '⭐',
        'titolo': 'Qualità, Ispezioni SLA & QR (/qualita-ispezioni/)',
        'descrizione': 'Verbali di sopralluogo 1-5 stelle, report PDF di cortesia al cliente e QR Code Geofence',
        'default_responsabile': True,
    },
    {
        'codice': 'preventivi_crm',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📐',
        'titolo': 'Preventivazione Rapida CRM (/preventivi-crm/)',
        'descrizione': 'Configuratore sopralluoghi (m², resa oraria, margine), PDF offerta e conversione 1-Click',
        'default_responsabile': True,
    },
    {
        'codice': 'pre_fatturazione',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '🧾',
        'titolo': 'Pre-Fatturazione & Lavori Extra (/pre-fatturazione/)',
        'descrizione': 'Prospetto mensile Canoni + Lavori Straordinari + Extra rilevati dall\'IA per fatturazione',
        'default_responsabile': False,
    },
    {
        'codice': 'procedure',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📋',
        'titolo': 'Procedure & Avvalli (/procedure/)',
        'descrizione': 'Checklist operative, disdetta contratti e avvallo passaggi colleghi',
        'default_responsabile': True,
    },
    {
        'codice': 'gestione_dati',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '💾',
        'titolo': 'Gestione Dati (Import/Export/Backup)',
        'descrizione': 'Importazione ed esportazione Excel/CSV e backup database',
        'default_responsabile': False,
    },
    {
        'codice': 'centro_ia',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '🤖',
        'titolo': 'Centro IA & Smart (/ia-hub/)',
        'descrizione': 'Revisore ore 1-click, Smart Sostituzioni, Compliance ZTL/Corsi e Extra',
        'default_responsabile': True,
    },
    {
        'codice': 'guide_manuali',
        'gruppo': 'OPERAZIONI',
        'gruppo_label': '⚡ Card Operazioni Frequenti & Moduli Principali',
        'icona': '📘',
        'titolo': 'Guide & Manuali',
        'descrizione': 'Manuali operativi Admin e Dipendenti in formato Web e PDF',
        'default_responsabile': True,
    },

    # --- GRUPPO 2: WIDGET & PANNELLI DASHBOARD ---
    {
        'codice': 'widget_procedure_evidenza',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '📌',
        'titolo': 'Banner Procedure in Evidenza & Avvalli',
        'descrizione': 'Riquadro superiore con le proprie procedure in evidenza e OK richiesti',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_telegram_feed',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '📱',
        'titolo': 'Feed Operativo Live (Telegram & App)',
        'descrizione': 'Flusso in tempo reale di ultime ore dichiarate, assenze e segnalazioni',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_scadenze_mezzi',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '🚗',
        'titolo': 'Widget Scadenze Mezzi & ZTL',
        'descrizione': 'Avvisi scadenza assicurazione, revisione e permesso Città Alta',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_scadenze_visite',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '🩺',
        'titolo': 'Widget Scadenze Visite Mediche',
        'descrizione': 'Avvisi visite mediche periodiche dei dipendenti in scadenza/scadute',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_scadenze_corsi',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '🎓',
        'titolo': 'Widget Scadenze Corsi Formazione',
        'descrizione': 'Avvisi attestati sicurezza D.Lgs. 81/08 in scadenza o scaduti',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_compleanni',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '🎂',
        'titolo': 'Widget Compleanni in Arrivo',
        'descrizione': 'Promemoria compleanni di dipendenti e referenti clienti',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_contratti_scadenza',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '📄',
        'titolo': 'Widget Contratti Clienti in Scadenza',
        'descrizione': 'Elenco programmazioni contrattuali in scadenza con proroga rapida',
        'default_responsabile': True,
    },
    {
        'codice': 'widget_calendario_settimanale',
        'gruppo': 'WIDGET',
        'gruppo_label': '📊 Widget, Scadenze & Calendario in Dashboard',
        'icona': '📅',
        'titolo': 'Calendario Programmazione Settimanale',
        'descrizione': 'Griglia interattiva settimanale dei turni, validazione ore e sostituti',
        'default_responsabile': True,
    },

    # --- GRUPPO 3: VOCI OPERATIVITÀ GIORNALIERA, ANAGRAFICHE & SISTEMA ---
    {
        'codice': 'mod_AssegnazioneTurno',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📅',
        'titolo': 'Operatività: Assegnazioni Turni',
        'descrizione': 'Accesso alla tabella completa delle assegnazioni turni giornaliere',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_Assenza',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🏥',
        'titolo': 'Operatività: Assenze',
        'descrizione': 'Gestione e avvallo di malattie, ferie, permessi e Legge 104',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_TimeTracking',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '⏱️',
        'titolo': 'Operatività: Time Tracking (Ore)',
        'descrizione': 'Elenco analitico delle registrazioni ore lavorate e validate',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_Turno',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🔄',
        'titolo': 'Operatività: Turni',
        'descrizione': 'Gestione turni base associati alle squadre',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_ProceduraAvviata',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📋',
        'titolo': 'Operatività: Procedure Avviate (Pratiche)',
        'descrizione': 'Archivio pratiche e checklist operative avviate',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_LottoBustePaga',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📄',
        'titolo': 'Operatività: Lotti Buste Paga',
        'descrizione': 'Archivio lotti mensili buste paga caricati',
        'default_responsabile': False,
    },
    {
        'codice': 'mod_CedolinoDipendente',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📑',
        'titolo': 'Operatività: Buste Paga Dipendenti',
        'descrizione': 'Archivio singoli cedolini PDF estratti per dipendente',
        'default_responsabile': False,
    },
    {
        'codice': 'mod_Dipendente',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '👥',
        'titolo': 'Anagrafiche: Dipendenti',
        'descrizione': 'Elenco e schede anagrafiche dei lavoratori, PIN App e corsi',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_Cliente',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🏢',
        'titolo': 'Anagrafiche: Clienti & Programmazioni',
        'descrizione': 'Schede clienti, sedi cantieri e programmazioni ricorrenti',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_Squadra',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '👷',
        'titolo': 'Anagrafiche: Squadre',
        'descrizione': 'Composizione squadre operative e capisquadra',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_Mezzo',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🚐',
        'titolo': 'Anagrafiche: Mezzi Aziendali',
        'descrizione': 'Parco automezzi, targhe, scadenze e permessi ZTL',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_Qualifica',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🎖️',
        'titolo': 'Anagrafiche: Qualifiche',
        'descrizione': 'Catalogo qualifiche e competenze tecniche',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_CorsoFormazione',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🎓',
        'titolo': 'Anagrafiche: Corsi di Formazione',
        'descrizione': 'Catalogo corsi di sicurezza e durate di validità',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_ModelloProcedura',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📝',
        'titolo': 'Anagrafiche: Modelli Procedura',
        'descrizione': 'Template base delle checklist procedurali',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_MessaggioProgrammato',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📨',
        'titolo': 'Anagrafiche: Messaggi Programmati',
        'descrizione': 'Pianificazione invii programmati a squadre o dipendenti',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_ProdottoMagazzino',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '🧴',
        'titolo': 'Magazzino: Catalogo Prodotti & Scorte',
        'descrizione': 'Detergenti, consumabili, attrezzature e costi unitari',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_DotazioneCantiere',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '⚙️',
        'titolo': 'Magazzino: Dotazioni & Macchinari Cantiere',
        'descrizione': 'Inventario macchinari, scale, carrelli e chiavi presso i clienti',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_ConsegnaRichiestaMateriale',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📦',
        'titolo': 'Operatività: Richieste & Consegne Materiali',
        'descrizione': 'Ordini materiali inviati dai dipendenti e consegne contabilizzate',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_IspezioneQualitaCantiere',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '⭐',
        'titolo': 'Operatività: Ispezioni Qualità & SLA',
        'descrizione': 'Verbali di sopralluogo qualità e report PDF per i clienti',
        'default_responsabile': True,
    },
    {
        'codice': 'mod_PreventivoCommerciale',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '📐',
        'titolo': 'Commerciale: Preventivi & Sopralluoghi',
        'descrizione': 'Archivio preventivi commerciali e conversioni in cliente attivo',
        'default_responsabile': True,
    },
    {
        'codice': 'col_sistema',
        'gruppo': 'TABELLE',
        'gruppo_label': '🗂️ Voci Operatività Giornaliera, Anagrafiche & Sistema',
        'icona': '⚙️',
        'titolo': 'Amministrazione Sistema & Utenti',
        'descrizione': 'Sezione finale Utenti/Gruppi di sistema e Modalità Locale',
        'default_responsabile': False,
    },
]

TUTTI_CODICI_SEZIONI = [s['codice'] for s in CATALOGO_SEZIONI_PORTALE]
DEFAULT_CODICI_RESPONSABILE = [s['codice'] for s in CATALOGO_SEZIONI_PORTALE if s.get('default_responsabile', True)]

# Mappa URL path -> codice sezione per proteggere anche l'accesso diretto via URL
URL_PREFIX_TO_SECTION = [
    ('/find-jolly/', 'jolly'),
    ('/verifica-ore/', 'report_ore'),
    ('/pdf-verifica-ore/', 'report_ore'),
    ('/report-paghe/', 'cedolini_paghe'),
    ('/buste-paga/', 'buste_paga'),
    ('/chat-simulator/', 'chat_telegram'),
    ('/analisi-contratti/', 'analisi_contratti'),
    ('/magazzino-dotazioni/', 'magazzino_dotazioni'),
    ('/qualita-ispezioni/', 'qualita_ispezioni'),
    ('/preventivi-crm/', 'preventivi_crm'),
    ('/pre-fatturazione/', 'pre_fatturazione'),
    ('/procedure/', 'procedure'),
    ('/data-management/', 'gestione_dati'),
    ('/ia-hub/', 'centro_ia'),
    ('/manuale/', 'guide_manuali'),
]


def _genera_username_da_dipendente(dip):
    """Genera uno username pulito e intuitivo dal nome del responsabile (es. 'simone', 'roberta', 'giorgio')."""
    nome_clean = (dip.nome or '').strip().lower().replace(' ', '')
    cognome_clean = (dip.cognome or '').strip().lower().replace(' ', '')
    if 'giancarlo' in nome_clean and 'serra' in cognome_clean:
        return 'serra'
    base = nome_clean or cognome_clean or f"resp{dip.pk}"
    return base


def _genera_password_default(dip, is_prog=False):
    if is_prog:
        return 'Serra2026!'
    nome_cap = (dip.nome or 'Kandor').strip().split()[0].capitalize()
    return f"{nome_cap}2026!"


def assicura_profili_accesso_portale():
    """
    Garantisce che:
    1. Esista l'account Programmatore per Serra Gian Carlo ('serra') con ruolo PROGRAMMATORE e tutte le sezioni attive.
    2. Esistano i profili di accesso per tutti i Responsabili (Simone, Roberta, Giorgio, Sonia, Consuelo, Carla, ecc.)
       collegati al rispettivo Dipendente e utente Django.
    """
    from .models import Dipendente, ProfiloAccessoPortale
    from .services import get_operatori_rapidi_portale

    try:
        with transaction.atomic():
            # 1. Trova o crea il Dipendente GIAN CARLO SERRA
            dip_serra = Dipendente.objects.filter(
                nome__iexact='GIAN CARLO',
                cognome__iexact='SERRA',
            ).first()
            if not dip_serra:
                dip_serra = Dipendente.objects.filter(cognome__iexact='SERRA').first()

            # 2. Trova o crea l'utente Django 'serra' (Programmatore)
            user_serra = User.objects.filter(username__iexact='serra').first()
            created_serra = False
            if not user_serra:
                user_serra = User(
                    username='serra',
                    first_name='Gian Carlo',
                    last_name='Serra',
                    email='direzione@serrastudio.it',
                    is_staff=True,
                    is_superuser=True,
                    is_active=True,
                )
                user_serra.set_password('Serra2026!')
                user_serra.save()
                created_serra = True
            else:
                changed = False
                if not user_serra.is_staff or not user_serra.is_superuser or not user_serra.is_active:
                    user_serra.is_staff = True
                    user_serra.is_superuser = True
                    user_serra.is_active = True
                    changed = True
                if not user_serra.first_name or not user_serra.last_name:
                    user_serra.first_name = 'Gian Carlo'
                    user_serra.last_name = 'Serra'
                    changed = True
                if changed:
                    user_serra.save()

            prof_serra, prof_created = ProfiloAccessoPortale.objects.get_or_create(
                user=user_serra,
                defaults={
                    'dipendente': dip_serra,
                    'ruolo': 'PROGRAMMATORE',
                    'password_visibile': 'Serra2026!',
                    'sezioni_abilitate': list(TUTTI_CODICI_SEZIONI),
                    'attivo': True,
                }
            )
            if not prof_created:
                update_fields = []
                if prof_serra.ruolo != 'PROGRAMMATORE':
                    prof_serra.ruolo = 'PROGRAMMATORE'
                    update_fields.append('ruolo')
                if dip_serra and prof_serra.dipendente_id != dip_serra.id:
                    prof_serra.dipendente = dip_serra
                    update_fields.append('dipendente')
                if not prof_serra.password_visibile:
                    prof_serra.password_visibile = 'Serra2026!'
                    user_serra.set_password('Serra2026!')
                    user_serra.save(update_fields=['password'])
                    update_fields.append('password_visibile')
                if set(prof_serra.sezioni_abilitate or []) != set(TUTTI_CODICI_SEZIONI):
                    prof_serra.sezioni_abilitate = list(TUTTI_CODICI_SEZIONI)
                    update_fields.append('sezioni_abilitate')
                if update_fields:
                    prof_serra.save(update_fields=update_fields)
            else:
                if not created_serra:
                    # Imposta la password nota Serra2026! al primo aggancio del profilo Programmatore
                    user_serra.set_password('Serra2026!')
                    user_serra.save(update_fields=['password'])

            # 3. Assicura un ProfiloAccessoPortale per ciascun Responsabile attivo
            responsabili_dips = get_operatori_rapidi_portale()
            for dip in responsabili_dips:
                if dip_serra and dip.id == dip_serra.id:
                    continue

                prof_esistente = ProfiloAccessoPortale.objects.filter(dipendente=dip).select_related('user').first()
                if prof_esistente:
                    continue

                base_uname = _genera_username_da_dipendente(dip)
                pwd_default = _genera_password_default(dip, is_prog=False)

                # Cerca se esiste già un utente Django per questo responsabile (non 'admin' e non 'serra')
                user_resp = User.objects.filter(
                    Q(username__iexact=base_uname)
                    | (Q(first_name__iexact=dip.nome.strip()) & Q(last_name__iexact=dip.cognome.strip()))
                ).exclude(username__in=['admin', 'serra']).first()

                if not user_resp:
                    uname_candidate = base_uname
                    counter = 2
                    while User.objects.filter(username__iexact=uname_candidate).exists():
                        uname_candidate = f"{base_uname}{counter}"
                        counter += 1
                    user_resp = User(
                        username=uname_candidate,
                        first_name=(dip.nome or '').strip().title(),
                        last_name=(dip.cognome or '').strip().title(),
                        email=(dip.email or '').strip(),
                        is_staff=True,
                        is_superuser=True,
                        is_active=True,
                    )
                    user_resp.set_password(pwd_default)
                    user_resp.save()
                else:
                    if not user_resp.is_staff or not user_resp.is_superuser:
                        user_resp.is_staff = True
                        user_resp.is_superuser = True
                        user_resp.save(update_fields=['is_staff', 'is_superuser'])

                # Se l'utente aveva già un profilo accesso non collegato al dipendente, aggiornalo
                prof_user = ProfiloAccessoPortale.objects.filter(user=user_resp).first()
                if prof_user:
                    prof_user.dipendente = dip
                    if not prof_user.sezioni_abilitate:
                        prof_user.sezioni_abilitate = list(DEFAULT_CODICI_RESPONSABILE)
                    if not prof_user.password_visibile:
                        prof_user.password_visibile = pwd_default
                        user_resp.set_password(pwd_default)
                        user_resp.save(update_fields=['password'])
                    prof_user.save()
                else:
                    user_resp.set_password(pwd_default)
                    user_resp.save(update_fields=['password'])
                    ProfiloAccessoPortale.objects.create(
                        user=user_resp,
                        dipendente=dip,
                        ruolo='RESPONSABILE',
                        password_visibile=pwd_default,
                        sezioni_abilitate=list(DEFAULT_CODICI_RESPONSABILE),
                        attivo=True,
                    )
    except Exception as exc:
        print(f"[AccessiService] Avviso in assicura_profili_accesso_portale: {exc}")


def is_utente_programmatore(user):
    """
    Restituisce True se l'utente Django autenticato è Serra Gian Carlo (Programmatore)
    oppure l'account superuser di sistema 'admin'.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    uname = (user.username or '').strip().lower()
    if uname in ('serra', 'admin', 'programmatore'):
        return True
    try:
        prof = getattr(user, 'profilo_accesso_portale', None)
        if prof and prof.ruolo == 'PROGRAMMATORE':
            return True
    except Exception:
        pass
    if (user.first_name or '').strip().upper() == 'GIAN CARLO' and (user.last_name or '').strip().upper() == 'SERRA':
        return True
    return False


def get_profilo_accesso_corrente(request):
    """
    Restituisce una tupla (profilo, is_prog_reale, in_preview_mode):
    - Se l'utente è il Programmatore (Serra Gian Carlo) e ha attivato '?preview_responsabile_id=...'
      (salvato in sessione), restituisce il profilo di quel Responsabile in modalità anteprima,
      così il Programmatore può verificare dal vivo cosa vede quel Responsabile.
    - Altrimenti restituisce il profilo dell'utente loggato.
    """
    from .models import ProfiloAccessoPortale

    if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
        return None, False, False

    assicura_profili_accesso_portale()
    user = request.user
    prog_reale = is_utente_programmatore(user)

    # Gestione eventuale parametro GET per entrare/uscire dalla modalità Anteprima Responsabile (solo per Programmatore)
    if prog_reale and hasattr(request, 'session'):
        if hasattr(request, 'GET') and 'preview_responsabile_id' in request.GET:
            raw_prev = (request.GET.get('preview_responsabile_id') or '').strip()
            if raw_prev in ('0', '', 'off', 'none', 'NONE'):
                request.session.pop('preview_responsabile_id', None)
            elif raw_prev.isdigit():
                request.session['preview_responsabile_id'] = int(raw_prev)

        prev_id = request.session.get('preview_responsabile_id')
        if prev_id:
            prof_prev = ProfiloAccessoPortale.objects.filter(pk=prev_id).select_related('user', 'dipendente').first()
            if prof_prev:
                return prof_prev, True, True
            else:
                request.session.pop('preview_responsabile_id', None)

    prof = ProfiloAccessoPortale.objects.filter(user=user).select_related('user', 'dipendente').first()
    return prof, prog_reale, False


def get_sezioni_abilitate_per_request(request):
    """
    Restituisce il set dei codici sezione abilitati per l'utente corrente.
    - Per il Programmatore (Serra Gian Carlo, quando non è in modalità anteprima): TUTTE le sezioni sono abilitate.
    - Per un Responsabile: solo i codici presenti nel suo ProfiloAccessoPortale.sezioni_abilitate.
    """
    prof, prog_reale, in_preview = get_profilo_accesso_corrente(request)
    if prog_reale and not in_preview:
        return set(TUTTI_CODICI_SEZIONI)
    if prof:
        if prof.ruolo == 'PROGRAMMATORE' and not in_preview:
            return set(TUTTI_CODICI_SEZIONI)
        return set(prof.sezioni_abilitate or [])
    return set(TUTTI_CODICI_SEZIONI)
