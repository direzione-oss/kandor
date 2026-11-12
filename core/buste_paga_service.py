import io
import os
import re
import secrets
from datetime import datetime
from urllib.parse import quote

import pypdf
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import CedolinoDipendente, Dipendente, LottoBustePaga, MessaggioChat
from .utils_cf import extract_data_nascita


# Regex per Codice Fiscale italiano (16 caratteri alfanumerici, inclusi casi di omocodia)
CF_STRICT_RE = re.compile(
    r'\b([A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])\b'
)

# Riga tipica Zucchetti: "0000002 BONALUMI GABRIELLA BNLGRL66B53C635E 002"
CF_LINE_RE = re.compile(
    r'^(?:\d+\s+)?([A-Z\'\s\-\.]+?)\s+([A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])\b',
    re.MULTILINE,
)

# Periodo di retribuzione (es. "Settembre 2026", "Tredicesima 2026", "Ottobre 2026")
PERIODO_RE = re.compile(
    r'\b((?:Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre|Tredicesima|Quattordicesima|13ma|14ma)[^\n\r]{0,25}?\d{4})\b',
    re.IGNORECASE,
)

# Importo netto (es. "627,00 €" o "1.735,00 €")
NETTO_RE = re.compile(r'([\d\.]+,\d{2})\s*€')

# Date anagrafiche Zucchetti: Data di Nascita e Data Assunzione (ed eventuale Data Cessazione)
DATES_LINE_RE = re.compile(
    r'\b(\d{2}-\d{2}-\d{4})\s+(\d{2}-\d{2}-\d{4})(?:\s+(\d{2}-\d{2}-\d{4}))?\b'
)


def _slugify_filename(value):
    if not value:
        return ''
    s = re.sub(r'[^A-Za-z0-9]+', '_', value.strip())
    return re.sub(r'_+', '_', s).strip('_')


def _parse_date_dmy(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), '%d-%m-%Y').date()
    except ValueError:
        return None


def _normalize_name_tokens(value):
    if not value:
        return ''
    s = re.sub(r'[^A-Z0-9\s]', ' ', value.upper())
    return re.sub(r'\s+', ' ', s).strip()


def trova_dipendente_per_cf_o_nome(cf, nominativo_pdf='', aggiorna_cf_se_refuso=True):
    """
    Cerca il Dipendente corrispondente al Codice Fiscale estratto dal PDF.
    1. Match esatto (case-insensitive) per codice_fiscale.
    2. Fallback per Cognome + Nome (o Nome + Cognome) se in anagrafica il CF aveva un refuso.
    """
    cf_clean = (cf or '').strip().upper()
    if not cf_clean:
        return None, False

    dip = Dipendente.objects.filter(codice_fiscale__iexact=cf_clean).first()
    if dip:
        return dip, False

    target_norm = _normalize_name_tokens(nominativo_pdf)
    if not target_norm:
        return None, False

    target_tokens = set(target_norm.split())
    candidati = list(Dipendente.objects.all())

    for d in candidati:
        c_norm = _normalize_name_tokens(f"{d.cognome} {d.nome}")
        inv_norm = _normalize_name_tokens(f"{d.nome} {d.cognome}")
        if target_norm in (c_norm, inv_norm) or (len(target_tokens) >= 2 and set(c_norm.split()) == target_tokens):
            cf_aggiornato = False
            if aggiorna_cf_se_refuso and len(cf_clean) == 16:
                conflitto = Dipendente.objects.filter(codice_fiscale__iexact=cf_clean).exclude(pk=d.pk).exists()
                if not conflitto:
                    Dipendente.objects.filter(pk=d.pk).update(codice_fiscale=cf_clean)
                    d.codice_fiscale = cf_clean
                    cf_aggiornato = True
            return d, cf_aggiornato

    return None, False


