import hashlib
import random
import string
import logging
from datetime import datetime, timezone as dt_timezone

from django.contrib import messages
from django.core import signing
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.utils.translation import activate
from django.utils import timezone

from eventyay.common.exporter import BaseExporter
from eventyay.common.signals import register_data_exporters, register_my_data_exporters


# Same escaping Django applies inside json_script to prevent XSS in <script> tags.
JSON_SCRIPT_ESCAPES = {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}


def escape_json_for_script(json_str: str) -> str:
    """Escape a JSON string for safe embedding in an HTML ``<script>`` tag."""
    return json_str.translate(JSON_SCRIPT_ESCAPES)
from eventyay.common.text.path import safe_filename
from eventyay.base.models.submission import SubmissionFavourite
from eventyay.schedule.exporters import FavedICalExporter

logger = logging.getLogger(__name__)

def load_starred_ics_token(token: str, *, event=None):
    """Validate and decode a starred-ICS token.

    Returns a tuple of (user_id, expiry_datetime_utc) on success, otherwise (None, None).
    Validation is centralized here so export + redirect flows share identical semantics.

    Note: Token lifetime is defined at issuance time (see ScheduleMixin.generate_ics_token):
    typically valid until event end + 24h, with a short-lived fallback after that point.
    Expiry is enforced via the embedded signed 'exp' timestamp.
    The token is also bound to the issuing event via a signed event identifier.
    """

    try:
        value = signing.loads(
            token,
            salt='my-starred-ics',
        )
        if event is not None:
            token_event_id = value.get('event_id')
            if not token_event_id or int(token_event_id) != event.pk:
                return None, None
        user_id = value['user_id']
        exp_ts = int(value['exp'])
        expiry_dt = datetime.fromtimestamp(exp_ts, tz=dt_timezone.utc)
        if expiry_dt <= timezone.now():
            return None, None
        return user_id, expiry_dt
    except (
        signing.BadSignature,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        OverflowError,
    ) as e:
        logger.debug('Failed to parse ICS token: %s', e)
        return None, None


def parse_ics_token(token: str, *, event=None):
    user_id, _expiry_dt = load_starred_ics_token(token, event=event)
    return user_id


def redirect_to_presale_with_warning(request, message):
    """Redirect to the event presale area with a warning message."""
    messages.warning(request, message)
    return HttpResponseRedirect(request.event.urls.base)


def is_public_schedule_empty(request):
    """True if a schedule is public but contains no published sessions."""
    return bool(
        request.event.is_public
        and request.event.get_feature_flag('show_schedule')
        and request.event.current_schedule
        and not request.event.has_schedule_content
    )


def is_public_speakers_empty(request):
    """True if speakers are public but there are no published speakers."""
    return bool(
        request.event.is_public
        and request.event.get_feature_flag('show_schedule')
        and request.event.current_schedule
        and not request.event.speakers.exists()
    )


def is_visible(exporter: BaseExporter, request: HttpRequest, public: bool = False) -> bool:
    if not public:
        return request.user.is_authenticated

    if not request.user.has_perm('base.list_schedule', request.event):
        return False

    if isinstance(exporter, FavedICalExporter):
        return exporter.is_public(request=request)
    return bool(exporter.public)


def get_schedule_exporters(request, public=False):
    exporters = [exporter(request.event) for _, exporter in register_data_exporters.send_robust(request.event)]
    my_exporters = [exporter(request.event) for _, exporter in register_my_data_exporters.send_robust(request.event)]
    all_exporters = exporters + my_exporters
    return [
        exporter
        for exporter in all_exporters
        if (not isinstance(exporter, Exception) and is_visible(exporter, request, public=public))
    ]


