@echo off
title Kandor — Pubblicazione Modifiche Online (Render)
cd /d "%~dp0"
if not exist "manage.py" (
    if exist "%USERPROFILE%\Kandor\manage.py" (
        cd /d "%USERPROFILE%\Kandor"
    )
)

echo.
echo  ============================================================
echo    KANDOR - Pubblicazione Modifiche su Render (Produzione)
echo  ============================================================
echo.

git status -s

echo.
set /p MSG="Inserisci una breve descrizione delle modifiche (invio per default): "

if "%MSG%"=="" (
    set MSG=Aggiornamento programma Kandor
)

echo.
echo  1/3 Aggiunta file modificati...
git add .

echo  2/3 Creazione commit...
git commit -m "%MSG%"

echo  3/3 Invio aggiornamenti a GitHub e Render...
git push origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo  ============================================================
    echo    SUCCESS: Modifiche inviate con successo!
    echo    Render aggiornera automaticamente il sito online
    echo    (kandor.onrender.com) in circa 1-2 minuti, applicando
    echo    anche le nuove migrazioni del database senza perdere dati.
    echo  ============================================================
) else (
    echo.
    echo  [ERRORE] Invio fallito. Controlla la connessione o eventuali conflitti Git.
)

echo.
pause
