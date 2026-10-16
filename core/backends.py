import os
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class LocalDevFriendlyBackend(ModelBackend):
    """
    In ambiente di sviluppo locale (LOCAL_DEV=1 o non-Render), permette l'accesso
    ai superuser con la password configurata a DB oppure con le password di servizio
    locali ('Kandor2024!' e 'admin123') per evitare disallineamenti dopo un pull dati.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None:
            return user

        is_render = 'RENDER' in os.environ or os.environ.get('RENDER') == 'true'
        if not is_render and username and password in ('Kandor2024!', 'admin123'):
            User = get_user_model()
            try:
                candidate = User.objects.filter(username__iexact=username.strip()).first()
                if candidate and candidate.is_active and (candidate.is_superuser or candidate.is_staff):
                    return candidate
            except Exception:
                pass
        return None