def analizza_pagina_cedolino(text):
    """
    Estrae da una singola pagina di testo del PDF Zucchetti:
    - codice_fiscale (16 caratteri)
    - nominativo_pdf
    - periodo
    - netto (lista di importi con €)
    - data_nascita, data_assunzione
    - is_riepilogo
    """
    txt = text or ''
    is_riepilogo = 'RIEPILOGO GENERALE' in txt.upper()

    periodo = ''
    m_per = PERIODO_RE.search(txt)
    if m_per:
        # Pulisci eventuali suffissi giorno (es. "Settembre 2026 1/10" -> "Settembre 2026")
        raw_per = m_per.group(1).strip()
        m_clean_per = re.match(
            r'^([A-Za-z0-9]+\s+\d{4})',
            raw_per,
        )
        periodo = m_clean_per.group(1).strip() if m_clean_per else raw_per

    cf = ''
    nominativo = ''
    m_line = CF_LINE_RE.search(txt)
    if m_line:
        nominativo = re.sub(r'\s+', ' ', m_line.group(1)).strip()
        cf = m_line.group(2).strip().upper()
    else:
        m_any = CF_STRICT_RE.search(txt.upper())
        if m_any:
            cf = m_any.group(1).strip().upper()

    netti = NETTO_RE.findall(txt)

    data_nascita = None
    data_assunzione = None
    m_dates = DATES_LINE_RE.search(txt)
    if m_dates:
        data_nascita = _parse_date_dmy(m_dates.group(1))
        data_assunzione = _parse_date_dmy(m_dates.group(2))

    return {
        'cf': cf,
        'nominativo': nominativo,
        'periodo': periodo,
        'netti': netti,
        'data_nascita': data_nascita,
        'data_assunzione': data_assunzione,
        'is_riepilogo': is_riepilogo or not bool(cf),
    }


