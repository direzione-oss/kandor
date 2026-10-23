from django.core.management.base import BaseCommand
from core.utils_kandor_chat import invia_promemoria_ore_mancanti


class Command(BaseCommand):
    help = "Invia promemoria Telegram ai dipendenti che non hanno inserito le ore lavorate nelle ultime 24 ore."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Controlla solo quali dipendenti dovrebbero ricevere l avviso senza inviare messaggi.',
        )
        parser.add_argument(
            '--chat-id',
            type=str,
            help='Invia il promemoria solo a uno specifico Telegram Chat ID per test.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        chat_id = options.get('chat_id')

        self.stdout.write(self.style.NOTICE("🔍 Avvio controllo ore lavorate non inserite (ultime 24h)..."))

        res = invia_promemoria_ore_mancanti(only_check=dry_run, test_chat_id=chat_id)

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"[DRY-RUN] Trovati {res['inviati']} dipendenti con turni da registrare:"))
            for d in res['dettagli']:
                self.stdout.write(f"  • {d['dipendente']} (Chat ID: {d['chat_id']}) — {d['turni_mancanti']} turno/i mancanti")
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ Inviati {res['inviati']} promemoria Telegram. Errori: {res['errori']}"))
            for d in res['dettagli']:
                status = d.get('stato', 'Inviato')
                self.stdout.write(f"  • {d['dipendente']} (Chat ID: {d['chat_id']}) -> {status}")
