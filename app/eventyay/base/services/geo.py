import hashlib
import logging
import math
from urllib.parse import quote_plus

import requests
from django.conf import settings
from django.core.cache import cache

from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.utils.language import localize_event_text


logger = logging.getLogger(__name__)

NULL_ISLAND_EPSILON = 1e-6


def clean_address_query(address: str) -> str:
    return ' '.join(address.replace('\n', ', ').split())


def normalize_coordinate(value) -> float | None:
    if value is None or value == '':
        return None
    try:
        coordinate = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None
    if math.isnan(coordinate) or math.isinf(coordinate):
        return None
    return coordinate


def is_valid_geo_coordinates(lat, lon) -> bool:
    lat_value = normalize_coordinate(lat)
    lon_value = normalize_coordinate(lon)
    if lat_value is None or lon_value is None:
        return False
    if lat_value < -90 or lat_value > 90:
        return False
    if lon_value < -180 or lon_value > 180:
        return False
    if abs(lat_value) < NULL_ISLAND_EPSILON and abs(lon_value) < NULL_ISLAND_EPSILON:
        return False
    return True


def clip_geo_coordinates(lat: float, lon: float) -> tuple[float, float]:
    clipped_lat = min(max(lat, -90), 90)
    clipped_lon = min(max(lon, -180), 180)
    return clipped_lat, clipped_lon


def get_localized_location(location) -> str | None:
    if not location:
        return None
    localized = localize_event_text(location)
    if localized is None:
        return None
    cleaned = clean_address_query(str(localized).strip())
    return cleaned or None


def _can_use_nominatim(gs: GlobalSettingsObject) -> bool:
    if not gs.settings.opencagedata_apikey and not gs.settings.mapquest_apikey:
        return True
    return gs.settings.nominatim_geocoding_enabled


def geocoding_is_available() -> bool:
    gs = GlobalSettingsObject()
    return bool(
        gs.settings.opencagedata_apikey
        or gs.settings.mapquest_apikey
        or _can_use_nominatim(gs)
    )


def geocode_query_candidates(query: str) -> list[str]:
    """Build progressively simpler queries when a full address is not found."""
    cleaned_query = clean_address_query(query)
    if not cleaned_query:
        return []

    parts = [part.strip() for part in cleaned_query.split(',') if part.strip()]
    candidates = [cleaned_query]

    if len(parts) >= 4:
        candidates.append(', '.join([parts[0], parts[-3], parts[-1]]))
    if len(parts) >= 3:
        candidates.append(', '.join([parts[0], parts[-2], parts[-1]]))
        candidates.append(' '.join([parts[0], parts[-2], parts[-1]]))
    if len(parts) >= 2:
        candidates.append(', '.join([parts[0], parts[-1]]))

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique_candidates.append(candidate)
    return unique_candidates


def geocode_address(query: str) -> list[dict]:
    cleaned_query = clean_address_query(query)
    if not cleaned_query:
        return []

    query_hash = hashlib.sha256(cleaned_query.encode('utf-8')).hexdigest()
    cache_key = f'geocode:v2:{query_hash}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if not geocoding_is_available():
        return []

    gs = GlobalSettingsObject()
    try:
        results = _geocode_with_configured_providers(cleaned_query, gs)
    except (requests.RequestException, ValueError):
        logger.exception('Geocoding failed for query %r', cleaned_query)
        results = []

    if results:
        cache.set(cache_key, results, timeout=3600 * 6)
    return results


def _geocode_with_configured_providers(query: str, gs: GlobalSettingsObject) -> list[dict]:
    providers = []
    if gs.settings.opencagedata_apikey:
        api_key = gs.settings.opencagedata_apikey

        def opencage_provider(candidate_query, key=api_key):
            return _geocode_with_opencage(candidate_query, key)

        providers.append(opencage_provider)
    if gs.settings.mapquest_apikey:
        api_key = gs.settings.mapquest_apikey

        def mapquest_provider(candidate_query, key=api_key):
            return _geocode_with_mapquest(candidate_query, key)

        providers.append(mapquest_provider)
    if _can_use_nominatim(gs):
        providers.append(_geocode_with_nominatim)
    elif providers:
        providers.append(_geocode_with_nominatim)

    for candidate_query in geocode_query_candidates(query):
        for provider in providers:
            results = provider(candidate_query)
            if results:
                return results
    return []


def resolve_venue_map_coordinates(venue) -> dict[str, float] | None:
    """Resolve map coordinates for an Event or SubEvent.

    Stored coordinates are preferred when valid. Otherwise the localized venue
    address is geocoded. Returns None when no usable coordinates can be found.
    """
    if is_valid_geo_coordinates(venue.geo_lat, venue.geo_lon):
        lat, lon = clip_geo_coordinates(
            normalize_coordinate(venue.geo_lat),
            normalize_coordinate(venue.geo_lon),
        )
        return {'lat': lat, 'lon': lon}

    address = get_localized_location(venue.location)
    if not address:
        return None

    results = geocode_address(address)
    if not results:
        return None

    first = results[0]
    if not is_valid_geo_coordinates(first.get('lat'), first.get('lon')):
        return None

    lat, lon = clip_geo_coordinates(
        normalize_coordinate(first['lat']),
        normalize_coordinate(first['lon']),
    )
    return {'lat': lat, 'lon': lon}


def _geocode_with_opencage(query: str, api_key: str) -> list[dict]:
    response = requests.get(
        f'https://api.opencagedata.com/geocode/v1/json?q={quote_plus(query)}&key={api_key}',
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        return [
            {
                'formatted': result['formatted'],
                'lat': result['geometry']['lat'],
                'lon': result['geometry']['lng'],
            }
            for result in payload['results']
        ]
    except (KeyError, TypeError, ValueError):
        return []


def _geocode_with_mapquest(query: str, api_key: str) -> list[dict]:
    response = requests.get(
        f'https://www.mapquestapi.com/geocoding/v1/address?location={quote_plus(query)}&key={api_key}',
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        return [
            {
                'formatted': query,
                'lat': result['locations'][0]['latLng']['lat'],
                'lon': result['locations'][0]['latLng']['lng'],
            }
            for result in payload['results']
        ]
    except (KeyError, TypeError, ValueError, IndexError):
        return []


def _geocode_with_nominatim(query: str) -> list[dict]:
    response = requests.get(
        'https://nominatim.openstreetmap.org/search',
        params={
            'q': query,
            'format': 'jsonv2',
            'limit': 5,
        },
        headers={
            'User-Agent': f'{settings.INSTANCE_NAME}/1.0 ({settings.SITE_URL})',
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    try:
        return [
            {
                'formatted': result['display_name'],
                'lat': float(result['lat']),
                'lon': float(result['lon']),
            }
            for result in payload
        ]
    except (KeyError, TypeError, ValueError):
        return []
