# ============================================================
#  KANDOR - dev_pull.ps1
#  Scarica i dati da Supabase e avvia Django in locale.
#  USO: .\dev_pull.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==========================================="-ForegroundColor Cyan
Write-Host "  KANDOR - Pull DB da Supabase" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Carica variabili .env ---
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $key   = $parts[0].Trim()
            $val   = $parts[1].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
    Write-Host "OK: File .env caricato" -ForegroundColor Green
} else {
    Write-Host "AVVISO: File .env non trovato" -ForegroundColor Yellow
}

# Assicurati di usare Supabase per il dump
Remove-Item Env:LOCAL_DEV -ErrorAction SilentlyContinue
$env:USE_POSTGRES = "1"

# --- 2. Export da Supabase ---
Write-Host ""
Write-Host "Download dati da Supabase..." -ForegroundColor Yellow

# Forza Python in modalita UTF-8 (necessario su Windows con caratteri speciali)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$dumpFile = "db_dump.json"

python manage.py dumpdata `
    --natural-foreign `
    --natural-primary `
    --exclude auth.permission `
    --exclude contenttypes `
    --indent 2 `
    -o $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRORE durante il dump. Controlla la connessione a Supabase." -ForegroundColor Red
    exit 1
}

$sizeKB = [math]::Round((Get-Item $dumpFile).Length / 1KB, 1)
Write-Host ("OK: Dump completato -> " + $dumpFile + " (" + $sizeKB + " KB)") -ForegroundColor Green

# --- 3. Passa a SQLite locale ---
Write-Host ""
Write-Host "Passaggio a modalita locale (SQLite)..." -ForegroundColor Yellow
$env:LOCAL_DEV = "1"
$env:USE_POSTGRES = "0"

if (Test-Path "db_local.sqlite3") {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*manage.py*" -or $_.CommandLine -like "*runserver*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Remove-Item "db_local.sqlite3" -Force -ErrorAction SilentlyContinue
    Write-Host "DB locale precedente eliminato" -ForegroundColor Gray
}

# --- 4. Migrate e loaddata ---
Write-Host ""
Write-Host "Creazione schema SQLite..." -ForegroundColor Yellow

python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Alcune migration non compatibili con SQLite. Applico --fake sugli indici..." -ForegroundColor Yellow
    # 0041 contiene solo indici di performance, sicuro farlo --fake in locale
    python manage.py migrate core 0040
    python manage.py migrate core 0041 --fake
    python manage.py migrate
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRORE: migrate fallito anche con il fallback." -ForegroundColor Red
        exit 1
    }
}
Write-Host "OK: Schema creato" -ForegroundColor Green

Write-Host ""
Write-Host "Caricamento dati in SQLite..." -ForegroundColor Yellow
$env:SKIP_GEOCODING = "1"
python manage.py loaddata $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRORE loaddata. Prova con --exclude su modelli problematici." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  DB locale pronto!" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Per avviare il server locale esegui:" -ForegroundColor White
Write-Host '  $env:LOCAL_DEV="1"; python manage.py runserver' -ForegroundColor Cyan
Write-Host ""
Write-Host "Quando hai finito, carica le modifiche con:" -ForegroundColor White
Write-Host "  .\dev_push.ps1" -ForegroundColor Cyan
Write-Host ""
