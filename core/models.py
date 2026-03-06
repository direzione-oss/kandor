from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .utils_geocoding import geocode_address
from django.utils.translation import gettext_lazy as _

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

    # Dati Contrattuali
    categoria_protetta = models.BooleanField(default=False)
    file_contratto = models.FileField(upload_to='contratti/', null=True, blank=True)
    
    # Relazioni
    qualifiche = models.ManyToManyField(Qualifica, related_name='dipendenti', blank=True, verbose_name="Qualifiche Possedute")
    
    # Integrazione Chat
    telegram_chat_id = models.CharField(max_length=64, blank=True, null=True, help_text="ID Chat Telegram per invio ore", verbose_name="Telegram Chat ID")
    
    # Stato
    stato = models.CharField(max_length=20, choices=STATO_CHOICES, default='ATTIVO')

    def save(self, *args, **kwargs):
        # Auto-calculate data_nascita from CF if missing
        if not self.data_nascita and self.codice_fiscale:
            from .utils_cf import extract_data_nascita
            extracted_date = extract_data_nascita(self.codice_fiscale)
            if extracted_date:
                self.data_nascita = extracted_date
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cognome} {self.nome}"

    class Meta:
        verbose_name_plural = "Dipendenti"

class Cliente(models.Model):
    ragione_sociale = models.CharField(max_length=200, verbose_name="Ragione Sociale")
    partita_iva = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Partita IVA")
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
    note_mansioni = models.TextField(blank=True, help_text="Mansioni richieste specifiche", verbose_name="Note Mansioni")

    def __str__(self):
        return self.ragione_sociale

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clienti"

