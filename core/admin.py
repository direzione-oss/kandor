from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.http import HttpResponseRedirect
from django.db import IntegrityError
from django.core.exceptions import ValidationError

class KandorBaseAdmin(admin.ModelAdmin):
    """
    Base ModelAdmin per Kandor.
    Intercetta eccezioni di salvataggio (es. vincoli di integrità DB, dati duplicati)
    mostrando un messaggio chiaro in cima alla pagina senza mandare in crash l'applicazione con 500.
    """
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except Exception as e:
            err_msg = str(e)
            if 'UNIQUE constraint failed' in err_msg or 'unique' in err_msg.lower():
                err_msg = "È già presente un elemento con gli stessi dati univoci (es. Codice Fiscale, Targa, o combinazione unica già esistente)."
            messages.error(request, f"⚠️ Errore nel salvataggio dei dati: {err_msg}")
            referer = request.META.get('HTTP_REFERER')
            if referer and request.method == 'POST':
                return HttpResponseRedirect(referer)
            raise

from .models import (
    Dipendente, Qualifica, Cliente, Mezzo, 
    Squadra, Turno, AssegnazioneTurno, TimeTracking,
    ProgrammazioneRicorrente, RichiestaStraordinaria, Assenza,
    ResponsabileArea, RichiestaSostituzione, Titolare, ModificaCedolino
)

@admin.register(ModificaCedolino)
class ModificaCedolinoAdmin(KandorBaseAdmin):
    list_display = (
        'dipendente', 'data_inizio', 'data_fine',
        'giorni_lavorati_override', 'ore_lavorate_override', 'ore_validate_override',
        'giorni_ferie_override', 'giorni_permesso_override', 'giorni_malattia_override', 'giorni_104_override',
        'modificato_da', 'updated_at'
    )
    list_filter = ('data_inizio', 'data_fine', 'modificato_da')
    search_fields = ('dipendente__cognome', 'dipendente__nome', 'note')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Titolare)
class TitolareAdmin(KandorBaseAdmin):
    list_display = ('nome', 'user', 'telegram_chat_id', 'notifiche_attive')
    list_editable = ('notifiche_attive',)
    search_fields = ('nome', 'user__username')
    actions = ['invia_test_notifica', 'invia_riepilogo_ora']

    def invia_test_notifica(self, request, queryset):
        from .services import notifica_titolari
        notifica_titolari('🔔 Test notifica Kandor — sistema operativo!')
        self.message_user(request, 'Notifica di test inviata.')
    invia_test_notifica.short_description = 'Invia notifica di test'

    def invia_riepilogo_ora(self, request, queryset):
        from django.core.management import call_command
        call_command('riepilogo_settimanale')
        self.message_user(request, 'Riepilogo settimanale inviato ora.')
    invia_riepilogo_ora.short_description = 'Invia riepilogo settimanale adesso'

