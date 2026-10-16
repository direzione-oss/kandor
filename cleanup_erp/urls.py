"""
URL configuration for cleanup_erp project.
"""
import traceback
import sys
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseServerError, JsonResponse

def debug_db_view(request):
    """Vista di diagnostica DB per verificare lo stato di migrazione su Render."""
    info = {}
    try:
        from django.db import connection, connections, DEFAULT_DB_ALIAS
        from django.core.management import call_command

        db_settings = settings.DATABASES['default']
        info['engine'] = db_settings.get('ENGINE')
        info['host'] = db_settings.get('HOST')
        info['port'] = db_settings.get('PORT')
        info['name'] = db_settings.get('NAME')

        # Connessione
        connection.ensure_connection()
        info['connection'] = 'OK'

        # Tabelle esistenti
        tables = connection.introspection.table_names()
        info['tables_count'] = len(tables)
        info['has_django_session'] = 'django_session' in tables

        # Esegue migrazione
        call_command('migrate', interactive=False)
        info['migration_status'] = 'SUCCESS'

        # Re-check tabelle
        tables_after = connection.introspection.table_names()
        info['has_django_session_after'] = 'django_session' in tables_after

    except Exception as e:
        info['error'] = str(e)
        info['traceback'] = traceback.format_exc()

    return JsonResponse(info)

def handler500(request, *args, **kwargs):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    return HttpResponseServerError(f"<h1>500 Internal Server Error</h1><pre>{tb_str}</pre>", content_type="text/html")

handler500 = handler500

from core.views_cron import invia_auguri_cron_view

urlpatterns = [
    path('api/cron/invia-auguri/', invia_auguri_cron_view),
    path('debug-db/', debug_db_view),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
