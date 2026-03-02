from django.core.management.base import BaseCommand
from django.conf import settings
import requests
import sys

class Command(BaseCommand):
    help = 'Imposta il Webhook di Telegram per ricevere messaggi.'

    def add_arguments(self, parser):
        parser.add_argument('public_url', type=str, help='URL pubblico HTTPS del tuo server (es. https://miosito.ngrok.io)')

    def handle(self, *args, **options):
        public_url = options['public_url']
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')

        if not token:
            self.stdout.write(self.style.ERROR("ERRORE: TELEGRAM_BOT_TOKEN non trovato in settings.py o variabili d'ambiente."))
            return

        # Rimuovi slash finale se presente
        if public_url.endswith('/'):
            public_url = public_url[:-1]

        webhook_url = f"{public_url}/telegram-webhook/"
        
        self.stdout.write(f"Configurando Webhook su: {webhook_url}")

        api_url = f"https://api.telegram.org/bot{token}/setWebhook"
        
        try:
            response = requests.post(api_url, data={'url': webhook_url})
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    self.stdout.write(self.style.SUCCESS(f"SUCCESS: Webhook impostato correttamente! {result.get('description')}"))
                else:
                    self.stdout.write(self.style.ERROR(f"TELEGRAM ERROR: {result.get('description')}"))
            else:
                self.stdout.write(self.style.ERROR(f"HTTP ERROR: {response.status_code} - {response.text}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"EXCEPTION: {str(e)}"))
