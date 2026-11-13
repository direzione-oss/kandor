import calendar
import os
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .utils_geocoding import geocode_address, get_cached_geocode, schedule_async_geocode
from django.utils.translation import gettext_lazy as _


def to_decimal(val, places=2):
    """
    Converte in modo sicuro qualsiasi valore numerico o stringa in Decimal
    arrotondato con ROUND_HALF_UP al numero di cifre decimali specificato.
    """
    quant = Decimal(10) ** -places
    if val is None or val == '':
        return Decimal('0').quantize(quant)
    try:
        if isinstance(val, Decimal):
            d = val
        elif isinstance(val, (int, float)):
            d = Decimal(str(val))
        else:
            d = Decimal(str(val).strip().replace(',', '.'))
        return d.quantize(quant, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0').quantize(quant)

# Se PostGIS fosse attivo:
# from django.contrib.gis.db import models as gis_models

class Qualifica(models.Model):
    nome = models.CharField(max_length=100)
    descrizione = models.TextField(blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Qualifica"
        verbose_name_plural = "Qualifiche"

class Dipendente(models.Model):
    STATO_CHOICES = [
        ('ATTIVO', 'Attivo'),
        ('TIROCINIO', 'Tirocinio'),
        ('MALATTIA', 'In Malattia'),
        ('FERIE', 'In Ferie'),
        ('PERMESSO', 'In Permesso'),
        ('104', 'Legge 104'),
        ('INATTIVO', 'Licenziato/Inattivo'),
    ]

    # Dati Anagrafici
    nome = models.CharField(max_length=100, verbose_name="Nome")
    cognome = models.CharField(max_length=100, verbose_name="Cognome")
    codice_fiscale = models.CharField(max_length=16, unique=True, verbose_name="Codice Fiscale")
    data_nascita = models.DateField(null=True, blank=True, verbose_name="Data di Nascita")
    indirizzo_residenza = models.CharField(max_length=255, verbose_name="Indirizzo Residenza")
    email = models.EmailField(blank=True, verbose_name="Email")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Telefono")
    
    # Coordinate (Semplificato per MVP senza PostGIS attivo, in futuro usare PointField)
    latitudine = models.FloatField(null=True, blank=True)
    longitudine = models.FloatField(null=True, blank=True)

    TIPO_PART_TIME_CHOICES = [
        ('M', 'M - Misto'),
        ('V', 'V - Verticale'),
        ('O', 'O - Orizzontale'),
    ]

    # Dati Contrattuali
    categoria_protetta = models.BooleanField(default=False)
    usufruisce_104 = models.BooleanField(
        default=False,
        verbose_name="Usufruisce della Legge 104",
        help_text="Se attivo, abilita la richiesta e il calcolo dei permessi Legge 104 per questo dipendente"
    )
    file_contratto = models.FileField(upload_to='contratti/', null=True, blank=True)
    data_assunzione = models.DateField(null=True, blank=True, verbose_name="Data di Assunzione")
    data_licenziamento = models.DateField(null=True, blank=True, verbose_name="Data di Licenziamento")
    is_part_time = models.BooleanField(default=False, verbose_name="Contratto Part-Time")
    tipo_part_time = models.CharField(
        max_length=1,
        choices=TIPO_PART_TIME_CHOICES,
        null=True, blank=True,
        verbose_name="Tipo Part-Time",
        help_text="Selezionare M (Misto), V (Verticale) o O (Orizzontale)"
    )
    ore_settimanali_part_time = models.DecimalField(
        max_digits=4, decimal_places=1,
        null=True, blank=True,
        verbose_name="Ore Settimanali (Part-Time)",
        help_text="Facoltativo"
    )
    LIVELLO_CONTRATTUALE_CHOICES = [
        ('TIROCINANTE', 'Tirocinante / Stage'),
        ('1_LIVELLO', '1° Livello (Operaio Comune)'),
        ('2_LIVELLO', '2° Livello (Operaio Qualificato)'),
        ('3_LIVELLO', '3° Livello (Operaio Specializzato / Caposquadra)'),
        ('4_LIVELLO', '4° Livello (Responsabile / Impiegato)'),
        ('5_LIVELLO', '5° Livello / Quadro'),
    ]
    livello_contrattuale = models.CharField(
        max_length=30,
        choices=LIVELLO_CONTRATTUALE_CHOICES,
        default='2_LIVELLO',
        blank=True,
        verbose_name="Livello Contrattuale CCNL",
    )
    costo_orario_aziendale = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=16.50,
        verbose_name="Costo Orario Aziendale (€/h - Lordo/TFR/INAIL)",
        help_text="Costo aziendale reale pieno (retribuzione lorda + contributi INPS/INAIL + TFR + ratei 13ª/14ª)",
    )
    data_ultima_visita_medica = models.DateField(null=True, blank=True, verbose_name="Prossima scadenza visita medica")
    
    # Relazioni
    qualifiche = models.ManyToManyField(Qualifica, related_name='dipendenti', blank=True, verbose_name="Qualifiche Possedute")
    
    # Integrazione Chat & App Mobile
    telegram_chat_id = models.CharField(max_length=64, blank=True, null=True, help_text="ID Chat Telegram per invio ore", verbose_name="Telegram Chat ID")
    pin_accesso = models.CharField(
        max_length=4,
        blank=True,
        default='',
        verbose_name="PIN Accesso App (4 cifre)",
        help_text="PIN numerico di 4 cifre per l'accesso alla Web App Dipendenti (generato in automatico se lasciato vuoto)"
    )
    foto_profilo_url = models.URLField(blank=True, null=True, verbose_name="Foto Profilo", help_text="URL foto profilo (inviata via bot Telegram)")
    
    # Stato
    stato = models.CharField(max_length=20, choices=STATO_CHOICES, default='ATTIVO')
    
    # Sostituto
    is_sostituto = models.BooleanField(default=False, verbose_name="Disponibile come Sostituto", help_text="Se attivo, questo dipendente può essere chiamato per sostituzioni")

    # Notifiche messaggi
    riceve_notifiche_messaggi = models.BooleanField(
        default=False,
        verbose_name="Riceve notifiche messaggi (Solo Responsabili)",
        help_text="Se attivo e l'utente ricopre un ruolo di Responsabile/Titolare, riceve una notifica Telegram quando un dipendente invia un messaggio."
    )

    # Foto profilo
    foto = models.ImageField(upload_to='foto_dipendenti/', null=True, blank=True, verbose_name="Foto Profilo")
    foto_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL Foto (Supabase)")
    foto_profilo_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL Foto Profilo (Telegram/Supabase)")

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.codice_fiscale:
            self.codice_fiscale = self.codice_fiscale.strip().upper()
            if len(self.codice_fiscale) != 16:
                raise ValidationError({'codice_fiscale': "Il codice fiscale deve contenere esattamente 16 caratteri."})
        if self.data_assunzione and self.data_licenziamento:
            if self.data_licenziamento < self.data_assunzione:
                raise ValidationError({'data_licenziamento': "La data di licenziamento non può essere precedente alla data di assunzione."})
        if self.is_part_time and not self.tipo_part_time:
            raise ValidationError({'tipo_part_time': "Per i contratti Part-Time è necessario selezionare la tipologia: M (Misto), V (Verticale) o O (Orizzontale)."})
        if self.pin_accesso:
            self.pin_accesso = self.pin_accesso.strip()
            if not (len(self.pin_accesso) == 4 and self.pin_accesso.isdigit()):
                raise ValidationError({'pin_accesso': "Il PIN di accesso deve essere composto da esattamente 4 cifre numeriche (es. 1234)."})
        if self.telegram_chat_id is not None:
            self.telegram_chat_id = str(self.telegram_chat_id).strip()
            if self.telegram_chat_id:
                conflitto = Dipendente.objects.filter(
                    telegram_chat_id=self.telegram_chat_id
                ).exclude(pk=self.pk).first()
                if conflitto:
                    raise ValidationError({
                        'telegram_chat_id': (
                            f"⚠️ Attenzione: questo ID Telegram ({self.telegram_chat_id}) è già associato al dipendente "
                            f"{conflitto.cognome} {conflitto.nome} (Stato: {conflitto.get_stato_display()}). "
                            "Non è consentito associare lo stesso account Telegram a due dipendenti diversi."
                        )
                    })
            else:
                self.telegram_chat_id = None

    def save(self, *args, **kwargs):
        from django.utils import timezone
        import random
        today = timezone.now().date()
        if self.codice_fiscale:
            self.codice_fiscale = self.codice_fiscale.strip().upper()
        if self.telegram_chat_id is not None:
            self.telegram_chat_id = str(self.telegram_chat_id).strip() or None
        if not self.pin_accesso or len(self.pin_accesso.strip()) != 4:
            self.pin_accesso = f"{random.randint(1000, 9999)}"
        else:
            self.pin_accesso = self.pin_accesso.strip()
        # Auto-calculate data_nascita from CF if missing
        if not self.data_nascita and self.codice_fiscale:
            from .utils_cf import extract_data_nascita
            extracted_date = extract_data_nascita(self.codice_fiscale)
            if extracted_date:
                self.data_nascita = extracted_date

        # Sincronizza stato INATTIVO e data_licenziamento
        if self.data_licenziamento and self.data_licenziamento <= today:
            self.stato = 'INATTIVO'
        elif self.stato == 'INATTIVO' and not self.data_licenziamento:
            self.data_licenziamento = today
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cognome} {self.nome}"

    class Meta:
        verbose_name_plural = "Dipendenti"
        ordering = ['cognome', 'nome']

class Cliente(models.Model):
    ragione_sociale = models.CharField(max_length=200, verbose_name="Ragione Sociale")
    partita_iva = models.CharField(max_length=20, blank=True, null=True, verbose_name="Partita IVA")
    codice_fiscale = models.CharField(max_length=16, blank=True, null=True, verbose_name="Codice Fiscale")
    
    indirizzo_sede = models.CharField(max_length=255, verbose_name="Indirizzo Sede")
    
    # Coordinate
    latitudine = models.FloatField(null=True, blank=True)
    longitudine = models.FloatField(null=True, blank=True)

    # Referente / Titolare
    referente_nome = models.CharField(max_length=100, blank=True, verbose_name="Nome Titolare/Referente")
    referente_ruolo = models.CharField(max_length=100, blank=True, verbose_name="Ruolo")
    referente_data_nascita = models.DateField(null=True, blank=True, verbose_name="Data di Nascita Referente")

    # Requisiti
    ore_mensili_contratto = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, help_text="Ore mensili previste da contratto", verbose_name="Ore Mensili Contratto")
    importo_mensile_contratto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Importo mensile concordato (EUR)", verbose_name="Importo Mensile Contratto (€)")
    note_mansioni = models.TextField(blank=True, help_text="Mansioni richieste specifiche", verbose_name="Note Mansioni")

    @property
    def importo_orario_decimal(self):
        """Calcola l'importo orario con precisione Decimal (ROUND_HALF_UP)."""
        ore = to_decimal(self.ore_mensili_contratto)
        if ore > Decimal('0.00'):
            return to_decimal(to_decimal(self.importo_mensile_contratto) / ore, places=2)
        return Decimal('0.00')

    @property
    def importo_orario(self):
        """Calcola l'importo orario: importo_mensile / ore_mensili"""
        ore = to_decimal(self.ore_mensili_contratto)
        if ore > Decimal('0.00'):
            return float(self.importo_orario_decimal)
        return 0

    def get_condizioni_contrattuali_alla_data(self, target_date):
        """
        Restituisce la tupla (ore_mensili_dec, importo_mensile_dec) valida alla data `target_date`.
        Se esiste uno storico contrattuale (`storico_contratti`), individua il periodo di competenza
        che copre `target_date` senza alterare i consuntivi dei mesi precedenti in caso di rinnovo/adeguamento.
        """
        if not self.pk:
            return to_decimal(self.ore_mensili_contratto), to_decimal(self.importo_mensile_contratto)

        records = list(self.storico_contratti.all())
        if not records:
            return to_decimal(self.ore_mensili_contratto), to_decimal(self.importo_mensile_contratto)

        # Ordina per valido_dal decrescente, id decrescente (in memoria per sfruttare prefetch_related)
        records_desc = sorted(records, key=lambda r: (r.valido_dal or date.min, r.pk or 0), reverse=True)
        for rec in records_desc:
            if rec.valido_dal <= target_date and (rec.valido_al is None or rec.valido_al >= target_date):
                return to_decimal(rec.ore_mensili_contratto), to_decimal(rec.importo_mensile_contratto)

        # Se target_date è antecedente al primo record storico registrato, usa il record più antico
        earliest = records_desc[-1]
        if target_date < earliest.valido_dal:
            return to_decimal(earliest.ore_mensili_contratto), to_decimal(earliest.importo_mensile_contratto)

        return to_decimal(self.ore_mensili_contratto), to_decimal(self.importo_mensile_contratto)

    def get_condizioni_contrattuali_mese(self, anno, mese):
        """
        Restituisce (ore_mensili_dec, importo_mensile_dec) validi nel mese `(anno, mese)`,
        valutati all'ultimo giorno del mese di competenza.
        """
        _, last_day = calendar.monthrange(int(anno), int(mese))
        return self.get_condizioni_contrattuali_alla_data(date(int(anno), int(mese), last_day))

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.codice_fiscale:
            self.codice_fiscale = self.codice_fiscale.strip().upper()
        if self.partita_iva:
            self.partita_iva = self.partita_iva.strip()
        if self.ore_mensili_contratto is not None and self.ore_mensili_contratto < 0:
            raise ValidationError({'ore_mensili_contratto': "Le ore mensili previste da contratto non possono essere un valore negativo."})
        if self.importo_mensile_contratto is not None and self.importo_mensile_contratto < 0:
            raise ValidationError({'importo_mensile_contratto': "L'importo mensile di contratto non può essere un valore negativo."})

    def __str__(self):
        return self.ragione_sociale

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clienti"
        ordering = ['ragione_sociale']