class ProgrammazioneRicorrente(models.Model):
    TIPO_RIPETIZIONE = [
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
    
    # Per bisettimanale: data di riferimento per calcolare settimane pari/dispari
    data_inizio_ciclo = models.DateField(null=True, blank=True, verbose_name="Data Inizio Ciclo", help_text="Solo per Bisettimanale: data di riferimento della prima settimana attiva")

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
        
        # Validazione Tipo Ripetizione
        if self.tipo_ripetizione == 'SETTIMANALE' and self.giorno_settimana is None:
            raise ValidationError("Per ripetizione Settimanale devi selezionare un Giorno della Settimana.")
        if self.tipo_ripetizione == 'BISETTIMANALE':
            if self.giorno_settimana is None:
                raise ValidationError("Per ripetizione Bisettimanale devi selezionare un Giorno della Settimana.")
            if not self.data_inizio_ciclo:
                raise ValidationError("Per ripetizione Bisettimanale devi inserire la Data Inizio Ciclo.")
        if self.tipo_ripetizione == 'MENSILE' and self.giorno_mese is None:
            raise ValidationError("Per ripetizione Mensile devi inserire un Giorno del Mese.")

        # Calcolo proiettivo ora_fine per la validazione (se non ancora salvato)
        check_ora_fine = self.ora_fine
        if not check_ora_fine and self.ora_inizio and self.durata:
            dummy_date = datetime.date.today()
            dt_start = datetime.datetime.combine(dummy_date, self.ora_inizio)
            hours = int(self.durata)
            minutes = int((self.durata - hours) * 60)
            dt_end = dt_start + datetime.timedelta(hours=hours, minutes=minutes)
            check_ora_fine = dt_end.time()
        
        # Validazione Sovrapposizioni (Squadra e Mezzo)
        if self.ora_inizio and check_ora_fine and (self.squadra_abituale or self.mezzo_abituale):
            # Filtro base: stessa periodicità
            query = Q(tipo_ripetizione=self.tipo_ripetizione)
            if self.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE'):
                query &= Q(giorno_settimana=self.giorno_settimana)
            elif self.tipo_ripetizione == 'MENSILE':
                query &= Q(giorno_mese=self.giorno_mese)
            
            # Filtro orario: overlap (StartA < EndB) and (EndA > StartB)
            query &= Q(ora_inizio__lt=check_ora_fine) & Q(ora_fine__gt=self.ora_inizio)
            
            # Escludi se stesso (in caso di modifica)
            if self.pk:
                query &= ~Q(pk=self.pk)
            
            # Controllo Squadra
            if self.squadra_abituale:
                conflitti_squadra = ProgrammazioneRicorrente.objects.filter(query, squadra_abituale=self.squadra_abituale)
                if conflitti_squadra.exists():
                    conflitto = conflitti_squadra.first()
                    raise ValidationError(f"La squadra '{self.squadra_abituale}' è già impegnata in orario sovrapposto (Cliente: {conflitto.cliente}).")

            # Controllo Mezzo
            if self.mezzo_abituale:
                conflitti_mezzo = ProgrammazioneRicorrente.objects.filter(query, mezzo_abituale=self.mezzo_abituale)
                if conflitti_mezzo.exists():
                    conflitto = conflitti_mezzo.first()
                    raise ValidationError(f"Il mezzo '{self.mezzo_abituale}' è già impegnato in orario sovrapposto (Cliente: {conflitto.cliente}).")

    def __str__(self):
        tipo = self.get_tipo_ripetizione_display()
        if self.tipo_ripetizione == 'SETTIMANALE':
             giorno = self.get_giorno_settimana_display()
        else:
             giorno = f"Giorno {self.giorno_mese}"
        return f"{self.cliente} - {tipo} {giorno} ({self.ora_inizio} + {self.durata}h)"

    class Meta:
        verbose_name = "Programmazione Ricorrente"
        verbose_name_plural = "Programmazioni Ricorrenti"
        ordering = ['tipo_ripetizione', 'giorno_settimana', 'giorno_mese', 'ora_inizio']


class RichiestaStraordinaria(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='richieste_straordinarie')
    data_inizio = models.DateField()
    data_fine = models.DateField(null=True, blank=True, help_text="Se il lavoro dura più giorni (opzionale)")
    
    ora_inizio = models.TimeField(verbose_name="Ora Inizio")
    ora_fine = models.TimeField(verbose_name="Ora Fine")
    
    descrizione = models.TextField(verbose_name="Descrizione Attività")
    completata = models.BooleanField(default=False, verbose_name="Completata")

    def __str__(self):
        return f"Straordinario {self.cliente} - {self.data_inizio}"

    class Meta:
        verbose_name_plural = "Richieste Straordinarie"

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
    scadenza_bollo = models.DateField(null=True, blank=True, verbose_name="Scadenza Bollo")

    def __str__(self):
        return f"{self.modello} ({self.targa})"

    class Meta:
        verbose_name_plural = "Mezzi Aziendali"

class Squadra(models.Model):
    nome = models.CharField(max_length=100)
    caposquadra = models.ForeignKey(Dipendente, on_delete=models.SET_NULL, null=True, related_name='squadre_capitanate')
    componenti = models.ManyToManyField(Dipendente, related_name='squadre_appartenenza', blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Squadre"

class Turno(models.Model):
    data = models.DateField(verbose_name="Data Turno")
    squadra = models.ForeignKey(Squadra, on_delete=models.CASCADE, verbose_name="Squadra Assegnata")
    mezzo = models.ForeignKey(Mezzo, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mezzo Utilizzato")
    
    def __str__(self):
        return f"Turno {self.data} - {self.squadra}"

    class Meta:
        verbose_name_plural = "Turni"

class AssegnazioneTurno(models.Model):
    turno = models.ForeignKey(Turno, on_delete=models.CASCADE, related_name='assegnazioni')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    
    # Link alla programmazione (Opzionale, ma consigliato per tracciabilità)
    programmazione_feriale = models.ForeignKey(ProgrammazioneRicorrente, on_delete=models.SET_NULL, null=True, blank=True, related_name='assegnazioni_svolte')
    richiesta_straordinaria = models.ForeignKey(RichiestaStraordinaria, on_delete=models.SET_NULL, null=True, blank=True, related_name='assegnazioni_svolte')
    
    orario_inizio_previsto = models.TimeField()
    orario_fine_previsto = models.TimeField()
    
    mansione_svolta = models.TextField(blank=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.programmazione_feriale and self.richiesta_straordinaria:
            raise ValidationError("Un'assegnazione non può essere legata contemporaneamente a una programmazione feriale e straordinaria.")

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

class TimeTracking(models.Model):
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE)
    assegnazione = models.ForeignKey(AssegnazioneTurno, on_delete=models.CASCADE, related_name='timetracks')
    
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    
    note = models.TextField(blank=True)
    
    SOURCE_CHOICES = [
        ('MANUAL', 'Manuale'),
        ('TELEGRAM', 'Telegram'),
        ('WHATSAPP', 'WhatsApp'),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='MANUAL')
    is_validated = models.BooleanField(default=False, verbose_name="Validato")

    @property
    def durata_ore(self):
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
    
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='assenze')
    tipo = models.CharField(max_length=20, choices=TIPO_ASSENZA)
    data_inizio = models.DateField()
    data_fine = models.DateField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True) # Allow null for existing rows
    source = models.CharField(max_length=20, default='MANUAL') # MANUAL, TELEGRAM
    is_processed = models.BooleanField(default=False, verbose_name="Processato")

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.data_fine < self.data_inizio:
            raise ValidationError("La data di fine non può essere precedente all'inizio.")

    def __str__(self):
        return f"{self.dipendente} - {self.tipo} ({self.data_inizio} a {self.data_fine})"

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
    testo = models.TextField(verbose_name="Testo del Messaggio")
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


# --- Geocoding Signals ---
@receiver(pre_save, sender=Dipendente)
def geocode_dipendente_address(sender, instance, **kwargs):
    geocode_helper(instance, 'indirizzo_residenza')

@receiver(pre_save, sender=Cliente)
def geocode_cliente_address(sender, instance, **kwargs):
    geocode_helper(instance, 'indirizzo_sede')

def geocode_helper(instance, address_field):
    address = getattr(instance, address_field)
    if not address:
        return

    # Check if address changed or is new
    should_geocode = False
    if instance.pk:
        try:
            old_instance = instance.__class__.objects.get(pk=instance.pk)
            old_address = getattr(old_instance, address_field)
            if address != old_address:
                should_geocode = True
        except instance.__class__.DoesNotExist:
            should_geocode = True
    else:
        should_geocode = True

    if should_geocode:
        lat, lon = geocode_address(address)
        if lat is not None and lon is not None:
            instance.latitudine = lat
            instance.longitudine = lon

