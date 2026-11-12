import traceback
import logging
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.utils.html import escape

logger = logging.getLogger(__name__)

class ExceptionTracebackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"[Kandor Exception Captured] Path: {request.path} | Error: {e}\n{tb}")
            
            # Messaggio errore sicuro (non espone dettagli DB interni in produzione)
            err_text = str(e)
            if 'UNIQUE constraint failed' in err_text or 'unique' in err_text.lower() or 'duplicate key' in err_text.lower():
                safe_err_text = "Dato duplicato o già presente a sistema."
            elif getattr(settings, 'DEBUG', False):
                safe_err_text = err_text
            else:
                safe_err_text = "Si è verificato un errore durante l'elaborazione della richiesta."

            # Se è una richiesta AJAX / API: restituisci JSON 400
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
                      request.content_type == 'application/json' or \
                      request.path.startswith('/api/')

            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'ok': False, 'error': safe_err_text}, status=400)

            # Se è un invio form POST dall'interfaccia/admin: rimani sulla pagina ed evidenzia l'errore
            if request.method == 'POST':
                try:
                    messages.error(
                        request,
                        f"⚠️ Impossibile salvare i dati: {safe_err_text} Verificare i campi inseriti e riprovare."
                    )
                except Exception:
                    pass

                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return HttpResponseRedirect(referer)

            if getattr(settings, 'DEBUG', False):
                return HttpResponse(
                    f"<html><body><h1>Django Runtime Exception Captured (DEBUG)</h1><pre>{escape(tb)}</pre></body></html>",
                    status=500
                )

            return HttpResponse(
                "<html><head><meta charset='utf-8'><title>Errore di Sistema — Kandor ERP</title></head>"
                "<body style='font-family:sans-serif;max-width:600px;margin:60px auto;padding:24px;border:1px solid #e2e8f0;border-radius:12px;'>"
                "<h2 style='color:#dc2626;margin-top:0;'>⚠️ Si è verificato un problema tecnico</h2>"
                "<p style='color:#334155;'>L'operazione non è andata a buon fine. L'anomalia è stata registrata automaticamente nei log di sistema.</p>"
                "<p><a href='/admin/' style='display:inline-block;background:#0f172a;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;'>Torna alla Dashboard</a></p>"
                "</body></html>",
                status=500
            )

    def process_exception(self, request, exception):
        return None