class StoricoContrattoCliente(models.Model):
    """
    Storicizzazione delle condizioni economiche e orarie del contratto Cliente.
    Garantisce che un adeguamento tariffario o una variazione del monte ore mensile
    non sovrascriva retroattivamente i report di riconciliazione, verifica ore e MOL dei mesi passati.
    """
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='storico_contratti',
        verbose_name="Cliente",
    )
    valido_dal = models.DateField(verbose_name="Valido Dal")
    valido_al = models.DateField(
        null=True,
        blank=True,
        verbose_name="Valido Fino Al",
        help_text="Lasciare vuoto se è il contratto attualmente in vigore",
    )
    ore_mensili_contratto = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Ore Mensili Contratto",
    )
    importo_mensile_contratto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Importo Mensile Contratto (€)",
    )
    note_variazione = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Note Variazione / Adeguamento",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def importo_orario(self):
        ore = to_decimal(self.ore_mensili_contratto)
        if ore > Decimal('0.00'):
            return float(to_decimal(to_decimal(self.importo_mensile_contratto) / ore, places=2))
        return 0.0

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.valido_dal and self.valido_al and self.valido_al < self.valido_dal:
            raise ValidationError({'valido_al': "La data di fine validità non può essere antecedente alla data di inizio validità."})

    def __str__(self):
        fine_str = self.valido_al.strftime('%d/%m/%Y') if self.valido_al else 'In corso'
        return (
            f"{self.cliente.ragione_sociale}: {self.valido_dal.strftime('%d/%m/%Y')} → {fine_str} "
            f"({self.ore_mensili_contratto}h / €{self.importo_mensile_contratto})"
        )

    class Meta:
        verbose_name = "Storico Contratto Cliente"
        verbose_name_plural = "Storico Contratti Clienti"
        ordering = ['-valido_dal', '-id']
        indexes = [
            models.Index(fields=['cliente', 'valido_dal', 'valido_al'], name='core_storicocontr_cli_dt_idx'),
        ]

