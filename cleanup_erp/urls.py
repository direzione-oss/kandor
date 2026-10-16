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
    """Vista di diagnostica DB per verificare lo stato di migrazione e auth su Render."""
    info = {}
    try:
        from django.db import connection
        from django.core.management import call_command
        from django.contrib.auth import get_user_model, authenticate

        db_settings = settings.DATABASES['default']
        info['engine'] = db_settings.get('ENGINE')
        info['host'] = db_settings.get('HOST')
        info['port'] = db_settings.get('PORT')

        connection.ensure_connection()
        info['connection'] = 'OK'

        # Migrazione
        call_command('migrate', interactive=False)
        info['migration_status'] = 'SUCCESS'

        # Superuser verification & creation
        User = get_user_model()
        users = list(User.objects.values_list('username', flat=True))
        info['users_count'] = len(users)
        info['usernames'] = users

        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'Kandor2024!')
            info['admin_user_action'] = 'CREATED'
        else:
            admin_user.set_password('Kandor2024!')
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.is_active = True
            admin_user.save()
            info['admin_user_action'] = 'RESET_PASSWORD'

        # Test auth
        auth_user = authenticate(request, username='admin', password='Kandor2024!')
        info['test_auth'] = 'SUCCESS' if auth_user else 'FAILED'

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
