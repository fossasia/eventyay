import hashlib
import os
from urllib.parse import unquote

from csp.decorators import csp_exempt
from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.templatetags.static import static
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import condition
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import SpeakerProfile, TalkSlot
from eventyay.base.models.schedule import make_speaker_qr_map, make_talk_qr_map
from eventyay.common.views import conditional_cache_page
from eventyay.presale.style import (
    SYSTEM_FONTS,
    get_font_stylesheet,
    get_fonts,
    resolve_font,
)
from eventyay.talk_rules.agenda import (
    can_access_schedule_widget,
    can_view_wip_schedule,
    is_widget_visible,
    wip_preview_build_data,
)
from eventyay.talk_rules.submission import (
    are_featured_speakers_visible,
    schedule_widget_featured_cache_key_part,
)


WIDGET_JS_CHECKSUM = None
WIDGET_JS_MTIME = None
WIDGET_PATH = 'schedule/pretalx-schedule.js'


def color_etag(request, organizer=None, event=None, **kwargs):
    header_background_color = request.event.settings.get('header_background_color')
    header_text_color = request.event.settings.get('header_text_color')
    navigation_text_color = request.event.settings.get('navigation_text_color')
    primary_font = request.event.settings.get('primary_font')
    parts = [
        request.event.visible_primary_color or '',
        header_background_color or '',
        header_text_color or '',
        navigation_text_color or '',
        primary_font or '',
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


def qrcodes_prefix(request, organizer=None, event=None, version=None, kind=None, code=None, **kwargs):
    return f'{version_prefix(request, organizer=organizer, event=event, version=version)}-qrcodes-{kind}-{code}'


@gzip_page
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
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        return response
    if not can_access_schedule_widget(request.user, event):
        raise Http404()

    version = version or unquote(request.GET.get('v') or '')
    schedule = None
    if version and version == 'wip':
        if not can_view_wip_schedule(request.user, event):
            raise Http404()
        schedule = request.event.wip_schedule
    elif version:
        schedule = event.schedules.filter(version__iexact=version).first()

    schedule = schedule or event.current_schedule
    if not schedule:
        raise Http404()

    enrich = request.GET.get('enrich') in {'1', 'true', 'True'}
    include_qrcodes = request.GET.get('qrcodes') in {'1', 'true', 'True'}
    preview = wip_preview_build_data(request.user, event, schedule)
    result = schedule.build_data(
        all_talks=not schedule.version,
        enrich=enrich,
        include_featured_speaker_metadata=are_featured_speakers_visible(AnonymousUser(), event),
        include_qrcodes=include_qrcodes,
        respect_public_visibility=not preview,
    )
    response = JsonResponse(result, encoder=I18nJSONEncoder)
    response['Access-Control-Allow-Headers'] = 'authorization,content-type'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@gzip_page
@conditional_cache_page(
    60,
    key_prefix=qrcodes_prefix,
    condition=is_public_and_versioned,
    server_timeout=5 * 60,
    headers={
        'Access-Control-Allow-Headers': 'authorization,content-type',
        'Access-Control-Allow-Origin': '*',
    },
)
@csp_exempt()
def widget_qrcodes(request, organizer=None, event=None, version=None, kind=None, code=None, **kwargs):
    event = request.event
    if request.method == 'OPTIONS':
        response = JsonResponse({})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'authorization,content-type'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        return response
    if not can_access_schedule_widget(request.user, event):
        raise Http404()

    version = version or unquote(request.GET.get('v') or '')
    schedule = None
    if version and version == 'wip':
        if not can_view_wip_schedule(request.user, event):
            raise Http404()
        schedule = request.event.wip_schedule
    elif version:
        schedule = event.schedules.filter(version__iexact=version).first()
    schedule = schedule or event.current_schedule
    if not schedule:
        raise Http404()

    # Validate that the requested entity exists in this event/schedule to avoid
    # unbounded cache entries and unnecessary CPU work for random codes.
    if kind == 'talk':
        talk_filter = {'schedule': schedule, 'submission__isnull': False, 'submission__code__iexact': code}
        if not wip_preview_build_data(request.user, event, schedule):
            talk_filter['is_visible'] = True
        exists = TalkSlot.objects.filter(**talk_filter).exists()
        if not exists:
            raise Http404()
    elif kind == 'speaker':
        exists = (
            SpeakerProfile.objects.filter(event=event, user__code__iexact=code).exists()
            and TalkSlot.objects.filter(
                schedule=schedule,
                is_visible=True,
                submission__isnull=False,
                submission__speakers__code__iexact=code,
            ).exists()
        )
        if not exists:
            raise Http404()
    else:
        raise Http404()

    full_base = str(event.urls.base.full())
    if kind == 'talk':
        qrcodes = make_talk_qr_map(full_base, code)
    elif kind == 'speaker':
        qrcodes = make_speaker_qr_map(f'{full_base}speakers/{code}')

    response = JsonResponse({'qrcodes': qrcodes}, encoder=I18nJSONEncoder)
    response['Access-Control-Allow-Headers'] = 'authorization,content-type'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@condition(etag_func=widget_js_etag)
@gzip_page
@csp_exempt()
def widget_script(request, organizer=None, event=None, **kwargs):
    # Keep this endpoint backwards-compatible for third-party embeds that use a classic
    # <script src=".../widgets/schedule.js"></script> tag. We serve a tiny loader that
    # injects the actual ESM widget bundle from the static URL.
    # IMPORTANT: this endpoint is typically embedded cross-origin. A relative /static/ URL would
    # resolve against the embedding page's origin, not ours. We therefore build an absolute URL
    # based on the current script's URL at runtime.
    from django.urls import reverse
    if request.event:
        module_src = reverse('agenda:widget.schedule.chunk', kwargs={'organizer': request.organizer.slug, 'event': request.event.slug, 'filename': 'pretalx-schedule.js'})
    else:
        module_src = static(WIDGET_PATH)

    loader = (
        "(function(){"
        f"var staticPath={module_src!r};"
        "var base=(document.currentScript&&document.currentScript.src)?document.currentScript.src:window.location.href;"
        "var u=(function(){try{return new URL(staticPath, base).href;}catch(e){return staticPath;}})();"
        "var s=document.createElement('script');"
        "s.type='module';"
        "s.crossOrigin='anonymous';"
        "s.src=u;"
        "(document.head||document.documentElement).appendChild(s);"
        "})();"
    )
    response = HttpResponse(loader, content_type='text/javascript; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=86400'
    return response


@csp_exempt()
def widget_schedule_chunk(request, organizer=None, event=None, filename=None, **kwargs):
    file_path = finders.find(f'schedule/{filename}')
    if not file_path:
        raise Http404
    try:
        response = FileResponse(open(file_path, 'rb'), content_type='application/javascript; charset=utf-8')
    except OSError:
        raise Http404
    response['Cache-Control'] = 'public, max-age=86400'
    response['Access-Control-Allow-Origin'] = '*'
    return response


@condition(etag_func=color_etag)
@csp_exempt()
def event_css(request, organizer=None, event=None, **kwargs):
    # If this event has custom colours or font, we send back a simple CSS file that sets the
    # root colours and font properties for the event.
    variables = []
    header_background_color = request.event.settings.get('header_background_color')
    header_text_color = request.event.settings.get('header_text_color')
    navigation_text_color = request.event.settings.get('navigation_text_color')
    primary_font = request.event.settings.get('primary_font')

    if request.event.visible_primary_color:
        if request.GET.get('target') == 'orga':
            # The organizer area sometimes needs the event’s colour, but shouldn’t use
            # it as primary colour automatically.
            variables.append(f'--color-primary-event: {request.event.visible_primary_color};')
        else:
            variables.append(f'--color-primary: {request.event.visible_primary_color};')
    if header_background_color:
        variables.append(f'--color-header-background: {header_background_color};')
    if header_text_color:
        variables.append(f'--color-header-text: {header_text_color};')
    if navigation_text_color:
        variables.append(f'--color-header-navigation: {navigation_text_color};')

    font_css = ''
    if primary_font and request.GET.get('target') != 'orga':
        resolved_font, font_family_value = resolve_font(request.event)
        if resolved_font and resolved_font not in SYSTEM_FONTS:
            fonts_dict = get_fonts()
            if resolved_font in fonts_dict:
                font_css = get_font_stylesheet(resolved_font, fonts=fonts_dict, for_sass=False)

        if font_family_value:
            variables.append(f'--font-family: {font_family_value};')
            variables.append(f'--font-family-title: {font_family_value};')

    root_css = f':root {{{" ".join(variables)}}}' if variables else ''
    result = f'{font_css}\n{root_css}'.strip()
    response = HttpResponse(result, content_type='text/css')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
