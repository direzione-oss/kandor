"""
KANDOR — Avvio locale
Doppio click per avviare. Nessun terminale visibile.
Richiede: Python installato + progetto nella stessa cartella.
"""
import subprocess
import sys
import os
import time
import webbrowser
import threading
from pathlib import Path

# Cartella del progetto
BASE = Path(__file__).resolve().parent
os.chdir(BASE)

# Variabili ambiente per modalità locale
os.environ['LOCAL_DEV'] = '1'
os.environ['DEBUG'] = 'True'
os.environ['PYTHONUTF8'] = '1'

HIDE = subprocess.CREATE_NO_WINDOW  # Nessuna finestra nera

def log(msg):
    """Scrive su file di log invece del terminale."""
    with open(BASE / 'kandor_avvia.log', 'a', encoding='utf-8') as f:
        from datetime import datetime
        f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")


def run_hidden(cmd, env=None):
    """Esegue un comando senza mostrare finestre."""
    return subprocess.run(
        cmd,
        cwd=str(BASE),
        env=env or os.environ.copy(),
        creationflags=HIDE,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )


def wait_for_server(port=8000, timeout=15):
    """Aspetta che il server Django risponda."""
    import urllib.request
    import urllib.error
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1)
            return True
        except Exception:
            time.sleep(1)
    return False


log("=== Kandor avvio ===")

# 1. Installa dipendenze mancanti (solo se necessario)
req_file = BASE / 'requirements.txt'
if req_file.exists():
    log("Verifica dipendenze...")
    run_hidden([sys.executable, '-m', 'pip', 'install', '-r', str(req_file), '-q'])

# 2. Esegui migrazioni (veloce se già aggiornate)
log("Migrazione DB locale...")
result = run_hidden([sys.executable, 'manage.py', 'migrate', '--no-input'])
if result.returncode != 0:
    # Fallback: fake migration indici
    run_hidden([sys.executable, 'manage.py', 'migrate', 'core', '0040'])
    run_hidden([sys.executable, 'manage.py', 'migrate', 'core', '0041', '--fake'])
    run_hidden([sys.executable, 'manage.py', 'migrate', '--no-input'])
log("Migrazioni OK")

# 3. Avvia il server Django (nascosto)
log("Avvio server Django...")
server = subprocess.Popen(
    [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload'],
    cwd=str(BASE),
    env=os.environ.copy(),
    creationflags=HIDE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# 4. Aspetta che il server sia pronto
log("Attesa server...")
ok = wait_for_server()

# 5. Apri il browser
if ok:
    log("Server pronto — apertura browser")
    webbrowser.open('http://127.0.0.1:8000/dev-tools/')
else:
    log("ERRORE: server non risponde dopo 15 secondi")
    # Prova comunque ad aprire
    webbrowser.open('http://127.0.0.1:8000/dev-tools/')

# 6. Tieni il processo vivo finché il server gira
log("Server in esecuzione. Chiudi il browser quando finisci.")
server.wait()
log("Server fermato.")