def elabora_lotto_buste_paga(file_obj, filename='', periodo_override='', note='', user=None):
    """
    Legge il PDF unico inviato dal commercialista, suddivide le pagine per ogni
    Codice Fiscale identificato, salva i singoli PDF e li associa ai dipendenti.
    Restituisce un dizionario con il LottoBustePaga creato e le statistiche.
    """
    raw_bytes = file_obj.read()
    reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
    totale_pagine = len(reader.pages)

    if totale_pagine == 0:
        raise ValueError("Il file PDF caricato non contiene pagine valide.")

    by_cf = {}
    cf_order = []
    riepilogo_page_indices = []
    periodo_rilevato = ''

    for idx, page in enumerate(reader.pages):
        txt = page.extract_text() or ''
        info = analizza_pagina_cedolino(txt)

        if info['periodo'] and not periodo_rilevato:
            periodo_rilevato = info['periodo']

        cf = info['cf']
        if not cf:
            riepilogo_page_indices.append(idx)
            continue

        if cf not in by_cf:
            cf_order.append(cf)
            by_cf[cf] = {
                'cf': cf,
                'nominativo': info['nominativo'],
                'periodo': info['periodo'],
                'page_indices': [],
                'page_numbers': [],
                'netti': [],
                'data_nascita': info['data_nascita'],
                'data_assunzione': info['data_assunzione'],
            }

        entry = by_cf[cf]
        if info['nominativo'] and not entry['nominativo']:
            entry['nominativo'] = info['nominativo']
        if info['periodo'] and not entry['periodo']:
            entry['periodo'] = info['periodo']
        if info['data_nascita'] and not entry['data_nascita']:
            entry['data_nascita'] = info['data_nascita']
        if info['data_assunzione'] and not entry['data_assunzione']:
            entry['data_assunzione'] = info['data_assunzione']

        entry['page_indices'].append(idx)
        entry['page_numbers'].append(idx + 1)
        for n_val in info['netti']:
            if not entry['netti'] or entry['netti'][-1] != n_val:
                entry['netti'].append(n_val)

    periodo_finale = (periodo_override or '').strip() or periodo_rilevato or timezone.now().strftime('%m/%Y')
    periodo_slug = _slugify_filename(periodo_finale) or 'Mese'
    orig_safe_name = _slugify_filename(os.path.splitext(filename or 'Libro_Unico')[0]) or 'Libro_Unico'

    with transaction.atomic():
        lotto = LottoBustePaga(
            titolo=f"Buste Paga — {periodo_finale}",
            periodo=periodo_finale,
            totale_pagine=totale_pagine,
            totale_cedolini=len(cf_order),
            pagine_riepilogo=len(riepilogo_page_indices),
            note=note or '',
            caricato_da=user if (user and getattr(user, 'is_authenticated', False)) else None,
        )
        lotto.file_originale.save(
            f"{orig_safe_name}_{periodo_slug}.pdf",
            ContentFile(raw_bytes),
            save=False,
        )

        # Se presenti pagine di riepilogo generale, salva un PDF separato per l'ufficio
        if riepilogo_page_indices:
            riep_writer = pypdf.PdfWriter()
            for r_idx in riepilogo_page_indices:
                riep_writer.add_page(reader.pages[r_idx])
            riep_buf = io.BytesIO()
            riep_writer.write(riep_buf)
            lotto.file_riepilogo.save(
                f"Riepilogo_Generale_{periodo_slug}.pdf",
                ContentFile(riep_buf.getvalue()),
                save=False,
            )

        lotto.save()

        associati_count = 0
        cf_allineati_count = 0
        non_associati_count = 0

        for cf in cf_order:
            item = by_cf[cf]
            writer = pypdf.PdfWriter()
            for p_idx in item['page_indices']:
                writer.add_page(reader.pages[p_idx])
            pdf_buf = io.BytesIO()
            writer.write(pdf_buf)
            single_pdf_bytes = pdf_buf.getvalue()

            dip, cf_aggiornato = trova_dipendente_per_cf_o_nome(
                cf=cf,
                nominativo_pdf=item['nominativo'],
                aggiorna_cf_se_refuso=True,
            )
            if dip:
                associati_count += 1
                if cf_aggiornato:
                    cf_allineati_count += 1
            else:
                non_associati_count += 1

            nome_label = item['nominativo'] or (f"{dip.cognome} {dip.nome}" if dip else cf)
            nome_slug = _slugify_filename(nome_label) or cf
            single_filename = f"Busta_Paga_{periodo_slug}_{nome_slug}_{cf}.pdf"

            netto_str = ''
            if item['netti']:
                if len(item['netti']) == 1:
                    netto_str = f"{item['netti'][0]} €"
                else:
                    # Es. dipendente con cedolino + Co.Co.Co. o doppio periodo nello stesso PDF
                    netto_str = " + ".join(f"{n} €" for n in item['netti'])

            pagine_str = ", ".join(str(p) for p in item['page_numbers'])

            cedolino = CedolinoDipendente(
                lotto=lotto,
                dipendente=dip,
                codice_fiscale=cf,
                nominativo_pdf=nome_label,
                periodo=item['periodo'] or periodo_finale,
                pagine_pdf=pagine_str,
                numero_pagine=len(item['page_numbers']),
                netto_mese=netto_str,
                data_nascita_pdf=item['data_nascita'] or extract_data_nascita(cf),
                data_assunzione_pdf=item['data_assunzione'],
                token_download=secrets.token_urlsafe(24),
            )
            cedolino.file_pdf.save(single_filename, ContentFile(single_pdf_bytes), save=True)

    return {
        'lotto': lotto,
        'totale_pagine': totale_pagine,
        'totale_cedolini': len(cf_order),
        'pagine_riepilogo': len(riepilogo_page_indices),
        'associati_count': associati_count,
        'cf_allineati_count': cf_allineati_count,
        'non_associati_count': non_associati_count,
    }


def get_base_public_url(request=None):
    base_url = (
        getattr(settings, 'PUBLIC_BASE_URL', '')
        or os.environ.get('PUBLIC_BASE_URL', '')
        or os.environ.get('RENDER_EXTERNAL_URL', '')
        or 'https://kandor.187.126.30.207.sslip.io'
    ).rstrip('/')
    if request and ('127.0.0.1' not in request.get_host() and 'localhost' not in request.get_host()):
        scheme = 'https' if request.is_secure() or 'sslip.io' in request.get_host() else request.scheme
        base_url = f"{scheme}://{request.get_host()}"
    return base_url


def normalizza_telefono_whatsapp(telefono):
    raw_phone = re.sub(r'\D', '', telefono or '')
    if not raw_phone:
        return ''
    if raw_phone.startswith('00'):
        raw_phone = raw_phone[2:]
    if len(raw_phone) in (9, 10) and raw_phone.startswith('3'):
        raw_phone = '39' + raw_phone
    return raw_phone


