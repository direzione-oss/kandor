# ============================================================
#  KANDOR — dev_push.ps1
#  Carica il DB locale (SQLite) su Supabase.
#  ⚠️  ATTENZIONE: sovrascrive i dati su Supabase!
#  USO: .\dev_push.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   KANDOR  —  Push DB verso Supabase      ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "⚠️  ATTENZIONE: i dati su Supabase verranno SOSTITUITI" -ForegroundColor Red
Write-Host "   con quelli del DB locale." -ForegroundColor Red
Write-Host ""
$confirm = Read-Host "Continuare? (scrivi SI per procedere)"
if ($confirm -ne "SI") {
    Write-Host "Operazione annullata." -ForegroundColor Yellow
    exit 0
}

# ── 1. Carica variabili .env ────────────────────────────────
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
            $name  = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host "✅ File .env caricato" -ForegroundColor Green
}

# ── 2. Verifica che il DB locale esista ─────────────────────
if (-not (Test-Path "db_local.sqlite3")) {
    Write-Host "❌ db_local.sqlite3 non trovato. Esegui prima .\dev_pull.ps1" -ForegroundColor Red
    exit 1
}

# ── 3. Export dal DB locale ──────────────────────────────────
Write-Host ""
Write-Host "📤 Export dati dal DB locale..." -ForegroundColor Yellow
$env:LOCAL_DEV = "1"

$pushFile = "db_push.json"
python manage.py dumpdata `
    --natural-foreign `
    --natural-primary `
    --exclude auth.permission `
    --exclude contenttypes `
    --indent 2 `
    -o $pushFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Errore dump locale." -ForegroundColor Red
    exit 1
}

$size = [math]::Round((Get-Item $pushFile).Length / 1KB, 1)
Write-Host "✅ Dump locale: $pushFile ($size KB)" -ForegroundColor Green

# ── 4. Passa a Supabase ──────────────────────────────────────
Write-Host ""
Write-Host "🔄 Connessione a Supabase..." -ForegroundColor Yellow
Remove-Item Env:LOCAL_DEV -ErrorAction SilentlyContinue

# ── 5. Backup di sicurezza prima del flush ───────────────────
Write-Host "💾 Backup Supabase prima del push..." -ForegroundColor Yellow
python manage.py dumpdata `
    --natural-foreign --natural-primary `
    --exclude auth.permission --exclude contenttypes `
    --indent 2 -o "db_backup_pre_push.json" 2>$null
Write-Host "✅ Backup salvato in db_backup_pre_push.json" -ForegroundColor Green

# ── 6. Flush e loaddata su Supabase ─────────────────────────
Write-Host ""
Write-Host "🗑️  Pulizia dati Supabase..." -ForegroundColor Yellow
python manage.py flush --no-input

Write-Host ""
Write-Host "📦 Caricamento dati su Supabase..." -ForegroundColor Yellow
python manage.py loaddata $pushFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Errore! Ripristino backup..." -ForegroundColor Red
    python manage.py flush --no-input
    python manage.py loaddata "db_backup_pre_push.json"
    Write-Host "✅ Dati originali ripristinati." -ForegroundColor Green
    exit 1
}

# ── 7. Pulizia file temporanei ───────────────────────────────
Remove-Item $pushFile -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   ✅  Push completato!                   ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "I dati locali sono ora su Supabase." -ForegroundColor White
Write-Host "Il sito su Render è aggiornato." -ForegroundColor White
Write-Host ""
