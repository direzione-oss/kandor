# ============================================================
#  KANDOR - dev_run.ps1
#  Avvia il server Django in locale (dopo aver eseguito dev_pull.ps1)
#  USO: .\dev_run.ps1
# ============================================================

Set-Location $PSScriptRoot

if (-not (Test-Path "db_local.sqlite3")) {
    Write-Host "ATTENZIONE: db_local.sqlite3 non trovato." -ForegroundColor Red
    Write-Host "Esegui prima: .\dev_pull.ps1" -ForegroundColor Yellow
    exit 1
}

$env:LOCAL_DEV = "1"
$env:DEBUG = "1"
$env:PYTHONUTF8 = "1"

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  KANDOR - Server locale" -ForegroundColor Green
Write-Host "  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  Usa Ctrl+C per fermare il server" -ForegroundColor Gray
Write-Host ""

python manage.py runserver
