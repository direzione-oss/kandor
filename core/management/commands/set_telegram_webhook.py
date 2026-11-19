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

            # Configura il tasto Menu in basso a sinistra per aprire la Scheda Web App
            menu_btn_url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
            try:
                btn_resp = requests.post(menu_btn_url, json={
                    "menu_button": {
                        "type": "web_app",
                        "text": "📱 Scheda",
                        "web_app": {"url": f"{public_url}/app/"}
                    }
                }, timeout=8)
                if btn_resp.status_code == 200 and btn_resp.json().get('ok'):
                    self.stdout.write(self.style.SUCCESS("SUCCESS: Tasto Menu configurato per aprire la Scheda Web App!"))
                else:
                    self.stdout.write(self.style.WARNING(f"WARN: Impossibile impostare menu_button: {btn_resp.text}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"WARN: Eccezione menu_button: {e}"))

            # Configura l'elenco dei comandi bot
            cmd_url = f"https://api.telegram.org/bot{token}/setMyCommands"
            try:
                cmd_resp = requests.post(cmd_url, json={
                    "commands": [
                        {"command": "start", "description": "Menu principale"},
                        {"command": "scheda", "description": "Apri la tua Scheda Web App"},
                        {"command": "ore", "description": "Registra ore lavorate"},
                        {"command": "calendario", "description": "Visualizza il tuo calendario turni"},
                        {"command": "malattia", "description": "Comunica assenza per malattia"},
                        {"command": "ferie", "description": "Richiedi ferie"},
                        {"command": "permesso", "description": "Richiedi permesso"},
                        {"command": "buste_paga", "description": "Consulta le tue buste paga"},
                        {"command": "segnalazione", "description": "Invia una segnalazione"},
                        {"command": "nuovocliente", "description": "Registra nuovo cliente (Solo Responsabili)"},
                    ]
                }, timeout=8)
                if cmd_resp.status_code == 200 and cmd_resp.json().get('ok'):
                    self.stdout.write(self.style.SUCCESS("SUCCESS: Comandi bot Telegram aggiornati!"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"WARN: Eccezione setMyCommands: {e}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"EXCEPTION: {str(e)}"))
