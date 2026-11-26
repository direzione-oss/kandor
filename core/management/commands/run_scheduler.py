"""
Comando di gestione per eseguire lo scheduler e i job periodici di Kandor ERP.
Supporta:
- Esecuzione 'one-off' per integrazione con cron di sistema o Coolify (es: --once)
- Esecuzione continua come worker di background dedicato (senza appoggiarsi ai thread Gunicorn)
"""

import time
import sys
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.scheduler import esegui_tutti_i_job_pianificati, esegui_promemoria_giornaliero_atomico


class Command(BaseCommand):
    help = 'Esegue lo scheduler periodico di Kandor ERP (promemoria 17:00, audit scadenze, batch sync).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Esegue i job previsti per la data corrente una sola volta ed esce (ideale per crontab).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forza l\'esecuzione anche se il lock giornaliero risulta già acquisito.',
        )

    def handle(self, *args, **options):
        is_once = options['once']
        is_force = options['force']

        if is_once:
            self.stdout.write(self.style.NOTICE("Esecuzione 'one-off' job periodici Kandor..."))
            res = esegui_tutti_i_job_pianificati(force=is_force)
            self.stdout.write(self.style.SUCCESS(f"✅ Job periodici completati: {res}"))
            return

        self.stdout.write(self.style.SUCCESS("🚀 Kandor Scheduler Worker avviato in modalità continua (loop 30s)..."))
        try:
            while True:
                now = timezone.localtime(timezone.now())
                today = now.date()

                if now.hour == 17 and 0 <= now.minute <= 5:
                    res = esegui_promemoria_giornaliero_atomico(target_date=today, force=is_force)
                    if not res.get('skipped_locked'):
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"⏰ [17:00] Inviati {res.get('inviati', 0)} promemoria Telegram (Errori: {res.get('errori', 0)})."
                            )
                        )

                time.sleep(30)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Arresto dello scheduler richiesto dall'utente."))
            sys.exit(0)
