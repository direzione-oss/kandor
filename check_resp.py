import subprocess

py_script = """
from core.models import Dipendente
from core.utils_kandor_chat import is_responsabile

print("ID | Dipendente | is_responsabile | riceve_notifiche | TG")
print("-" * 60)
for d in Dipendente.objects.filter(stato='ATTIVO').order_by('cognome'):
    resp = is_responsabile(d)
    notif = getattr(d, 'riceve_notifiche_messaggi', False)
    tg = bool(d.telegram_chat_id)
    print(f"{d.id:3d} | {d.cognome} {d.nome} | {resp} | {notif} | {tg}")
"""

ssh_cmd = "docker exec -i $(docker ps -qf name=kandor) python manage.py shell"
proc = subprocess.run(["ssh", "root@187.126.30.207", ssh_cmd], input=py_script, text=True, capture_output=True)
print("OUT:\n", proc.stdout)
print("ERR:\n", proc.stderr)
