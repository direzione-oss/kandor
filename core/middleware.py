import traceback
import logging
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.contrib import messages

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
            
            # Se è una richiesta AJAX / API: restituisci JSON 400
            is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or \
                      request.content_type == 'application/json' or \
                      request.path.startswith('/api/')

            if is_ajax:
                return JsonResponse({'status': 'error', 'success': False, 'error': str(e)}, status=400)

            # Se è un invio form POST dall'interfaccia/admin: rimani sulla pagina ed evidenzia l'errore
            if request.method == 'POST':
                try:
                    err_text = str(e)
                    if 'UNIQUE constraint failed' in err_text or 'unique' in err_text.lower():
                        err_text = "Dato duplicato o già presente a sistema."
                    messages.error(
                        request,
                        f"⚠️ Impossibile salvare i dati: {err_text}. Verificare i campi inseriti e riprovare."
                    )
                except Exception:
                    pass

                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return HttpResponseRedirect(referer)

            return HttpResponse(
                f"<html><body><h1>Django Runtime Exception Captured</h1><pre>{tb}</pre></body></html>",
                status=500
            )

    def process_exception(self, request, exception):
        return None
