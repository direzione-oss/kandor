import os
import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from core.utils_kandor_chat import handle_telegram_message

class Command(BaseCommand):
    help = 'Runs the Telegram bot in polling mode'

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found in settings."))
            return

        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0
        
        self.stdout.write(self.style.SUCCESS("Bot started in polling mode..."))

        # Clean any webhook first to allow polling
        try:
            requests.post(f"{base_url}/deleteWebhook")
            self.stdout.write("Webhook deleted (required for polling).")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Failed to delete webhook: {e}"))

        from django.utils import timezone
        from core.models import MessaggioProgrammato, Dipendente
        from core.utils_kandor_chat import (
            send_telegram_message,
            send_and_record_telegram_to_employee,
            _save_uploaded_attachment_storage,
            _is_image_file,
        )

        last_check = time.time()

        while True:
            try:
                # --- CHECK SCHEDULED MESSAGES (Every 60s) ---
                if time.time() - last_check > 60:
                    last_check = time.time()
                    now = timezone.now()
                    pending_msgs = MessaggioProgrammato.objects.filter(inviato=False, data_programmata__lte=now)
                    
                    for msg in pending_msgs:
                        self.stdout.write(f"Sending scheduled message: {msg.titolo}")
                        recipients = []
                        if msg.invia_a_tutti:
                            recipients = Dipendente.objects.filter(stato='ATTIVO')
                        else:
                            recipients = msg.destinatari.all()
                        
                        attachments = []
                        if msg.allegato:
                            try:
                                msg.allegato.open('rb')
                                file_bytes = msg.allegato.read()
                                msg.allegato.close()
                                filename = os.path.basename(msg.allegato.name)
                                storage_url = _save_uploaded_attachment_storage(file_bytes, filename)
                                is_image = _is_image_file(filename)
                                attachments.append({
                                    'bytes': file_bytes,
                                    'name': filename,
                                    'content_type': None,
                                    'url': storage_url,
                                    'is_image': is_image,
                                })
                            except Exception as e:
                                self.stdout.write(self.style.WARNING(f"Error reading attachment for scheduled msg {msg.pk}: {e}"))

                        count = 0
                        for emp in recipients:
                            if emp.telegram_chat_id:
                                if send_and_record_telegram_to_employee(emp, text=msg.testo or '', attachments=attachments):
                                    count += 1
                        
                        msg.inviato = True
                        msg.save()
                        self.stdout.write(self.style.SUCCESS(f"Message '{msg.titolo}' sent to {count} recipients."))

                # --- LONG POLLING ---
                response = requests.get(
                    f"{base_url}/getUpdates",
                    params={'offset': offset + 1, 'timeout': 30},
                    timeout=35
                )
                
                if response.status_code != 200:
                    time.sleep(5)
                    continue

                data = response.json()
                if not data.get('ok'):
                    time.sleep(5)
                    continue

                results = data.get('result', [])
                
                for update in results:
                    update_id = update['update_id']
                    if update_id > offset:
                        offset = update_id
                        
                    if 'message' not in update:
                        continue
                        
                    message = update['message']
                    chat_id = message['chat']['id']
                    first_name = message.get('from', {}).get('first_name', 'Utente')
                    
                    # --- HANDLE LOCATION UPDATES ---
                    if 'location' in message:
                        from core.models import Dipendente
                        from core.utils_kandor_chat import check_proximity
                        
                        lat = message['location']['latitude']
                        lon = message['location']['longitude']
                        
                        try:
                            dipendente = Dipendente.objects.get(telegram_chat_id=str(chat_id))
                            
                            # Aggiorna coordinate dipendente
                            dipendente.latitudine = lat
                            dipendente.longitudine = lon
                            dipendente.save()
                            
                            # Controlla prossimità
                            events = check_proximity(dipendente, lat, lon)
                            
                            if events:
                                event_msgs = []
                                for event in events:
                                    if event['type'] == 'entry':
                                        event_msgs.append(f"✅ Sei entrato presso {event['cliente'].ragione_sociale}")
                                    else:
                                        event_msgs.append(f"👋 Hai lasciato {event['cliente'].ragione_sociale}")
                                
                                reply_text = "\n".join(event_msgs)
                            else:
                                reply_text = "📍 Posizione aggiornata."
                            
                            requests.post(
                                f"{base_url}/sendMessage",
                                json={'chat_id': chat_id, 'text': reply_text}
                            )
                            
                        except Dipendente.DoesNotExist:
                            self.stdout.write(f"Unknown chat_id for location: {chat_id}")
                        
                        continue
                    
                    # --- HANDLE TEXT MESSAGES ---
                    text = message.get('text', '')
                    
                    if not text:
                        continue
                        
                    self.stdout.write(f"Received from {first_name}: {text}")
                    
                    # Save message and notify Responsabili & PC Gestionale
                    dip = None
                    try:
                        from core.models import MessaggioChat, Dipendente
                        from core.services import notifica_nuovo_messaggio
                        dip = Dipendente.objects.filter(telegram_chat_id=str(chat_id)).first()
                        if dip:
                            MessaggioChat.objects.create(
                                dipendente=dip,
                                testo=text,
                                direzione='IN'
                            )
                            notifica_nuovo_messaggio(dip, testo=text)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error saving/notifying incoming chat message: {e}"))

                    # Process message
                    try:
                        reply_text = handle_telegram_message(chat_id, text, sender_name=first_name)
                    except Exception as e:
                        reply_text = f"⚠️ Errore interno: {str(e)}"
                        self.stdout.write(self.style.ERROR(f"Error processing message: {e}"))

                    # Send reply
                    if reply_text:
                        payload = {'chat_id': chat_id}
                        if isinstance(reply_text, dict):
                            payload['text'] = reply_text.get('text', '')
                            if reply_text.get('reply_markup'):
                                payload['reply_markup'] = reply_text['reply_markup']
                            testo_out = reply_text.get('text', '')
                        else:
                            payload['text'] = str(reply_text)
                            testo_out = str(reply_text)

                        requests.post(
                            f"{base_url}/sendMessage",
                            json=payload
                        )
                        if dip and testo_out:
                            try:
                                MessaggioChat.objects.create(
                                    dipendente=dip,
                                    testo=testo_out,
                                    direzione='OUT'
                                )
                            except Exception:
                                pass

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Polling error: {e}"))
                time.sleep(5)
