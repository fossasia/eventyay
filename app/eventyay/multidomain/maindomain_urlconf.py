import importlib.util
import os

from django.apps import apps
from django.urls import include, path, re_path
from django.views.generic import TemplateView, View
from django.http import HttpResponse, Http404
from django.views.static import serve as static_serve
from django.conf import settings
from mimetypes import guess_type

# Ticket-video integration: plugin URLs are auto-included via plugin handler below.

from eventyay.config.urls import common_patterns
from eventyay.multidomain.plugin_handler import plugin_event_urls
from eventyay.multidomain import redirects
from eventyay.presale.urls import (
    event_patterns,
    locale_patterns,
    organizer_patterns,
)
from eventyay.base.models import Event  # Added for /video event context

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WEBAPP_DIST_DIR = os.path.normpath(os.path.join(BASE_DIR, 'static', 'webapp'))

EXCLUDED_LEGACY_PREFIXES = (
    "common",
    "control",
    "orga",
    "admin",
    "api",
    "video",
    "static",
    "media",
)

MATCHED_LEGACY_SUBPATHS = (
    "schedule",
    "talk",
    "speaker",
    "featured",
    "sneak",
    "cfp",
    "submit",
    "me",
    "login",
    "logout",
    "auth",
    "reset",
    "invitation",
    "online-video",
    "widgets",
    "static",
    "locale",
    "sw\\.js",
)

EXCLUDED_LEGACY_PREFIXES_REGEX = "|".join(EXCLUDED_LEGACY_PREFIXES)
MATCHED_LEGACY_SUBPATHS_REGEX = "|".join(MATCHED_LEGACY_SUBPATHS)

class VideoSPAView(View):
    def get(self, request, *args, **kwargs):
        # Now expecting organizer and event from URL pattern: /{organizer}/{event}/video
        organizer_slug = kwargs.get('organizer')
        event_slug = kwargs.get('event')
        
        # TODO remove debug logging once new video routing is stable
        event = None
        if organizer_slug and event_slug:
            try:
                event = Event.objects.select_related('organizer').get(
                    slug=event_slug,
                    organizer__slug=organizer_slug
                )
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
            api_base = f"/api/v1/events/{event.pk}/"  # TODO replace with reverse once API namespace wired
            # Best effort reverse for optional endpoints
            def safe_reverse(name, **kw):
                try:
                    return reverse(name, kwargs=kw) if kw else reverse(name)
                except Exception:
                    return None
            cfg = event.config or {}
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
                # Extra values expected by config.js/theme
                'basePath': base_path,
                'defaultLocale': 'en',
                'locales': ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
                'noThemeEndpoint': True,  # Prevent frontend from requesting missing /theme endpoint
            }
            # Always prepend to guarantee execution before any module scripts
            import json as _json
            serialized = _json.dumps(injected)
            content = f"<script>window.eventyay={serialized};window.venueless={serialized};</script>{content}"
            if '<base ' not in content.lower():
                content = content.replace('<head>', f'<head><base href="{base_href}">', 1)
        elif '<base ' not in content.lower():
            # Legacy plain /video should still load SPA; ensure assets resolve correctly
            content = content.replace('<head>', f'<head><base href="{base_href}">', 1)
        
        resp = HttpResponse(content, content_type='text/html')
        resp._csp_ignore = True  # Disable CSP for SPA (relies on dynamic inline scripts)
        return resp

