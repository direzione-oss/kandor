"""
Motore di Task Asincroni e Code di Lavoro in Background per Kandor ERP.
Permette l'esecuzione non-bloccante di operazioni I/O-intensive:
- Invio massivo e broadcasting di messaggi e PDF su Telegram
- Elaborazioni e generazioni PDF voluminosi
- Chiamate IA esterne (Gemini API)
- Pulizia e sync dati asincroni
"""

import os
import uuid
import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('kandor.tasks')

# Pool dedicato di worker in background (non blocca i thread HTTP di Gunicorn)
_TASK_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix='KandorBgWorker')

TASK_STATUS_PENDING = 'PENDING'
TASK_STATUS_RUNNING = 'RUNNING'
TASK_STATUS_SUCCESS = 'SUCCESS'
TASK_STATUS_FAILURE = 'FAILURE'


def _run_task_wrapper(task_id: str, task_name: str, func: Callable, args: tuple, kwargs: dict):
    from .models import SchedulerExecutionLog

    start_time = time.time()
    logger.info(f"🚀 [Task {task_id}] Avvio esecuzione: {task_name}")

    state = {
        'task_id': task_id,
        'name': task_name,
        'status': TASK_STATUS_RUNNING,
        'started_at': timezone.now().isoformat(),
        'progress': 0,
        'result': None,
        'error': None,
    }
    cache.set(f"kandor_task_{task_id}", state, timeout=3600)

    try:
        result = func(*args, **kwargs)
        duration = round(time.time() - start_time, 2)
        state.update({
            'status': TASK_STATUS_SUCCESS,
            'progress': 100,
            'finished_at': timezone.now().isoformat(),
            'duration_seconds': duration,
            'result': result if isinstance(result, (dict, list, str, int, float, bool)) else str(result),
        })
        cache.set(f"kandor_task_{task_id}", state, timeout=3600)
        logger.info(f"✅ [Task {task_id}] Completato con successo in {duration}s")

        # Persistenza opzionale su SchedulerExecutionLog per audit
        try:
            today = timezone.localtime(timezone.now()).date()
            SchedulerExecutionLog.objects.create(
                job_name=f"task:{task_name[:50]}",
                execution_date=today,
                worker_pid=os.getpid(),
                details={
                    'task_id': task_id,
                    'status': TASK_STATUS_SUCCESS,
                    'duration_seconds': duration,
                    'result': state['result'],
                }
            )
        except Exception:
            pass

    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        err_msg = str(exc)
        tb = traceback.format_exc()
        logger.error(f"❌ [Task {task_id}] Fallito dopo {duration}s: {err_msg}\n{tb}")

        state.update({
            'status': TASK_STATUS_FAILURE,
            'finished_at': timezone.now().isoformat(),
            'duration_seconds': duration,
            'error': err_msg,
        })
        cache.set(f"kandor_task_{task_id}", state, timeout=3600)


def enqueue_task(func: Callable, *args, task_name: Optional[str] = None, **kwargs) -> str:
    """
    Inserisce un'operazione nella coda asincrona di background.
    Restituisce un ID univoco (task_id) per monitorarne lo stato.
    Se TASKS_ALWAYS_EAGER=True (es. nei test unitari), esegue sincronamente.
    """
    task_id = str(uuid.uuid4())
    name = task_name or getattr(func, '__name__', 'unnamed_task')

    init_state = {
        'task_id': task_id,
        'name': name,
        'status': TASK_STATUS_PENDING,
        'created_at': timezone.now().isoformat(),
        'progress': 0,
        'result': None,
        'error': None,
    }
    cache.set(f"kandor_task_{task_id}", init_state, timeout=3600)

    # In modalità test unitari, esegui subito senza thread separato se configurato
    is_eager = getattr(settings, 'TASKS_ALWAYS_EAGER', False)
    if is_eager:
        _run_task_wrapper(task_id, name, func, args, kwargs)
    else:
        _TASK_EXECUTOR.submit(_run_task_wrapper, task_id, name, func, args, kwargs)

    return task_id


def get_task_status(task_id: str) -> Dict[str, Any]:
    """Restituisce lo stato corrente di un task dato il suo ID."""
    state = cache.get(f"kandor_task_{task_id}")
    if not state:
        return {
            'task_id': task_id,
            'status': 'NOT_FOUND',
            'error': 'Task non trovato o scaduto dalla cache.',
        }
    return state


def update_task_progress(task_id: str, progress: int, message: Optional[str] = None):
    """Permette alla funzione in esecuzione di aggiornare la percentuale di avanzamento."""
    state = cache.get(f"kandor_task_{task_id}")
    if state:
        state['progress'] = min(100, max(0, progress))
        if message:
            state['message'] = message
        cache.set(f"kandor_task_{task_id}", state, timeout=3600)
