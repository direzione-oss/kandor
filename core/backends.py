import os
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class LocalDevFriendlyBackend(ModelBackend):
    """
    Esclusivamente in ambiente di sviluppo locale (LOCAL_DEV=1 e non VPS_PROD/RENDER),
    permette l'accesso ai superuser con la password configurata a DB oppure con le
    password di servizio locali per evitare disallineamenti dopo un pull dati.
    Disattivato rigorosamente in produzione (VPS Coolify).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is not None:
            return user

        is_prod = (
            os.environ.get('VPS_PROD') in ('1', 'true', 'True')
            or 'RENDER' in os.environ
            or os.environ.get('RENDER') == 'true'
        )
        is_explicit_local = os.environ.get('LOCAL_DEV', '').strip() == '1'

        if is_explicit_local and not is_prod and username and password in ('Kandor2024!', 'admin123'):
            User = get_user_model()
            try:
                candidate = User.objects.filter(username__iexact=username.strip()).first()
                if candidate and candidate.is_active and (candidate.is_superuser or candidate.is_staff):
                    return candidate
            except Exception:
                pass
        return None
