import hashlib
import os
import ssl
import threading
import certifi
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


GEOCODE_CACHE_TTL = 60 * 60 * 24 * 30  # 30 giorni


def _cache_key_for_address(address: str) -> str:
    norm = " ".join((address or "").strip().lower().split())
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:24]
    return f"geocode_coord_{digest}"


def get_cached_geocode(address: str):
    """Restituisce (lat, lon) dalla cache se l'indirizzo è già stato geocodificato, altrimenti None."""
    if not address or not address.strip():
        return None
    try:
        from django.core.cache import cache
        return cache.get(_cache_key_for_address(address))
    except Exception:
        return None


def geocode_address(address, timeout=5):
    """
    Geocodifica un indirizzo in (latitudine, longitudine) con cache persistente a 30 giorni.
    Ritorna (None, None) in caso di errore o timeout.
    """
    if not address or not address.strip():
        return None, None

    cached = get_cached_geocode(address)
    if cached and isinstance(cached, (tuple, list)) and len(cached) == 2:
        return cached[0], cached[1]

    ctx = ssl.create_default_context(cafile=certifi.where())
    geolocator = Nominatim(user_agent="kandor_erp_geocoder", ssl_context=ctx)

    try:
        location = geolocator.geocode(address, timeout=timeout)
        if location:
            coords = (float(location.latitude), float(location.longitude))
            try:
                from django.core.cache import cache
                cache.set(_cache_key_for_address(address), coords, GEOCODE_CACHE_TTL)
            except Exception:
                pass
            print(f"Geocoding SUCCESS: {address} -> {coords[0]}, {coords[1]}")
            return coords
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding ERROR for address '{address}': {e}")
    except Exception as e:
        print(f"Geocoding GENERIC ERROR for '{address}': {e}")

    return None, None


def _async_geocode_worker(model_cls, pk, address_field, address_value):
    """Worker eseguito in un thread daemon separato dopo il commit DB per non bloccare mai la richiesta HTTP."""
    from django.db import close_old_connections
    try:
        close_old_connections()
        lat, lon = geocode_address(address_value)
        if lat is not None and lon is not None:
            model_cls.objects.filter(pk=pk, **{address_field: address_value}).update(
                latitudine=lat,
                longitudine=lon,
            )
    except Exception as e:
        print(f"[AsyncGeocode] Errore aggiornamento coordinate per {model_cls.__name__}#{pk}: {e}")
    finally:
        try:
            close_old_connections()
        except Exception:
            pass


def schedule_async_geocode(model_cls, pk, address_field: str, address_value: str):
    """
    Pianifica il geocoding in background dopo il commit della transazione corrente
    (oppure in modo sincrono se SYNC_GEOCODING=1).
    """
    if not pk or not address_value or os.environ.get('SKIP_GEOCODING'):
        return

    if os.environ.get('SYNC_GEOCODING') == '1':
        _async_geocode_worker(model_cls, pk, address_field, address_value)
        return

    from django.db import transaction

    def _launch_thread():
        t = threading.Thread(
            target=_async_geocode_worker,
            args=(model_cls, pk, address_field, address_value),
            daemon=True,
            name=f"KandorGeocode-{model_cls.__name__}-{pk}",
        )
        t.start()

    try:
        transaction.on_commit(_launch_thread)
    except Exception:
        _launch_thread()
