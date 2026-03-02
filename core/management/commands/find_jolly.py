from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, time
from core.models import Cliente
from core.services import trova_jolly

class Command(BaseCommand):
    help = 'Trova un dipendente Jolly per un cliente specifico'

    def add_arguments(self, parser):
        parser.add_argument('cliente_id', type=int)
        parser.add_argument('--data', type=str, help='YYYY-MM-DD (default: oggi)')
        parser.add_argument('--ora_inizio', type=str, default='09:00')
        parser.add_argument('--ora_fine', type=str, default='13:00')

    def handle(self, *args, **options):
        try:
            cliente = Cliente.objects.get(pk=options['cliente_id'])
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR('Cliente non trovato'))
            return

        date_str = options['data']
        if date_str:
            data = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            data = timezone.now().date()
            
        ora_inizio = datetime.strptime(options['ora_inizio'], '%H:%M').time()
        ora_fine = datetime.strptime(options['ora_fine'], '%H:%M').time()

        self.stdout.write(f"Cercando Jolly per {cliente} il {data} dalle {ora_inizio} alle {ora_fine}...")

        risultati = trova_jolly(cliente, data, ora_inizio, ora_fine)

        if not risultati:
            self.stdout.write(self.style.WARNING("Nessun dipendente disponibile trovato."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Trovati {len(risultati)} candidati:"))
            for i, res in enumerate(risultati, 1):
                dip = res['dipendente']
                dist = f"{res['distanza_km']:.2f} km" if res['distanza_km'] != float('inf') else "N/A"
                skills = ", ".join(res['skills'])
                self.stdout.write(f"{i}. {dip} - Distanza: {dist} - Skills: {skills}")
