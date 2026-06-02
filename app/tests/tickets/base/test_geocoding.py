from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer
from eventyay.base.services import geo as geocoding


@pytest.fixture
@scopes_disabled()
def geocoding_event():
    organizer = Organizer.objects.create(name='Geo Organizer', slug='geo-org')
    return Event.objects.create(
        organizer=organizer,
        name='Geo Event',
        slug='geo-event',
        date_from=now() + timedelta(days=30),
        live=True,
    )


BANGKOK_ADDRESS = (
    'True Digital Park West, Soi Punnawithi 4, Bang Chak Subdistrict, '
    'Phra Khanong District, Bangkok, 10260, Thailand'
)
BANGKOK_COORDS = {'lat': 13.6989, 'lon': 100.5858}


class TestGeoCoordinateValidation:
    def test_cleans_multiline_addresses(self):
        assert geocoding.clean_address_query('Line one\nLine two') == 'Line one, Line two'

    def test_rejects_null_island(self):
        assert geocoding.is_valid_geo_coordinates(0, 0) is False

    def test_rejects_invalid_latitude(self):
        assert geocoding.is_valid_geo_coordinates(120, 10) is False

    def test_accepts_bangkok_coordinates(self):
        assert geocoding.is_valid_geo_coordinates(BANGKOK_COORDS['lat'], BANGKOK_COORDS['lon']) is True

    def test_normalizes_comma_decimal_separator(self):
        assert geocoding.is_valid_geo_coordinates('13,6989', '100,5858') is True


BANGKOK_FULL_ADDRESS = BANGKOK_ADDRESS


class TestGeocodeQueryCandidates:
    def test_builds_simplified_fallback_queries(self):
        candidates = geocoding.geocode_query_candidates(BANGKOK_FULL_ADDRESS)

        assert BANGKOK_FULL_ADDRESS in candidates
        assert 'True Digital Park West, Bangkok, Thailand' in candidates
        assert 'True Digital Park West, Thailand' in candidates


class TestGeocodeAddress:
    def test_uses_simplified_query_when_full_address_is_not_found(self):
        nominatim_result = [{'formatted': BANGKOK_FULL_ADDRESS, **BANGKOK_COORDS}]

        def fake_nominatim(query):
            if query == BANGKOK_FULL_ADDRESS:
                return []
            if query == 'True Digital Park West, Bangkok, Thailand':
                return nominatim_result
            return []

        with patch.object(geocoding, '_geocode_with_nominatim', side_effect=fake_nominatim):
            with patch.object(geocoding, 'GlobalSettingsObject') as gs_mock:
                gs_mock.return_value.settings.opencagedata_apikey = ''
                gs_mock.return_value.settings.mapquest_apikey = ''
                gs_mock.return_value.settings.nominatim_geocoding_enabled = False
                with patch.object(geocoding.cache, 'get', return_value=None):
                    results = geocoding.geocode_address(BANGKOK_FULL_ADDRESS)

        assert results == nominatim_result

    def test_falls_back_to_nominatim_when_opencage_returns_no_results(self):
        nominatim_result = [{'formatted': BANGKOK_FULL_ADDRESS, **BANGKOK_COORDS}]

        with patch.object(geocoding, '_geocode_with_opencage', return_value=[]):
            with patch.object(geocoding, '_geocode_with_nominatim', return_value=nominatim_result) as nominatim_mock:
                with patch.object(geocoding, 'GlobalSettingsObject') as gs_mock:
                    gs_mock.return_value.settings.opencagedata_apikey = 'test-key'
                    gs_mock.return_value.settings.mapquest_apikey = ''
                    gs_mock.return_value.settings.nominatim_geocoding_enabled = True
                    with patch.object(geocoding.cache, 'get', return_value=None):
                        results = geocoding.geocode_address(BANGKOK_FULL_ADDRESS)

        assert results == nominatim_result
        nominatim_mock.assert_called()

    def test_uses_nominatim_when_no_api_keys_configured(self):
        nominatim_result = [{'formatted': BANGKOK_ADDRESS, **BANGKOK_COORDS}]
        with patch.object(geocoding, '_geocode_with_nominatim', return_value=nominatim_result) as nominatim_mock:
            with patch.object(geocoding, 'GlobalSettingsObject') as gs_mock:
                gs_mock.return_value.settings.opencagedata_apikey = ''
                gs_mock.return_value.settings.mapquest_apikey = ''
                gs_mock.return_value.settings.nominatim_geocoding_enabled = False
                with patch.object(geocoding.cache, 'get', return_value=None):
                    results = geocoding.geocode_address(BANGKOK_ADDRESS)

        assert results == nominatim_result
        nominatim_mock.assert_called_once()

    def test_does_not_cache_empty_results(self):
        with patch.object(geocoding, '_geocode_with_configured_providers', return_value=[]):
            with patch.object(geocoding.cache, 'get', return_value=None):
                with patch.object(geocoding.cache, 'set') as cache_set_mock:
                    results = geocoding.geocode_address(BANGKOK_ADDRESS)

        assert results == []
        cache_set_mock.assert_not_called()

    def test_returns_cached_results_when_geocoding_unavailable(self):
        cached = [{'formatted': BANGKOK_ADDRESS, **BANGKOK_COORDS}]
        with patch.object(geocoding, 'geocoding_is_available', return_value=False):
            with patch.object(geocoding, '_geocode_with_configured_providers') as provider_mock:
                with patch.object(geocoding.cache, 'get', return_value=cached):
                    results = geocoding.geocode_address(BANGKOK_ADDRESS)

        assert results == cached
        provider_mock.assert_not_called()


