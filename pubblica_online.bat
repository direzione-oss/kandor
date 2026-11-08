@echo off
title Kandor ERP — Pubblicazione Modifiche su VPS (Coolify)
cd /d "%~dp0"
if not exist "manage.py" (
    if exist "%USERPROFILE%\Kandor\manage.py" (
        cd /d "%USERPROFILE%\Kandor"
    )
)

echo.
echo  ============================================================
echo    KANDOR ERP - Pubblicazione su VPS (187.126.30.207)
echo    URL: https://kandor.187.126.30.207.sslip.io
echo  ============================================================
echo.

git status -s

echo.
set /p MSG="Inserisci una breve descrizione delle modifiche (invio per default): "

if "%MSG%"=="" (
    set MSG=Aggiornamento programma Kandor su VPS
)

echo.
echo  1/3 Aggiunta file modificati...
git add -A

echo  2/3 Creazione commit e invio a GitHub...
git commit -m "%MSG%"
git push origin main

echo  3/3 Avvio deploy automatico su VPS Coolify...
ssh root@187.126.30.207 "/root/deploy_app.sh kandor000000000000000001"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo  ============================================================
    echo    SUCCESS: Modifiche inviate e deploy avviato sulla VPS!
    echo    Sito online: https://kandor.187.126.30.207.sslip.io
    echo  ============================================================
) else (
    echo.
    echo  [ERRORE] Invio o deploy fallito.
)

echo.
pause