class ProgrammazioneRicorrente(models.Model):
    TIPO_RIPETIZIONE = [
        ('GIORNALIERO', 'Giornaliero (ogni giorno)'),
        ('SETTIMANALE', 'Settimanale'),
        ('BISETTIMANALE', 'Ogni 2 Settimane'),
        ('MENSILE', 'Mensile'),
    ]
    GIORNI_SETTIMANA = [
        (0, 'Lunedì'), (1, 'Martedì'), (2, 'Mercoledì'),
        (3, 'Giovedì'), (4, 'Venerdì'), (5, 'Sabato'), (6, 'Domenica'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='programmazione_ricorrente')
    tipo_ripetizione = models.CharField(max_length=20, choices=TIPO_RIPETIZIONE, default='SETTIMANALE')
    
    # Campo giorno separato per gestire meglio l'interfaccia (lettere vs numeri)
    giorno_settimana = models.IntegerField(choices=GIORNI_SETTIMANA, null=True, blank=True, verbose_name="Giorno della Settimana")
    giorno_mese = models.IntegerField(null=True, blank=True, verbose_name="Giorno del Mese (1-31)")
    
    ora_inizio = models.TimeField(help_text="Formato HH:MM (es. 06:30)")
    durata = models.DecimalField(max_digits=4, decimal_places=2, help_text="Durata in ore (es. 2.5 per 2 ore e mezza)", default=1.0)
    ora_fine = models.TimeField(editable=False, null=True) # Calcolato autom.
    
    orario_flessibile = models.BooleanField(default=False, help_text="Se attivo, gli orari sono indicativi")
    qualifica_richiesta = models.ForeignKey(Qualifica, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mansione/Qualifica")
    
    # Per l'automazione dei turni: chi fa questo lavoro di solito?
    squadra_abituale = models.ForeignKey('Squadra', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Squadra Abituale", help_text="Squadra che esegue solitamente questo turno")
    mezzo_abituale = models.ForeignKey('Mezzo', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mezzo Abituale")
    
    # Periodo attivo del contratto
    data_inizio_contratto = models.DateField(null=True, blank=True, verbose_name="Data Inizio Contratto", help_text="Data dalla quale iniziano i turni")
    data_fine_contratto = models.DateField(null=True, blank=True, verbose_name="Data Fine Contratto", help_text="Data fino alla quale generare i turni (vuoto = a tempo indeterminato)")

    def save(self, *args, **kwargs):
        # Calcolo automatico ora_fine
        if self.ora_inizio and self.durata:
            # Trucco per sommare ore a un TimeField (richiede trasformazione in datetime dummy)
            import datetime
            dummy_date = datetime.date.today()
            dt_start = datetime.datetime.combine(dummy_date, self.ora_inizio)
            # Durata in ore -> timedelta
            hours = int(self.durata)
            minutes = int((self.durata - hours) * 60)
            dt_end = dt_start + datetime.timedelta(hours=hours, minutes=minutes)
            self.ora_fine = dt_end.time()
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.db.models import Q
        import datetime
        
        # Validazione Durata
        if self.durata is None or self.durata <= 0:
            raise ValidationError({'durata': "La durata del turno deve essere un valore numerico maggiore di zero."})

        # Validazione Tipo Ripetizione
        if self.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE') and self.giorno_settimana is None:
            raise ValidationError({'giorno_settimana': "Devi selezionare un Giorno della Settimana."})
        if self.tipo_ripetizione == 'BISETTIMANALE' and not self.data_inizio_contratto:
            raise ValidationError({'data_inizio_contratto': "Per ripetizione Bisettimanale devi inserire la Data Inizio Contratto (usata come riferimento ciclo)."})
        if self.tipo_ripetizione == 'MENSILE':
            if self.giorno_mese is None:
                raise ValidationError({'giorno_mese': "Per la ripetizione Mensile devi inserire un Giorno del Mese."})
            if self.giorno_mese < 1 or self.giorno_mese > 31:
                raise ValidationError({'giorno_mese': "Il giorno del mese deve essere un numero compreso tra 1 e 31."})
        
        # Validazione date contratto
        if self.data_inizio_contratto and self.data_fine_contratto:
            if self.data_fine_contratto < self.data_inizio_contratto:
                raise ValidationError("La Data Fine Contratto non puo' essere precedente alla Data Inizio.")

        # Calcolo proiettivo ora_fine per la validazione (se non ancora salvato)
        check_ora_fine = self.ora_fine
        if self.ora_inizio and self.durata:
            dummy_date = datetime.date.today()
            dt_start = datetime.datetime.combine(dummy_date, self.ora_inizio)
            hours = int(self.durata)
            minutes = int((self.durata - hours) * 60)
            dt_end = dt_start + datetime.timedelta(hours=hours, minutes=minutes)
            if dt_end.date() > dummy_date:
                check_ora_fine = datetime.time(23, 59, 59)
            else:
                check_ora_fine = dt_end.time()
        
        # Validazione Sovrapposizioni (Squadra e Mezzo)
        if self.ora_inizio and check_ora_fine and check_ora_fine > self.ora_inizio and (self.squadra_abituale or self.mezzo_abituale):
            today = datetime.date.today()
            # Filtro base: stessa periodicità
            query = Q(tipo_ripetizione=self.tipo_ripetizione)
            if self.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE'):
                query &= Q(giorno_settimana=self.giorno_settimana)
            elif self.tipo_ripetizione == 'MENSILE':
                query &= Q(giorno_mese=self.giorno_mese)
            
            # Filtro orario: overlap (StartA < EndB) and (EndA > StartB)
            query &= Q(ora_inizio__lt=check_ora_fine) & Q(ora_fine__gt=self.ora_inizio)

            # Escludi contratti già scaduti o con periodo contrattuale non sovrapposto
            query &= (Q(data_fine_contratto__isnull=True) | Q(data_fine_contratto__gte=today))
            if self.data_inizio_contratto:
                query &= (Q(data_fine_contratto__isnull=True) | Q(data_fine_contratto__gte=self.data_inizio_contratto))
            if self.data_fine_contratto:
                query &= (Q(data_inizio_contratto__isnull=True) | Q(data_inizio_contratto__lte=self.data_fine_contratto))
            
            # Escludi se stesso (in caso di modifica)
            if self.pk:
                query &= ~Q(pk=self.pk)
            
            # Controllo Squadra
            if self.squadra_abituale:
                conflitti_squadra = ProgrammazioneRicorrente.objects.filter(query, squadra_abituale=self.squadra_abituale).select_related('cliente')
                if conflitti_squadra.exists():
                    conflitto = conflitti_squadra.first()
                    raise ValidationError(f"La squadra '{self.squadra_abituale}' è già impegnata in orario sovrapposto (Cliente: {conflitto.cliente}).")

            # Controllo Mezzo
            if self.mezzo_abituale:
                conflitti_mezzo = ProgrammazioneRicorrente.objects.filter(query, mezzo_abituale=self.mezzo_abituale).select_related('cliente')
                if conflitti_mezzo.exists():
                    conflitto = conflitti_mezzo.first()
                    raise ValidationError(f"Il mezzo '{self.mezzo_abituale}' è già impegnato in orario sovrapposto (Cliente: {conflitto.cliente}).")

    def __str__(self):
        tipo = self.get_tipo_ripetizione_display()
        if self.tipo_ripetizione == 'GIORNALIERO':
             giorno = "ogni giorno"
        elif self.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE'):
             giorno = self.get_giorno_settimana_display()
        else:
             giorno = f"Giorno {self.giorno_mese}"
        periodo = ""
        if self.data_inizio_contratto:
            periodo = f" dal {self.data_inizio_contratto.strftime('%d/%m/%Y')}"
        if self.data_fine_contratto:
            periodo += f" al {self.data_fine_contratto.strftime('%d/%m/%Y')}"
        return f"{self.cliente} - {tipo} {giorno} ({self.ora_inizio} + {self.durata}h){periodo}"

    class Meta:
        verbose_name = "Programmazione Ricorrente"
        verbose_name_plural = "Programmazioni Ricorrenti"
        ordering = ['tipo_ripetizione', 'giorno_settimana', 'giorno_mese', 'ora_inizio']


class RichiestaStraordinaria(models.Model):
    STATO_FATTURAZIONE_CHOICES = [
        ('DA_FATTURARE', '💰 Da Fatturare a parte'),
        ('INCLUSO_NEL_CANONE', '🤝 Incluso nel Canone'),
        ('FATTURATO', '✅ Fatturato'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='richieste_straordinarie')
    data_inizio = models.DateField()
    data_fine = models.DateField(null=True, blank=True, help_text="Se il lavoro dura più giorni (opzionale)")
    
    ora_inizio = models.TimeField(verbose_name="Ora Inizio")
    ora_fine = models.TimeField(verbose_name="Ora Fine")
    
    descrizione = models.TextField(verbose_name="Descrizione Attività")
    completata = models.BooleanField(default=False, verbose_name="Completata")

    # Pre-Fatturazione Attiva (Miglioria 5)
    stato_fatturazione = models.CharField(
        max_length=25,
        choices=STATO_FATTURAZIONE_CHOICES,
        default='DA_FATTURARE',
        verbose_name="Stato Fatturazione",
    )
    prezzo_concordato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Prezzo Concordato (€)",
        help_text="Importo extra concordato col cliente per questo lavoro straordinario (escluso IVA)",
    )
    numero_fattura_rif = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name="Rif. Fattura / Note Amministrative",
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.data_inizio and self.data_fine and self.data_fine < self.data_inizio:
            raise ValidationError({'data_fine': "La data di fine lavoro non può essere precedente alla data di inizio."})
        if self.ora_inizio and self.ora_fine and self.ora_fine <= self.ora_inizio:
            raise ValidationError({'ora_fine': "L'ora di fine deve essere successiva all'ora di inizio."})

    def __str__(self):
        return f"Straordinario {self.cliente} - {self.data_inizio}"

    class Meta:
        verbose_name_plural = "Richieste Straordinarie"
        ordering = ['-data_inizio', 'ora_inizio']

class Mezzo(models.Model):
    STATO_MEZZO = [
        ('DISPONIBILE', 'Disponibile'),
        ('MANUTENZIONE', 'In Manutenzione'),
        ('RIPARAZIONE', 'In Riparazione'),
    ]

    modello = models.CharField(max_length=100, verbose_name="Modello Mezzo")
    targa = models.CharField(max_length=20, unique=True, verbose_name="Targa")
    stato = models.CharField(max_length=20, choices=STATO_MEZZO, default='DISPONIBILE', verbose_name="Stato Attuale")
    km_attuali = models.IntegerField(default=0, verbose_name="Km Percorsi")
    scadenza_polizza = models.DateField(null=True, blank=True, verbose_name="Scadenza Polizza")
    scadenza_revisione = models.DateField(null=True, blank=True, verbose_name="Scadenza Revisione")
    numero_permesso_citta_alta = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Numero Permesso Città Alta (Bergamo)",
    )
    scadenza_permesso_citta_alta = models.DateField(
        null=True,
        blank=True,
        verbose_name="Scadenza Permesso Città Alta (Bergamo)",
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.targa:
            self.targa = self.targa.strip().upper()
        if self.km_attuali is not None and self.km_attuali < 0:
            raise ValidationError({'km_attuali': "I chilometri percorsi non possono essere un valore negativo."})

    def __str__(self):
        return f"{self.modello} ({self.targa})"

    class Meta:
        verbose_name_plural = "Mezzi Aziendali"
        ordering = ['modello', 'targa']

class Squadra(models.Model):
    nome = models.CharField(max_length=100)
    caposquadra = models.ForeignKey(Dipendente, on_delete=models.SET_NULL, null=True, related_name='squadre_capitanate')
    componenti = models.ManyToManyField(Dipendente, related_name='squadre_appartenenza', blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Squadre"
        ordering = ['nome']

class Turno(models.Model):
    data = models.DateField(verbose_name="Data Turno")
    squadra = models.ForeignKey(Squadra, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Squadra Assegnata")
    mezzo = models.ForeignKey(Mezzo, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mezzo Utilizzato")

    @property
    def nome_squadra(self):
        if self.squadra_id and self.squadra:
            return self.squadra.nome
        for a in self.assegnazioni.all():
            if a.mansione_svolta and '[Squadra:' in a.mansione_svolta:
                try:
                    return a.mansione_svolta.split('[Squadra:')[1].split(']')[0].strip()
                except Exception:
                    pass
        return "Squadra Storica"
    
    def __str__(self):
        return f"Turno {self.data} - {self.nome_squadra}"

    class Meta:
        verbose_name_plural = "Turni"
        indexes = [
            models.Index(fields=['data', 'squadra'], name='core_turno_data_sq_idx'),
        ]

class AssegnazioneTurno(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='assegnazioni')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    
    # Link alla programmazione (Opzionale, ma consigliato per tracciabilità)
    programmazione_feriale = models.ForeignKey(ProgrammazioneRicorrente, on_delete=models.SET_NULL, null=True, blank=True, related_name='assegnazioni_svolte')
    richiesta_straordinaria = models.ForeignKey(RichiestaStraordinaria, on_delete=models.SET_NULL, null=True, blank=True, related_name='assegnazioni_svolte')
    
    orario_inizio_previsto = models.TimeField()
    orario_fine_previsto = models.TimeField()
    ore_previste_contratto = models.DecimalField(
        max_digits=6, decimal_places=2,
        null=True, blank=True,
        verbose_name="Ore previste (contratto)",
        help_text="Ore contrattuali previste per questo turno. Possono differire dalla durata orario inizio-fine."
    )
    dipendenti_esclusi = models.ManyToManyField(
        'Dipendente',
        blank=True,
        related_name='turni_escluso',
        verbose_name="Dipendenti esclusi",
        help_text="Dipendenti della squadra NON presenti in questo turno (es. lavoro da soli)."
    )
    
    mansione_svolta = models.TextField(blank=True)

    @property
    def dipendenti_presenti(self):
        """Restituisce i dipendenti della squadra effettivamente presenti (squadra - esclusi), inclusi eventuali componenti storici."""
        squadra = self.turno.squadra if self.turno else None
        esclusi = {d.pk for d in self.dipendenti_esclusi.all()}
        presenti = []
        presenti_pks = set()
        if squadra:
            if squadra.caposquadra_id and squadra.caposquadra_id not in esclusi and squadra.caposquadra:
                presenti.append(squadra.caposquadra)
                presenti_pks.add(squadra.caposquadra_id)
            for c in squadra.componenti.all():
                if c.pk not in esclusi and c.pk not in presenti_pks:
                    presenti.append(c)
                    presenti_pks.add(c.pk)
        for tt in self.timetracks.all():
            if tt.dipendente_id and tt.dipendente_id not in esclusi and tt.dipendente_id not in presenti_pks and tt.dipendente:
                presenti.append(tt.dipendente)
                presenti_pks.add(tt.dipendente_id)
        return presenti

    @property
    def n_presenti(self):
        return len(self.dipendenti_presenti)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.programmazione_feriale and self.richiesta_straordinaria:
            raise ValidationError("Un'assegnazione non può essere legata contemporaneamente a una programmazione feriale e straordinaria.")
        if self.orario_inizio_previsto and self.orario_fine_previsto:
            if self.orario_fine_previsto == self.orario_inizio_previsto:
                raise ValidationError({'orario_fine_previsto': "L'orario di fine non può essere uguale all'orario di inizio."})
        if self.ore_previste_contratto is not None and self.ore_previste_contratto < 0:
            raise ValidationError({'ore_previste_contratto': "Le ore previste non possono essere un valore negativo."})

    def save(self, *args, **kwargs):
        # Auto-fill orari se linkato a una programmazione e orari non specificati
        if not self.id: # Solo in creazione
            if self.programmazione_feriale and not self.orario_inizio_previsto:
                self.orario_inizio_previsto = self.programmazione_feriale.ora_inizio
                self.orario_fine_previsto = self.programmazione_feriale.ora_fine
            elif self.richiesta_straordinaria and not self.orario_inizio_previsto:
                self.orario_inizio_previsto = self.richiesta_straordinaria.ora_inizio
                self.orario_fine_previsto = self.richiesta_straordinaria.ora_fine
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} ({self.orario_inizio_previsto}-{self.orario_fine_previsto})"

    class Meta:
        verbose_name = "Assegnazione Turno"
        verbose_name_plural = "Assegnazioni Turno"
        indexes = [
            models.Index(fields=['turno', 'cliente'], name='core_assign_turno_cli_idx'),
        ]

class TimeTracking(models.Model):
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE)
    assegnazione = models.ForeignKey(AssegnazioneTurno, on_delete=models.CASCADE, related_name='timetracks')
    
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    ore_dichiarate = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name="Ore Dichiarate", help_text="Ore inserite dal dipendente")
    
    note = models.TextField(blank=True)
    
    SOURCE_CHOICES = [
        ('MANUAL', 'Manuale'),
        ('TELEGRAM', 'Telegram'),
        ('WHATSAPP', 'WhatsApp'),
        ('WEBAPP', 'Web App'),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='MANUAL')
    is_validated = models.BooleanField(default=False, verbose_name="Validato")

    class Meta:
        indexes = [
            models.Index(fields=['dipendente', 'assegnazione'], name='core_tt_dip_assign_idx'),
            models.Index(fields=['assegnazione', 'is_validated'], name='core_tt_assign_val_idx'),
        ]

    @property
    def durata_ore(self):
        if self.ore_dichiarate:
            return float(self.ore_dichiarate)
        if self.check_in and self.check_out:
            diff = self.check_out - self.check_in
            return diff.total_seconds() / 3600
        return 0

class Assenza(models.Model):
    TIPO_ASSENZA = [
        ('FERIE', 'Ferie'),
        ('MALATTIA', 'Malattia'),
        ('PERMESSO', 'Permesso'),
        ('104', 'Legge 104'),
        ('ALTRO', 'Altro'),
    ]
    
    STATO_APPROVAZIONE = [
        ('IN_ATTESA', 'In Attesa Avvallo Amministrazione'),
        ('APPROVATA', 'Approvata (Avvallata)'),
        ('RIFIUTATA', 'Rifiutata dall\'Amministrazione'),
    ]

    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='assenze')
    tipo = models.CharField(max_length=20, choices=TIPO_ASSENZA)
    data_inizio = models.DateField()
    data_fine = models.DateField()
    ora_inizio = models.TimeField(null=True, blank=True, verbose_name="Ora Inizio")
    ora_fine = models.TimeField(null=True, blank=True, verbose_name="Ora Fine")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True) # Allow null for existing rows
    source = models.CharField(max_length=20, default='MANUAL') # MANUAL, TELEGRAM
    is_processed = models.BooleanField(default=False, verbose_name="Processato")
    stato_approvazione = models.CharField(
        max_length=20,
        choices=STATO_APPROVAZIONE,
        default='IN_ATTESA',
        verbose_name="Stato Avvallo Amministrazione"
    )
    approvata_da_admin_il = models.DateTimeField(null=True, blank=True, verbose_name="Avvallata il")

    @property
    def ore_permesso(self):
        """Calcola la durata in ore del permesso se specificati ora_inizio e ora_fine."""
        if self.ora_inizio and self.ora_fine:
            import datetime
            d = datetime.date.today()
            t_start = datetime.datetime.combine(d, self.ora_inizio)
            t_end = datetime.datetime.combine(d, self.ora_fine)
            if t_end > t_start:
                diff = (t_end - t_start).total_seconds() / 3600.0
                return round(diff, 1)
        return None

    def get_orario_display(self):
        """Restituisce la stringa formattata dell'orario o dell'intera giornata."""
        if self.ora_inizio and self.ora_fine:
            durata = f" ({self.ore_permesso}h)" if self.ore_permesso else ""
            return f"{self.ora_inizio.strftime('%H:%M')} - {self.ora_fine.strftime('%H:%M')}{durata}"
        return "Intera Giornata"
    get_orario_display.short_description = "Orario / Durata"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.data_inizio and self.data_fine:
            if self.data_fine < self.data_inizio:
                raise ValidationError({'data_fine': "La data di fine assenza non può essere precedente alla data di inizio."})
        if self.ora_inizio and self.ora_fine:
            if self.ora_fine <= self.ora_inizio:
                raise ValidationError({'ora_fine': "L'ora di fine deve essere successiva all'ora di inizio."})
        if self.tipo == '104':
            if self.dipendente_id and hasattr(self.dipendente, 'usufruisce_104') and not self.dipendente.usufruisce_104:
                raise ValidationError({'tipo': "Il dipendente selezionato non è abilitato alla fruizione dei permessi Legge 104."})

    def __str__(self):
        orario = f" {self.get_orario_display()}" if self.ora_inizio else ""
        return f"{self.dipendente} - {self.tipo} ({self.data_inizio} a {self.data_fine}{orario})"

    class Meta:
        verbose_name_plural = "Assenze"

class Segnalazione(models.Model):
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='segnalazioni')
    testo = models.TextField(verbose_name="Testo Segnalazione")
    data_inserimento = models.DateTimeField(auto_now_add=True)
    risolto = models.BooleanField(default=False, verbose_name="Risolto")
    note_amministrazione = models.TextField(blank=True, verbose_name="Note Amministrazione")

    def __str__(self):
        return f"Segnalazione di {self.dipendente} del {self.data_inserimento.strftime('%d/%m/%Y')}"

    class Meta:
        verbose_name_plural = "Segnalazioni"

    class Meta:
        verbose_name_plural = "Segnalazioni"

class MessaggioProgrammato(models.Model):
    titolo = models.CharField(max_length=200, verbose_name="Titolo/Descrizione")
    testo = models.TextField(blank=True, default='', verbose_name="Testo del Messaggio")
    allegato = models.FileField(
        upload_to='messaggi_programmati/',
        null=True,
        blank=True,
        verbose_name="File Allegato (Foto, Cedolino PDF, ecc.)",
    )
    data_programmata = models.DateTimeField(verbose_name="Data e Ora di Invio")
    destinatari = models.ManyToManyField(Dipendente, blank=True, verbose_name="Destinatari Specifici")
    invia_a_tutti = models.BooleanField(default=False, verbose_name="Invia a TUTTI i dipendenti attivi")
    inviato = models.BooleanField(default=False, verbose_name="Inviato", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "✅ Inviato" if self.inviato else "⏳ In attesa"
        return f"{self.titolo} ({self.data_programmata.strftime('%d/%m %H:%M')}) - {status}"

    class Meta:
        verbose_name = "Messaggio Programmato"
        verbose_name_plural = "Messaggi Programmabili"

class ProximityLog(models.Model):
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='proximity_logs')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='proximity_logs')
    is_near = models.BooleanField(default=False, verbose_name="Attualmente Vicino")
    entered_at = models.DateTimeField(null=True, blank=True, verbose_name="Entrato alle")
    exited_at = models.DateTimeField(null=True, blank=True, verbose_name="Uscito alle")
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Log Prossimità"
        verbose_name_plural = "Log Prossimità"
        unique_together = ('dipendente', 'cliente')
    
    def __str__(self):
        status = "🟢 Vicino" if self.is_near else "🔴 Lontano"
        return f"{self.dipendente} @ {self.cliente} - {status}"


