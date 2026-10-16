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

from core.views import debug_db_view

def handler500(request, *args, **kwargs):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    return HttpResponseServerError(f"<h1>500 Internal Server Error</h1><pre>{tb_str}</pre>", content_type="text/html")

handler500 = handler500

from core.views_cron import invia_auguri_cron_view

def ping_view(request):
    return JsonResponse({'status': 'ok', 'message': 'gunicorn is alive'})

def ping_db_view(request):
    import traceback
    from django.db import connection
    from django.conf import settings
    res = {
        'engine': settings.DATABASES['default'].get('ENGINE'),
        'host': settings.DATABASES['default'].get('HOST'),
        'port': settings.DATABASES['default'].get('PORT'),
        'name': str(settings.DATABASES['default'].get('NAME')),
    }
    try:
        connection.ensure_connection()
        res['db_connection'] = 'SUCCESS'
    except Exception as e:
        res['db_connection'] = 'FAILED'
        res['error'] = str(e)
        res['traceback'] = traceback.format_exc()
    return JsonResponse(res)

def test_admin_debug_view(request):
    import traceback
    from django.contrib.auth import get_user_model
    from django.http import JsonResponse
    
    User = get_user_model()
    admin_user = User.objects.filter(username='admin').first()
    request.user = admin_user
    
    steps = {}
    try:
        steps['1_user'] = str(admin_user)
        
        from core.templatetags.dashboard_extras import (
            expiring_vehicles_widget, upcoming_birthdays_widget,
            weekly_schedule_widget, telegram_feed_widget, expiring_contracts_widget
        )
        
        try:
            expiring_vehicles_widget()
            steps['widget_expiring_vehicles'] = 'OK'
        except Exception as e:
            steps['widget_expiring_vehicles'] = f"ERR: {e}"
            
        try:
            upcoming_birthdays_widget()
            steps['widget_upcoming_birthdays'] = 'OK'
        except Exception as e:
            steps['widget_upcoming_birthdays'] = f"ERR: {e}"
            
        try:
            weekly_schedule_widget({'request': request})
            steps['widget_weekly_schedule'] = 'OK'
        except Exception as e:
            steps['widget_weekly_schedule'] = f"ERR: {e}"
            
        try:
            telegram_feed_widget()
            steps['widget_telegram_feed'] = 'OK'
        except Exception as e:
            steps['widget_telegram_feed'] = f"ERR: {e}"
            
        try:
            expiring_contracts_widget()
            steps['widget_expiring_contracts'] = 'OK'
        except Exception as e:
            steps['widget_expiring_contracts'] = f"ERR: {e}"
            
        try:
            rendered = admin.site.index(request)
            steps['admin_site_index'] = f"OK status {rendered.status_code}"
        except Exception as e:
            steps['admin_site_index'] = f"ERR: {e}\n{traceback.format_exc()}"

    except Exception as e:
        steps['catastrophic_error'] = f"{e}\n{traceback.format_exc()}"
        
    return JsonResponse(steps)

urlpatterns = [
    path('ping/', ping_view),
    path('ping-db/', ping_db_view),
    path('test-admin-debug/', test_admin_debug_view),
    path('api/cron/invia-auguri/', invia_auguri_cron_view),
    path('debug-db/', debug_db_view),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