@admin.register(Assenza)
class AssenzaAdmin(KandorBaseAdmin):
    list_display = (
        'dipendente', 'tipo', 'data_inizio', 'data_fine',
        'get_orario_display', 'source', 'stato_approvazione',
        'avvallo_action_button', 'is_processed'
    )
    list_filter = ('stato_approvazione', 'tipo', 'data_inizio', 'is_processed', 'source')
    search_fields = ('dipendente__cognome', 'dipendente__nome', 'note')
    readonly_fields = ('source', 'created_at', 'approvata_da_admin_il')
    actions = ['avvalla_assenze_action', 'gestisci_sostituti_periodo']

    fieldsets = (
        ('👤 Dipendente e Tipo', {
            'fields': ('dipendente', 'tipo', 'source', 'stato_approvazione', 'approvata_da_admin_il', 'is_processed')
        }),
        ('📅 Periodo Assenza', {
            'fields': ('data_inizio', 'data_fine')
        }),
        ('🕒 Orario e Ore Permesso (se applicabile)', {
            'fields': ('ora_inizio', 'ora_fine'),
            'description': 'Specificare orario di inizio e fine per assenze ad ore (es. Permessi).'
        }),
        ('📝 Dettagli', {
            'fields': ('note', 'created_at')
        }),
    )

    def avvallo_action_button(self, obj):
        from .services import get_richieste_sostituzione_per_assenza
        is_avvallata = obj.stato_approvazione in ('APPROVATA_AMMINISTRAZIONE', 'APPROVATA')
        if is_avvallata:
            richieste = list(get_richieste_sostituzione_per_assenza(obj))
            if richieste:
                aperta = next((r for r in richieste if r.stato not in ('ACCETTATA', 'COMPLETATA')), richieste[0])
                coperte = sum(1 for r in richieste if r.stato in ('ACCETTATA', 'COMPLETATA'))
                in_attesa_tg = sum(1 for r in richieste if r.stato == 'INVIATA')
                tot = len(richieste)
                if coperte == tot:
                    sost_names = ", ".join(sorted({f"{r.sostituto.cognome} {r.sostituto.nome}" for r in richieste if r.sostituto}))
                    return format_html(
                        '<span style="color:#16A34A; font-weight:bold;">✅ Sostituito ({})</span> &nbsp;'
                        '<button type="button" class="button" style="background:#475569; color:#fff; border:none; padding:4px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;" onclick="apriModalSelezionaSostituti({})">👥 Dettagli ({}/{})</button>',
                        sost_names or 'OK', aperta.id, coperte, tot
                    )
                elif in_attesa_tg > 0:
                    sost_corr = aperta.sostituto
                    sost_lbl = f"⏳ Attesa TG ({sost_corr.cognome})" if sost_corr else "⏳ Attesa TG"
                    return format_html(
                        '<span style="color:#D97706; font-weight:bold;">{}</span> &nbsp;'
                        '<button type="button" class="button" style="background:#059669; color:#fff; border:none; padding:4px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;" onclick="apriModalSelezionaSostituti({})">🏢 Conferma / Sostituti ({}/{})</button>',
                        sost_lbl, aperta.id, coperte, tot
                    )
                else:
                    return format_html(
                        '<span style="color:#16A34A; font-weight:bold;">✅ Avvallata</span> &nbsp;'
                        '<button type="button" class="button" style="background:#059669; color:#fff; border:none; padding:4px 9px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;" onclick="apriModalSelezionaSostituti({})">👥 Scegli Sostituto ({}/{})</button>',
                        aperta.id, coperte, tot
                    )
            return format_html(
                '<span style="color:#16A34A; font-weight:bold;">✅ Avvallata</span> &nbsp;'
                '<button type="button" class="button" style="background:#0284C7; color:#fff; border:none; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;" onclick="validaAssenzaEApriSostituti({})">🔍 Cerca Turni / Sostituti</button>',
                obj.pk
            )
        elif obj.stato_approvazione == 'RIFIUTATA':
            return mark_safe('<span style="color:#DC2626; font-weight:bold;">❌ Rifiutata</span>')
        else:
            return format_html(
                '<button type="button" class="button" style="background:#16A34A; color:white; border:none; font-size:11px; padding:4px 10px; border-radius:4px; font-weight:bold; cursor:pointer;" onclick="validaAssenzaEApriSostituti({})">✅ Valida e Sostituisci</button>',
                obj.pk
            )
    avvallo_action_button.short_description = "Validazione & Sostituzione"

    def changelist_view(self, request, extra_context=None):
        if 'avvalla' in request.GET:
            try:
                assenza_id = int(request.GET['avvalla'])
                from .services import avvalla_assenza_da_amministrazione
                res = avvalla_assenza_da_amministrazione(assenza_id)
                if res.get('ok'):
                    self.message_user(request, f"✅ Assenza ID {assenza_id} validata con successo! ({res.get('num_sostituzioni', 0)} turni da coprire)")
                else:
                    self.message_user(request, f"Errore nella validazione dell'assenza: {res.get('error')}", level=messages.ERROR)
            except Exception as e:
                self.message_user(request, f"Errore: {e}", level=messages.ERROR)
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            return HttpResponseRedirect(reverse('admin:core_assenza_changelist'))
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='✅ Valida assenze selezionate e prepara sostituzioni')
    def avvalla_assenze_action(self, request, queryset):
        from .services import avvalla_assenza_da_amministrazione
        totale = 0
        totale_sost = 0
        for assenza in queryset:
            res = avvalla_assenza_da_amministrazione(assenza.pk)
            if res.get('ok'):
                totale += 1
                totale_sost += res.get('num_sostituzioni', 0)
        self.message_user(request, f"✅ {totale} assenze validate dall'Amministrazione ({totale_sost} richieste di sostituzione pronte).", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.stato_approvazione in ('APPROVATA_AMMINISTRAZIONE', 'APPROVATA') or obj.is_processed:
            from .services import avvia_sostituzione_per_assenza
            totale_create = avvia_sostituzione_per_assenza(obj)
            if totale_create > 0:
                self.message_user(request, f"⚡ Assenza validata: create {totale_create} richieste di sostituzione per i turni scoperti.")

    @admin.action(description='🔄 Crea/Aggiorna richieste sostituzione per i turni del periodo')
    def gestisci_sostituti_periodo(self, request, queryset):
        from .services import avvalla_assenza_da_amministrazione
        totale = 0
        for assenza in queryset:
            res = avvalla_assenza_da_amministrazione(assenza.pk)
            if res.get('ok'):
                totale += res.get('num_sostituzioni', 0)
        self.message_user(request, f"✅ Procedura sostituzione aggiornata: {totale} richieste di sostituzione create.", messages.SUCCESS)


# -- Branding Configuration --
admin.site.site_header = "Kandor Administration"
admin.site.site_title = "Kandor Portal"
admin.site.index_title = "Benvenuto in Kandor"

@admin.register(Dipendente)
class DipendenteAdmin(KandorBaseAdmin):
    list_display = ('foto_avatar', 'cognome', 'nome', 'stato', 'data_assunzione', 'part_time_display', 'usufruisce_104_display', 'data_ultima_visita_medica', 'data_licenziamento', 'is_sostituto', 'category_protetta_display', 'telegram_chat_id')
    search_fields = ('cognome', 'nome', 'codice_fiscale', 'telegram_chat_id')
    list_filter = ('stato', 'usufruisce_104', 'is_part_time', 'tipo_part_time', 'is_sostituto', 'qualifiche', 'riceve_notifiche_messaggi')
    filter_horizontal = ('qualifiche',)
    actions = ['send_telegram_message_action']
    readonly_fields = ('anteprima_foto_telegram',)
    fieldsets = (
        ('Dati Anagrafici', {
            'fields': (('nome', 'cognome', 'anteprima_foto_telegram'), 'codice_fiscale', 'data_nascita', 'indirizzo_residenza', 'email', 'telefono')
        }),
        ('Stato', {
            'fields': ('stato',)
        }),
        ('Dati Contrattuali', {
            'fields': (
                'categoria_protetta', 'usufruisce_104', 'file_contratto',
                'data_assunzione', 'data_licenziamento',
                'is_part_time', 'tipo_part_time', 'ore_settimanali_part_time',
                'data_ultima_visita_medica',
            ),
            'description': 'Inserire la data di assunzione e, se il contratto è Part-Time, selezionare la sigla: M (Misto), V (Verticale) o O (Orizzontale).',
        }),
        ('Qualifiche & Squadra', {
            'fields': ('qualifiche', 'is_sostituto')
        }),
        ('Integrazione Telegram', {
            'fields': ('telegram_chat_id', 'riceve_notifiche_messaggi', 'foto_profilo_url', 'foto', 'foto_url'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Legge 104', boolean=True)
    def usufruisce_104_display(self, obj):
        return obj.usufruisce_104

    @admin.display(description='Contratto')
    def part_time_display(self, obj):
        if not obj.is_part_time:
            return "Full-Time"
        tipo = obj.get_tipo_part_time_display() or obj.tipo_part_time
        return f"Part-Time ({tipo})" if tipo else "Part-Time"

    def _get_photo_url(self, obj):
        if not obj:
            return None
        # 1. File caricato locale (ImageField)
        if obj.foto and hasattr(obj.foto, 'url') and obj.foto.url:
            try:
                return obj.foto.url
            except Exception:
                pass
        # 2. URL Supabase o permanente
        if obj.foto_url:
            return obj.foto_url
        # 3. URL profilo Telegram/Supabase
        if obj.foto_profilo_url:
            return obj.foto_profilo_url
        return None

    def anteprima_foto_telegram(self, obj):
        from django.utils.html import format_html
        from django.utils.safestring import mark_safe
        
        img_url = self._get_photo_url(obj)

        if img_url:
            return format_html(
                '<div style="display:inline-flex; align-items:center; gap:12px; border: 1.5px solid #CBD5E1; border-radius: 12px; padding: 8px 12px; background: #FFFFFF; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">'
                '  <img src="{}" style="width: 72px; height: 72px; object-fit: cover; border-radius: 10px; border: 2px solid #FF6F00;" alt="Foto Telegram" />'
                '  <div style="display:flex; flex-direction:column;">'
                '    <span style="font-size: 11px; font-weight: 700; color: #0F172A; text-transform: uppercase; letter-spacing: 0.5px;">Foto Telegram</span>'
                '    <span style="font-size: 11px; color: #16A34A; font-weight: 600; margin-top: 2px;">✓ Inviata dal Bot</span>'
                '    <a href="{}" target="_blank" style="font-size: 10px; color: #2563EB; text-decoration: underline; margin-top: 4px;">Apri originale ↗</a>'
                '  </div>'
                '</div>',
                img_url, img_url
            )
        return mark_safe(
            '<div style="display:inline-flex; align-items:center; gap:10px; border: 1.5px dashed #CBD5E1; border-radius: 12px; padding: 10px 14px; background: #F8FAFC; color: #64748B;">'
            '  <span style="font-size: 20px;">📸</span>'
            '  <div style="display:flex; flex-direction:column;">'
            '    <span style="font-size: 11px; font-weight: 600; color: #475569;">Foto Telegram Non Presente</span>'
            '    <span style="font-size: 10px; color: #94A3B8;">Il dipendente non ha inviato una foto via bot</span>'
            '  </div>'
            '</div>'
        )
    anteprima_foto_telegram.short_description = 'Foto Telegram'
    
    def foto_avatar(self, obj):
        from django.utils.html import format_html
        img_url = self._get_photo_url(obj)
        if img_url:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;border:2px solid #ff6f00;" />',
                img_url
            )
        initials = (obj.nome[0] if obj.nome else '') + (obj.cognome[0] if obj.cognome else '')
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:#ff6f00;color:#fff;'
            'display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:13px;'
            'line-height:1;">{}</div>',
            initials.upper()
        )
    foto_avatar.short_description = '📸'
    foto_avatar.allow_tags = True

    def category_protetta_display(self, obj):
        return obj.categoria_protetta
    category_protetta_display.boolean = True
    category_protetta_display.short_description = "Protetta"

    @admin.action(description='💬 Invia Messaggio Telegram')
    def send_telegram_message_action(self, request, queryset):
        # Check if confirmed
        if 'apply' in request.POST:
            from core.utils_kandor_chat import send_telegram_message
            message = request.POST.get('message_text')
            count_success = 0
            count_fail = 0
            
            for emp in queryset:
                if emp.telegram_chat_id:
                    if send_telegram_message(emp.telegram_chat_id, message):
                        count_success += 1
                    else:
                        count_fail += 1
                else:
                    count_fail += 1 # Or count as ignored
            
            self.message_user(request, f"Messaggio inviato a {count_success} dipendenti. ({count_fail} falliti o senza ID)")
            return None # Return None to go back to changelist

        # Render intermediate page
        from django.shortcuts import render
        return render(request, 'admin/core/dipendente/send_message.html', {
            'employees': queryset,
            'selected_ids': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        })

    def _safe_delete_or_terminate_dipendente(self, obj, today):
        """
        Se il dipendente ha storico passato (ore lavorate, assenze o cedolini),
        evita la cancellazione fisica (che farebbe perdere i cedolini passati)
        e lo imposta come INATTIVO (licenziato) cancellando solo i turni da oggi in poi.
        """
        from .models import TimeTracking, Assenza, ModificaCedolino
        from .signals import gestisci_licenziamento_dipendente

        cutoff = obj.data_licenziamento or today
        gestisci_licenziamento_dipendente(obj, cutoff_date=cutoff)

        has_past_history = (
            TimeTracking.objects.filter(dipendente=obj, assegnazione__turno__data__lt=cutoff).exists()
            or Assenza.objects.filter(dipendente=obj, data_inizio__lt=cutoff).exists()
            or ModificaCedolino.objects.filter(dipendente=obj).exists()
        )
        if has_past_history:
            obj.stato = 'INATTIVO'
            if not obj.data_licenziamento:
                obj.data_licenziamento = today
            obj.save()
            return False  # Convertito in licenziamento/inattivazione per preservare lo storico
        else:
            obj.delete()
            return True

    def delete_model(self, request, obj):
        from django.utils import timezone
        today = timezone.now().date()
        deleted = self._safe_delete_or_terminate_dipendente(obj, today)
        if not deleted:
            self.message_user(
                request,
                f"ℹ️ Il dipendente {obj} possiede ore/cedolini storici: è stato impostato come INATTIVO (licenziato in data {obj.data_licenziamento.strftime('%d/%m/%Y')}), "
                f"rimuovendo tutti i turni futuri ma preservando lo storico passato per i cedolini.",
                messages.WARNING,
            )

    def delete_queryset(self, request, queryset):
        from django.utils import timezone
        today = timezone.now().date()
        preserved = 0
        deleted = 0
        for obj in queryset:
            if self._safe_delete_or_terminate_dipendente(obj, today):
                deleted += 1
            else:
                preserved += 1
        if preserved:
            self.message_user(
                request,
                f"ℹ️ {preserved} dipendente/i con storico ore/cedolini impostato/i come INATTIVO (turni futuri rimossi, storico passato preservato).",
                messages.WARNING,
            )


class ProgrammazioneInline(admin.StackedInline):
    model = ProgrammazioneRicorrente
    extra = 1
    readonly_fields = ('ora_fine',)
    ordering = ('tipo_ripetizione', 'giorno_settimana', 'ora_inizio')
    autocomplete_fields = ('squadra_abituale', 'mezzo_abituale')
    fieldsets = (
        ('🗓️ Frequenza e Orari', {
            'fields': (
                ('tipo_ripetizione', 'giorno_settimana', 'giorno_mese'),
                ('ora_inizio', 'durata', 'ora_fine', 'orario_flessibile'),
            )
        }),
        ('👥 Squadra e Mezzo Abituali', {
            'fields': (
                ('squadra_abituale', 'mezzo_abituale', 'qualifica_richiesta'),
            )
        }),
        ('📅 Validità Contratto', {
            'fields': (
                ('data_inizio_contratto', 'data_fine_contratto'),
            )
        }),
    )

class StraordinarioInline(admin.StackedInline):
    model = RichiestaStraordinaria
    extra = 0

@admin.register(ProgrammazioneRicorrente)
class ProgrammazioneRicorrenteAdmin(KandorBaseAdmin):
    list_display = (
        'cliente', 'tipo_ripetizione', 'get_giorno_display',
        'ora_inizio', 'durata', 'ora_fine',
        'squadra_abituale', 'mezzo_abituale',
        'data_inizio_contratto', 'data_fine_contratto'
    )
    list_filter = ('tipo_ripetizione', 'giorno_settimana', 'squadra_abituale', 'mezzo_abituale')
    search_fields = ('cliente__ragione_sociale', 'squadra_abituale__nome', 'mezzo_abituale__targa')
    autocomplete_fields = ('cliente', 'squadra_abituale', 'mezzo_abituale')
    readonly_fields = ('ora_fine',)
    ordering = ('cliente', 'tipo_ripetizione', 'giorno_settimana', 'ora_inizio')
    fieldsets = (
        ('🏢 Cliente', {
            'fields': ('cliente',)
        }),
        ('🗓️ Frequenza e Orari', {
            'fields': (
                ('tipo_ripetizione', 'giorno_settimana', 'giorno_mese'),
                ('ora_inizio', 'durata', 'ora_fine', 'orario_flessibile'),
            )
        }),
        ('👥 Risorse Abituali', {
            'fields': (
                ('squadra_abituale', 'mezzo_abituale', 'qualifica_richiesta'),
            )
        }),
        ('📅 Periodo Contratto', {
            'fields': (
                ('data_inizio_contratto', 'data_fine_contratto'),
            )
        }),
    )

    def get_giorno_display(self, obj):
        if obj.tipo_ripetizione == 'GIORNALIERO':
            return 'Ogni Giorno'
        elif obj.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE'):
            return obj.get_giorno_settimana_display() or '-'
        return f"Giorno {obj.giorno_mese}" if obj.giorno_mese else '-'
    get_giorno_display.short_description = 'Giorno'

@admin.register(RichiestaStraordinaria)
class RichiestaStraordinariaAdmin(KandorBaseAdmin):
    list_display = ('cliente', 'data_inizio', 'data_fine', 'ora_inizio', 'ora_fine', 'completata')
    list_filter = ('completata', 'data_inizio')
    search_fields = ('cliente__ragione_sociale', 'descrizione')
    autocomplete_fields = ('cliente',)

@admin.register(Cliente)
class ClienteAdmin(KandorBaseAdmin):
    list_display = ('ragione_sociale', 'indirizzo_sede', 'ore_mensili_contratto', 'importo_mensile_contratto')
    search_fields = ('ragione_sociale', 'partita_iva')
    inlines = [ProgrammazioneInline, StraordinarioInline]
    actions = ['duplica_per_nuova_sede']
    
    def duplica_per_nuova_sede(self, request, queryset):
        """Duplica i clienti selezionati per gestire sedi multiple."""
        count = 0
        for cliente in queryset:
            # Trova un nome univoco con suffisso sede
            base_name = cliente.ragione_sociale
            sede_num = 2
            new_name = f"{base_name} - Sede {sede_num}"
            while Cliente.objects.filter(ragione_sociale=new_name).exists():
                sede_num += 1
                new_name = f"{base_name} - Sede {sede_num}"
            
            # Crea il duplicato (senza pk per crearne uno nuovo)
            Cliente.objects.create(
                ragione_sociale=new_name,
                partita_iva='',  # P.IVA vuota per evitare duplicati unique
                codice_fiscale='',
                indirizzo_sede=f"INSERIRE INDIRIZZO SEDE {sede_num}",
                referente_nome=cliente.referente_nome,
                referente_ruolo=cliente.referente_ruolo,
                referente_data_nascita=cliente.referente_data_nascita,
                ore_mensili_contratto=0,
                importo_mensile_contratto=0,
                note_mansioni=f"Sede secondaria di: {base_name}",
            )
            count += 1
        
        self.message_user(
            request,
            f"✅ {count} cliente/i duplicato/i. Modifica indirizzo, ore e importo delle nuove sedi.",
            messages.SUCCESS
        )
    duplica_per_nuova_sede.short_description = "📋 Duplica per nuova sede"

@admin.register(Mezzo)
class MezzoAdmin(KandorBaseAdmin):
    list_display = ('targa', 'modello', 'stato', 'km_attuali', 'scadenza_polizza', 'scadenza_revisione')
    list_filter = ('stato',)
    search_fields = ('targa', 'modello')  # Necessario per autocomplete_fields

@admin.register(Squadra)
class SquadraAdmin(KandorBaseAdmin):
    list_display = ('nome_con_componenti', 'caposquadra', 'get_responsabile_area')
    filter_horizontal = ('componenti',)
    search_fields = ('nome',)
    actions = ['send_team_message_action']

    class Media:
        css = {}
        # CSS iniettato inline via override changelist_view non necessario:
        # usiamo extrastyle nel template oppure un tag <style> nel campo HTML stesso.

    def nome_con_componenti(self, obj):
        from django.utils.html import format_html
        componenti = list(obj.componenti.all().order_by('cognome', 'nome'))
        if obj.caposquadra and obj.caposquadra not in componenti:
            componenti.insert(0, obj.caposquadra)
        if not componenti:
            return format_html('<strong>{}</strong>', obj.nome)
        # Costruiamo le righe senza backslash nelle espressioni f-string (Python 3.11)
        righe_parts = []
        for c in componenti:
            icona = '\u2b50 ' if c == obj.caposquadra else '\u2022 '
            nome_c = f'{c.cognome} {c.nome}'
            righe_parts.append(
                f'<div style="padding:3px 0;border-bottom:1px solid #eee;white-space:nowrap">'
                f'{icona}{nome_c}'
                f'</div>'
            )
        righe = ''.join(righe_parts)
        tid = f'sq-tt-{obj.pk}'
        # JS senza backslash nelle f-string: uso variabili per i valori con apici
        show_js = f"document.getElementById('{tid}').style.display='block'"
        hide_js = f"document.getElementById('{tid}').style.display='none'"
        nome = obj.nome
        html = (
            f'<span style="position:relative;display:inline-block"'
            f' onmouseenter="{show_js}"'
            f' onmouseleave="{hide_js}">'
            f'<strong style="cursor:help;border-bottom:1px dotted #999">{nome}</strong> '
            f'<span style="font-size:10px;color:#aaa">\U0001f465</span>'
            f'<div id="{tid}" style="display:none;position:absolute;top:110%;left:0;z-index:9999;'
            f'background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px 12px;'
            f'min-width:200px;box-shadow:0 4px 12px rgba(0,0,0,.2);font-size:12px;line-height:1.6">'
            f'{righe}'
            f'</div>'
            f'</span>'
        )
        return mark_safe(html)
    nome_con_componenti.short_description = 'Nome'
    nome_con_componenti.allow_tags = True

    def get_responsabile_area(self, obj):
        ra = obj.responsabile_area.first()
        return f"{ra.dipendente} ({ra.nome_area})" if ra else "—"
    get_responsabile_area.short_description = "Responsabile Area"


    @admin.action(description='💬 Invia Messaggio alla Squadra')
    def send_team_message_action(self, request, queryset):
        if 'apply' in request.POST:
            from core.utils_kandor_chat import send_telegram_message
            message = request.POST.get('message_text')
            
            # Collect unique recipients
            recipients = set()
            for squad in queryset:
                for member in squad.componenti.all():
                    if member.telegram_chat_id:
                        recipients.add(member)
            
            count_success = 0
            for emp in recipients:
                if send_telegram_message(emp.telegram_chat_id, message):
                    count_success += 1
            
            self.message_user(request, f"Messaggio inviato a {count_success} membri unici delle squadre selezionate.")
            return None

        # Render intermediate page
        from django.shortcuts import render
        
        # Calculate stats for preview
        total_recipients = 0
        for squad in queryset:
            total_recipients += squad.componenti.count()

        return render(request, 'admin/core/squadra/send_message.html', {
            'squads': queryset,
            'total_recipients': total_recipients,
            'selected_ids': request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME)
        })

    def delete_model(self, request, obj):
        from django.utils import timezone
        from .signals import gestisci_eliminazione_squadra
        today = timezone.now().date()
        gestisci_eliminazione_squadra(obj, cutoff_date=today)
        super().delete_model(request, obj)
        self.message_user(
            request,
            f"✅ Squadra '{obj.nome}' eliminata: rimossi solo i turni dal {today.strftime('%d/%m/%Y')} in poi. Tutti i turni e le ore del passato sono stati mantenuti.",
            messages.SUCCESS,
        )

    def delete_queryset(self, request, queryset):
        from django.utils import timezone
        from .signals import gestisci_eliminazione_squadra
        today = timezone.now().date()
        for obj in list(queryset):
            gestisci_eliminazione_squadra(obj, cutoff_date=today)
            obj.delete()
        self.message_user(
            request,
            f"✅ Squadre eliminate: rimossi solo i turni dal {today.strftime('%d/%m/%Y')} in poi. Tutti i turni e le ore del passato sono stati mantenuti.",
            messages.SUCCESS,
        )


class AssegnazioneInline(admin.TabularInline):
    model = AssegnazioneTurno
    extra = 1
    fields = ('cliente', 'orario_inizio_previsto', 'orario_fine_previsto', 'ore_previste_contratto', 'dipendenti_esclusi', 'mansione_svolta')
    filter_horizontal = ('dipendenti_esclusi',)
    verbose_name_plural = 'Assegnazioni turno (cliente, orari, ore contratto, dipendenti esclusi)'
    # Select2: ricerca per sottostringa nel campo cliente
    autocomplete_fields = ('cliente',)

@admin.register(Turno)
class TurnoAdmin(KandorBaseAdmin):
    list_display = ('data', 'squadra', 'mezzo')
    list_filter = ('data', 'squadra')
    search_fields = ('data', 'squadra__nome')  # Richiesto da autocomplete_fields
    inlines = [AssegnazioneInline]

admin.site.register(Qualifica)

@admin.register(AssegnazioneTurno)
class AssegnazioneTurnoAdmin(KandorBaseAdmin):
    search_fields = ('cliente__ragione_sociale', 'turno__squadra__nome')
    autocomplete_fields = ('cliente', 'turno')

@admin.register(TimeTracking)
class TimeTrackingAdmin(KandorBaseAdmin):
    list_display = ('dipendente', 'get_cliente', 'get_data', 'ore_dichiarate', 'source', 'is_validated')
    list_filter = ('is_validated', 'source', 'assegnazione__turno__data')
    search_fields = ('dipendente__cognome', 'dipendente__nome', 'assegnazione__cliente__ragione_sociale')
    list_editable = ('is_validated',)
    list_per_page = 50
    ordering = ('-assegnazione__turno__data',)
    actions = ['valida_ore']

    def get_cliente(self, obj):
        return obj.assegnazione.cliente.ragione_sociale
    get_cliente.short_description = 'Cliente'
    get_cliente.admin_order_field = 'assegnazione__cliente__ragione_sociale'

    def get_data(self, obj):
        return obj.assegnazione.turno.data
    get_data.short_description = 'Data'
    get_data.admin_order_field = 'assegnazione__turno__data'

    @admin.action(description="Valida ore selezionate")
    def valida_ore(self, request, queryset):
        updated = queryset.update(is_validated=True)
        self.message_user(request, f"{updated} ore validate.", messages.SUCCESS)

from .models import MessaggioProgrammato
@admin.register(MessaggioProgrammato)
class MessaggioProgrammatoAdmin(KandorBaseAdmin):
    list_display = ('titolo', 'data_programmata', 'invia_a_tutti', 'inviato')
    list_filter = ('inviato', 'data_programmata')
    search_fields = ('titolo', 'testo')
    filter_horizontal = ('destinatari',)
    date_hierarchy = 'data_programmata'


@admin.register(ResponsabileArea)
class ResponsabileAreaAdmin(KandorBaseAdmin):
    list_display = ('dipendente', 'nome_area')
    search_fields = ('dipendente__cognome', 'dipendente__nome', 'nome_area')
    filter_horizontal = ('squadre',)


@admin.register(RichiestaSostituzione)
class RichiestaSostituzioneAdmin(KandorBaseAdmin):
    list_display = ('creata_il', 'get_data_turno', 'get_cliente', 'dipendente_assente', 'motivo_assenza', 'sostituto', 'stato', 'distanza_km', 'azione_seleziona_sostituti')
    list_filter = ('stato', 'motivo_assenza')
    search_fields = ('dipendente_assente__cognome', 'sostituto__cognome', 'assegnazione_originale__cliente__ragione_sociale')
    readonly_fields = ('creata_il', 'approvata_ra_il', 'inviata_sostituto_il', 'risposta_sostituto_il', 'sostituti_candidati', 'sostituto_corrente_idx')
    date_hierarchy = 'creata_il'
    actions = ['approva_selezionate', 'conferma_ufficio_selezionate']

    def get_data_turno(self, obj):
        return obj.assegnazione_originale.turno.data
    get_data_turno.short_description = 'Data Turno'
    get_data_turno.admin_order_field = 'assegnazione_originale__turno__data'

    def get_cliente(self, obj):
        return obj.assegnazione_originale.cliente.ragione_sociale
    get_cliente.short_description = 'Cliente'

    def azione_seleziona_sostituti(self, obj):
        count = len(obj.sostituti_candidati or [])
        if obj.stato in ('ACCETTATA', 'COMPLETATA') and obj.sostituto:
            return format_html(
                '<span style="color:#16A34A; font-weight:bold;">✅ {}</span> &nbsp;'
                '<button type="button" class="button" style="background:#475569; color:#fff; border:none; padding:4px 10px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;" onclick="apriModalSelezionaSostituti({})">🔄 Cambia Sostituto</button>',
                f"{obj.sostituto.cognome} {obj.sostituto.nome}", obj.id
            )
        elif obj.stato == 'INVIATA' and obj.sostituto:
            return format_html(
                '<button type="button" class="button" style="background:#2563EB; color:#fff; border:none; padding:5px 10px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer; margin-right:4px;" onclick="confermaSostitutoUfficioDiretto({}, {}, \'{}\')">🏢 Conferma Ufficio ({})</button>'
                '<button type="button" class="button" style="background:#059669; color:#fff; border:none; padding:5px 10px; border-radius:4px; font-size:11px; font-weight:bold; cursor:pointer;" onclick="apriModalSelezionaSostituti({})">👥 Altri Candidati</button>',
                obj.id, obj.sostituto.id, f"{obj.sostituto.cognome} {obj.sostituto.nome}".replace("'", "\\'"), obj.sostituto.cognome, obj.id
            )
        lbl = f"👥 Scegli Sostituto ({count})" if count > 0 else "👥 Scegli / Conferma Sostituto"
        btn_color = "#059669" if obj.stato in ['APERTA', 'APPROVATA_RA', 'NESSUN_DISPONIBILE', 'RIFIUTATA'] else "#475569"
        return format_html(
            '<button type="button" class="button" style="background:{}; color:#fff; border:none; padding:5px 12px; border-radius:4px; font-weight:bold; cursor:pointer;" onclick="apriModalSelezionaSostituti({})">{}</button>',
            btn_color, obj.id, lbl
        )
    azione_seleziona_sostituti.short_description = 'Gestione Sostituto'

    def approva_selezionate(self, request, queryset):
        from .services import approva_e_invia_sostituto
        count = 0
        for richiesta in queryset.filter(stato='APERTA'):
            from django.utils import timezone
            richiesta.stato = 'APPROVATA_RA'
            richiesta.approvata_ra_il = timezone.now()
            richiesta.save()
            approva_e_invia_sostituto(richiesta.pk)
            count += 1
        self.message_user(request, f"{count} richieste approvate e inviate via Telegram.", messages.SUCCESS)
    approva_selezionate.short_description = "🚀 Approva e invia notifica Telegram ai sostituti"

    def conferma_ufficio_selezionate(self, request, queryset):
        from .services import assegna_sostituto_da_ufficio
        count = 0
        errori = 0
        for richiesta in queryset:
            if richiesta.sostituto_id:
                res = assegna_sostituto_da_ufficio(richiesta.pk, sostituto_id=richiesta.sostituto_id)
                if res.get('ok'):
                    count += 1
                else:
                    errori += 1
            else:
                errori += 1
        if count > 0:
            self.message_user(request, f"✅ {count} sostituzioni confermate direttamente dall'ufficio.", messages.SUCCESS)
        if errori > 0:
            self.message_user(request, f"⚠️ {errori} richieste non avevano ancora un sostituto selezionato (usa il pulsante '👥 Scegli / Conferma Sostituto').", messages.WARNING)
    conferma_ufficio_selezionate.short_description = "🏢 Conferma dall'Ufficio il sostituto indicato"

