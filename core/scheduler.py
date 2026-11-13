import os
import threading
import time
from django.db import IntegrityError, transaction
from django.utils import timezone

_ULTIMO_INVIO_PROMEMORIA_DATA = None
_SCHEDULER_THREAD = None

JOB_PROMEMORIA_ORE_17 = 'promemoria_ore_17'


def acquisisci_lock_scheduler_giornaliero(job_name: str, target_date=None):
    """
    Acquisisce un lock atomico persistente su database per (job_name, target_date).
    Garantisce che anche con N worker Gunicorn o dopo un riavvio del container,
    un job giornaliero venga eseguito una sola volta per data.
    Ritorna (True, log_obj) se il worker corrente ha acquisito il lock,
    oppure (False, None) se un altro worker lo ha già acquisito.
    """
    if target_date is None:
        target_date = timezone.localtime(timezone.now()).date()

    from .models import SchedulerExecutionLog

    try:
        with transaction.atomic():
            log_obj = SchedulerExecutionLog.objects.create(
                job_name=job_name,
                execution_date=target_date,
                worker_pid=os.getpid(),
                details={'status': 'RUNNING'},
            )
            return True, log_obj
    except IntegrityError:
        return False, None


def esegui_promemoria_giornaliero_atomico(target_date=None, force: bool = False) -> dict:
    """
    Esegue l'invio del promemoria ore delle 17:00 acquisendo prima il lock DB.
    Se `force=True`, ignora il lock giornaliero (utile per invio manuale da dashboard).
    """
    global _ULTIMO_INVIO_PROMEMORIA_DATA
    if target_date is None:
        target_date = timezone.localtime(timezone.now()).date()

    log_obj = None
    if not force:
        acquired, log_obj = acquisisci_lock_scheduler_giornaliero(JOB_PROMEMORIA_ORE_17, target_date)
        if not acquired:
            _ULTIMO_INVIO_PROMEMORIA_DATA = target_date
            return {
                'inviati': 0,
                'errori': 0,
                'totale_mancanti': 0,
                'skipped_locked': True,
            }

    try:
        from .utils_kandor_chat import invia_promemoria_ore_mancanti
        res = invia_promemoria_ore_mancanti(only_check=False)
        _ULTIMO_INVIO_PROMEMORIA_DATA = target_date
        if log_obj is not None:
            log_obj.details = {
                'status': 'COMPLETED',
                'inviati': res.get('inviati', 0),
                'errori': res.get('errori', 0),
                'totale_mancanti': res.get('totale_mancanti', 0),
            }
            log_obj.save(update_fields=['details'])
        res['skipped_locked'] = False
        return res
    except Exception as exc:
        if log_obj is not None:
            log_obj.details = {'status': 'ERROR', 'error': str(exc)}
            log_obj.save(update_fields=['details'])
        raise


def _reminder_loop():
    global _ULTIMO_INVIO_PROMEMORIA_DATA
    while True:
        try:
            now = timezone.localtime(timezone.now())
            today = now.date()

            # L'avviso scatta alle ore 17:00 (tra le 17:00 e le 17:05 ora italiana)
            if now.hour == 17 and 0 <= now.minute <= 5:
                if _ULTIMO_INVIO_PROMEMORIA_DATA != today:
                    res = esegui_promemoria_giornaliero_atomico(target_date=today)
                    if not res.get('skipped_locked'):
                        print(
                            f"⏰ [Scheduler 17:00 PID={os.getpid()}] "
                            f"Inviati {res['inviati']} promemoria Telegram per il {today} (Errori: {res['errori']})."
                        )
        except Exception as e:
            print(f"⚠️ [Scheduler Error] {e}")

        time.sleep(30)


def start_scheduler():
    global _SCHEDULER_THREAD
    if _SCHEDULER_THREAD is None or not _SCHEDULER_THREAD.is_alive():
        _SCHEDULER_THREAD = threading.Thread(target=_reminder_loop, daemon=True, name="KandorReminderScheduler")
        _SCHEDULER_THREAD.start()
        print(f"⏰ [Scheduler PID={os.getpid()}] Avviato thread di controllo promemoria ore (lock atomico DB multi-worker attivo).")