def costruisci_dati_whatsapp_cedolino(cedolino, request=None):
    """
    Costruisce il messaggio e l'URL WhatsApp (wa.me) per l'invio rapido
    della busta paga al dipendente, includendo il link diretto sicuro al PDF
    e l'accesso rapido alla Web App Kandor.
    """
    base_url = get_base_public_url(request=request)
    download_url = f"{base_url}/buste-paga/scarica/{cedolino.token_download}/"

    dip = cedolino.dipendente
    nome_saluto = dip.nome if dip else (cedolino.nominativo_pdf or 'Collega')
    periodo_str = cedolino.periodo or cedolino.lotto.periodo or 'del mese'
    netto_info = f" (Netto: *{cedolino.netto_mese}*)" if cedolino.netto_mese else ""

    raw_phone = normalizza_telefono_whatsapp(dip.telefono if dip else '')

    app_section = ""
    if dip:
        if not dip.pin_accesso or len(dip.pin_accesso.strip()) != 4:
            dip.save()
        cf = (dip.codice_fiscale or '').strip().upper()
        pin = (dip.pin_accesso or '').strip()
        app_url = f"{base_url}/app/login/?cf={quote(cf)}&pin={quote(pin)}"
        app_section = (
            f"\n\n📲 *Archivio Buste Paga sull'App Kandor:*\n"
            f"{app_url}"
        )

    msg = (
        f"Ciao {nome_saluto}! 👋\n"
        f"📄 Ecco la tua *Busta Paga di {periodo_str}*{netto_info}.\n\n"
        f"👉 *Scarica subito il PDF della busta paga:*\n"
        f"{download_url}"
        f"{app_section}\n\n"
        f"Buon lavoro da *Kandor*!"
    )
    encoded_msg = quote(msg)
    wa_url = f"https://wa.me/{raw_phone}?text={encoded_msg}" if raw_phone else f"https://wa.me/?text={encoded_msg}"

    return {
        'raw_phone': raw_phone,
        'has_phone': bool(raw_phone),
        'download_url': download_url,
        'msg': msg,
        'wa_url': wa_url,
    }


def invia_cedolino_telegram(cedolino, force_resend=False):
    """
    Invia il file PDF della busta paga direttamente nella chat Telegram
    del dipendente tramite il bot ufficiale @kandor_gestionale_bot.
    Registra inoltre il documento nello storico MessaggioChat (così è visibile anche sull'App).
    """
    dip = cedolino.dipendente
    if not dip:
        dip, _ = trova_dipendente_per_cf_o_nome(cedolino.codice_fiscale, cedolino.nominativo_pdf)
        if dip:
            cedolino.dipendente = dip
            cedolino.save(update_fields=['dipendente'])

    if not dip:
        cedolino.errore_telegram = "Dipendente non ancora associato in anagrafica"
        cedolino.save(update_fields=['errore_telegram'])
        return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'NO_DIPENDENTE'}

    chat_id = (dip.telegram_chat_id or '').strip()
    if not chat_id:
        cedolino.errore_telegram = "Telegram Chat ID non presente per questo dipendente"
        cedolino.save(update_fields=['errore_telegram'])
        return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'NO_CHAT_ID'}

    if cedolino.inviato_telegram and not force_resend:
        return {'ok': True, 'already_sent': True, 'message': 'Già inviato su Telegram'}

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or os.environ.get('TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        cedolino.errore_telegram = "TELEGRAM_BOT_TOKEN non configurato sul server"
        cedolino.save(update_fields=['errore_telegram'])
        return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'NO_TOKEN'}

    if not cedolino.file_pdf:
        cedolino.errore_telegram = "File PDF non trovato"
        cedolino.save(update_fields=['errore_telegram'])
        return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'NO_FILE'}

    try:
        cedolino.file_pdf.open('rb')
        pdf_bytes = cedolino.file_pdf.read()
        cedolino.file_pdf.close()
    except Exception as e:
        cedolino.errore_telegram = f"Errore lettura PDF: {e}"
        cedolino.save(update_fields=['errore_telegram'])
        return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'READ_ERROR'}

    periodo_str = cedolino.periodo or cedolino.lotto.periodo or ''
    netto_line = f"💰 Netto in busta: {cedolino.netto_mese}\n" if cedolino.netto_mese else ""
    caption = (
        f"📄 BUSTA PAGA — {periodo_str}\n\n"
        f"👤 Gentile {dip.nome} {dip.cognome},\n"
        f"in allegato trovi il documento PDF della tua busta paga di {periodo_str}.\n"
        f"{netto_line}\n"
        f"📲 Puoi consultare le tue buste paga in qualsiasi momento anche sull'App Kandor."
    )

    safe_doc_name = os.path.basename(cedolino.file_pdf.name) or f"Busta_Paga_{ _slugify_filename(periodo_str) }_{dip.codice_fiscale}.pdf"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            data={
                'chat_id': chat_id,
                'caption': caption,
            },
            files={
                'document': (safe_doc_name, pdf_bytes, 'application/pdf'),
            },
            timeout=30,
        )
        if resp.status_code == 200 and resp.json().get('ok'):
            now = timezone.now()
            cedolino.inviato_telegram = True
            cedolino.data_invio_telegram = now
            cedolino.errore_telegram = ''
            cedolino.save(update_fields=['inviato_telegram', 'data_invio_telegram', 'errore_telegram'])

            # Registra anche in MessaggioChat per mostrarlo nella Chat / WebApp Dipendente
            try:
                pdf_url = f"/buste-paga/scarica/{cedolino.token_download}/"
                MessaggioChat.objects.create(
                    dipendente=dip,
                    testo=f"📄 Busta Paga — {periodo_str}" + (f" (Netto: {cedolino.netto_mese})" if cedolino.netto_mese else ""),
                    allegato_url=pdf_url,
                    allegato_nome=safe_doc_name,
                    direzione='OUT',
                    letto=True,
                )
            except Exception:
                pass

            return {
                'ok': True,
                'already_sent': False,
                'data_invio': now.strftime('%d/%m/%Y %H:%M'),
                'dipendente': str(dip),
            }
        else:
            err_desc = ''
            try:
                err_desc = resp.json().get('description', f'HTTP {resp.status_code}')
            except Exception:
                err_desc = f'HTTP {resp.status_code}'
            cedolino.errore_telegram = f"Telegram: {err_desc}"[:250]
            cedolino.save(update_fields=['errore_telegram'])
            return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'API_ERROR'}
    except Exception as e:
        cedolino.errore_telegram = f"Errore di rete Telegram: {e}"[:250]
        cedolino.save(update_fields=['errore_telegram'])
        return {'ok': False, 'error': cedolino.errore_telegram, 'code': 'NETWORK_ERROR'}


