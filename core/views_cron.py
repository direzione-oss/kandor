from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from django.conf import settings
import os
import hmac

def invia_auguri_cron_view(request):
    # Usa un token fisso (o da variabile d'ambiente) per proteggere l'endpoint
    expected_token = (os.environ.get("CRON_TOKEN") or "kandor_cron_secure_auguri_2026").strip()
    provided_token = (request.GET.get("token") or "").strip()
    
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        return HttpResponse("Unauthorized", status=401)
    
    try:
        call_command('invia_auguri')
        return JsonResponse({"status": "success", "message": "Auguri inviati con successo."})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def api_cron_run_tasks_view(request):
    """Esegue tutti i job periodici e lo scheduler via HTTP con token di sicurezza."""
    expected_token = (os.environ.get("CRON_TOKEN") or "kandor_cron_secure_auguri_2026").strip()
    provided_token = (request.GET.get("token") or "").strip()
    
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        return HttpResponse("Unauthorized", status=401)
    
    from .scheduler import esegui_tutti_i_job_pianificati
    is_force = request.GET.get("force") == "1"
    try:
        res = esegui_tutti_i_job_pianificati(force=is_force)
        return JsonResponse({"ok": True, "results": res})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def api_task_status_view(request, task_id):
    """Restituisce lo stato corrente di avanzamento di un task asincrono in background."""
    from .tasks import get_task_status
    status_data = get_task_status(task_id)
    return JsonResponse(status_data)