def build_public_schedule_exporters(event, version=None):
    """Build serialized exporter metadata for public schedule pages.

    Returns a list of dicts suitable for JSON serialization, each with
    identifier, verbose_name, icon, export_url, and qrcode_svg.
    Used by both the agenda view and the video SPA to ensure identical
    exporter lists in both UIs.
    """
    from django.urls import reverse, NoReverseMatch
    from django.utils.encoding import force_str

    all_exporters = []
    for signal in (register_data_exporters, register_my_data_exporters):
        for _, exporter_cls in signal.send_robust(event):
            if isinstance(exporter_cls, Exception):
                continue
            exporter = exporter_cls(event)
            try:
                is_public = exporter.show_public
            except NotImplementedError:
                is_public = False
            if is_public:
                all_exporters.append(exporter)

    order = {
        'google-calendar': 0, 'webcal': 1,
        'schedule.ics': 10, 'schedule.json': 11, 'schedule.xml': 12, 'schedule.xcal': 13,
        'faved.ics': 14,
        'my-google-calendar': 100, 'my-webcal': 101,
        'schedule-my.ics': 110, 'schedule-my.json': 111, 'schedule-my.xml': 112, 'schedule-my.xcal': 113,
    }
    all_exporters.sort(key=lambda e: (order.get(e.identifier, 50), force_str(e.verbose_name), e.identifier))

    export_kwargs = {'organizer': event.organizer.slug, 'event': event.slug}
    view_name = 'agenda:export'
    if version:
        view_name = 'agenda:versioned-export'
        export_kwargs['version'] = version

    result = []
    for exporter in all_exporters:
        try:
            url = reverse(view_name, kwargs={**export_kwargs, 'name': exporter.identifier})
        except NoReverseMatch:
            continue
        result.append({
            'identifier': exporter.identifier,
            'verbose_name': force_str(exporter.verbose_name),
            'icon': getattr(exporter, 'icon', ''),
            'export_url': url,
            'qrcode_svg': str(exporter.get_qrcode()) if getattr(exporter, 'show_qrcode', False) else '',
        })
    return result


def find_schedule_exporter(request, name, public=False):
    for exporter in get_schedule_exporters(request, public=public):
        if exporter.identifier == name:
            return exporter
    return None


def encode_email(email):
    """
    Encode email to a short hash and get first 7 characters
    @param email: User's email
    @return: encoded string
    """
    hash_object = hashlib.sha256(email.encode())
    hash_hex = hash_object.hexdigest()
    short_hash = hash_hex[:7]
    characters = string.ascii_letters + string.digits
    random_suffix = ''.join(random.choice(characters) for _ in range(7 - len(short_hash)))
    final_result = short_hash + random_suffix
    return final_result.upper()


def get_schedule_exporter_content(request, exporter_name, schedule, token=None):
    is_organizer = request.user.has_perm('base.orga_view_schedule', request.event)
    exporter = find_schedule_exporter(request, exporter_name, public=not is_organizer)
    if not exporter:
        return
    exporter.schedule = schedule
    exporter.is_orga = is_organizer
    lang_code = request.GET.get('lang')
    if lang_code and lang_code in request.event.locales:
        activate(lang_code)
    elif 'lang' in request.GET:
        activate(request.event.locale)
    if '-my' in exporter.identifier and request.user.id is None and not token:
        if request.GET.get('talks'):
            exporter.talk_ids = request.GET.get('talks').split(',')
        else:
            return HttpResponseRedirect(request.event.urls.login)
    if token and "-my" in exporter.identifier:
        user_id = parse_ics_token(token, event=request.event)
        if not user_id:
            return
        talk_ids = list(
            SubmissionFavourite.objects.filter(
                user_id=user_id,
                submission__event=request.event,
            ).values_list('submission__code', flat=True)
        )
        if talk_ids:
            exporter.talk_ids = talk_ids
    elif "-my" in exporter.identifier:
        talk_ids = list(
            SubmissionFavourite.objects.filter(
                user_id=request.user.id,
                submission__event=request.event,
            ).values_list('submission__code', flat=True)
        )
        if talk_ids:
            exporter.talk_ids = talk_ids
    try:
        file_name, file_type, data = exporter.render(request=request)
        etag = hashlib.sha1(str(data).encode()).hexdigest()
    except Exception:
        logger.exception(f'Failed to use {exporter.identifier} for {request.event.slug}')
        return
    if request.headers.get('If-None-Match') == etag:
        return HttpResponseNotModified()
    headers = {'ETag': f'"{etag}"'}
    if file_type not in ('application/json', 'text/xml'):
        headers['Content-Disposition'] = f'attachment; filename="{safe_filename(file_name)}"'
    if exporter.cors:
        headers['Access-Control-Allow-Origin'] = exporter.cors
    return HttpResponse(data, content_type=file_type, headers=headers)