def invia_lotto_telegram_massivo(lotto, force_resend=False, solo_ids=None):
    """
    Invia automaticamente via Telegram tutte le buste paga del lotto
    ai dipendenti che hanno il Telegram Chat ID collegato.
    """
    qs = lotto.cedolini.select_related('dipendente').all()
    if solo_ids:
        qs = qs.filter(pk__in=solo_ids)

    inviati = 0
    gia_inviati = 0
    senza_telegram = 0
    non_associati = 0
    errori = 0
    dettagli_errori = []

    for ced in qs:
        if not force_resend and ced.inviato_telegram:
            gia_inviati += 1
            continue

        res = invia_cedolino_telegram(ced, force_resend=force_resend)
        if res.get('ok'):
            if res.get('already_sent'):
                gia_inviati += 1
            else:
                inviati += 1
        else:
            code = res.get('code')
            if code == 'NO_DIPENDENTE':
                non_associati += 1
            elif code == 'NO_CHAT_ID':
                senza_telegram += 1
            else:
                errori += 1
                dettagli_errori.append(f"{ced.nominativo_pdf or ced.codice_fiscale}: {res.get('error')}")

    return {
        'ok': True,
        'inviati': inviati,
        'gia_inviati': gia_inviati,
        'senza_telegram': senza_telegram,
        'non_associati': non_associati,
        'errori': errori,
        'dettagli_errori': dettagli_errori,
    }


