import importlib.util
import logging

from django.apps import apps
from django.urls import include, path, re_path

from eventyay.common.urls import OrganizerSlugConverter  # noqa: F401 (registers converter)

# Ticket-video integration: plugin URLs are auto-included via plugin handler below.
from eventyay.config.urls import common_patterns
from eventyay.multidomain.plugin_handler import plugin_event_urls
from eventyay.presale.urls import (
    event_patterns,
    locale_patterns,
    organizer_patterns,
)
from eventyay.presale.views.startpage import StartPageView

from .views import VideoAssetView, VideoSPAView, AnonymousInviteRedirectView

logger = logging.getLogger(__name__)


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
                        StartPageView.as_view(),
                        name='index',
                    ),
                ],
                'presale',
            )
        ),
    )
]

# Plugin URL registration strategy:
# - Auto-discover any installed plugin that provides EventyayPluginMeta and URLs.

raw_plugin_patterns = []

# Auto-register installed plugins with EventyayPluginMeta
for app in apps.get_app_configs():
    if hasattr(app, 'EventyayPluginMeta'):
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


plugin_patterns = [path('', include((raw_plugin_patterns, 'plugins')))]

# Add storage URLs for file uploads
storage_patterns = [
    path('storage/', include('eventyay.storage.urls', namespace='storage')),
]

# Add live URLs for video/BBB features (CSS endpoints, etc.)
live_patterns = [
    path('', include(('eventyay.features.live.urls', 'live'))),
]

unified_event_patterns = [
    path(
        '<orgslug:organizer>/<slug:event>/',
        include(
            [
                # Video patterns under {organizer}/{event}/video/
                # Match static assets with file extensions (js, css, png, etc.)
                re_path(r'^video/assets/(?P<path>.*)$', VideoAssetView.as_view(), name='video.assets'),
                re_path(
                    r'^video/(?P<path>[^?]*\.[a-zA-Z0-9._-]+)$',
                    VideoAssetView.as_view(),
                    name='video.assets.file',
                ),
                # The frontend Video SPA app is not served by Nginx so the Django view needs to
                # serve all paths under /video/ to allow client-side routing.
                # This catch-all must come after the asset pattern to allow SPA routes like /video/admin/rooms
                re_path(r'^video(?:/.*)?$', VideoSPAView.as_view(), name='video.spa'),
                path('', include(('eventyay.agenda.urls', 'agenda'))),
                path('', include(('eventyay.cfp.urls', 'cfp'))),
            ]
        ),
    ),
]

# Anonymous room invite short token pattern (6 characters)
# The token uses characters: abcdefghijklmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ123456789
# (excludes visually confusing characters: l, o, I, O, 0)
anonymous_invite_patterns = [
    re_path(
        r'^(?P<token>[a-km-np-zA-HJ-NP-Z1-9]{6})/?$',
        AnonymousInviteRedirectView.as_view(),
        name='anonymous.invite.redirect',
    ),
]

urlpatterns = (
    common_patterns
    + storage_patterns
    + live_patterns
    # The plugins patterns must be before presale_patterns_main
    # to avoid misdetection of plugin prefixes and organizer/event slugs.
    # Anonymous invite short token redirects (before presale to avoid slug conflict)
    + anonymous_invite_patterns
    + plugin_patterns
    + presale_patterns_main
    + unified_event_patterns
)

handler404 = 'eventyay.base.views.errors.page_not_found'
handler500 = 'eventyay.base.views.errors.server_error'
