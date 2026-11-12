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
