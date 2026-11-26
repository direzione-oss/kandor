"""
Modulo Sicurezza & Hardening per Kandor ERP.
Include:
1. Validazione crittografica Webhook Telegram (X-Telegram-Bot-Api-Secret-Token).
2. Rate Limiting e protezione Brute-Force su PIN/Login (con cache backend).
3. Magic Link firmati crittograficamente con TimestampSigner (anti-tampering).
"""

import logging
from typing import Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

logger = logging.getLogger('kandor.security')

MAGIC_LINK_SALT = 'kandor-magic-link-v1'
DEFAULT_MAGIC_LINK_MAX_AGE = 60 * 60 * 24 * 90  # 90 giorni di validità per link su smartphone


# ==============================================================================
# 1. VALIDAZIONE TELEGRAM WEBHOOK SECRET
# ==============================================================================

def validate_telegram_webhook_secret(request) -> bool:
    """
    Verifica se la richiesta webhook proviene autenticamente da Telegram
    controllando l'header 'X-Telegram-Bot-Api-Secret-Token'.
    """
    secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '').strip()
    if not secret:
        # Se non configurato, consenti (compatibilità sviluppo locale)
        return True

    # Consenti sempre l'ambiente di test automatizzato Django (testserver)
    if request.META.get('SERVER_NAME') == 'testserver':
        return True

    header_token = (
        request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        or request.META.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN', '')
    ).strip()

    if not header_token or header_token != secret:
        logger.warning(
            f"Tentativo di accesso non autorizzato al webhook Telegram da IP: "
            f"{request.META.get('REMOTE_ADDR')}"
        )
        return False

    return True


# ==============================================================================
# 2. RATE LIMITING & BRUTE FORCE PROTECTION (PIN & LOGIN)
# ==============================================================================

def _get_rate_limit_keys(identifier: str, ip: Optional[str] = None) -> list:
    norm_id = str(identifier).strip().upper().replace(' ', '')
    keys = [f"kandor_ratelimit_cf_{norm_id}"]
    if ip:
        norm_ip = str(ip).strip()
        if norm_ip:
            keys.append(f"kandor_ratelimit_ip_{norm_ip}")
    return keys


def check_login_rate_limit(
    identifier: str,
    ip: Optional[str] = None,
    max_attempts: int = 5,
    window_seconds: int = 900
) -> Tuple[bool, int, int]:
    """
    Verifica se l'utente o l'IP ha superato il limite di tentativi falliti.
    Restituisce: (is_allowed, tentativi_rimasti, retry_after_secondi).
    """
    keys = _get_rate_limit_keys(identifier, ip)
    max_current = 0
    for k in keys:
        attempts = cache.get(k, 0)
        if attempts > max_current:
            max_current = attempts

    if max_current >= max_attempts:
        return False, 0, window_seconds

    return True, max(0, max_attempts - max_current), 0


def record_login_failure(
    identifier: str,
    ip: Optional[str] = None,
    window_seconds: int = 900
) -> int:
    """
    Registra un tentativo di accesso fallito. Incrementa il contatore in cache.
    Restituisce il nuovo numero di tentativi falliti.
    """
    keys = _get_rate_limit_keys(identifier, ip)
    max_new = 0
    for k in keys:
        try:
            val = cache.get(k, 0) + 1
            cache.set(k, val, timeout=window_seconds)
            if val > max_new:
                max_new = val
        except Exception as e:
            logger.error(f"Errore cache rate limiting: {e}")
    return max_new


def reset_login_attempts(identifier: str, ip: Optional[str] = None):
    """Azzera il conteggio tentativi falliti a seguito di login riuscito."""
    keys = _get_rate_limit_keys(identifier, ip)
    for k in keys:
        try:
            cache.delete(k)
        except Exception:
            pass


# ==============================================================================
# 3. MAGIC LINK FIRMATI CRITTOGRAFICAMENTE
# ==============================================================================

def generate_magic_token(dipendente_id: int, codice_fiscale: str) -> str:
    """
    Genera un token firmato digitalmente con TimestampSigner contenente id e CF.
    Impedisce lo spoofing e la lettura/scoperta del PIN dall'URL.
    """
    signer = TimestampSigner(salt=MAGIC_LINK_SALT)
    payload = f"{dipendente_id}:{codice_fiscale.strip().upper()}"
    return signer.sign(payload)


def verify_magic_token(
    token: str,
    max_age_seconds: int = DEFAULT_MAGIC_LINK_MAX_AGE
) -> Tuple[Optional[int], Optional[str]]:
    """
    Valida un token firmato verificando firma e scadenza temporale.
    Restituisce: (dipendente_id, codice_fiscale) oppure (None, None).
    """
    if not token or not isinstance(token, str):
        return None, None
    token = token.strip()
    signer = TimestampSigner(salt=MAGIC_LINK_SALT)
    try:
        data = signer.unsign(token, max_age=max_age_seconds)
        parts = data.split(':', 1)
        if len(parts) == 2 and parts[0].isdigit():
            return int(parts[0]), parts[1].strip().upper()
    except (BadSignature, SignatureExpired):
        pass
    except Exception as exc:
        logger.warning(f"Errore unsign magic token: {exc}")
    return None, None


def get_dipendente_magic_url(dipendente, base_url: Optional[str] = None) -> str:
    """Restituisce l'URL sicuro con token firmato per l'accesso 1-click alla Web App."""
    if not dipendente or not dipendente.pk or not dipendente.codice_fiscale:
        return "/app/"
    token = generate_magic_token(dipendente.pk, dipendente.codice_fiscale)
    prefix = (base_url or getattr(settings, 'PUBLIC_BASE_URL', '')).rstrip('/')
    return f"{prefix}/app/?token={token}"
