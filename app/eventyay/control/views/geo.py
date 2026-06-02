from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic.base import View

from eventyay.base.services.geo import clean_address_query, geocode_address, geocoding_is_available


class GeoCodeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query = self.request.GET.get('q')
        if not query:
            return JsonResponse({'success': False, 'results': []}, status=400)

        cleaned_query = clean_address_query(query)
        if not cleaned_query:
            return JsonResponse({'success': False, 'results': []}, status=400)

        results = geocode_address(cleaned_query)
        if not results:
            if not geocoding_is_available():
                return JsonResponse(
                    {'success': False, 'results': [], 'error': 'no_provider'},
                    status=200,
                )
            return JsonResponse(
                {'success': False, 'results': [], 'error': 'not_found'},
                status=200,
            )

        return JsonResponse({'success': True, 'results': results}, status=200)
