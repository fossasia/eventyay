import json
import logging
import os
from mimetypes import guess_type
from pathlib import Path
from typing import cast

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.views.generic import View
from django.views.static import serve as static_serve
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.base.models import Event  # Added for /video event context

WEBAPP_DIST_DIR = cast(Path, settings.STATIC_ROOT) / 'webapp'
logger = logging.getLogger(__name__)


def safe_reverse(name: str, **kw) -> str:
    try:
        return reverse(name, kwargs=kw) if kw else reverse(name)
    except NoReverseMatch as e:
        logger.warning('Video SPA: Could not reverse %s with %s: %s', name, kw, e)
        return '/missing-url-registration/'


class VideoSPAView(View):
    def get(self, request, *args, **kwargs):
        # Now expecting organizer and event from URL pattern: /{organizer}/{event}/video
        organizer_slug = kwargs.get('organizer')
        event_slug = kwargs.get('event')
        event_identifier = kwargs.get('event_identifier')

        # TODO remove debug logging once new video routing is stable
        event = None
        if organizer_slug and event_slug:
            try:
                event = Event.objects.select_related('organizer').get(slug=event_slug, organizer__slug=organizer_slug)
            except Event.DoesNotExist:
                return HttpResponse('Event not found', status=404)

        index_path = WEBAPP_DIST_DIR / 'index.html'
        if index_path.is_file():
            html_content = index_path.read_text()
        else:
            html_content = '<!-- /video build missing: {} -->'.format(index_path)

        base_href = '/video/'
        if event:
            # Inject window.venueless config (frontend still expects this name)
            # Mirror structure used in legacy live AppView but adjusted basePath

            # Quick fix: avoid reverse('api:root') which is currently not included -> NoReverseMatch
            api_base = f'/api/v1/events/{event.pk}/'  # TODO replace with reverse once API namespace wired

            # Best effort reverse for optional endpoints

            cfg = event.config or {}

            with scope(event=event):
                schedule = event.current_schedule or event.wip_schedule
                schedule_data = schedule.build_data(all_talks=False) if schedule else None

            base_path = event.urls.video_base.rstrip('/')
            base_href = event.urls.video_base
            injected = {
                'api': {
                    'base': api_base,
                    'socket': '{}://{}/ws/event/{}/'.format(
                        'wss' if request.is_secure() else 'ws',
                        request.get_host(),
                        event.pk,
                    ),
                    'upload': safe_reverse('storage:upload', event_id=event.pk) or '',
                    'scheduleImport': safe_reverse('storage:schedule_import', event_id=event.pk) or '',
                    'systemlog': safe_reverse('live:systemlog') or '',
                },
                'features': getattr(event, 'feature_flags', {}) or {},
                'externalAuthUrl': getattr(event, 'external_auth_url', None),
                'locale': event.locale,
                'date_locale': cfg.get('date_locale', 'en-ie'),
                'theme': cfg.get('theme', {}),
                'video_player': cfg.get('video_player', {}),
                'mux': cfg.get('mux', {}),
                'schedule': schedule_data,
                # Extra values expected by config.js/theme
                'basePath': base_path,
                'defaultLocale': 'en',
                'locales': ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
                'noThemeEndpoint': True,  # Prevent frontend from requesting missing /theme endpoint
            }

            class EventyayJSONEncoder(DjangoJSONEncoder):
                def default(self, obj):
                    if isinstance(obj, (Promise, LazyI18nString)):
                        return force_str(obj)
                    return super().default(obj)

            extra_script = f'<script>window.eventyay={json.dumps(injected, cls=EventyayJSONEncoder)}</script>'
            # Inject extra_script before the first <script ...> occurrence (handles attributes like type/src)
            lower_html = html_content.lower()
            before, sep, _ = lower_html.partition('<script ')
            if sep:
                idx = len(before)
                html_content = f'{html_content[:idx]}{extra_script}{html_content[idx:]}'
            else:
                html_content = f'{extra_script}{html_content}'

        elif event_identifier:
            # Event identifier provided but not found -> 404
            return HttpResponse('Event not found', status=404)

        if '<base ' not in html_content.lower():
            # Ensure assets resolve correctly regardless of nested route
            html_content = html_content.replace('<head>', f'<head><base href="{base_href}">', 1)

        resp = HttpResponse(html_content, content_type='text/html')
        resp._csp_ignore = True  # Disable CSP for SPA (relies on dynamic inline scripts)
        return resp


class VideoAssetView(View):
    def get(self, request, path='', *args, **kwargs):
        # Accept empty path -> index handling done by SPA view
        candidate_paths = (
            [
                os.path.join(WEBAPP_DIST_DIR, path),
                os.path.join(WEBAPP_DIST_DIR, 'assets', path),
            ]
            if path
            else []
        )
        for fp in candidate_paths:
            if os.path.isfile(fp):
                rel = os.path.relpath(fp, WEBAPP_DIST_DIR)
                resp = static_serve(request, rel, document_root=WEBAPP_DIST_DIR)
                resp._csp_ignore = True
                # Ensure proper content type for module scripts
                ctype, _ = guess_type(fp)
                if ctype:
                    resp['Content-Type'] = ctype
                return resp
        logger.warning('Video asset not found: %s', path)
        raise Http404()
