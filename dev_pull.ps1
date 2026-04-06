# ============================================================
#  KANDOR — dev_pull.ps1
#  Scarica i dati da Supabase e avvia Django in locale.
#  USO: .\dev_pull.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   KANDOR  —  Pull DB da Supabase         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

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
} else {
    Write-Host "⚠️  File .env non trovato — le credenziali devono essere già nelle variabili d'ambiente" -ForegroundColor Yellow
}

# ── 2. Export da Supabase (connessione remota) ───────────────
Write-Host ""
Write-Host "📥 Download dati da Supabase..." -ForegroundColor Yellow

# Assicurati di NON usare LOCAL_DEV durante il dump
Remove-Item Env:LOCAL_DEV -ErrorAction SilentlyContinue

$dumpFile = "db_dump.json"
python manage.py dumpdata `
    --natural-foreign `
    --natural-primary `
    --exclude auth.permission `
    --exclude contenttypes `
    --indent 2 `
    -o $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Errore durante il dump da Supabase. Controlla la connessione." -ForegroundColor Red
    exit 1
}

$size = [math]::Round((Get-Item $dumpFile).Length / 1KB, 1)
Write-Host "✅ Dump completato: $dumpFile ($size KB)" -ForegroundColor Green

# ── 3. Passa a SQLite locale ─────────────────────────────────
Write-Host ""
Write-Host "🔄 Passaggio a modalità locale (SQLite)..." -ForegroundColor Yellow
$env:LOCAL_DEV = "1"

# Elimina SQLite vecchio se esiste
if (Test-Path "db_local.sqlite3") {
    Remove-Item "db_local.sqlite3"
    Write-Host "🗑️  DB locale precedente eliminato" -ForegroundColor Gray
}

# ── 4. Migrate e loaddata ────────────────────────────────────
Write-Host ""
Write-Host "🏗️  Creazione schema SQLite..." -ForegroundColor Yellow
python manage.py migrate --run-syncdb 2>&1 | Where-Object { $_ -notmatch "^No changes|^Apply" }

Write-Host ""
Write-Host "📦 Caricamento dati in SQLite..." -ForegroundColor Yellow
python manage.py loaddata $dumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Errore loaddata. Il file dump potrebbe avere formati incompatibili." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   ✅  DB locale pronto!                  ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Per avviare il server locale:" -ForegroundColor White
Write-Host '  $env:LOCAL_DEV="1"; python manage.py runserver' -ForegroundColor Cyan
Write-Host ""
Write-Host "Quando hai finito, carica le modifiche su Supabase con:" -ForegroundColor White
Write-Host "  .\dev_push.ps1" -ForegroundColor Cyan
Write-Host ""
