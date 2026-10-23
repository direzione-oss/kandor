import threading
import time
from django.utils import timezone

_ULTIMO_INVIO_PROMEMORIA_DATA = None
_SCHEDULER_THREAD = None


def _reminder_loop():
    global _ULTIMO_INVIO_PROMEMORIA_DATA
    while True:
        try:
            now = timezone.now()
            today = now.date()

            # L avviso scatta alle ore 17:00 (tra le 17:00 e le 17:05)
            if now.hour == 17 and 0 <= now.minute <= 5:
                if _ULTIMO_INVIO_PROMEMORIA_DATA != today:
                    _ULTIMO_INVIO_PROMEMORIA_DATA = today
                    print(f"⏰ [Scheduler 17:00] Avvio promemoria automatico ore lavorate per il {today}...")
                    from .utils_kandor_chat import invia_promemoria_ore_mancanti
                    res = invia_promemoria_ore_mancanti(only_check=False)
                    print(f"⏰ [Scheduler 17:00] Inviati {res['inviati']} promemoria Telegram (Errori: {res['errori']}).")
        except Exception as e:
            print(f"⚠️ [Scheduler Error] {e}")

        time.sleep(30)


def start_scheduler():
    global _SCHEDULER_THREAD
    if _SCHEDULER_THREAD is None or not _SCHEDULER_THREAD.is_alive():
        _SCHEDULER_THREAD = threading.Thread(target=_reminder_loop, daemon=True, name="KandorReminderScheduler")
        _SCHEDULER_THREAD.start()
        print("⏰ [Scheduler] Avviato thread di controllo promemoria ore (scatto automatico ogni giorno alle 17:00).")
