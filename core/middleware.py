import traceback
from django.http import HttpResponse

class ExceptionTracebackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as e:
            tb = traceback.format_exc()
            return HttpResponse(
                f"<html><body><h1>Django Runtime Exception Captured</h1><pre>{tb}</pre></body></html>",
                status=500
            )

    def process_exception(self, request, exception):
        tb = traceback.format_exc()
        return HttpResponse(
            f"<html><body><h1>Django Process Exception Captured</h1><pre>{tb}</pre></body></html>",
            status=500
        )
