import hashlib
import logging
from urllib.parse import quote_plus

import requests
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.views.generic.base import View

from eventyay.base.settings import GlobalSettingsObject


logger = logging.getLogger(__name__)


class GeoCodeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        q = self.request.GET.get('q')
        if not q:
            return JsonResponse({'success': False, 'results': []}, status=400)

        q_hash = hashlib.sha256(q.encode('utf-8')).hexdigest()
        cache_key = f'geocode:{q_hash}'
        cd = cache.get(cache_key)
        if cd is not None:
            return JsonResponse({'success': True, 'results': cd}, status=200)

        gs = GlobalSettingsObject()
        try:
            if gs.settings.opencagedata_apikey:
                res = self._use_opencage(q)
            elif gs.settings.mapquest_apikey:
                res = self._use_mapquest(q)
            elif gs.settings.nominatim_geocoding_enabled:
                res = self._use_nominatim(q)
            else:
                res = []
        except requests.RequestException:
            logger.exception('Geocoding failed')
            return JsonResponse({'success': False, 'results': []}, status=200)

        cache.set(cache_key, res, timeout=3600 * 6)
        return JsonResponse({'success': True, 'results': res}, status=200)

    def _use_opencage(self, q):
        gs = GlobalSettingsObject()

        r = requests.get(
            f'https://api.opencagedata.com/geocode/v1/json?q={quote_plus(q)}&key={gs.settings.opencagedata_apikey}',
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        res = [
            {
                'formatted': r['formatted'],
                'lat': r['geometry']['lat'],
                'lon': r['geometry']['lng'],
            }
            for r in d['results']
        ]
        return res

    def _use_mapquest(self, q):
        gs = GlobalSettingsObject()

        r = requests.get(
            f'https://www.mapquestapi.com/geocoding/v1/address?location={quote_plus(q)}&key={gs.settings.mapquest_apikey}',
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        res = [
            {
                'formatted': q,
                'lat': r['locations'][0]['latLng']['lat'],
                'lon': r['locations'][0]['latLng']['lng'],
            }
            for r in d['results']
        ]
        return res

    def _use_nominatim(self, q):
        r = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': q,
                'format': 'jsonv2',
                'limit': 5,
            },
            headers={
                'User-Agent': 'eventyay/1.0 (https://eventyay.com)',
            },
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        try:
            return [
                {
                    'formatted': result['display_name'],
                    'lat': float(result['lat']),
                    'lon': float(result['lon']),
                }
                for result in d
            ]
        except (KeyError, TypeError, ValueError):
            return []
