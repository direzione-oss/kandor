import os
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

    # Dati Contrattuali
    categoria_protetta = models.BooleanField(default=False)
    file_contratto = models.FileField(upload_to='contratti/', null=True, blank=True)
    data_assunzione = models.DateField(null=True, blank=True, verbose_name="Data di Assunzione")
    data_licenziamento = models.DateField(null=True, blank=True, verbose_name="Data di Licenziamento")
    is_part_time = models.BooleanField(default=False, verbose_name="Contratto Part-Time")
    ore_settimanali_part_time = models.DecimalField(
        max_digits=4, decimal_places=1,
        null=True, blank=True,
        verbose_name="Ore Settimanali (Part-Time)",
        help_text="Compilare solo se il contratto è Part-Time"
    )
    data_ultima_visita_medica = models.DateField(null=True, blank=True, verbose_name="Data Ultima Visita Medica")
    
    # Relazioni
    qualifiche = models.ManyToManyField(Qualifica, related_name='dipendenti', blank=True, verbose_name="Qualifiche Possedute")
    
    # Integrazione Chat
    telegram_chat_id = models.CharField(max_length=64, blank=True, null=True, help_text="ID Chat Telegram per invio ore", verbose_name="Telegram Chat ID")
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
    def importo_orario(self):
        """Calcola l'importo orario: importo_mensile / ore_mensili"""
        if self.ore_mensili_contratto and self.ore_mensili_contratto > 0:
            return round(float(self.importo_mensile_contratto) / float(self.ore_mensili_contratto), 2)
        return 0

    def __str__(self):
        return self.ragione_sociale

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clienti"
        ordering = ['ragione_sociale']

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
        
        # Validazione Tipo Ripetizione
        if self.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE') and self.giorno_settimana is None:
            raise ValidationError("Devi selezionare un Giorno della Settimana.")
        if self.tipo_ripetizione == 'BISETTIMANALE' and not self.data_inizio_contratto:
            raise ValidationError("Per ripetizione Bisettimanale devi inserire la Data Inizio Contratto (usata come riferimento ciclo).")
        if self.tipo_ripetizione == 'MENSILE' and self.giorno_mese is None:
            raise ValidationError("Per ripetizione Mensile devi inserire un Giorno del Mese.")
        
        # Validazione date contratto
        if self.data_inizio_contratto and self.data_fine_contratto:
            if self.data_fine_contratto < self.data_inizio_contratto:
                raise ValidationError("La Data Fine Contratto non puo' essere precedente alla Data Inizio.")

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
        if self.tipo_ripetizione in ('SETTIMANALE', 'BISETTIMANALE'):
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
    scadenza_bollo = models.DateField(null=True, blank=True, verbose_name="Scadenza Bollo")

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
    ore_previste_contratto = models.FloatField(
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
        """Restituisce i dipendenti della squadra effettivamente presenti (squadra - esclusi)."""
        squadra = self.turno.squadra
        esclusi = self.dipendenti_esclusi.values_list('pk', flat=True)
        from django.db.models import Q
        presenti = []
        if squadra.caposquadra and squadra.caposquadra.pk not in esclusi:
            presenti.append(squadra.caposquadra)
        for c in squadra.componenti.exclude(pk__in=esclusi):
            if c not in presenti:
                presenti.append(c)
        return presenti

    @property
    def n_presenti(self):
        return len(self.dipendenti_presenti)

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
    ore_dichiarate = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, verbose_name="Ore Dichiarate", help_text="Ore inserite dal dipendente")
    
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
        if self.data_fine < self.data_inizio:
            raise ValidationError("La data di fine non può essere precedente all'inizio.")
        if self.ora_inizio and self.ora_fine and self.ora_fine <= self.ora_inizio:
            raise ValidationError("L'ora di fine deve essere successiva all'ora di inizio.")

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


class MessaggioChat(models.Model):
    """Messaggio scambiato tra dipendente (Telegram) e admin (Chat Simulator)."""
    DIREZIONE_CHOICES = [
        ('IN', 'Ricevuto dal dipendente'),
        ('OUT', 'Inviato dall\'admin'),
    ]
    dipendente = models.ForeignKey(Dipendente, on_delete=models.CASCADE, related_name='messaggi_chat')
    testo = models.TextField(blank=True, default='')
    foto_url = models.URLField(blank=True, default='', verbose_name="URL Foto")
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


# --- Geocoding Signals ---
@receiver(pre_save, sender=Dipendente)
def geocode_dipendente_address(sender, instance, **kwargs):
    geocode_helper(instance, 'indirizzo_residenza')

@receiver(pre_save, sender=Cliente)
def geocode_cliente_address(sender, instance, **kwargs):
    geocode_helper(instance, 'indirizzo_sede')

def geocode_helper(instance, address_field):
    # Skip durante loaddata/push per evitare chiamate lente all'API
    if os.environ.get('SKIP_GEOCODING'):
        return

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


