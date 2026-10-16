from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import ProgrammazioneRicorrente, Turno, AssegnazioneTurno, Squadra
from datetime import timedelta, date
import calendar

class Command(BaseCommand):
    help = 'Genera i turni futuri basandosi sulla Programmazione Ricorrente'

    def add_arguments(self, parser):
        parser.add_argument('days', type=int, help='Numero di giorni da generare (es. 7 per una settimana)')

    def handle(self, *args, **options):
        days = options['days']
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=days)
        
        self.stdout.write(f"Generazione turni dal {start_date} al {end_date}...")

        programmazioni = ProgrammazioneRicorrente.objects.all()
        count = 0

        # Iteriamo ogni giorno nel range
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.weekday() # 0=Lun, 6=Dom
            day_of_month = current_date.day
            
            # Troviamo le programmazioni che matchano oggi
            match_giornalieri = programmazioni.filter(tipo_ripetizione='GIORNALIERO')
            match_settimanali = programmazioni.filter(tipo_ripetizione='SETTIMANALE', giorno_settimana=weekday)
            match_mensili = programmazioni.filter(tipo_ripetizione='MENSILE', giorno_mese=day_of_month)
            
            matches = list(match_giornalieri) + list(match_settimanali) + list(match_mensili)
            
            for prog in matches:
                # 1. Trova la Squadra
                # Usiamo la squadra abituale definita nella programmazione, oppure saltiamo (o loggiamo warning)
                squadra = prog.squadra_abituale
                if not squadra:
                    # Fallback opzionale: prima squadra disponibile o skip
                    # self.stdout.write(self.style.WARNING(f"Nessuna squadra assegnata per {prog}. Salto."))
                    # Per ora saltiamo per essere precisi
                    continue

                # 2. Crea o Recupera il Turno
                turno = Turno.objects.filter(data=current_date, squadra=squadra).first()
                if not turno:
                    turno = Turno.objects.create(
                        data=current_date,
                        squadra=squadra,
                        mezzo=None
                    )
                
                # 3. Crea l'Assegnazione se non esiste già
                exists = AssegnazioneTurno.objects.filter(
                    turno=turno,
                    programmazione_feriale=prog
                ).exists()
                
                if not exists:
                    # Calcolo orari
                    import datetime
                    orario_inizio = prog.ora_inizio
                    
                    # Calcolo fine basato su durata
                    if prog.durata:
                         dummy_date = date.today()
                         dt_start = datetime.datetime.combine(dummy_date, orario_inizio)
                         hours = int(prog.durata)
                         minutes = int((prog.durata - hours) * 60)
                         dt_end = dt_start + timedelta(hours=hours, minutes=minutes)
                         orario_fine = dt_end.time()
                    else:
                         orario_fine = orario_inizio # Fallback
                    
                    AssegnazioneTurno.objects.create(
                        turno=turno,
                        cliente=prog.cliente,
                        programmazione_feriale=prog,
                        orario_inizio_previsto=orario_inizio,
                        orario_fine_previsto=orario_fine,
                        mansione_svolta=f"Generato da programmazione (Qualifica: {prog.qualifica_richiesta})"
                    )
                    count += 1
            
            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"Generazione completata! Creati {count} nuovi inserimenti in agenda."))
