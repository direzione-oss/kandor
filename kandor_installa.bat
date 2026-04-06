@echo off
title Kandor — Installazione
cd /d "%~dp0"

echo.
echo  ==========================================
echo    KANDOR - Installazione (una tantum)
echo  ==========================================
echo.

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERRORE: Python non trovato!
    echo  Scarica Python da: https://www.python.org/downloads/
    echo  Assicurati di spuntare "Add Python to PATH" durante l'installazione.
    pause
    exit /b 1
)

echo  Python trovato. Installazione dipendenze...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo  ERRORE nell'installazione delle dipendenze.
    pause
    exit /b 1
)

echo.
echo  Creazione variabili di ambiente...
setx PYTHONUTF8 1 >nul

echo.
echo  ==========================================
echo    Installazione completata!
echo    D'ora in poi usa: kandor_avvia.pyw
echo  ==========================================
echo.
pause
