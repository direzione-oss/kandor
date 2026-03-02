from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import ssl
import certifi

def geocode_address(address):
    """
    Geocodes an address string to (latitude, longitude).
    Returns (None, None) on failure.
    """
    if not address:
        return None, None

    # Fix per SSL su Windows
    ctx = ssl.create_default_context(cafile=certifi.where())
    geolocator = Nominatim(user_agent="phantom_ionosphere_erp", ssl_context=ctx)
    
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            print(f"Geocoding SUCCESS: {address} -> {location.latitude}, {location.longitude}")
            return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding ERROR for address '{address}': {e}")
    except Exception as e:
        print(f"Geocoding GENERIC ERROR for '{address}': {e}")
    
    return None, None