class VideoAssetView(View):
    def get(self, request, path='', *args, **kwargs):
        # Accept empty path -> index handling done by SPA view
        candidate_paths = [
            os.path.join(WEBAPP_DIST_DIR, path),
            os.path.join(WEBAPP_DIST_DIR, 'assets', path),
        ] if path else []
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
                    re_path(r'^(?P<organizer>[^/]+)/', include(organizer_patterns)),
                    re_path(
                        r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/',
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

raw_plugin_patterns = []
for app in apps.get_app_configs():
    if hasattr(app, 'EventyayPluginMeta'):
        if importlib.util.find_spec(app.name + '.urls'):
            urlmod = importlib.import_module(app.name + '.urls')
            single_plugin_patterns = []
            if hasattr(urlmod, 'urlpatterns'):
                single_plugin_patterns += urlmod.urlpatterns
            if hasattr(urlmod, 'event_patterns'):
                patterns = plugin_event_urls(urlmod.event_patterns, plugin=app.name)
                single_plugin_patterns.append(
                    re_path(r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/', include(patterns))
                )
            if hasattr(urlmod, 'organizer_patterns'):
                patterns = urlmod.organizer_patterns
                single_plugin_patterns.append(
                    re_path(r'^(?P<organizer>[^/]+)/', include(patterns))
                )
            raw_plugin_patterns.append(path('', include((single_plugin_patterns, app.label))))

# Fallback: include pretix_venueless plugin URLs even if lacking EventyayPluginMeta
try:
    if importlib.util.find_spec('pretix_venueless.urls'):
        urlmod = importlib.import_module('pretix_venueless.urls')
        single_plugin_patterns = []
        if hasattr(urlmod, 'urlpatterns'):
            single_plugin_patterns += urlmod.urlpatterns
        if hasattr(urlmod, 'event_patterns'):
            patterns = plugin_event_urls(urlmod.event_patterns, plugin='pretix_venueless')
            single_plugin_patterns.append(
                re_path(r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/', include(patterns))
            )
        if hasattr(urlmod, 'organizer_patterns'):
            patterns = urlmod.organizer_patterns
            single_plugin_patterns.append(
                re_path(r'^(?P<organizer>[^/]+)/', include(patterns))
            )
        raw_plugin_patterns.append(path('', include((single_plugin_patterns, 'pretix_venueless'))))
except Exception:
    pass

plugin_patterns = [path('', include((raw_plugin_patterns, 'plugins')))]

# Add storage URLs for file uploads
storage_patterns = [
    path('storage/', include('eventyay.storage.urls', namespace='storage')),
]

unified_event_patterns = [
    re_path(
        r'^(?P<organizer>[^/]+)/(?P<event>[^/]+)/',
        include(
            [
                # Video patterns under {organizer}/{event}/video/
                re_path(r'^video/assets/(?P<path>.*)$', VideoAssetView.as_view(), name='video.assets'),
                re_path(
                    r'^video/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$',
                    VideoAssetView.as_view(),
                    name='video.assets.file',
                ),
                re_path(r'^video(?:/.*)?$', VideoSPAView.as_view(), name='video.spa'),
                path('', include(('eventyay.agenda.urls', 'agenda'))),
                path('', include(('eventyay.cfp.urls', 'cfp'))),
            ]
        ),
    ),
]

# Legacy redirect patterns for backward compatibility
legacy_redirect_patterns = [
    # Legacy standalone video SPA at /video
    re_path(r'^video/assets/(?P<path>.*)$', VideoAssetView.as_view(), name='video.legacy.assets'),
    re_path(
        r'^video/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$',
        VideoAssetView.as_view(),
        name='video.legacy.assets.file',
    ),
    re_path(r'^video/?$', VideoSPAView.as_view(), name='video.legacy.index'),
    # Legacy video URLs: /video/<event_identifier> -> /{organizer}/{event}/video
    re_path(
        r'^video/(?P<event_identifier>(?!assets)[^/]+)(?:/.*)?$',
        redirects.legacy_video_redirect,
        name='video.legacy.redirect',
    ),
    # Legacy talk URLs: /<event>/(path) -> /{organizer}/{event}/(path)
    # This excludes known top-level namespaces before treating the first segment as an event slug.
    re_path(
        rf'^(?!(?:{EXCLUDED_LEGACY_PREFIXES_REGEX})/)(?P<event_slug>[^/]+)/({MATCHED_LEGACY_SUBPATHS_REGEX})(?:/|$)',
        redirects.legacy_talk_redirect,
        name='talk.legacy.redirect',
    ),
    # Legacy event base URL: /<event>/ -> /{organizer}/{event}/
    re_path(
        rf'^(?!(?:{EXCLUDED_LEGACY_PREFIXES_REGEX})/)(?P<event_slug>[^/]+)/$',
        redirects.legacy_talk_redirect,
        name='talk.legacy.base.redirect',
    ),
]

urlpatterns = (
    common_patterns
    + storage_patterns
    + legacy_redirect_patterns
    + presale_patterns_main
    + unified_event_patterns
    + plugin_patterns
)

handler404 = 'eventyay.base.views.errors.page_not_found'
handler500 = 'eventyay.base.views.errors.server_error'
