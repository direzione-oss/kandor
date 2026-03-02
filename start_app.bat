@echo off
echo ========================================================
echo   Kandor - Gestionale
echo ========================================================
echo.
echo Avvio del server e del Bot Telegram in corso...
echo Una volta pronto, il browser si aprira' automaticamente.
echo.
echo Per chiudere tutto: Chiudi le finestre aperte.
echo.

start "Kandor Server" cmd /c "python manage.py runserver && pause"
start "Kandor Telegram Bot" cmd /c "python manage.py run_telegram_bot && pause"

timeout /t 5 >nul
start "" "http://127.0.0.1:8000/admin/"
exit
