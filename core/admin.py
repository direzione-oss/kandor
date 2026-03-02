from django.contrib import admin
from .models import (
    Dipendente, Qualifica, Cliente, Mezzo, 
    Squadra, Turno, AssegnazioneTurno, TimeTracking,
    ProgrammazioneRicorrente, RichiestaStraordinaria, Assenza
)

@admin.register(Assenza)
class AssenzaAdmin(admin.ModelAdmin):
    list_display = ('dipendente', 'tipo', 'data_inizio', 'data_fine')
    list_filter = ('tipo', 'data_inizio')
    search_fields = ('dipendente__cognome',)

# -- Branding Configuration --
admin.site.site_header = "Kandor Administration"
admin.site.site_title = "Kandor Portal"
admin.site.index_title = "Benvenuto in Kandor"

@admin.register(Dipendente)
class DipendenteAdmin(admin.ModelAdmin):
    list_display = ('cognome', 'nome', 'stato', 'category_protetta_display', 'telegram_chat_id')
    search_fields = ('cognome', 'nome', 'codice_fiscale', 'telegram_chat_id')
    list_filter = ('stato', 'qualifiche')
    filter_horizontal = ('qualifiche',) # Migliora la selezione multipla
    actions = ['send_telegram_message_action']
    
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

class ProgrammazioneInline(admin.TabularInline):
    model = ProgrammazioneRicorrente
    extra = 1
    # Ordiniamo i campi logicamente: Tipo, Giorni, Ora Inizio, Durata, Ora Fine (calcolata)
    fields = ('tipo_ripetizione', 'giorno_settimana', 'giorno_mese', 'ora_inizio', 'durata', 'ora_fine', 'qualifica_richiesta', 'squadra_abituale', 'mezzo_abituale')
    readonly_fields = ('ora_fine',)
    ordering = ('tipo_ripetizione', 'giorno_settimana', 'ora_inizio')

class StraordinarioInline(admin.TabularInline):
    model = RichiestaStraordinaria
    extra = 0

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('ragione_sociale', 'indirizzo_sede', 'ore_mensili_contratto')
    search_fields = ('ragione_sociale', 'partita_iva')
    inlines = [ProgrammazioneInline, StraordinarioInline]

@admin.register(Mezzo)
class MezzoAdmin(admin.ModelAdmin):
    list_display = ('targa', 'modello', 'stato', 'km_attuali', 'scadenza_polizza', 'scadenza_bollo')
    list_filter = ('stato',)

@admin.register(Squadra)
class SquadraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'caposquadra')
    filter_horizontal = ('componenti',) # Migliora la selezione dei dipendenti per la squadra
    search_fields = ('nome',)
    actions = ['send_team_message_action']

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

class AssegnazioneInline(admin.TabularInline):
    model = AssegnazioneTurno
    extra = 1

@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ('data', 'squadra', 'mezzo')
    list_filter = ('data', 'squadra')
    inlines = [AssegnazioneInline]

admin.site.register(Qualifica)
admin.site.register(AssegnazioneTurno)
admin.site.register(TimeTracking)

from .models import MessaggioProgrammato
@admin.register(MessaggioProgrammato)
class MessaggioProgrammatoAdmin(admin.ModelAdmin):
    list_display = ('titolo', 'data_programmata', 'invia_a_tutti', 'inviato')
    list_filter = ('inviato', 'data_programmata')
    search_fields = ('titolo', 'testo')
    filter_horizontal = ('destinatari',)
    date_hierarchy = 'data_programmata'
