@echo off
REM Ferma il server Kandor locale
taskkill /f /im python.exe /fi "WINDOWTITLE eq Kandor*" >nul 2>&1
REM Alternativa: ferma tutti i Python che ascoltano sulla porta 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %%a >nul 2>&1
echo Kandor server fermato.
timeout /t 2 /nobreak >nul