class MessaggioChat(models.Model):
    """Messaggio scambiato tra dipendente (Telegram) e admin (Chat Simulator)."""
    DIREZIONE_CHOICES = [
        ('IN', 'Ricevuto dal dipendente'),
        ('OUT', 'Inviato dall\'admin'),
    ]
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='messaggi_chat')
    testo = models.TextField(blank=True, default='')
    foto_url = models.URLField(blank=True, default='', verbose_name="URL Foto")
    allegato_url = models.CharField(max_length=500, blank=True, default='', verbose_name="URL Allegato")
    allegato_nome = models.CharField(max_length=255, blank=True, default='', verbose_name="Nome File Allegato")
    direzione = models.CharField(max_length=3, choices=DIREZIONE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    letto = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Messaggio Chat"
        verbose_name_plural = "Messaggi Chat"
        ordering = ['timestamp']

    def __str__(self):
        arrow = "←" if self.direzione == 'IN' else "→"
        return f"{arrow} {self.dipendente.nome}: {self.testo[:50]}"


class ResponsabileArea(models.Model):
    dipendente = models.OneToOneField(Dipendente, on_delete=models.CASCADE, related_name='ruolo_responsabile')
    nome_area = models.CharField(max_length=100, verbose_name="Nome Area")
    squadre = models.ManyToManyField('Squadra', related_name='responsabile_area', blank=True, verbose_name="Squadre Supervisionate")

    def __str__(self):
        return f"{self.dipendente} - {self.nome_area}"

    class Meta:
        verbose_name = "Responsabile Area"
        verbose_name_plural = "Responsabili Area"
        ordering = ['nome_area']


class Titolare(models.Model):
    """Titolare/proprietario con accesso alla dashboard di supervisione.
    Può essere collegato a un Dipendente esistente (se il titolare lavora anche in organico).
    In quel caso il telegram_chat_id viene preso automaticamente dal Dipendente collegato.
    """
    from django.contrib.auth.models import User as AuthUser
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profilo_titolare', verbose_name="Utente Django")
    nome = models.CharField(max_length=100, verbose_name="Nome Completo")
    dipendente = models.OneToOneField(
        'Dipendente', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='profilo_titolare', verbose_name="Dipendente collegato",
        help_text="Se il titolare è anche un dipendente in organico, collegalo qui. Il Chat ID Telegram verrà preso dal dipendente."
    )
    telegram_chat_id = models.CharField(
        max_length=50, blank=True, verbose_name="Telegram Chat ID",
        help_text="Lascia vuoto se hai collegato un Dipendente (verrà usato il suo Chat ID)"
    )
    notifiche_attive = models.BooleanField(default=True, verbose_name="Notifiche Telegram Attive")

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.dipendente and not self.telegram_chat_id:
            raise ValidationError("È necessario collegare un Dipendente o inserire un Telegram Chat ID per ricevere le notifiche.")

    def get_chat_id(self):
        """Restituisce il Chat ID: dal Dipendente collegato se presente, altrimenti dal campo diretto."""
        if self.dipendente and self.dipendente.telegram_chat_id:
            return self.dipendente.telegram_chat_id
        return self.telegram_chat_id

    def __str__(self):
        if self.dipendente:
            return f"Titolare: {self.nome} (dip. {self.dipendente})"
        return f"Titolare: {self.nome}"

    class Meta:
        verbose_name = "Titolare"
        verbose_name_plural = "Titolari"


class RichiestaSostituzione(models.Model):
    STATO_RICHIESTA = [
        ('APERTA', 'Aperta'),
        ('APPROVATA_RA', 'Approvata dal Responsabile'),
        ('INVIATA', 'Inviata al Sostituto'),
        ('ACCETTATA', 'Accettata'),
        ('RIFIUTATA', 'Rifiutata'),
        ('SCADUTA', 'Scaduta (timeout 1h)'),
        ('COMPLETATA', 'Completata'),
        ('ANNULLATA', 'Annullata'),
    ]

    # Turno da coprire
    assegnazione_originale = models.ForeignKey(AssegnazioneTurno, on_delete=models.CASCADE, related_name='richieste_sostituzione')
    dipendente_assente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='sostituzioni_assente')
    motivo_assenza = models.CharField(max_length=20, verbose_name="Motivo Assenza")

    # Sostituto selezionato
    sostituto = models.ForeignKey(Dipendente, on_delete=models.SET_NULL, null=True, blank=True, related_name='sostituzioni_effettuate', verbose_name="Sostituto Assegnato")

    # Responsabile Area
    responsabile_area = models.ForeignKey(ResponsabileArea, on_delete=models.SET_NULL, null=True, blank=True)

    # Stato e timing
    stato = models.CharField(max_length=20, choices=STATO_RICHIESTA, default='APERTA')
    creata_il = models.DateTimeField(auto_now_add=True)
    approvata_ra_il = models.DateTimeField(null=True, blank=True, verbose_name="Approvata RA il")
    inviata_sostituto_il = models.DateTimeField(null=True, blank=True, verbose_name="Inviata al Sostituto il")
    risposta_sostituto_il = models.DateTimeField(null=True, blank=True, verbose_name="Risposta Sostituto il")

    # Coda sostituti (ordine di contatto)
    sostituti_candidati = models.JSONField(default=list, blank=True, help_text="Lista ordinata ID sostituti da contattare")
    sostituto_corrente_idx = models.IntegerField(default=0, verbose_name="Indice Sostituto Corrente")

    # Distanza
    distanza_km = models.FloatField(null=True, blank=True, verbose_name="Distanza km")

    note = models.TextField(blank=True)

    def __str__(self):
        data = self.assegnazione_originale.turno.data
        return f"Sost. {self.dipendente_assente} → {self.sostituto or '?'} ({data}) [{self.stato}]"

    class Meta:
        verbose_name = "Richiesta Sostituzione"
        verbose_name_plural = "Richieste Sostituzione"
        ordering = ['-creata_il']


class ModificaCedolino(models.Model):
    """
    Rettifiche manuali apportate dall'amministrazione alle ore e giornate
    nell'elaborazione dei cedolini paghe per un determinato periodo.
    """
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='modifiche_cedolino')
    data_inizio = models.DateField(verbose_name="Data Inizio Periodo")
    data_fine = models.DateField(verbose_name="Data Fine Periodo")
    giorni_lavorati_override = models.IntegerField(null=True, blank=True, verbose_name="Giorni Lavorati Rettificati")
    ore_lavorate_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Ore Totali Rettificate")
    ore_validate_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Ore Validate Rettificate")
    giorni_ferie_override = models.IntegerField(null=True, blank=True, verbose_name="Giorni Ferie Rettificati")
    giorni_permesso_override = models.IntegerField(null=True, blank=True, verbose_name="Giorni Permesso Rettificati")
    giorni_malattia_override = models.IntegerField(null=True, blank=True, verbose_name="Giorni Malattia Rettificati")
    giorni_104_override = models.IntegerField(null=True, blank=True, verbose_name="Giorni 104 Rettificati")
    note = models.TextField(blank=True, verbose_name="Motivazione / Note Rettifica")
    modificato_da = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Modificato da")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.data_inizio and self.data_fine and self.data_fine < self.data_inizio:
            raise ValidationError({'data_fine': "La data di fine periodo non può essere precedente alla data di inizio."})

    class Meta:
        verbose_name = "Modifica / Rettifica Cedolino"
        verbose_name_plural = "Modifiche / Rettifiche Cedolino"
        unique_together = ('dipendente', 'data_inizio', 'data_fine')

    def __str__(self):
        return f"Rettifica Cedolino — {self.dipendente} ({self.data_inizio} - {self.data_fine})"


DEFAULT_CORSI_FORMAZIONE = [
    (1, "Corso sicurezza generale", 5),
    (2, "Corso Specifico Basso Rischio", 5),
    (3, "Corso Movimentazione manuale carichi", 5),
    (4, "Corso DPI 3 lavori in quota", 5),
    (5, "Corso RLS", 3),
    (6, "Corso preposto", 2),
    (7, "Corso primo soccorso", 3),
    (8, "Corso piattaforme mobili con o senza stabilizzatori", 5),
    (9, "Corso HACCP", 2),
    (10, "Corso antincendio livello 2", 5),
]


def calcola_data_scadenza_corso(data_esecuzione, durata_anni):
    """Calcola automaticamente la data di scadenza sommando gli anni di durata alla data di esecuzione."""
    if not data_esecuzione or not durata_anni or durata_anni <= 0:
        return None
    try:
        return data_esecuzione.replace(year=data_esecuzione.year + int(durata_anni))
    except ValueError:
        # Gestione 29 febbraio su anno non bisestile -> 28 febbraio
        return data_esecuzione.replace(year=data_esecuzione.year + int(durata_anni), day=28)


class CorsoFormazione(models.Model):
    nome = models.CharField(max_length=200, unique=True, verbose_name="Nome Corso")
    durata_anni = models.PositiveIntegerField(
        default=5,
        verbose_name="Durata (anni)",
        help_text="Durata di validità del corso in anni (calcola automaticamente la data di scadenza)",
    )
    descrizione = models.TextField(blank=True, verbose_name="Descrizione / Note")
    ordine = models.PositiveIntegerField(default=100, verbose_name="Ordine")
    attivo = models.BooleanField(default=True, verbose_name="Attivo")

    def __str__(self):
        unita = "anno" if self.durata_anni == 1 else "anni"
        return f"{self.nome} ({self.durata_anni} {unita})"

    class Meta:
        verbose_name = "Corso di Formazione"
        verbose_name_plural = "Corsi di Formazione"
        ordering = ['ordine', 'nome']


class CorsoDipendente(models.Model):
    STATO_CHOICES = [
        ('NON_PREVISTO', '— Seleziona (Fatto / Deve essere fatto) —'),
        ('DA_FARE', '⏳ Deve essere fatto'),
        ('FATTO', '✅ Fatto'),
    ]

    dipendente = models.ForeignKey(
        Dipendente,
        on_delete=models.CASCADE,
        related_name='corsi_formazione',
        verbose_name="Dipendente",
    )
    corso = models.ForeignKey(
        CorsoFormazione,
        on_delete=models.CASCADE,
        related_name='dipendenti_iscritti',
        verbose_name="Corso di Formazione",
    )
    stato = models.CharField(
        max_length=20,
        choices=STATO_CHOICES,
        default='NON_PREVISTO',
        verbose_name="Stato (Fatto / Deve essere fatto)",
    )
    data_esecuzione = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data di Esecuzione",
    )
    data_scadenza = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data di Scadenza",
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Note",
    )

    class Meta:
        verbose_name = "Corso di Formazione"
        verbose_name_plural = "🎓 Corsi di Formazione"
        unique_together = ('dipendente', 'corso')
        ordering = ['corso__ordine', 'corso__nome']

    def _applica_calcolo_automatico(self):
        # Se il corso è FATTO e la data è stata inserita in data_scadenza con data_esecuzione vuota,
        # la usiamo come data_esecuzione e calcoliamo la scadenza dopo il periodo di validità
        if not self.data_esecuzione and self.data_scadenza and self.stato == 'FATTO':
            self.data_esecuzione = self.data_scadenza
        if self.data_esecuzione:
            if self.stato == 'NON_PREVISTO':
                self.stato = 'FATTO'
            if self.corso_id and self.corso and self.corso.durata_anni:
                self.data_scadenza = calcola_data_scadenza_corso(
                    self.data_esecuzione,
                    self.corso.durata_anni,
                )

    def clean(self):
        super().clean()
        self._applica_calcolo_automatico()

    def save(self, *args, **kwargs):
        self._applica_calcolo_automatico()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dipendente} - {self.corso} ({self.get_stato_display()})"


def ensure_default_corsi_formazione():
    """Assicura che i 10 corsi di formazione standard siano presenti nel catalogo con la relativa durata."""
    try:
        for ordine, nome, durata_anni in DEFAULT_CORSI_FORMAZIONE:
            corso, created = CorsoFormazione.objects.get_or_create(
                nome=nome,
                defaults={'ordine': ordine, 'durata_anni': durata_anni, 'attivo': True}
            )
            if not created and corso.durata_anni != durata_anni:
                corso.durata_anni = durata_anni
                corso.save(update_fields=['durata_anni'])
    except Exception:
        pass


def ensure_corsi_per_dipendente(dipendente):
    """Assicura che il dipendente abbia una riga in tabella per ogni corso attivo nel catalogo."""
    if not dipendente or not dipendente.pk:
        return
    try:
        ensure_default_corsi_formazione()
        corsi_attivi = list(CorsoFormazione.objects.filter(attivo=True).order_by('ordine', 'nome'))
        esistenti_ids = set(
            CorsoDipendente.objects.filter(dipendente=dipendente).values_list('corso_id', flat=True)
        )
        nuovi = [
            CorsoDipendente(dipendente=dipendente, corso=corso, stato='NON_PREVISTO')
            for corso in corsi_attivi
            if corso.id not in esistenti_ids
        ]
        if nuovi:
            CorsoDipendente.objects.bulk_create(nuovi, ignore_conflicts=True)
        # Allinea eventuali corsi già inseriti in precedenza (es. data inserita solo in data_scadenza su corso FATTO)
        for cd in CorsoDipendente.objects.filter(dipendente=dipendente).select_related('corso'):
            if cd.stato == 'FATTO' and not cd.data_esecuzione and cd.data_scadenza:
                cd.data_esecuzione = cd.data_scadenza
                cd.data_scadenza = calcola_data_scadenza_corso(cd.data_esecuzione, cd.corso.durata_anni)
                cd.save(update_fields=['data_esecuzione', 'data_scadenza'])
            elif cd.data_esecuzione and cd.corso and cd.corso.durata_anni:
                attesa = calcola_data_scadenza_corso(cd.data_esecuzione, cd.corso.durata_anni)
                if attesa and cd.data_scadenza != attesa:
                    cd.data_scadenza = attesa
                    cd.save(update_fields=['data_scadenza'])
    except Exception:
        pass


# ==============================================================================
# GESTIONE PROCEDURE OPERATIVE E CHECKLIST (es. Disdetta Contratto, ecc.)
# ==============================================================================

