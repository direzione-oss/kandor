from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Dipendente, ResponsabileArea
from core.utils_kandor_chat import send_telegram_message

class Command(BaseCommand):
    help = "Invia auguri di compleanno ai dipendenti tramite Telegram e notifica i responsabili."

    def handle(self, *args, **kwargs):
        oggi = timezone.now().date()
        
        # Trova dipendenti attivi che compiono gli anni oggi
        festeggiati = Dipendente.objects.filter(
            stato='ATTIVO',
            data_nascita__day=oggi.day,
            data_nascita__month=oggi.month
        )
        
        if not festeggiati.exists():
            self.stdout.write("Nessun compleanno oggi.")
            return

        # 1. Invia auguri ai festeggiati
        for dip in festeggiati:
            if dip.telegram_chat_id:
                messaggio_auguri = (
                    f"🎉🎂 Tanti auguri di buon compleanno, {dip.nome}!\n\n"
                    f"Da parte di tutto il team Kandor ti auguriamo una giornata speciale e felice! 🎈🎁"
                )
                inviato = send_telegram_message(dip.telegram_chat_id, messaggio_auguri)
                if inviato:
                    self.stdout.write(self.style.SUCCESS(f"Auguri inviati a {dip.nome} {dip.cognome}."))
                else:
                    self.stdout.write(self.style.WARNING(f"Impossibile inviare auguri a {dip.nome} {dip.cognome}."))
            else:
                self.stdout.write(f"{dip.nome} {dip.cognome} non ha collegato Telegram.")

        # 2. Notifica i responsabili area e l'admin
        testo_notifica = "🎂 Oggi è il compleanno di:\n\n"
        for dip in festeggiati:
            eta = oggi.year - dip.data_nascita.year
            testo_notifica += f"🔸 {dip.nome} {dip.cognome} ({eta} anni)\n"
        testo_notifica += "\nNon dimenticate di fargli gli auguri! 🎉"

        # Invia ai responsabili area (escludendo chi compie gli anni per evitare auto-notifiche di compleanno agli altri se non necessario, ma vabbè li notifichiamo comunque)
        responsabili = ResponsabileArea.objects.filter(dipendente__stato='ATTIVO').select_related('dipendente')
        for ra in responsabili:
            if ra.dipendente.telegram_chat_id:
                send_telegram_message(ra.dipendente.telegram_chat_id, testo_notifica)
                self.stdout.write(f"Notificato RA: {ra.dipendente.nome} {ra.dipendente.cognome}.")

        # Invia all'admin
        from django.conf import settings
        admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
        if admin_chat_id:
            send_telegram_message(admin_chat_id, testo_notifica)
            self.stdout.write("Notificato Admin.")

        self.stdout.write(self.style.SUCCESS("Procedura compleanni completata."))