class TestResolveVenueMapCoordinates:
    @pytest.mark.django_db
    def test_uses_stored_coordinates_when_valid(self, geocoding_event):
        geocoding_event.geo_lat = BANGKOK_COORDS['lat']
        geocoding_event.geo_lon = BANGKOK_COORDS['lon']
        geocoding_event.location = BANGKOK_ADDRESS

        with patch.object(geocoding, 'geocode_address') as geocode_mock:
            resolved = geocoding.resolve_venue_map_coordinates(geocoding_event)

        assert resolved == BANGKOK_COORDS
        geocode_mock.assert_not_called()

    @pytest.mark.django_db
    def test_geocodes_when_coordinates_are_null_island(self, geocoding_event):
        geocoding_event.geo_lat = 0
        geocoding_event.geo_lon = 0
        geocoding_event.location = BANGKOK_ADDRESS

        with patch.object(
            geocoding,
            'geocode_address',
            return_value=[{'formatted': BANGKOK_ADDRESS, **BANGKOK_COORDS}],
        ) as geocode_mock:
            resolved = geocoding.resolve_venue_map_coordinates(geocoding_event)

        assert resolved == BANGKOK_COORDS
        geocode_mock.assert_called_once_with(BANGKOK_ADDRESS)

    @pytest.mark.django_db
    def test_geocodes_when_coordinates_missing(self, geocoding_event):
        geocoding_event.geo_lat = None
        geocoding_event.geo_lon = None
        geocoding_event.location = BANGKOK_ADDRESS

        with patch.object(
            geocoding,
            'geocode_address',
            return_value=[{'formatted': BANGKOK_ADDRESS, **BANGKOK_COORDS}],
        ):
            resolved = geocoding.resolve_venue_map_coordinates(geocoding_event)

        assert resolved == BANGKOK_COORDS

    @pytest.mark.django_db
    def test_returns_none_when_geocoding_fails(self, geocoding_event):
        geocoding_event.geo_lat = None
        geocoding_event.geo_lon = None
        geocoding_event.location = BANGKOK_ADDRESS

        with patch.object(geocoding, 'geocode_address', return_value=[]):
            resolved = geocoding.resolve_venue_map_coordinates(geocoding_event)

        assert resolved is None

    @pytest.mark.django_db
    def test_returns_none_without_address_or_coordinates(self, geocoding_event):
        geocoding_event.geo_lat = None
        geocoding_event.geo_lon = None
        geocoding_event.location = None

        resolved = geocoding.resolve_venue_map_coordinates(geocoding_event)

        assert resolved is None
