"""
URL configuration for cleanup_erp project.
"""
import traceback
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseServerError

def handler500(request, *args, **kwargs):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    return HttpResponseServerError(f"<h1>500 Internal Server Error</h1><pre>{tb_str}</pre>", content_type="text/html")

import sys

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