DEFAULT_PROCEDURE = [
    {
        'nome': 'Disdetta di un contratto',
        'categoria': 'CONTRATTO_CLIENTE',
        'descrizione': 'Procedura standard per la gestione completa della disdetta di un contratto cliente.',
        'ordine': 1,
        'passaggi': [
            (1, 'Invio disdetta', 'Verifica o invio formale della comunicazione di disdetta contrattuale'),
            (2, 'Avviso degli operatori addetti', 'Comunicare la cessazione del servizio alle squadre e agli operatori assegnati'),
            (3, 'Recupero oggetti presso il cliente', 'Ritirare macchinari, prodotti, attrezzature e materiali lasciati in cantiere'),
            (4, 'Consegna chiavi o telecomandi', 'Riconsegnare al cliente o referente tutte le chiavi, badge o telecomandi in possesso'),
            (5, 'Invio ultima fattura', 'Emettere e inviare la fattura di chiusura/conguaglio finale'),
            (6, 'Aggiornare il database', 'Impostare la data di fine contratto nelle programmazioni ricorrenti e aggiornare l\'anagrafica'),
        ],
    },
    {
        'nome': 'Attivazione Nuovo Cantiere',
        'categoria': 'CONTRATTO_CLIENTE',
        'descrizione': 'Procedura standard di avvio operativo per un nuovo cliente/cantiere acquisito.',
        'ordine': 2,
        'passaggi': [
            (1, 'Sopralluogo tecnico e ritiro chiavi/codici allarme', 'Ritirare chiavi, badge, telecomandi e istruzioni di accesso/allarme dal referente'),
            (2, 'Prima fornitura prodotti, materiali e dotazioni in cantiere', 'Consegnare detergenti, sacchi, panni, carrello e macchinari registrandoli in Magazzino & Dotazioni'),
            (3, 'Assegnazione squadra abituale e briefing mansioni', 'Formare gli operatori sulle specifiche del capitolato e orari concordati'),
            (4, 'Stampa ed esposizione QR Code Cantiere', 'Posizionare il QR Code nel locale tecnico/ripostiglio per timbrature e ispezioni qualità'),
            (5, 'Controllo qualità 1ª settimana (Verbale Ispezione)', 'Effettuare la prima ispezione qualità Responsabile Area e verificare il feedback del cliente'),
        ],
    },
]


class ModelloProcedura(models.Model):
    CATEGORIA_CHOICES = [
        ('CONTRATTO_CLIENTE', '🏢 Contratto / Cliente'),
        ('DIPENDENTE', '👤 Personale / Dipendente'),
        ('MEZZO', '🚐 Mezzi / Attrezzature'),
        ('GENERALE', '📋 Amministrazione / Generale'),
    ]

    nome = models.CharField(max_length=200, unique=True, verbose_name="Nome Procedura")
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        default='CONTRATTO_CLIENTE',
        verbose_name="Categoria",
    )
    descrizione = models.TextField(blank=True, verbose_name="Descrizione / Istruzioni")
    ordine = models.PositiveIntegerField(default=10, verbose_name="Ordine")
    attivo = models.BooleanField(default=True, verbose_name="Attiva")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Modello Procedura"
        verbose_name_plural = "Modelli Procedure"
        ordering = ['ordine', 'nome']

    def __str__(self):
        return self.nome

    def riordina_passaggi(self):
        """Rinumera in modo progressivo (1, 2, 3...) i passaggi del modello."""
        for idx, passo in enumerate(self.passaggi.order_by('ordine', 'id'), start=1):
            if passo.ordine != idx:
                PassoModelloProcedura.objects.filter(pk=passo.pk).update(ordine=idx)


class PassoModelloProcedura(models.Model):
    modello = models.ForeignKey(
        ModelloProcedura,
        on_delete=models.CASCADE,
        related_name='passaggi',
        verbose_name="Modello Procedura",
    )
    ordine = models.PositiveIntegerField(default=1, verbose_name="N° Punto")
    titolo = models.CharField(max_length=255, verbose_name="Passaggio / Punto")
    descrizione = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Dettagli / Note Operative",
    )
    obbligatorio = models.BooleanField(default=True, verbose_name="Obbligatorio")
    incaricati_default = models.ManyToManyField(
        Dipendente,
        blank=True,
        related_name='passi_modello_incaricato',
        verbose_name="Colleghi per Avvallo / Incarico (Default)",
    )

    class Meta:
        verbose_name = "Punto del Modello Procedura"
        verbose_name_plural = "Punti del Modello Procedura"
        ordering = ['ordine', 'id']

    def __str__(self):
        return f"{self.ordine}) {self.titolo}"


class ProceduraAvviata(models.Model):
    STATO_CHOICES = [
        ('IN_CORSO', '⏳ In Corso'),
        ('COMPLETATA', '✅ Completata'),
        ('ANNULLATA', '❌ Annullata'),
    ]

    modello = models.ForeignKey(
        ModelloProcedura,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedure_avviate',
        verbose_name="Procedura",
    )
    titolo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Titolo / Riferimento Pratica",
        help_text="Se lasciato vuoto viene generato automaticamente dal nome della procedura e dal cliente/dipendente.",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedure',
        verbose_name="Cliente",
    )
    dipendente = models.ForeignKey(
        Dipendente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procedure',
        verbose_name="Dipendente (opzionale)",
    )
    stato = models.CharField(
        max_length=20,
        choices=STATO_CHOICES,
        default='IN_CORSO',
        verbose_name="Stato",
    )
    data_avvio = models.DateField(verbose_name="Data Avvio")
    data_scadenza = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Scadenza / Termine Previsto",
    )
    data_completamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completata il",
    )
    note = models.TextField(blank=True, verbose_name="Note Pratica")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Procedura Avviata"
        verbose_name_plural = "Procedure Avviate (Pratiche)"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.data_avvio:
            self.data_avvio = timezone.now().date()
        if not self.titolo or not self.titolo.strip():
            base = self.modello.nome if self.modello else "Procedura Operativa"
            target = ""
            if self.cliente:
                target = f" — {self.cliente.ragione_sociale}"
            elif self.dipendente:
                target = f" — {self.dipendente.cognome} {self.dipendente.nome}"
            self.titolo = f"{base}{target}"
        super().save(*args, **kwargs)

    @property
    def totale_passaggi(self):
        return self.passaggi.count()

    @property
    def passaggi_completati(self):
        return self.passaggi.filter(completato=True).count()

    @property
    def percentuale_completamento(self):
        tot = self.totale_passaggi
        if tot == 0:
            return 100 if self.stato == 'COMPLETATA' else 0
        return int(round((self.passaggi_completati / tot) * 100))

    def copia_passaggi_da_modello(self):
        """Copia i passaggi dal modello associato se la pratica non ha ancora passaggi."""
        if not self.pk or not self.modello_id:
            return 0
        if self.passaggi.exists():
            return 0
        passi_modello = list(self.modello.passaggi.prefetch_related('incaricati_default').order_by('ordine', 'id'))
        is_disdetta = 'disdetta' in (self.modello.nome or '').lower()
        dotazioni_str = ''
        if is_disdetta and self.cliente_id:
            try:
                dotazioni_qs = list(DotazioneCantiere.objects.filter(
                    cliente_id=self.cliente_id,
                    stato__in=['IN_CANTIERE', 'DA_RITIRARE', 'IN_MANUTENZIONE'],
                ))
                if dotazioni_qs:
                    DotazioneCantiere.objects.filter(
                        cliente_id=self.cliente_id,
                        stato='IN_CANTIERE',
                    ).update(stato='DA_RITIRARE')
                    items_txt = ", ".join(f"{d.quantita}x {d.descrizione}" + (f" ({d.matricola_codice})" if d.matricola_codice else "") for d in dotazioni_qs)
                    dotazioni_str = f" [📦 Dotazioni cantiere da ritirare: {items_txt}]"
            except Exception:
                pass

        creati = 0
        for idx, pm in enumerate(passi_modello, start=1):
            inc_list = list(pm.incaricati_default.all())
            desc_passo = pm.descrizione or ''
            if dotazioni_str and ('recupero oggetti' in (pm.titolo or '').lower() or idx == 3):
                desc_passo = (desc_passo + dotazioni_str)[:500]
            passo_avviato = PassoProceduraAvviata.objects.create(
                procedura=self,
                ordine=idx,
                titolo=pm.titolo,
                descrizione=desc_passo,
                completato=False,
                richiede_avvallo=bool(inc_list),
                bloccante=True,
            )
            creati += 1
            for dip_inc in inc_list:
                AvvalloPassoProcedura.objects.get_or_create(
                    passo=passo_avviato,
                    dipendente=dip_inc,
                    defaults={
                        'richiesto_da': self.dipendente,
                        'stato': 'IN_ATTESA',
                    }
                )
        return creati

    def riordina_passaggi(self):
        """Rinumera in modo progressivo (1, 2, 3...) i punti della pratica."""
        for idx, passo in enumerate(self.passaggi.order_by('ordine', 'id'), start=1):
            if passo.ordine != idx:
                PassoProceduraAvviata.objects.filter(pk=passo.pk).update(ordine=idx)

    def ricalcola_stato(self):
        """Aggiorna automaticamente lo stato in base ai punti completati."""
        from django.utils import timezone
        if self.stato == 'ANNULLATA':
            return
        tot = self.totale_passaggi
        comp = self.passaggi_completati
        if tot > 0 and comp == tot:
            if self.stato != 'COMPLETATA':
                self.stato = 'COMPLETATA'
                self.data_completamento = timezone.now()
                ProceduraAvviata.objects.filter(pk=self.pk).update(
                    stato='COMPLETATA',
                    data_completamento=self.data_completamento,
                )
        else:
            if self.stato == 'COMPLETATA':
                self.stato = 'IN_CORSO'
                self.data_completamento = None
                ProceduraAvviata.objects.filter(pk=self.pk).update(
                    stato='IN_CORSO',
                    data_completamento=None,
                )

    def __str__(self):
        return f"{self.titolo} ({self.passaggi_completati}/{self.totale_passaggi})"


class PassoProceduraAvviata(models.Model):
    procedura = models.ForeignKey(
        ProceduraAvviata,
        on_delete=models.CASCADE,
        related_name='passaggi',
        verbose_name="Procedura",
    )
    ordine = models.PositiveIntegerField(default=1, verbose_name="N° Punto")
    titolo = models.CharField(max_length=255, verbose_name="Passaggio / Punto")
    descrizione = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Dettagli / Istruzioni",
    )
    completato = models.BooleanField(default=False, verbose_name="Completato")
    data_completamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completato il",
    )
    note_esecuzione = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Note / Esito",
    )
    richiede_avvallo = models.BooleanField(
        default=False,
        verbose_name="Richiede Avvallo / Incarico Colleghi",
    )
    bloccante = models.BooleanField(
        default=True,
        verbose_name="Blocca passaggi successivi fino all'OK",
    )

    class Meta:
        verbose_name = "Punto della Procedura"
        verbose_name_plural = "Checklist Passaggi della Procedura"
        ordering = ['ordine', 'id']

    @property
    def ha_avvalli_in_attesa(self):
        return self.avvalli.filter(stato='IN_ATTESA').exists()

    @property
    def tutti_avvalli_approvati(self):
        qs = list(self.avvalli.all())
        return bool(qs) and all(a.stato == 'APPROVATO' for a in qs)

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.completato and not self.data_completamento:
            self.data_completamento = timezone.now()
        elif not self.completato:
            self.data_completamento = None
        super().save(*args, **kwargs)
        if self.procedura_id:
            self.procedura.ricalcola_stato()

    def __str__(self):
        check = "✅" if self.completato else "⬜"
        return f"{check} {self.ordine}) {self.titolo}"


class AvvalloPassoProcedura(models.Model):
    STATO_CHOICES = [
        ('IN_ATTESA', '⏳ In attesa di OK'),
        ('APPROVATO', '✅ OK / Avvallato'),
        ('RIFIUTATO', '❌ Rifiutato / Da rivedere'),
    ]

    passo = models.ForeignKey(
        PassoProceduraAvviata,
        on_delete=models.CASCADE,
        related_name='avvalli',
        verbose_name="Passaggio Procedura",
    )
    dipendente = models.ForeignKey(
        Dipendente,
        on_delete=models.CASCADE,
        related_name='avvalli_procedure',
        verbose_name="Collega Incaricato / Avvallante",
    )
    richiesto_da = models.ForeignKey(
        Dipendente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avvalli_richiesti',
        verbose_name="Richiesto da (Responsabile)",
    )
    stato = models.CharField(
        max_length=20,
        choices=STATO_CHOICES,
        default='IN_ATTESA',
        verbose_name="Stato Avvallo",
    )
    nota_richiesta = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Dettaglio / Messaggio Richiesta",
    )
    nota_risposta = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Nota Risposta / OK",
    )
    notifica_telegram_inviata = models.BooleanField(
        default=False,
        verbose_name="Notifica Telegram Inviata",
    )
    letto_da_responsabile = models.BooleanField(
        default=False,
        verbose_name="Esito visto dal Responsabile",
    )
    data_richiesta = models.DateTimeField(auto_now_add=True, verbose_name="Richiesto il")
    data_risposta = models.DateTimeField(null=True, blank=True, verbose_name="Risposto il")

    class Meta:
        verbose_name = "Avvallo / Incarico Passaggio Procedura"
        verbose_name_plural = "Avvalli / Incarichi Passaggi Procedure"
        unique_together = ('passo', 'dipendente')
        ordering = ['id']

    def __str__(self):
        return f"{self.passo} — {self.dipendente} ({self.get_stato_display()})"


def ensure_default_procedure():
    """
    Assicura che le procedure predefinite (es. 'Disdetta di un contratto' coi suoi 6 passaggi)
    siano presenti nel database. Non sovrascrive eventuali modifiche/aggiunte/rimozioni
    apportate dall'utente se il modello esiste già.
    """
    try:
        for p_def in DEFAULT_PROCEDURE:
            modello, created = ModelloProcedura.objects.get_or_create(
                nome=p_def['nome'],
                defaults={
                    'categoria': p_def.get('categoria', 'CONTRATTO_CLIENTE'),
                    'descrizione': p_def.get('descrizione', ''),
                    'ordine': p_def.get('ordine', 1),
                    'attivo': True,
                }
            )
            if created:
                passi = [
                    PassoModelloProcedura(
                        modello=modello,
                        ordine=ordine,
                        titolo=titolo,
                        descrizione=desc,
                        obbligatorio=True,
                    )
                    for ordine, titolo, desc in p_def.get('passaggi', [])
                ]
                if passi:
                    PassoModelloProcedura.objects.bulk_create(passi)
    except Exception:
        pass