def segna_cedolino_inviato_whatsapp(cedolino, request=None):
    """
    Segna la busta paga come inviata su WhatsApp, registra il messaggio
    anche nello storico chat dell'App Dipendente e restituisce i dati wa.me.
    """
    now = timezone.now()
    cedolino.inviato_whatsapp = True
    cedolino.data_invio_whatsapp = now
    cedolino.save(update_fields=['inviato_whatsapp', 'data_invio_whatsapp'])

    dip = cedolino.dipendente
    if dip:
        periodo_str = cedolino.periodo or cedolino.lotto.periodo or ''
        safe_doc_name = os.path.basename(cedolino.file_pdf.name) if cedolino.file_pdf else f"Busta_Paga_{periodo_str}.pdf"
        pdf_url = f"/buste-paga/scarica/{cedolino.token_download}/"
        try:
            # Evita duplicati se già registrato oggi
            if not MessaggioChat.objects.filter(dipendente=dip, allegato_url=pdf_url).exists():
                MessaggioChat.objects.create(
                    dipendente=dip,
                    testo=f"📄 Busta Paga — {periodo_str}" + (f" (Netto: {cedolino.netto_mese})" if cedolino.netto_mese else ""),
                    allegato_url=pdf_url,
                    allegato_nome=safe_doc_name,
                    direzione='OUT',
                    letto=True,
                )
        except Exception:
            pass

    wa_data = costruisci_dati_whatsapp_cedolino(cedolino, request=request)
    wa_data['data_invio'] = now.strftime('%d/%m/%Y %H:%M')
    return wa_data


def _split_nominativo_cognome_nome(nominativo_pdf):
    """
    Divide 'COGNOME NOME' estratto dal cedolino Zucchetti in (cognome, nome).
    Gestisce anche cognomi composti comuni (DI, DE, DAL, DEL, LO, LA, EL, BEN, VAN, D').
    """
    cleaned = re.sub(r'\s+', ' ', (nominativo_pdf or '').strip()).upper()
    if not cleaned:
        return ('DIPENDENTE', 'NUOVO')
    parts = cleaned.split(' ')
    if len(parts) == 1:
        return (parts[0].title(), '—')
    if len(parts) == 2:
        return (parts[0].title(), parts[1].title())

    prefissi_cognome = {'DI', 'DE', 'DAL', 'DEL', 'DELLA', 'DELLO', 'DEGLI', 'LO', 'LA', 'LE', 'EL', 'BEN', 'AL'}
    if parts[0] in prefissi_cognome and len(parts) >= 3:
        cognome = f"{parts[0]} {parts[1]}".title()
        nome = " ".join(parts[2:]).title()
        return (cognome, nome)

    # Default: prima parola cognome, resto nome (o se 3+ parole suddivide in modo leggibile)
    cognome = parts[0].title()
    nome = " ".join(parts[1:]).title()
    return (cognome, nome)


def crea_dipendente_da_cedolino(cedolino):
    """
    Crea automaticamente un nuovo record Dipendente in anagrafica a partire dai dati
    estratti dalla busta paga (Codice Fiscale, Nominativo, Data di Nascita, Data di Assunzione)
    e collega tutti i cedolini con lo stesso Codice Fiscale.
    """
    cf = (cedolino.codice_fiscale or '').strip().upper()
    if not cf or len(cf) != 16:
        return {'ok': False, 'error': 'Codice Fiscale non valido per creare il dipendente.'}

    esistente = Dipendente.objects.filter(codice_fiscale__iexact=cf).first()
    if esistente:
        CedolinoDipendente.objects.filter(codice_fiscale__iexact=cf, dipendente__isnull=True).update(dipendente=esistente)
        cedolino.dipendente = esistente
        return {'ok': True, 'dipendente': esistente, 'created': False}

    cognome, nome = _split_nominativo_cognome_nome(cedolino.nominativo_pdf)
    data_nascita = cedolino.data_nascita_pdf or extract_data_nascita(cf)

    with transaction.atomic():
        nuovo_dip = Dipendente(
            cognome=cognome.upper(),
            nome=nome.upper(),
            codice_fiscale=cf,
            data_nascita=data_nascita,
            data_assunzione=cedolino.data_assunzione_pdf,
            indirizzo_residenza='Da completare',
            stato='ATTIVO',
        )
        # Evita geocoding lento per indirizzo placeholder
        os.environ['SKIP_GEOCODING'] = '1'
        try:
            nuovo_dip.save()
        finally:
            os.environ.pop('SKIP_GEOCODING', None)

        CedolinoDipendente.objects.filter(codice_fiscale__iexact=cf).update(dipendente=nuovo_dip)
        cedolino.dipendente = nuovo_dip

    return {'ok': True, 'dipendente': nuovo_dip, 'created': True}
