"""
KANDOR — Avvio locale
Doppio click per avviare. Nessun terminale visibile.
"""
import subprocess
import sys
import os
import time
import webbrowser
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# Cerca manage.py risalendo le cartelle (funziona anche da Desktop, Download, ecc.)
def find_project_root():
    # Prima prova: stessa cartella del .pyw
    base = Path(__file__).resolve().parent
    if (base / 'manage.py').exists():
        return base
    # Seconda prova: cartella Kandor nella home
    home_kandor = Path.home() / 'Kandor'
    if (home_kandor / 'manage.py').exists():
        return home_kandor
    # Terza prova: chiedi all'utente
    return None


BASE = find_project_root()

if BASE is None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Kandor — Errore",
        "Impossibile trovare il progetto Kandor.\n\n"
        "Assicurati che questo file sia nella cartella del progetto\n"
        "(dove si trova manage.py), oppure in C:\\Kandor\\"
    )
    sys.exit(1)

os.chdir(BASE)
LOG = BASE / 'kandor_avvia.log'

os.environ['LOCAL_DEV'] = '1'
os.environ['DEBUG'] = 'True'
os.environ['PYTHONUTF8'] = '1'

HIDE = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def log(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
    except Exception:
        pass


def show_error(msg):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Kandor — Errore di avvio", msg)
    root.destroy()


def run_hidden(cmd):
    return subprocess.run(
        cmd,
        cwd=str(BASE),
        env=os.environ.copy(),
        creationflags=HIDE,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )


def wait_for_server(port=8000, timeout=15):
    import urllib.request
    import urllib.error
    # Polling veloce ogni 0.2s (fino a 15s max)
    for _ in range(timeout * 5):
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:{port}/dev-tools/',
                headers={'User-Agent': 'KandorLauncher/1.0'}
            )
            with urllib.request.urlopen(req, timeout=1) as response:
                if response.status in (200, 301, 302, 404):
                    return True
        except urllib.error.HTTPError:
            # Qualsiasi risposta HTTP (200, 302, 404) indica che il server Django è già ATTIVO!
            return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


try:
    log("=== Kandor avvio ===")
    log(f"Cartella progetto: {BASE}")

    # Migrazioni (esegui solo se il DB non esiste per avvio fulmineo)
    db_file = BASE / 'db_local.sqlite3'
    if not db_file.exists():
        log("Inizializzazione DB locale...")
        result = run_hidden([sys.executable, 'manage.py', 'migrate', '--no-input'])
        if result.returncode != 0:
            log(f"Migrate fallito: {result.stderr[:500]}")
            run_hidden([sys.executable, 'manage.py', 'migrate', 'core', '0040'])
            run_hidden([sys.executable, 'manage.py', 'migrate', 'core', '0041', '--fake'])
            run_hidden([sys.executable, 'manage.py', 'migrate', '--no-input'])
        log("Migrazioni OK")
    else:
        log("DB locale trovato: avvio rapido (migrazioni saltate)")

    # Avvio server
    log("Avvio server Django...")
    server = subprocess.Popen(
        [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload'],
        cwd=str(BASE),
        env=os.environ.copy(),
        creationflags=HIDE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    log("Attesa server (max 25s)...")
    ok = wait_for_server(timeout=25)

    if ok:
        log("Server pronto — apertura browser")
        webbrowser.open('http://127.0.0.1:8000/dev-tools/')
    else:
        # Leggi l'errore dal server
        try:
            server.terminate()
            out, err = server.communicate(timeout=3)
            err_msg = (err or b'').decode('utf-8', errors='replace')[:800]
        except Exception:
            err_msg = "Server non risponde."
        log(f"ERRORE server: {err_msg}")
        show_error(
            f"Il server Kandor non è partito entro 20 secondi.\n\n"
            f"Errore:\n{err_msg}\n\n"
            f"Controlla il file kandor_avvia.log nella cartella del progetto."
        )
        sys.exit(1)

    log("Server in esecuzione.")
    server.wait()
    log("Server fermato.")

except Exception as e:
    log(f"ECCEZIONE: {e}")
    show_error(f"Errore imprevisto:\n{e}\n\nDettagli nel file kandor_avvia.log")
    sys.exit(1)
