"""Script di build per Render - esegue installazione dipendenze e collectstatic in modo sicuro."""
import subprocess
import sys

print("\n==> 1/2 Installazione dipendenze...")
result_pip = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
if result_pip.returncode != 0:
    print(f"❌ ERRORE pip install: codice {result_pip.returncode}")
    sys.exit(result_pip.returncode)

print("\n==> 2/2 Raccolta file statici (collectstatic)...")
result_static = subprocess.run([sys.executable, "manage.py", "collectstatic", "--no-input"])
if result_static.returncode != 0:
    print(f"❌ ERRORE collectstatic: codice {result_static.returncode}")
    sys.exit(result_static.returncode)

# Esegui la migrazione DB in modo resiliente durante il build step
print("\n==> Tentativo di migrazione database pre-deploy...")
try:
    res_mig = subprocess.run([sys.executable, "manage.py", "migrate", "--no-input"])
    if res_mig.returncode == 0:
        print("   ✅ Migrazione pre-deploy completata con successo!")
    else:
        print("   ⚠️ Nota: Migrazione in build step terminata con avviso. Le tabelle verranno verificate all'avvio dell'app.")
except Exception as e:
    print(f"   ⚠️ Nota: Migrazione in build step saltata ({e}). Le tabelle verranno verificate all'avvio dell'app.")

print("\n==> Build completato con successo!")
sys.exit(0)
