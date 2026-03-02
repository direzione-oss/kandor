from django.urls import path
from .views import (
    find_jolly_view, reconciliation_view, generate_shifts_view,
    data_management_view, download_template_view, import_data_view,
    backup_db_view, restore_db_view, manuale_view,
    chat_simulator_view, telegram_webhook_view, toggle_telegram_status
)
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False)), # Redirect root to admin
    path('find-jolly/', find_jolly_view, name='find_jolly'),
    path('reconciliation/', reconciliation_view, name='reconciliation'),
    path('manuale/', manuale_view, name='manuale_utente'),
    path('generate-shifts/', generate_shifts_view, name='generate_shifts'),
    
    # Data Management
    path('data-management/', data_management_view, name='data_management'),
    path('data-management/download/<str:model_name>/', download_template_view, name='download_template'),
    path('data-management/import/', import_data_view, name='import_data'),
    path('data-management/backup/', backup_db_view, name='backup_db'),
    path('data-management/restore/', restore_db_view, name='restore_db'),
    
    # Chat & Telegram
    path('chat-simulator/', chat_simulator_view, name='chat_simulator'),
    path('telegram-webhook/', telegram_webhook_view, name='telegram_webhook'),
    path('telegram-toggle/<str:model_name>/<int:item_id>/', toggle_telegram_status, name='toggle_telegram_status'),
]
