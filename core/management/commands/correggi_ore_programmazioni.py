from django.core.management.base import BaseCommand
from decimal import Decimal
from datetime import datetime, date, timedelta
from core.models import ProgrammazioneRicorrente, AssegnazioneTurno


class Command(BaseCommand):
    help = "Corregge le durate fraintese nelle programmazioni ricorrenti e sincronizza i turni futuri."

    def handle(self, *args, **options):
        # Mappa delle correzioni mirate identificate (valori digitati in decimali pensando a minuti sessantesimali)
        CORREZIONI = {
            276: (Decimal('3.25'), "ARCLEGNO ARREDA (3.15 -> 3h15 = 3.25h)"),
            277: (Decimal('3.25'), "ARCLEGNO ARREDA (3.15 -> 3h15 = 3.25h)"),
            55:  (Decimal('1.17'), "CASA PRIVATA (1.10 -> 1h10 = 1.17h)"),
            384: (Decimal('1.25'), "CONDOMINIO SERENA (1.15 -> 1h15 = 1.25h)"),
            385: (Decimal('1.25'), "CONDOMINIO ORCHIDEA (1.15 -> 1h15 = 1.25h)"),
            399: (Decimal('1.25'), "CONDOMINIO SERENA (1.15 -> 1h15 = 1.25h)"),
        }

        self.stdout.write(self.style.NOTICE("Avvio correzione e sincronizzazione programmazioni ricorrenti..."))

        aggiornate = 0
        ricollegati_fine = 0

        for prog in ProgrammazioneRicorrente.objects.all():
            modificato = False
            if prog.pk in CORREZIONI:
                nuova_durata, desc = CORREZIONI[prog.pk]
                self.stdout.write(f"Aggiorno ID {prog.pk}: {desc}")
                prog.durata = nuova_durata
                modificato = True

            # Calcolo ora_fine se mancante o se modificato
            if prog.ora_inizio and prog.durata:
                hours = int(prog.durata)
                minutes = int(round((prog.durata - hours) * 60))
                calc_fine = (datetime.combine(date.today(), prog.ora_inizio) + timedelta(hours=hours, minutes=minutes)).time()
                if prog.ora_fine != calc_fine:
                    prog.ora_fine = calc_fine
                    modificato = True
                    ricollegati_fine += 1

            if modificato:
                prog.save()
                aggiornate += 1

        self.stdout.write(self.style.SUCCESS(f"Programmazioni modificate: {aggiornate} (di cui {ricollegati_fine} con ricalcolo orario fine)."))

        # Pulizia/rettifica orari nei turni futuri (dal giorno corrente) collegati alle programmazioni corrette
        today = date.today()
        # Per le 6 programmazioni, allinea orario_fine_previsto
        for pk, (durata_corretta, _) in CORREZIONI.items():
            prog = ProgrammazioneRicorrente.objects.filter(pk=pk).first()
            if prog and prog.ora_inizio and prog.ora_fine:
                count_turni = AssegnazioneTurno.objects.filter(
                    programmazione_feriale=prog,
                    turno__data__gte=today
                ).update(
                    orario_inizio_previsto=prog.ora_inizio,
                    orario_fine_previsto=prog.ora_fine
                )
                self.stdout.write(f"Allineati {count_turni} turni futuri per programmazione {prog.pk} ({prog.cliente.ragione_sociale}).")

        self.stdout.write(self.style.SUCCESS("Operazione completata con successo."))
