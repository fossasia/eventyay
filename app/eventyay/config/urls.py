import importlib.util

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.urls import re_path as url

import eventyay.control.urls
import eventyay.eventyay_common.urls
import eventyay.presale.urls
from eventyay.base.views import cachedfiles, csp, health, js_catalog, js_helpers, metrics, redirect
from eventyay.control.views import pages

base_patterns = [
    path(
        'download/<id>/',
        cachedfiles.DownloadView.as_view(),
        name='cachedfile.download',
    ),
    path('healthcheck/', health.healthcheck, name='healthcheck'),
    path('redirect/', redirect.redir_view, name='redirect'),
    path(
        'jsi18n/<slug:lang>/',
        js_catalog.js_catalog,
        name='javascript-catalog',
    ),
    path('metrics/', metrics.serve_metrics, name='metrics'),
    path('csp_report/', csp.csp_report, name='csp.report'),
    path('js_helpers/states/', js_helpers.states, name='js_helpers.states'),
    # path('api/v1/', include(('eventyay.api.urls', 'eventyayapi'), namespace='api-v1')),
    # path('api/', RedirectView.as_view(url='/api/v1/'), name='redirect-api-version'),
    path('accounts/', include('allauth.urls')),
]

control_patterns = [
    path('control/', include((eventyay.control.urls, 'control'))),
]

eventyay_common_patterns = [
    path('common/', include((eventyay.eventyay_common.urls, 'common'), namespace='common')),
]


page_patterns = [
    path('page/<slug:slug>/', pages.ShowPageView.as_view(), name='page'),
]

admin_patterns = [
    path('admin/', include(('eventyay.control.urls_admin', 'eventyay_admin'))),
]

orga_patterns = [
    path('orga/', include('eventyay.orga.urls')),
]

# Note: agenda and cfp patterns are now included under {organizer}/{event} in maindomain_urlconf.py
# They are no longer at the root level

debug_patterns = []

if settings.DEBUG and importlib.util.find_spec('debug_toolbar'):
    debug_patterns.append(path('__debug__/', include('debug_toolbar.urls')))
    debug_patterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

common_patterns = (
    base_patterns
    + control_patterns
    + debug_patterns
    + eventyay_common_patterns
    + page_patterns
    + admin_patterns
    + orga_patterns
)