# ==============================================================================
# GESTIONE BUSTE PAGA AUTOMATICHE (Split PDF per Codice Fiscale + Invio Telegram/WhatsApp)
# ==============================================================================

class LottoBustePaga(models.Model):
    """
    Lotto mensile caricato dall'amministrazione contenente il PDF unico
    delle buste paga inviato dal commercialista (es. Libro Unico Zucchetti).
    """
    titolo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Titolo / Riferimento",
        help_text="Generato automaticamente dal periodo rilevato se lasciato vuoto",
    )
    periodo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Periodo di Retribuzione",
        help_text="Es. Settembre 2026",
    )
    file_originale = models.FileField(
        upload_to='buste_paga/lotti/',
        verbose_name="PDF Unico Commercialista",
    )
    file_riepilogo = models.FileField(
        upload_to='buste_paga/riepiloghi/',
        null=True,
        blank=True,
        verbose_name="PDF Riepilogo Generale",
    )
    totale_pagine = models.PositiveIntegerField(default=0, verbose_name="Totale Pagine PDF")
    totale_cedolini = models.PositiveIntegerField(default=0, verbose_name="Cedolini Estratti (CF)")
    pagine_riepilogo = models.PositiveIntegerField(default=0, verbose_name="Pagine Riepilogo")
    note = models.TextField(blank=True, verbose_name="Note")
    caricato_da = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Caricato da",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data Caricamento")

    class Meta:
        verbose_name = "Lotto Buste Paga"
        verbose_name_plural = "Lotti Buste Paga"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.titolo or not self.titolo.strip():
            per = (self.periodo or '').strip() or timezone.now().strftime('%m/%Y')
            self.titolo = f"Buste Paga — {per}"
        super().save(*args, **kwargs)

    @property
    def cedolini_associati_count(self):
        return self.cedolini.filter(dipendente__isnull=False).count()

    @property
    def inviati_telegram_count(self):
        return self.cedolini.filter(inviato_telegram=True).count()

    @property
    def inviati_whatsapp_count(self):
        return self.cedolini.filter(inviato_whatsapp=True).count()

    def __str__(self):
        return f"{self.titolo} ({self.totale_cedolini} buste paga)"


class CedolinoDipendente(models.Model):
    """
    Singola busta paga PDF estratta per uno specifico Codice Fiscale
    dal file unico inviato dal commercialista.
    """
    lotto = models.ForeignKey(
        LottoBustePaga,
        on_delete=models.CASCADE,
        related_name='cedolini',
        verbose_name="Lotto Buste Paga",
    )
    dipendente = models.ForeignKey(
        Dipendente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='buste_paga',
        verbose_name="Dipendente Associato",
    )
    codice_fiscale = models.CharField(
        max_length=16,
        db_index=True,
        verbose_name="Codice Fiscale Rilevato",
    )
    nominativo_pdf = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nominativo sul Cedolino",
    )
    periodo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Periodo",
    )
    pagine_pdf = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Pagine nel PDF Originale",
    )
    numero_pagine = models.PositiveIntegerField(
        default=1,
        verbose_name="N° Pagine",
    )
    netto_mese = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Netto in Busta",
    )
    data_nascita_pdf = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Nascita (da PDF)",
    )
    data_assunzione_pdf = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data Assunzione (da PDF)",
    )
    file_pdf = models.FileField(
        upload_to='buste_paga/cedolini/',
        verbose_name="File PDF Busta Paga",
    )
    token_download = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Token Sicuro Download",
    )
    inviato_telegram = models.BooleanField(
        default=False,
        verbose_name="Inviato su Telegram",
    )
    data_invio_telegram = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Invio Telegram",
    )
    errore_telegram = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Note / Errore Telegram",
    )
    inviato_whatsapp = models.BooleanField(
        default=False,
        verbose_name="Inviato su WhatsApp",
    )
    data_invio_whatsapp = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Invio WhatsApp",
    )
    scaricato_dipendente = models.BooleanField(
        default=False,
        verbose_name="Scaricato dal Dipendente",
    )
    data_primo_scarico = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Primo Scarico",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Busta Paga Dipendente"
        verbose_name_plural = "Buste Paga Dipendenti"
        ordering = ['nominativo_pdf', 'codice_fiscale']

    def save(self, *args, **kwargs):
        import secrets
        if self.codice_fiscale:
            self.codice_fiscale = self.codice_fiscale.strip().upper()
        if not self.token_download:
            self.token_download = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self):
        nome = str(self.dipendente) if self.dipendente else (self.nominativo_pdf or self.codice_fiscale)
        return f"Busta Paga {self.periodo} — {nome} ({self.codice_fiscale})"


class ProfiloAccessoPortale(models.Model):
    """
    Configurazione dell'account di accesso al Portale Kandor e delle sezioni visibili.
    - Ruolo 'PROGRAMMATORE' (Serra Gian Carlo): visualizza sempre tutte le sezioni e gestisce i permessi dei Responsabili.
    - Ruolo 'RESPONSABILE': visualizza nel proprio accesso esclusivamente le sezioni abilitate dal Programmatore.
    """
    RUOLO_CHOICES = [
        ('PROGRAMMATORE', '💻 Programmatore / Super-Admin (Accesso Totale)'),
        ('RESPONSABILE', '👔 Responsabile / Operatore (Sezioni Personalizzate)'),
    ]

    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='profilo_accesso_portale',
        verbose_name="Utente di Accesso Django",
    )
    dipendente = models.OneToOneField(
        'Dipendente',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profilo_accesso_portale',
        verbose_name="Dipendente / Responsabile Collegato",
    )
    ruolo = models.CharField(
        max_length=30,
        choices=RUOLO_CHOICES,
        default='RESPONSABILE',
        verbose_name="Ruolo nel Portale",
    )
    password_visibile = models.CharField(
        max_length=120,
        blank=True,
        default='',
        verbose_name="Password Assegnata (Visibile al Programmatore)",
    )
    sezioni_abilitate = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Codici Sezioni Abilitate",
    )
    attivo = models.BooleanField(
        default=True,
        verbose_name="Accesso Attivo",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profilo Accesso & Sezioni Responsabile"
        verbose_name_plural = "Profili Accesso & Sezioni Responsabili"
        ordering = ['ruolo', 'user__username']

    def is_programmatore(self):
        return self.ruolo == 'PROGRAMMATORE'

    def __str__(self):
        label_dip = f"{self.dipendente.nome} {self.dipendente.cognome}" if self.dipendente else self.user.username
        return f"{label_dip} ({self.get_ruolo_display()}) — @{self.user.username}"


# ==============================================================================
# 1 & 2. MAGAZZINO PRODOTTI, DOTAZIONI MACCHINARI CANTIERE & CONSEGNE (MOL)
# ==============================================================================

class ProdottoMagazzino(models.Model):
    CATEGORIA_CHOICES = [
        ('DETERGENTE', '🧴 Detergente / Chimico'),
        ('CONSUMABILE', '🧻 Carta / Sacchi / Consumabile'),
        ('ATTREZZATURA', '🧹 Panni / Mop / Attrezzatura Minuta'),
        ('DPI', '🧤 Guanti / DPI Sicurezza'),
        ('MACCHINARIO', '⚙️ Macchinario / Ricambio'),
    ]

    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome Prodotto / Articolo")
    codice = models.CharField(max_length=50, blank=True, default='', verbose_name="Codice Articolo")
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES, default='DETERGENTE', verbose_name="Categoria")
    unita_misura = models.CharField(max_length=30, default='pz', verbose_name="Unità di Misura (pz, flaconi, cartoni, taniche)")
    costo_unitario = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00,
        verbose_name="Costo Unitario d'Acquisto (€)",
        help_text="Utilizzato per calcolare automaticamente il costo materiali consegnati nel MOL Cantiere",
    )
    giacenza_attuale = models.DecimalField(max_digits=8, decimal_places=1, default=0.0, verbose_name="Giacenza in Magazzino")
    scorta_minima = models.DecimalField(max_digits=8, decimal_places=1, default=5.0, verbose_name="Scorta Minima Alert")
    fornitore_abituale = models.CharField(max_length=150, blank=True, default='', verbose_name="Fornitore Abituale")
    attivo = models.BooleanField(default=True, verbose_name="Attivo")

    class Meta:
        verbose_name = "Prodotto di Magazzino"
        verbose_name_plural = "Prodotti di Magazzino"
        ordering = ['categoria', 'nome']

    @property
    def sotto_scorta(self):
        return self.giacenza_attuale <= self.scorta_minima

    def __str__(self):
        return f"{self.nome} (€{self.costo_unitario}/{self.unita_misura})"


DEFAULT_PRODOTTI_MAGAZZINO = [
    ("Detergente Pavimenti Universale 5L", "DET-001", "DETERGENTE", "tanica", Decimal("12.50"), Decimal("20"), Decimal("5")),
    ("Sgrassatore Multiuso Professionale 750ml", "DET-002", "DETERGENTE", "flacone", Decimal("2.80"), Decimal("36"), Decimal("10")),
    ("Disincrostante Bagni / Anticalcare 1L", "DET-003", "DETERGENTE", "flacone", Decimal("3.20"), Decimal("24"), Decimal("8")),
    ("Detergente Vetri e Specchi 750ml", "DET-004", "DETERGENTE", "flacone", Decimal("2.40"), Decimal("30"), Decimal("8")),
    ("Sacchi Neri Condominio 70x110 (rotolo)", "CON-001", "CONSUMABILE", "rotolo", Decimal("3.50"), Decimal("50"), Decimal("15")),
    ("Sacchi Cestini Ufficio 50x60 (rotolo)", "CON-002", "CONSUMABILE", "rotolo", Decimal("1.90"), Decimal("60"), Decimal("15")),
    ("Bobina Carta Asciugatutto Industriale", "CON-003", "CONSUMABILE", "rotolo", Decimal("6.80"), Decimal("24"), Decimal("6")),
    ("Carta Igienica Conf. 12 rotoli", "CON-004", "CONSUMABILE", "conf", Decimal("4.90"), Decimal("30"), Decimal("8")),
    ("Sapone Mani Liquido 5L", "CON-005", "CONSUMABILE", "tanica", Decimal("9.50"), Decimal("12"), Decimal("4")),
    ("Panni Microfibra Colorati (conf. 5 pz)", "ATT-001", "ATTREZZATURA", "conf", Decimal("5.50"), Decimal("25"), Decimal("6")),
    ("Frangia Mop Cotone/Microfibra", "ATT-002", "ATTREZZATURA", "pz", Decimal("4.20"), Decimal("20"), Decimal("5")),
    ("Guanti Nitrile Monouso (box 100 pz)", "DPI-001", "DPI", "box", Decimal("6.90"), Decimal("20"), Decimal("5")),
]


def ensure_default_prodotti_magazzino():
    try:
        if ProdottoMagazzino.objects.exists():
            return
        items = [
            ProdottoMagazzino(
                nome=n, codice=c, categoria=cat, unita_misura=um,
                costo_unitario=cu, giacenza_attuale=giac, scorta_minima=scmin, attivo=True
            )
            for n, c, cat, um, cu, giac, scmin in DEFAULT_PRODOTTI_MAGAZZINO
        ]
        ProdottoMagazzino.objects.bulk_create(items, ignore_conflicts=True)
    except Exception:
        pass


