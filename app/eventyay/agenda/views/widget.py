import hashlib
import os
from urllib.parse import unquote

from csp.decorators import csp_exempt
from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from eventyay.common.views import conditional_cache_page
from eventyay.talk_rules.agenda import is_widget_visible
from eventyay.talk_rules.submission import (
    are_featured_submissions_visible,
    schedule_widget_featured_cache_key_part,
)


WIDGET_JS_CHECKSUM = None
WIDGET_JS_MTIME = None
WIDGET_PATH = 'schedule/pretalx-schedule.js'


def color_etag(request, organizer=None, event=None, **kwargs):
    parts = [
        request.event.visible_primary_color or '',
        request.event.settings.get('header_background_color') or '',
        request.event.settings.get('header_text_color') or '',
        request.event.settings.get('navigation_text_color') or '',
    ]
    return '|'.join(parts) if any(parts) else 'none'


def widget_js_etag(request, organizer=None, event=None, **kwargs):
    # The widget is stable across all events, we just return a checksum of the JS file
    # to make sure clients reload the widget when it changes.
    global WIDGET_JS_CHECKSUM, WIDGET_JS_MTIME
    file_path = finders.find(WIDGET_PATH)
    if not file_path:
        return 'missing'

    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return 'missing'

    if WIDGET_JS_CHECKSUM is None or WIDGET_JS_MTIME != mtime:
        with open(file_path, encoding='utf-8') as fp:
            WIDGET_JS_CHECKSUM = hashlib.md5(fp.read().encode()).hexdigest()
        WIDGET_JS_MTIME = mtime
    return WIDGET_JS_CHECKSUM


def is_public_and_versioned(request, organizer=None, event=None, version=None, **kwargs):
    if version and version == 'wip':
        # We never cache the wip schedule
        return False
    if not is_widget_visible(None, request.event):
        # This will be either a 404, or a page only accessible to the user
        # due to their logged-in status, so we don't want to cache it.
        return False
    return True


def version_prefix(request, organizer=None, event=None, version=None, **kwargs):
    """On non-versioned pages, invalidate cache on schedule release and featured-setting changes."""
    featured_part = schedule_widget_featured_cache_key_part(request.event)
    if not version and request.event.current_schedule:
        return f'{request.event.current_schedule.version}-{featured_part}'
    if version:
        return f'{version}-{featured_part}'
    return f'nov-{featured_part}'


@conditional_cache_page(
    60,
    key_prefix=version_prefix,
    condition=is_public_and_versioned,
    server_timeout=5 * 60,
    headers={
        'Access-Control-Allow-Headers': 'authorization,content-type',
        'Access-Control-Allow-Origin': '*',
    },
)
@csp_exempt()
def widget_data(request, organizer=None, event=None, version=None, **kwargs):
    # Caching this page is tricky: We need the user to occasionally
    # ask for new data, and we definitely need to give them new data on schedule
    # release. This is because some information can change at any time, not just
    # in a new schedule version (like talk titles, speaker info etc).
    # So we:
    #  - tell the user a relatively short cache time that is safe to completely
    #    ignore new data for (1 minute)
    #  - simultaneously build a server-side cache that is invalidated on schedule
    #    release (by using the schedule version as key prefix), and that we keep
    #    around for a longer time (5 minutes), and that will be used for all users
    #  - also save a checksum of this server-side cache, and hand it to the client
    #    as an eTag, so they can ask for new data without it being too expensive
    #    on the server side
    # All this can ONLY take place if the schedule *has* a version (never caching
    # the WIP schedule page), and if anonymous users can see the schedule.
    event = request.event
    if request.method == 'OPTIONS':
        response = JsonResponse({})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'authorization,content-type'
        return response
    if not request.user.has_perm('base.view_widget_schedule', event):
        raise Http404()

    version = version or unquote(request.GET.get('v') or '')
    schedule = None
    if version and version == 'wip':
        if not request.user.has_perm('base.orga_view_schedule', event):
            raise Http404()
        schedule = request.event.wip_schedule
    elif version:
        schedule = event.schedules.filter(version__iexact=version).first()

    schedule = schedule or event.current_schedule
    if not schedule:
        raise Http404()

    enrich = request.GET.get('enrich') in {'1', 'true', 'True'}
    result = schedule.build_data(
        all_talks=not schedule.version,
        enrich=enrich,
        include_featured_speaker_metadata=are_featured_submissions_visible(AnonymousUser(), event),
    )
    response = JsonResponse(result, encoder=I18nJSONEncoder)
    response['Access-Control-Allow-Headers'] = 'authorization,content-type'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@condition(etag_func=widget_js_etag)
@csp_exempt()
def widget_script(request, organizer=None, event=None, **kwargs):
    # This page basically just serves a static file under a known path (ideally, the
    # administrators could and should even turn on gzip compression for the
    # /<event>/widget/schedule.js path, as it cuts down the transferred data
    # by about 80% for the schedule.js file, which is the largest file on the
    # main schedule page).
    file_path = finders.find(WIDGET_PATH)
    with open(file_path, encoding='utf-8') as fp:
        code = fp.read()
    data = code.encode()
    return HttpResponse(data, content_type='text/javascript')


@condition(etag_func=color_etag)
@csp_exempt()
def event_css(request, organizer=None, event=None, **kwargs):
    # If this event has custom colours, we send back a simple CSS file that sets the
    # root colours for the event.
    variables = []
    if request.event.visible_primary_color:
        if request.GET.get('target') == 'orga':
            # The organizer area sometimes needs the event’s colour, but shouldn’t use
            # it as primary colour automatically.
            variables.append(f'--color-primary-event: {request.event.visible_primary_color};')
        else:
            variables.append(f'--color-primary: {request.event.visible_primary_color};')
    if request.event.settings.get('header_background_color'):
        variables.append(
            f'--color-header-background: {request.event.settings.get("header_background_color")};'
        )
    if request.event.settings.get('header_text_color'):
        variables.append(f'--color-header-text: {request.event.settings.get("header_text_color")};')
    if request.event.settings.get('navigation_text_color'):
        variables.append(
            f'--color-header-navigation: {request.event.settings.get("navigation_text_color")};'
        )
    result = f':root {{{" ".join(variables)}}}' if variables else ''
    response = HttpResponse(result, content_type='text/css')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
