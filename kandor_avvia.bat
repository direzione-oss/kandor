@echo off
title Kandor — Server Locale
cd /d "C:\Users\serra\.gemini\antigravity\playground\phantom-ionosphere"

set LOCAL_DEV=1
set DEBUG=True
set PYTHONUTF8=1

echo.
echo  ==========================================
echo    KANDOR - Avvio server locale
echo  ==========================================
echo.

REM Esegui le migrazioni (crea il DB se non esiste, altrimenti veloce)
echo  Preparazione database locale...
python manage.py migrate >nul 2>&1

REM Avvia il server in una finestra minimizzata separata
echo  Avvio server...
start /min "Kandor Server — tieni aperto" cmd /k "cd /d C:\Users\serra\.gemini\antigravity\playground\phantom-ionosphere && set LOCAL_DEV=1 && set DEBUG=True && set PYTHONUTF8=1 && python manage.py runserver"

REM Aspetta che il server sia pronto (8 secondi per sicurezza)
timeout /t 8 /nobreak >nul

REM Apri il browser
echo  Apertura browser...
start http://127.0.0.1:8000/dev-tools/

echo.
echo  Il server e' avviato in una finestra separata (minimizzata).
echo  Chiudi quella finestra quando hai finito di lavorare.
echo.
timeout /t 4 /nobreak >nul