class DotazioneCantiere(models.Model):
    """
    Inventario di macchinari, attrezzature fisse, carrelli, chiavi e badge assegnati a uno specifico Cliente/Cantiere.
    Collegato direttamente al Punto 3 ('Recupero oggetti presso il cliente') della procedura di Disdetta Contratto.
    """
    TIPO_CHOICES = [
        ('MACCHINARIO', '⚙️ Macchinario (Lavasciuga, Monospazzola, Aspiratore)'),
        ('CARRELLO', '🛒 Carrello Pulizie / Attrezzatura Fissa'),
        ('SCALA', '🪜 Scala / Trabattello / Asta Telescopica'),
        ('CHIAVI_BADGE', '🔑 Chiavi / Telecomando / Badge Accesso'),
        ('DISPENSER', '🧻 Dispenser / Distributore in Comodato'),
        ('ALTRO', '📦 Altra Dotazione Cantiere'),
    ]
    STATO_CHOICES = [
        ('IN_CANTIERE', '🟢 Presente in Cantiere'),
        ('IN_MANUTENZIONE', '🟠 In Riparazione / Manutenzione'),
        ('DA_RITIRARE', '🔴 Da Recuperare (Fine Contratto / Disdetta)'),
        ('RITIRATO', '✅ Recuperato in Sede'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='dotazioni_cantiere', verbose_name="Cliente / Cantiere")
    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES, default='MACCHINARIO', verbose_name="Tipologia")
    descrizione = models.CharField(max_length=200, verbose_name="Modello / Descrizione Oggetto")
    matricola_codice = models.CharField(max_length=100, blank=True, default='', verbose_name="Matricola / Seriale / Rif.")
    quantita = models.PositiveIntegerField(default=1, verbose_name="Quantità")
    valore_stimato = models.DecimalField(max_digits=9, decimal_places=2, default=0.00, verbose_name="Valore Inventariale (€)")
    data_consegna = models.DateField(null=True, blank=True, verbose_name="Data Consegna in Cantiere")
    data_ritiro = models.DateField(null=True, blank=True, verbose_name="Data Ritiro da Cantiere")
    stato = models.CharField(max_length=25, choices=STATO_CHOICES, default='IN_CANTIERE', verbose_name="Stato Attuale")
    note = models.CharField(max_length=300, blank=True, default='', verbose_name="Note / Ubicazione (es. Sgabuzzino piano -1)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dotazione / Macchinario Cantiere"
        verbose_name_plural = "Dotazioni & Macchinari Cantiere"
        ordering = ['cliente__ragione_sociale', 'tipo', 'descrizione']

    def __str__(self):
        return f"{self.descrizione} ({self.cliente.ragione_sociale}) — {self.get_stato_display()}"


class ConsegnaRichiestaMateriale(models.Model):
    """
    Traccia sia le Richieste di Materiali inviate dagli operatori (da App Dipendenti / Telegram)
    sia le Consegne effettive in cantiere (che scaricano il magazzino e alimentano il costo materiali nel MOL).
    """
    STATO_CHOICES = [
        ('RICHIESTA', '🔔 Richiesto da Operatore (Da Preparare)'),
        ('IN_CONSEGNA', '🚐 In Consegna al Caposquadra'),
        ('CONSEGNATO', '✅ Consegnato in Cantiere (Contabilizzato nel MOL)'),
        ('ANNULLATO', '❌ Annullato'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='consegne_materiali', verbose_name="Cliente / Cantiere")
    prodotto = models.ForeignKey(
        ProdottoMagazzino, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='consegne', verbose_name="Prodotto di Magazzino"
    )
    descrizione_libera = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Articolo / Nota Prodotto (se fuori catalogo)",
    )
    quantita = models.DecimalField(max_digits=7, decimal_places=1, default=1.0, verbose_name="Quantità")
    costo_unitario_applicato = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, verbose_name="Costo Unitario (€)")
    costo_totale = models.DecimalField(max_digits=9, decimal_places=2, default=0.00, verbose_name="Costo Totale (€)")
    richiesto_da = models.ForeignKey(
        Dipendente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='richieste_materiali_inviate', verbose_name="Richiesto da (Operatore)"
    )
    consegnato_da = models.ForeignKey(
        Dipendente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='consegne_materiali_effettuate', verbose_name="Consegnato da"
    )
    stato = models.CharField(max_length=20, choices=STATO_CHOICES, default='RICHIESTA', verbose_name="Stato")
    urgenza = models.CharField(
        max_length=15,
        choices=[('NORMALE', 'Normale'), ('URGENTE', 'Urgente (Scorta Finita)')],
        default='NORMALE',
        verbose_name="Urgenza",
    )
    data_richiesta = models.DateField(verbose_name="Data Richiesta")
    data_consegna = models.DateField(null=True, blank=True, verbose_name="Data Consegna Effettiva")
    scaricato_magazzino = models.BooleanField(default=False, editable=False)
    note = models.CharField(max_length=300, blank=True, default='', verbose_name="Note")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Richiesta / Consegna Materiale Cantiere"
        verbose_name_plural = "Richieste & Consegne Materiali Cantiere"
        ordering = ['-data_richiesta', '-id']

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.data_richiesta:
            self.data_richiesta = timezone.now().date()
        if self.prodotto and (not self.costo_unitario_applicato or self.costo_unitario_applicato == 0):
            self.costo_unitario_applicato = self.prodotto.costo_unitario
        if self.prodotto and not self.descrizione_libera:
            self.descrizione_libera = self.prodotto.nome
        self.costo_totale = round(Decimal(str(self.quantita or 0)) * Decimal(str(self.costo_unitario_applicato or 0)), 2)
        if self.stato == 'CONSEGNATO' and not self.data_consegna:
            self.data_consegna = timezone.now().date()
        if self.stato == 'CONSEGNATO' and not self.scaricato_magazzino and self.prodotto_id:
            ProdottoMagazzino.objects.filter(pk=self.prodotto_id).update(
                giacenza_attuale=models.F('giacenza_attuale') - Decimal(str(self.quantita or 0))
            )
            self.scaricato_magazzino = True
        super().save(*args, **kwargs)

    def __str__(self):
        art = self.prodotto.nome if self.prodotto else self.descrizione_libera
        return f"{art} x{self.quantita:g} → {self.cliente.ragione_sociale} [{self.get_stato_display()}]"


# ==============================================================================
# 3. QUALITÀ, ISPEZIONI CANTIERE (SLA CLIENTE) & TIMBRATURA GEOFENCE / QR
# ==============================================================================

