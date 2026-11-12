"""
URL configuration for cleanup_erp project.
"""
import traceback
import sys
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseServerError, JsonResponse

from core.views import debug_db_view

def handler500(request, *args, **kwargs):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    sys.stderr.write(f"\n[KANDOR 500 ERROR] {request.method} {request.path}\n{tb_str}\n")
    sys.stderr.flush()
    if settings.DEBUG:
        return HttpResponseServerError(f"<h1>500 Internal Server Error</h1><pre>{tb_str}</pre>", content_type="text/html")
    return HttpResponseServerError(
        "<h1>500 — Errore Interno del Server</h1>"
        "<p>Si è verificato un problema temporaneo. L'errore è stato registrato nei log di sistema.</p>",
        content_type="text/html"
    )

handler500 = handler500

from core.views_cron import invia_auguri_cron_view

def ping_view(request):
    return JsonResponse({'status': 'ok', 'message': 'gunicorn is alive'})

def ping_db_view(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'error': 'Accesso negato: privilegi di superuser richiesti.'}, status=403)
    import traceback
    from django.db import connection
    from django.conf import settings
    res = {
        'engine': settings.DATABASES['default'].get('ENGINE'),
    }
    try:
        connection.ensure_connection()
        res['db_connection'] = 'SUCCESS'
    except Exception as e:
        res['db_connection'] = 'FAILED'
        res['error'] = str(e)
        if settings.DEBUG:
            res['traceback'] = traceback.format_exc()
    return JsonResponse(res)

def test_admin_debug_view(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'error': 'Accesso negato: privilegi di superuser richiesti.'}, status=403)
    step = request.GET.get('step', '0')
    import traceback
    res = {'requested_step': step}
    try:
        if step == '0':
            res['status'] = 'Step 0 OK - View reached'
        elif step == '1':
            from django.contrib.auth import get_user_model
            User = get_user_model()
            res['status'] = 'Step 1 OK - User model loaded'
        elif step == '2':
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.filter(username='admin').first()
            res['status'] = f"Step 2 OK - Admin user query done: {admin_user}"
        elif step == '3':
            from core.models import Cliente, Dipendente, Turno
            res['status'] = f"Step 3 OK - Models count: clients={Cliente.objects.count()}, dip={Dipendente.objects.count()}, turni={Turno.objects.count()}"
        elif step == '4':
            from core.templatetags.dashboard_extras import expiring_vehicles_widget
            res['widget'] = expiring_vehicles_widget()
            res['status'] = "Step 4 OK - expiring_vehicles_widget"
        elif step == '5':
            from core.templatetags.dashboard_extras import upcoming_birthdays_widget
            res['widget'] = upcoming_birthdays_widget()
            res['status'] = "Step 5 OK - upcoming_birthdays_widget"
        elif step == '6':
            from core.templatetags.dashboard_extras import weekly_schedule_widget
            res['widget_keys'] = list(weekly_schedule_widget({'request': request}).keys())
            res['status'] = "Step 6 OK - weekly_schedule_widget"
        elif step == '7':
            from core.templatetags.dashboard_extras import telegram_feed_widget
            res['widget_keys'] = list(telegram_feed_widget().keys())
            res['status'] = "Step 7 OK - telegram_feed_widget"
        elif step == '8':
            from core.templatetags.dashboard_extras import expiring_contracts_widget
            res['widget_keys'] = list(expiring_contracts_widget().keys())
            res['status'] = "Step 8 OK - expiring_contracts_widget"
        elif step == '9':
            from django.contrib import admin
            res['admin_index_status'] = admin.site.index(request).status_code
            res['status'] = "Step 9 OK - admin.site.index rendered"
        elif step == '10':
            res['status'] = "Step 10 Disabled for security"
        elif step == '11':
            from django.contrib import admin
            from django.template.response import TemplateResponse
            response = admin.site.index(request)
            if isinstance(response, TemplateResponse):
                response.render()
                res['content_len'] = len(response.content)
                res['status'] = "Step 11 OK - admin.site.index rendered completely"
            else:
                res['status'] = f"Step 11 - response was non-template: {response.status_code}"
        elif step == '12':
            from django.template.loader import render_to_string
            from core.templatetags.dashboard_extras import telegram_feed_widget
            ctx = telegram_feed_widget()
            html = render_to_string('admin/widgets/telegram_feed_widget.html', ctx)
            res['status'] = f"Step 12 OK - telegram_feed_widget rendered ({len(html)} bytes)"
        elif step == '13':
            from django.template.loader import render_to_string
            from core.templatetags.dashboard_extras import expiring_vehicles_widget
            ctx = expiring_vehicles_widget()
            html = render_to_string('admin/widgets/expiring_vehicles_widget.html', ctx)
            res['status'] = f"Step 13 OK - expiring_vehicles_widget rendered ({len(html)} bytes)"
        elif step == '14':
            from django.template.loader import render_to_string
            from core.templatetags.dashboard_extras import upcoming_birthdays_widget
            ctx = upcoming_birthdays_widget()
            html = render_to_string('admin/widgets/upcoming_birthdays_widget.html', ctx)
            res['status'] = f"Step 14 OK - upcoming_birthdays_widget rendered ({len(html)} bytes)"
        elif step == '15':
            from django.template.loader import render_to_string
            from core.templatetags.dashboard_extras import expiring_contracts_widget
            ctx = expiring_contracts_widget()
            html = render_to_string('admin/widgets/expiring_contracts_widget.html', ctx)
            res['status'] = f"Step 15 OK - expiring_contracts_widget rendered ({len(html)} bytes)"
        elif step == '16':
            from django.template.loader import render_to_string
            from core.templatetags.dashboard_extras import weekly_schedule_widget
            ctx = weekly_schedule_widget({'request': request})
            html = render_to_string('admin/widgets/weekly_schedule_widget.html', ctx)
            res['status'] = f"Step 16 OK - weekly_schedule_widget rendered ({len(html)} bytes)"
        else:
            res['status'] = "Unknown step"
    except Exception as e:
        res['error'] = str(e)
        if settings.DEBUG:
            res['traceback'] = traceback.format_exc()
    return JsonResponse(res)

urlpatterns = [
    path('ping/', ping_view),
    path('ping-db/', ping_db_view),
    path('test-admin-debug/', test_admin_debug_view),
    path('api/cron/invia-auguri/', invia_auguri_cron_view),
    path('debug-db/', debug_db_view),
    path('admin/', admin.site.urls),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
