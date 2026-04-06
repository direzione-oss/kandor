# ============================================================
#  KANDOR - dev_push.ps1
#  Carica il DB locale (SQLite) su Supabase.
#  ATTENZIONE: sovrascrive i dati su Supabase!
#  USO: .\dev_push.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "===========================================" -ForegroundColor Magenta
Write-Host "  KANDOR - Push DB verso Supabase" -ForegroundColor Magenta
Write-Host "===========================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "ATTENZIONE: i dati su Supabase verranno SOSTITUITI" -ForegroundColor Red
Write-Host "con quelli del DB locale (db_local.sqlite3)." -ForegroundColor Red
Write-Host ""
$confirm = Read-Host "Continuare? (scrivi SI per procedere)"
if ($confirm -ne "SI") {
    Write-Host "Operazione annullata." -ForegroundColor Yellow
    exit 0
}

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
}

# --- 2. Verifica DB locale ---
if (-not (Test-Path "db_local.sqlite3")) {
    Write-Host "ERRORE: db_local.sqlite3 non trovato. Esegui prima .\dev_pull.ps1" -ForegroundColor Red
    exit 1
}

# --- 3. Export dal DB locale ---
Write-Host ""
Write-Host "Export dati dal DB locale..." -ForegroundColor Yellow
$env:LOCAL_DEV = "1"

# Forza Python in modalita UTF-8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pushFile = "db_push.json"
python manage.py dumpdata `
    --natural-foreign `
    --natural-primary `
    --exclude auth.permission `
    --exclude contenttypes `
    --indent 2 `
    -o $pushFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRORE nel dump locale." -ForegroundColor Red
    exit 1
}

$sizeKB = [math]::Round((Get-Item $pushFile).Length / 1KB, 1)
Write-Host ("OK: Dump locale -> " + $pushFile + " (" + $sizeKB + " KB)") -ForegroundColor Green

# --- 4. Passa a Supabase ---
Write-Host ""
Write-Host "Connessione a Supabase..." -ForegroundColor Yellow
Remove-Item Env:LOCAL_DEV -ErrorAction SilentlyContinue

# --- 5. Backup di sicurezza Supabase ---
Write-Host "Backup Supabase prima del push..." -ForegroundColor Yellow
python manage.py dumpdata `
    --natural-foreign --natural-primary `
    --exclude auth.permission --exclude contenttypes `
    --indent 2 -o "db_backup_pre_push.json"
Write-Host "OK: Backup salvato in db_backup_pre_push.json" -ForegroundColor Green

# --- 6. Flush e restore su Supabase ---
Write-Host ""
Write-Host "Pulizia dati Supabase..." -ForegroundColor Yellow
python manage.py flush --no-input

Write-Host ""
Write-Host "Caricamento dati su Supabase..." -ForegroundColor Yellow
python manage.py loaddata $pushFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRORE nel caricamento! Ripristino backup in corso..." -ForegroundColor Red
    python manage.py flush --no-input
    python manage.py loaddata "db_backup_pre_push.json"
    Write-Host "OK: Dati originali ripristinati da backup." -ForegroundColor Green
    exit 1
}

# --- 7. Pulizia ---
Remove-Item $pushFile -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "===========================================" -ForegroundColor Green
Write-Host "  Push completato con successo!" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""
Write-Host "I dati locali sono ora su Supabase." -ForegroundColor White
Write-Host "Il sito su Render e' aggiornato." -ForegroundColor White
Write-Host ""