class IspezioneQualitaCantiere(models.Model):
    """
    Verbale di Sopralluogo / Controllo Qualità compilato dal Responsabile Area o Titolare
    con voti 1-5 stelle per ambiente, foto prima/dopo, firma e generazione PDF di cortesia per il cliente.
    """
    ESITO_CHOICES = [
        ('ECCELLENTE', '🌟 Eccellente (SLA Pienamente Rispettato)'),
        ('CONFORME', '✅ Conforme (Standard Regolare)'),
        ('DA_MIGLIORARE', '🟠 Da Migliorare (Richiamo Operativo Squadra)'),
        ('NON_CONFORME', '🔴 Non Conforme (Intervento Correttivo Urgente)'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='ispezioni_qualita', verbose_name="Cliente / Cantiere")
    ispettore = models.ForeignKey(
        Dipendente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ispezioni_effettuate', verbose_name="Responsabile / Ispettore"
    )
    squadra_valutata = models.ForeignKey(
        Squadra, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ispezioni_qualita', verbose_name="Squadra Valutata"
    )
    data_ispezione = models.DateTimeField(verbose_name="Data e Ora Sopralluogo")
    voto_ingressi_scale = models.PositiveSmallIntegerField(default=5, verbose_name="Voto Ingressi / Parti Comuni / Scale (1-5)")
    voto_uffici_postazioni = models.PositiveSmallIntegerField(default=5, verbose_name="Voto Uffici / Pavimenti / Postazioni (1-5)")
    voto_bagni_sanitari = models.PositiveSmallIntegerField(default=5, verbose_name="Voto Bagni e Sanitari (1-5)")
    voto_vetrate_infissi = models.PositiveSmallIntegerField(default=5, verbose_name="Voto Vetrate / Specchi / Infissi (1-5)")
    voto_riordino_dotazioni = models.PositiveSmallIntegerField(default=5, verbose_name="Voto Locale Tecnico / Prodotti / Macchinari (1-5)")
    media_voto = models.DecimalField(max_digits=3, decimal_places=2, default=5.00, verbose_name="Media Qualità (su 5)")
    esito = models.CharField(max_length=20, choices=ESITO_CHOICES, default='ECCELLENTE', verbose_name="Esito Complessivo")
    note_interne_squadra = models.TextField(blank=True, default='', verbose_name="Note Tecniche per la Squadra (Interne)")
    messaggio_cortesia_cliente = models.TextField(
        blank=True, default='',
        verbose_name="Note di Cortesia per il Report PDF Cliente",
        help_text="Visibile nel verbale PDF inviabile al cliente per certificare il controllo qualità",
    )
    foto_1 = models.ImageField(upload_to='ispezioni/', null=True, blank=True, verbose_name="Foto Rilievo 1 (Prima / Ambiente)")
    foto_2 = models.ImageField(upload_to='ispezioni/', null=True, blank=True, verbose_name="Foto Rilievo 2 (Dopo / Dettaglio)")
    firma_referente_cliente = models.CharField(max_length=150, blank=True, default='', verbose_name="Referente Cliente Presente (Opzionale)")
    latitudine_rilievo = models.FloatField(null=True, blank=True, verbose_name="Latitudine GPS Sopralluogo")
    longitudine_rilievo = models.FloatField(null=True, blank=True, verbose_name="Longitudine GPS Sopralluogo")
    inviato_al_cliente = models.BooleanField(default=False, verbose_name="Verbale Inviato al Cliente")
    token_pubblico = models.CharField(max_length=48, unique=True, db_index=True, blank=True, verbose_name="Token Link Cortesia")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ispezione Qualità & SLA Cantiere"
        verbose_name_plural = "Ispezioni Qualità & SLA Cantieri"
        ordering = ['-data_ispezione', '-id']

    def save(self, *args, **kwargs):
        import secrets
        from django.utils import timezone
        if not self.data_ispezione:
            self.data_ispezione = timezone.now()
        if not self.token_pubblico:
            self.token_pubblico = secrets.token_urlsafe(18)
        voti = [
            int(self.voto_ingressi_scale or 5),
            int(self.voto_uffici_postazioni or 5),
            int(self.voto_bagni_sanitari or 5),
            int(self.voto_vetrate_infissi or 5),
            int(self.voto_riordino_dotazioni or 5),
        ]
        media = round(sum(voti) / len(voti), 2)
        self.media_voto = Decimal(str(media))
        if media >= 4.5:
            self.esito = 'ECCELLENTE'
        elif media >= 3.5:
            self.esito = 'CONFORME'
        elif media >= 2.5:
            self.esito = 'DA_MIGLIORARE'
        else:
            self.esito = 'NON_CONFORME'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ispezione {self.cliente.ragione_sociale} ({self.data_ispezione.strftime('%d/%m/%Y')}) — ⭐ {self.media_voto}/5"


# ==============================================================================
# 4. MODULO PREVENTIVAZIONE RAPIDA (CRM COMMERCIALE) & CONVERSIONE 1-CLICK
# ==============================================================================

class PreventivoCommerciale(models.Model):
    """
    Configuratore Sopralluoghi & Preventivi per potenziali clienti (o nuove sedi):
    calcola automaticamente monte ore mensile da m² e resa oraria (m²/h), costo vivo
    (manodopera + prodotti + mezzi) e canone mensile consigliato col margine target,
    con generazione PDF professionale e conversione '1-Click' in Cliente Attivo.
    """
    STATO_CHOICES = [
        ('BOZZA', '📝 Bozza / Sopralluogo'),
        ('INVIATO', '📨 Preventivo Inviato al Cliente'),
        ('ACCETTATO', '✅ Accettato (Convertito in Cliente)'),
        ('RIFIUTATO', '❌ Non Accettato / Archiviato'),
    ]

    numero_preventivo = models.CharField(max_length=40, unique=True, blank=True, verbose_name="N° Preventivo")
    ragione_sociale_prospect = models.CharField(max_length=200, verbose_name="Ragione Sociale / Condominio")
    partita_iva = models.CharField(max_length=20, blank=True, default='', verbose_name="Partita IVA")
    codice_fiscale = models.CharField(max_length=16, blank=True, default='', verbose_name="Codice Fiscale")
    indirizzo_cantiere = models.CharField(max_length=255, verbose_name="Indirizzo Sede / Cantiere")
    referente_nome = models.CharField(max_length=120, blank=True, default='', verbose_name="Referente / Amministratore")
    referente_contatto = models.CharField(max_length=120, blank=True, default='', verbose_name="Email / Telefono Referente")

    # Parametri economici del configuratore
    costo_orario_applicato = models.DecimalField(max_digits=6, decimal_places=2, default=16.50, verbose_name="Costo Orario Aziendale Stimato (€/h)")
    incidenza_prodotti_perc = models.DecimalField(max_digits=5, decimal_places=2, default=6.00, verbose_name="Incidenza Prodotti/Attrezzature (%)")
    quota_fissa_mezzi_mensile = models.DecimalField(max_digits=7, decimal_places=2, default=25.00, verbose_name="Quota Mensile Trasferta/Mezzi (€)")
    margine_target_perc = models.DecimalField(max_digits=5, decimal_places=2, default=28.00, verbose_name="Margine Operativo Target (%)")

    # Totali calcolati
    totale_mq = models.DecimalField(max_digits=8, decimal_places=1, default=0.0, verbose_name="Totale Superficie (m²)")
    ore_settimanali_stimate = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name="Ore Settimanali Stimate")
    ore_mensili_stimate = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name="Monte Ore Mensile (h/mese)")
    costo_vivo_mensile = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Vivo Totale Mensile (€)")
    canone_consigliato_mensile = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Canone Consigliato (€/mese)")
    canone_finale_offerto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Canone Finale Offerto al Cliente (€/mese)")
    importo_una_tantum_sgrosso = models.DecimalField(max_digits=9, decimal_places=2, default=0.00, verbose_name="Eventuale Sgrosso Iniziale Una Tantum (€)")

    stato = models.CharField(max_length=20, choices=STATO_CHOICES, default='BOZZA', verbose_name="Stato Preventivo")
    cliente_convertito = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='preventivi_origine', verbose_name="Cliente Attivo Generato"
    )
    squadra_prevista = models.ForeignKey(
        Squadra, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Squadra Prevista (per attivazione)"
    )
    note_capitolato = models.TextField(blank=True, default='', verbose_name="Dettaglio Capitolato e Mansioni")
    data_emissione = models.DateField(verbose_name="Data Preventivo")
    validita_giorni = models.PositiveIntegerField(default=30, verbose_name="Validità Offerta (giorni)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Preventivo Commerciale"
        verbose_name_plural = "Preventivi Commerciali (CRM)"
        ordering = ['-created_at']

    def ricalcola_totali(self):
        voci = list(self.voci_ambienti.all())
        tot_mq = sum(float(v.metri_quadri or 0) for v in voci)
        ore_sett = sum(float(v.ore_settimanali_ambiente or 0) for v in voci)
        ore_mese = round(ore_sett * 4.33, 2)
        costo_manodopera = ore_mese * float(self.costo_orario_applicato or 16.50)
        costo_prodotti = costo_manodopera * (float(self.incidenza_prodotti_perc or 0) / 100.0)
        costo_vivo = round(costo_manodopera + costo_prodotti + float(self.quota_fissa_mezzi_mensile or 0), 2)
        margine_ratio = min(max(float(self.margine_target_perc or 25.0) / 100.0, 0.0), 0.85)
        canone_cons = round(costo_vivo / (1.0 - margine_ratio), 2) if (1.0 - margine_ratio) > 0 else costo_vivo

        self.totale_mq = Decimal(str(round(tot_mq, 1)))
        self.ore_settimanali_stimate = Decimal(str(round(ore_sett, 2)))
        self.ore_mensili_stimate = Decimal(str(ore_mese))
        self.costo_vivo_mensile = Decimal(str(costo_vivo))
        self.canone_consigliato_mensile = Decimal(str(canone_cons))
        if not self.canone_finale_offerto or float(self.canone_finale_offerto) <= 0:
            # Arrotonda ai 5 € più vicini per estetica commerciale
            arrotondato = round(canone_cons / 5.0) * 5.0
            self.canone_finale_offerto = Decimal(str(max(arrotondato, canone_cons)))
        PreventivoCommerciale.objects.filter(pk=self.pk).update(
            totale_mq=self.totale_mq,
            ore_settimanali_stimate=self.ore_settimanali_stimate,
            ore_mensili_stimate=self.ore_mensili_stimate,
            costo_vivo_mensile=self.costo_vivo_mensile,
            canone_consigliato_mensile=self.canone_consigliato_mensile,
            canone_finale_offerto=self.canone_finale_offerto,
        )

    @property
    def margine_euro_effettivo(self):
        return round(float(self.canone_finale_offerto or 0) - float(self.costo_vivo_mensile or 0), 2)

    @property
    def margine_perc_effettivo(self):
        canone = float(self.canone_finale_offerto or 0)
        if canone <= 0:
            return 0.0
        return round(((canone - float(self.costo_vivo_mensile or 0)) / canone) * 100.0, 1)

    @property
    def tariffa_oraria_offerta(self):
        ore = float(self.ore_mensili_stimate or 0)
        if ore <= 0:
            return 0.0
        return round(float(self.canone_finale_offerto or 0) / ore, 2)

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.data_emissione:
            self.data_emissione = timezone.now().date()
        if not self.numero_preventivo:
            anno = self.data_emissione.year
            count = PreventivoCommerciale.objects.filter(data_emissione__year=anno).count() + 1
            self.numero_preventivo = f"PREV-{anno}-{count:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_preventivo} — {self.ragione_sociale_prospect} (€{self.canone_finale_offerto}/mese)"


class VoceAmbientePreventivo(models.Model):
    FREQUENZA_CHOICES = [
        ('1_SETT', '1 volta a settimana', 1.0),
        ('2_SETT', '2 volte a settimana', 2.0),
        ('3_SETT', '3 volte a settimana', 3.0),
        ('5_SETT', '5 volte a settimana (Lun-Ven)', 5.0),
        ('6_SETT', '6 volte a settimana (Lun-Sab)', 6.0),
        ('7_SETT', '7 volte a settimana (Tutti i giorni)', 7.0),
        ('BISETT', 'Ogni 2 settimane (Quindicinale)', 0.5),
        ('MENSILE', '1 volta al mese', 0.23),
    ]

    preventivo = models.ForeignKey(PreventivoCommerciale, on_delete=models.CASCADE, related_name='voci_ambienti')
    nome_ambiente = models.CharField(max_length=150, verbose_name="Ambiente / Zona (es. Uffici, Bagni, Scale, Vetrate)")
    metri_quadri = models.DecimalField(max_digits=7, decimal_places=1, default=100.0, verbose_name="Superficie (m²)")
    resa_oraria_mq = models.DecimalField(
        max_digits=6, decimal_places=1, default=150.0,
        verbose_name="Resa Oraria Media (m²/h)",
        help_text="Es: Bagni/Sanitari 60 m²/h, Uffici arredati 150 m²/h, Scale condominiali 120 m²/h, Capannoni/Corridoi 350 m²/h",
    )
    passaggi_settimanali = models.DecimalField(
        max_digits=4, decimal_places=2, default=1.00,
        verbose_name="Interventi a Settimana (es. 1, 2, 5, 0.5 per bisettimanale)",
    )
    giorni_preferiti = models.CharField(
        max_length=50, blank=True, default='0',
        verbose_name="Giorni Settimana (0=Lun .. 6=Dom separati da virgola)",
    )
    ora_inizio_suggerita = models.TimeField(default='07:00', verbose_name="Ora Inizio Suggerita")
    ore_per_intervento = models.DecimalField(max_digits=5, decimal_places=2, default=1.00, verbose_name="Ore per singolo intervento")
    ore_settimanali_ambiente = models.DecimalField(max_digits=6, decimal_places=2, default=1.00, verbose_name="Ore Settimanali Totali")

    class Meta:
        verbose_name = "Ambiente / Zona Preventivo"
        verbose_name_plural = "Ambienti & Superfici del Preventivo"
        ordering = ['id']

    def save(self, *args, **kwargs):
        mq = float(self.metri_quadri or 0)
        resa = float(self.resa_oraria_mq or 150)
        if resa <= 0:
            resa = 150.0
        ore_singolo = max(round(mq / resa, 2), 0.25)
        self.ore_per_intervento = Decimal(str(ore_singolo))
        self.ore_settimanali_ambiente = Decimal(str(round(ore_singolo * float(self.passaggi_settimanali or 1), 2)))
        super().save(*args, **kwargs)
        if self.preventivo_id:
            self.preventivo.ricalcola_totali()

    def __str__(self):
        return f"{self.nome_ambiente} ({self.metri_quadri} m² @ {self.resa_oraria_mq} m²/h)"


# ==============================================================================
# STATO CONVERSAZIONALE TELEGRAM E LOCK MULTI-WORKER DELLO SCHEDULER
# ==============================================================================

class TelegramConversationState(models.Model):
    """
    Persiste su database lo stato conversazionale multi-step del bot Telegram
    (es. attesa ore turno, date malattia/ferie/104, permesso, segnalazione, materiali, PIN accreditamento).
    Garantisce che lo stato sia condiviso tra tutti i worker Gunicorn e sopravviva ai riavvii del container.
    """
    chat_id = models.CharField(max_length=64, primary_key=True, verbose_name="Telegram Chat ID")
    state_data = models.JSONField(default=dict, blank=True, verbose_name="Dati Stato Conversazione")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ultimo Aggiornamento")

    class Meta:
        verbose_name = "Stato Conversazione Telegram"
        verbose_name_plural = "Stati Conversazione Telegram"
        ordering = ['-updated_at']

    @property
    def action(self):
        return (self.state_data or {}).get('action', 'idle')

    @property
    def payload(self):
        return self.state_data or {}

    def __str__(self):
        return f"Telegram State [{self.chat_id}] -> {self.action}"


class SchedulerExecutionLog(models.Model):
    """
    Registro e lock atomico a database per i job schedulati giornalieri (es. promemoria ore 17:00).
    Il vincolo di unicità (job_name, execution_date) garantisce che in un ambiente multi-worker Gunicorn
    o in caso di riavvio del container, ciascun job venga eseguito una sola volta per giornata.
    """
    job_name = models.CharField(max_length=100, verbose_name="Nome Job Schedulato")
    execution_date = models.DateField(verbose_name="Data Esecuzione")
    executed_at = models.DateTimeField(auto_now_add=True, verbose_name="Timestamp Esecuzione")
    worker_pid = models.IntegerField(null=True, blank=True, verbose_name="PID Worker")
    details = models.JSONField(default=dict, blank=True, verbose_name="Esito / Dettagli")

    class Meta:
        verbose_name = "Log Esecuzione Scheduler"
        verbose_name_plural = "Log Esecuzioni Scheduler"
        unique_together = [('job_name', 'execution_date')]
        ordering = ['-execution_date', '-executed_at']

    @property
    def status(self):
        return (self.details or {}).get('status', 'COMPLETED')

    def __str__(self):
        return f"{self.job_name} ({self.execution_date})"


# --- Geocoding Signals (Non-blocking Post-Commit + Cache) ---
@receiver(pre_save, sender=Dipendente)
def geocode_dipendente_address(sender, instance, **kwargs):
    geocode_helper(instance, 'indirizzo_residenza')


@receiver(pre_save, sender=Cliente)
def geocode_cliente_address(sender, instance, **kwargs):
    geocode_helper(instance, 'indirizzo_sede')
    if instance.pk:
        old_vals = (
            Cliente.objects.filter(pk=instance.pk)
            .values_list('ore_mensili_contratto', 'importo_mensile_contratto')
            .first()
        )
        if old_vals:
            old_ore = to_decimal(old_vals[0])
            old_imp = to_decimal(old_vals[1])
            new_ore = to_decimal(instance.ore_mensili_contratto)
            new_imp = to_decimal(instance.importo_mensile_contratto)
            if old_ore != new_ore or old_imp != new_imp:
                instance._contract_change_transition = (old_ore, old_imp, new_ore, new_imp)


@receiver(post_save, sender=Dipendente)
def post_save_geocode_dipendente(sender, instance, **kwargs):
    pending = getattr(instance, '_pending_async_geocode', None)
    if pending:
        instance._pending_async_geocode = None
        schedule_async_geocode(Dipendente, instance.pk, 'indirizzo_residenza', pending)


@receiver(post_save, sender=Cliente)
def post_save_geocode_cliente(sender, instance, **kwargs):
    pending = getattr(instance, '_pending_async_geocode', None)
    if pending:
        instance._pending_async_geocode = None
        schedule_async_geocode(Cliente, instance.pk, 'indirizzo_sede', pending)

    transition = getattr(instance, '_contract_change_transition', None)
    if transition:
        instance._contract_change_transition = None
        old_ore, old_imp, new_ore, new_imp = transition
        from django.utils import timezone
        today = timezone.now().date()
        effective_start = getattr(instance, '_contract_effective_date', None) or date(today.year, today.month, 1)
        prev_end = effective_start - timedelta(days=1)

        existing = list(StoricoContrattoCliente.objects.filter(cliente=instance).order_by('valido_dal', 'id'))
        if not existing:
            # Storicizza automaticamente le condizioni precedenti per tutti i mesi passati
            StoricoContrattoCliente.objects.create(
                cliente=instance,
                valido_dal=date(2000, 1, 1),
                valido_al=prev_end,
                ore_mensili_contratto=old_ore,
                importo_mensile_contratto=old_imp,
                note_variazione="Condizioni contrattuali precedenti (storicizzate automaticamente)",
            )
            StoricoContrattoCliente.objects.create(
                cliente=instance,
                valido_dal=effective_start,
                valido_al=None,
                ore_mensili_contratto=new_ore,
                importo_mensile_contratto=new_imp,
                note_variazione=f"Adeguamento contrattuale dal {effective_start.strftime('%d/%m/%Y')}",
            )
        else:
            open_rec = StoricoContrattoCliente.objects.filter(cliente=instance, valido_al__isnull=True).order_by('-valido_dal', '-id').first()
            if open_rec:
                if open_rec.valido_dal < effective_start:
                    open_rec.valido_al = prev_end
                    open_rec.save(update_fields=['valido_al'])
                    StoricoContrattoCliente.objects.create(
                        cliente=instance,
                        valido_dal=effective_start,
                        valido_al=None,
                        ore_mensili_contratto=new_ore,
                        importo_mensile_contratto=new_imp,
                        note_variazione=f"Adeguamento contrattuale dal {effective_start.strftime('%d/%m/%Y')}",
                    )
                else:
                    open_rec.ore_mensili_contratto = new_ore
                    open_rec.importo_mensile_contratto = new_imp
                    open_rec.save(update_fields=['ore_mensili_contratto', 'importo_mensile_contratto'])
            else:
                StoricoContrattoCliente.objects.create(
                    cliente=instance,
                    valido_dal=effective_start,
                    valido_al=None,
                    ore_mensili_contratto=new_ore,
                    importo_mensile_contratto=new_imp,
                    note_variazione=f"Adeguamento contrattuale dal {effective_start.strftime('%d/%m/%Y')}",
                )

        if hasattr(instance, '_prefetched_objects_cache') and isinstance(instance._prefetched_objects_cache, dict):
            instance._prefetched_objects_cache.pop('storico_contratti', None)


def geocode_helper(instance, address_field):
    # Skip durante loaddata/push/test per evitare chiamate esterne
    if os.environ.get('SKIP_GEOCODING'):
        return

    address = (getattr(instance, address_field, '') or '').strip()
    if not address:
        return

    update_fields = kwargs_update_fields = getattr(instance, '_ geo_update_fields', None)
    if update_fields and address_field not in update_fields:
        return

    # Verifica se l'indirizzo è cambiato o se mancano le coordinate
    should_geocode = False
    if instance.pk:
        old_address = (
            instance.__class__.objects.filter(pk=instance.pk)
            .values_list(address_field, flat=True)
            .first()
        )
        if old_address is None or (old_address or '').strip() != address:
            should_geocode = True
    else:
        if instance.latitudine is None or instance.longitudine is None:
            should_geocode = True

    if not should_geocode:
        return

    # 1. Se le coordinate sono già in cache, applicale istantaneamente in 0ms
    cached = get_cached_geocode(address)
    if cached and isinstance(cached, (tuple, list)) and len(cached) == 2:
        instance.latitudine, instance.longitudine = cached[0], cached[1]
        return

    # 2. Se richiesto geocoding sincrono esplicito (SYNC_GEOCODING=1), esegui subito
    if os.environ.get('SYNC_GEOCODING') == '1':
        lat, lon = geocode_address(address)
        if lat is not None and lon is not None:
            instance.latitudine = lat
            instance.longitudine = lon
        return

    # 3. Altrimenti delega al worker asincrono post-commit in post_save per non bloccare mai l'Admin
    instance._pending_async_geocode = address



