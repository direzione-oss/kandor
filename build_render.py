"""Script di build per Render - esegue collectstatic e migrate."""
import subprocess
import sys

commands = [
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
    [sys.executable, "manage.py", "collectstatic", "--no-input"],
    [sys.executable, "manage.py", "migrate", "--no-input"],
]

for cmd in commands:
    print(f"\n==> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"ERRORE: comando fallito con codice {result.returncode}")
        sys.exit(result.returncode)

print("\n==> Build completato con successo!")
