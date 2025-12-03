import importlib.util
import json
import logging
import os
from mimetypes import guess_type

from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404, HttpResponse
from django.urls import include, path, re_path
from django.utils.encoding import force_str
from django.utils.functional import Promise
from django.views.generic import TemplateView, View
from django.views.static import serve as static_serve
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.base.models import Event  # Added for /video event context
from eventyay.cfp.views.event import EventStartpage
from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

# Ticket-video integration: plugin URLs are auto-included via plugin handler below.
from eventyay.config.urls import common_patterns
from eventyay.multidomain.plugin_handler import plugin_event_urls
from eventyay.presale.urls import (
    event_patterns,
    locale_patterns,
    organizer_patterns,
)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WEBAPP_DIST_DIR = os.path.normpath(os.path.join(BASE_DIR, 'static', 'webapp'))
logger = logging.getLogger(__name__)


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

        index_path = os.path.join(WEBAPP_DIST_DIR, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                content = f.read()
        else:
            content = '<!-- /video build missing: {} -->'.format(index_path)

        base_href = '/video/'
        if event:
            # Inject window.venueless config (frontend still expects this name)
            # Mirror structure used in legacy live AppView but adjusted basePath
            from django.urls import reverse

            # Quick fix: avoid reverse('api:root') which is currently not included -> NoReverseMatch
            api_base = f'/api/v1/events/{event.pk}/'  # TODO replace with reverse once API namespace wired

            # Best effort reverse for optional endpoints
            def safe_reverse(name, **kw):
                try:
                    return reverse(name, kwargs=kw) if kw else reverse(name)
                except Exception:
                    return None

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

            content = f'<script>window.eventyay={json.dumps(injected, cls=EventyayJSONEncoder)}</script>{content}'
        elif event_identifier:
            # Event identifier provided but not found -> 404
            return HttpResponse('Event not found', status=404)

        if '<base ' not in content.lower():
            # Ensure assets resolve correctly regardless of nested route
            content = content.replace('<head>', f'<head><base href="{base_href}">', 1)

        resp = HttpResponse(content, content_type='text/html')
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
        raise Http404()


presale_patterns_main = [
    path(
        '',
        include(
            (
                locale_patterns
                + [
                    path('<orgslug:organizer>/', include(organizer_patterns)),
                    path(
                        '<orgslug:organizer>/<slug:event>/',
                        include(event_patterns),
                    ),
                    path(
                        '',
                        TemplateView.as_view(template_name='pretixpresale/index.html'),
                        name='index',
                    ),
                ],
                'presale',
            )
        ),
    )
]

# Plugin URL registration strategy:
# - Local plugins (in eventyay.plugins.*): Dynamic discovery is safe because they're greppable
#   in the local codebase (eventyay/plugins/ directory).
# - External plugins (installed packages): Explicit registration for easier debugging and tracing.

raw_plugin_patterns = []

# Auto-register local plugins from eventyay.plugins.*
for app in apps.get_app_configs():
    if hasattr(app, 'EventyayPluginMeta') and app.name.startswith('eventyay.plugins.'):
        if importlib.util.find_spec(f'{app.name}.urls'):
            try:
                urlmod = importlib.import_module(f'{app.name}.urls')
                single_plugin_patterns = []
                if hasattr(urlmod, 'urlpatterns'):
                    single_plugin_patterns += urlmod.urlpatterns
                if hasattr(urlmod, 'event_patterns'):
                    patterns = plugin_event_urls(urlmod.event_patterns, plugin=app.name)
                    single_plugin_patterns.append(path('<orgslug:organizer>/<slug:event>/', include(patterns)))
                if hasattr(urlmod, 'organizer_patterns'):
                    patterns = urlmod.organizer_patterns
                    single_plugin_patterns.append(path('<orgslug:organizer>/', include(patterns)))
                raw_plugin_patterns.append(path('', include((single_plugin_patterns, app.label))))
                logger.debug('Registered URLs under "%s" namespace:\n%s', app.label, single_plugin_patterns)
            except (ImportError, AttributeError, TypeError):
                logger.exception('Error loading plugin URLs for %s', app.name)

# Explicit registration for external plugins (installed packages)
# Add external plugins here as they are installed and tested

# eventyay-paypal (always installed via pyproject.toml)
try:
    if importlib.util.find_spec('eventyay_paypal.urls'):
        urlmod = importlib.import_module('eventyay_paypal.urls')
        single_plugin_patterns = []
        if hasattr(urlmod, 'urlpatterns'):
            single_plugin_patterns += urlmod.urlpatterns
        if hasattr(urlmod, 'event_patterns'):
            patterns = plugin_event_urls(urlmod.event_patterns, plugin='eventyay_paypal')
            single_plugin_patterns.append(path('<orgslug:organizer>/<slug:event>/', include(patterns)))
        if hasattr(urlmod, 'organizer_patterns'):
            patterns = urlmod.organizer_patterns
            single_plugin_patterns.append(path('<orgslug:organizer>/', include(patterns)))
        raw_plugin_patterns.append(path('', include((single_plugin_patterns, 'eventyay_paypal'))))
        logger.debug('Registered URLs under "eventyay_paypal" namespace:\n%s', single_plugin_patterns)
except (ImportError, AttributeError, TypeError):
    logger.exception('Error loading plugin URLs for eventyay_paypal')

# eventyay-stripe (always installed via pyproject.toml)
try:
    if importlib.util.find_spec('eventyay_stripe.urls'):
        urlmod = importlib.import_module('eventyay_stripe.urls')
        single_plugin_patterns = []
        if hasattr(urlmod, 'urlpatterns'):
            single_plugin_patterns += urlmod.urlpatterns
        if hasattr(urlmod, 'event_patterns'):
            patterns = plugin_event_urls(urlmod.event_patterns, plugin='eventyay_stripe')
            single_plugin_patterns.append(path('<orgslug:organizer>/<slug:event>/', include(patterns)))
        if hasattr(urlmod, 'organizer_patterns'):
            patterns = urlmod.organizer_patterns
            single_plugin_patterns.append(path('<orgslug:organizer>/', include(patterns)))
        raw_plugin_patterns.append(path('', include((single_plugin_patterns, 'eventyay_stripe'))))
        logger.debug('Registered URLs under "eventyay_stripe" namespace:\n%s', single_plugin_patterns)
except (ImportError, AttributeError, TypeError):
    logger.exception('Error loading plugin URLs for eventyay_stripe')

# Fallback: include pretix_venueless plugin URLs even if lacking EventyayPluginMeta
# TODO: Do we really want this fallback?
try:
    if importlib.util.find_spec('pretix_venueless.urls'):
        urlmod = importlib.import_module('pretix_venueless.urls')
        single_plugin_patterns = []
        if hasattr(urlmod, 'urlpatterns'):
            single_plugin_patterns += urlmod.urlpatterns
        if hasattr(urlmod, 'event_patterns'):
            patterns = plugin_event_urls(urlmod.event_patterns, plugin='pretix_venueless')
            single_plugin_patterns.append(path('<orgslug:organizer>/<slug:event>/', include(patterns)))
        if hasattr(urlmod, 'organizer_patterns'):
            patterns = urlmod.organizer_patterns
            single_plugin_patterns.append(path('<orgslug:organizer>/', include(patterns)))
        raw_plugin_patterns.append(path('', include((single_plugin_patterns, 'pretix_venueless'))))
except (ImportError, AttributeError, TypeError):
    logger.exception('Error including pretix_venueless plugin URLs')

plugin_patterns = [path('', include((raw_plugin_patterns, 'plugins')))]

# Add storage URLs for file uploads
storage_patterns = [
    path('storage/', include('eventyay.storage.urls', namespace='storage')),
]

unified_event_patterns = [
    path(
        '<orgslug:organizer>/<slug:event>/',
        include(
            [
                # Video patterns under {organizer}/{event}/video/
                re_path(
                    r'^video/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$', VideoAssetView.as_view(), name='video.assets.file'
                ),
                path(
                    'video/<path:path>',
                    VideoAssetView.as_view(),
                    name='video.assets',
                ),
                # The frontend Video SPA app is not served by Nginx so the Django view needs to
                # serve all paths under /video/ to allow client-side routing.
                re_path(r'^video(?:/.*)?$', VideoSPAView.as_view(), name='video.spa'),
                path('talk/', EventStartpage.as_view(), name='event.talk'),
                path('', include(('eventyay.agenda.urls', 'agenda'))),
                path('', include(('eventyay.cfp.urls', 'cfp'))),
            ]
        ),
    ),
]

urlpatterns = (
    common_patterns
    + storage_patterns
    # The plugins patterns must be before presale_patterns_main
    # to avoid misdetection of plugin prefixes and organizer/event slugs.
    + plugin_patterns
    + presale_patterns_main
    + unified_event_patterns
)

handler404 = 'eventyay.base.views.errors.page_not_found'
handler500 = 'eventyay.base.views.errors.server_error'
