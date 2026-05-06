import hashlib
import json
import logging
import random
import string
from datetime import UTC, datetime

from django.contrib import messages
from django.core import signing
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.translation import activate
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import SpeakerProfile, User
from eventyay.base.models.submission import SubmissionFavourite
from eventyay.common.exporter import BaseExporter
from eventyay.common.signals import register_data_exporters, register_my_data_exporters
from eventyay.common.text.path import safe_filename
from eventyay.schedule.exporters import FavedICalExporter
from eventyay.talk_rules.submission import are_featured_submissions_visible


# Same escaping Django applies inside json_script to prevent XSS in <script> tags.
JSON_SCRIPT_ESCAPES = {ord('>'): '\\u003E', ord('<'): '\\u003C', ord('&'): '\\u0026'}


def escape_json_for_script(json_str: str) -> str:
    """Escape a JSON string for safe embedding in an HTML ``<script>`` tag."""
    return json_str.translate(JSON_SCRIPT_ESCAPES)


def build_enriched_schedule_json(request: HttpRequest) -> str:
    """Serialize the current schedule for inline first-party agenda views.

    Some public pages, such as featured talk pages, remain accessible even when the
    standalone widget JSON endpoint is intentionally hidden. Those pages need a
    self-contained payload instead of depending on ``widgets/schedule.json``.

    The result is cached for 5 minutes (keyed on schedule PK so invalidation is
    automatic when a new version is published).  WIP schedules are never cached.
    """
    schedule = request.event.current_schedule
    if not schedule:
        return '{}'

    featured = are_featured_submissions_visible(request.user, request.event)
    if schedule.version:
        cache_key = f'eagenda:enriched:{schedule.pk}:{int(featured)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    data = schedule.build_data(
        enrich=True,
        include_featured_speaker_metadata=featured,
    )
    result = escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))

    if schedule.version:
        cache.set(cache_key, result, 300)
    return result


def build_schedule_json(request: HttpRequest, schedule=None) -> str:
    """Build non-enriched schedule JSON for inline embedding on all schedule pages.

    Covers WIP and released schedules.  Released schedules are cached for 5 minutes
    keyed on schedule PK; WIP is never cached.  Callers that view a specific version
    should pass that ``schedule`` object directly.
    """
    if schedule is None:
        schedule = request.event.current_schedule
    if not schedule:
        return '{}'

    featured = are_featured_submissions_visible(request.user, request.event)
    if schedule.version:
        cache_key = f'eagenda:schedule:{schedule.pk}:{int(featured)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    data = schedule.build_data(
        all_talks=not bool(schedule.version),
        enrich=False,
        include_featured_speaker_metadata=featured,
    )
    result = escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))

    if schedule.version:
        cache.set(cache_key, result, 300)
    return result


def build_talk_schedule_json(request: HttpRequest, submission_code: str) -> str:
    """Build a minimal non-enriched schedule JSON scoped to a single talk.

    Only the target talk's slot is included.  Resources, answers, and exporters
    are intentionally omitted here; the Vue ``TalkDetail`` component fetches them
    from the submissions API endpoint so the inlined HTML payload stays tiny.
    """
    schedule = request.event.current_schedule
    if not schedule:
        return '{}'

    featured = are_featured_submissions_visible(request.user, request.event)
    if schedule.version:
        cache_key = f'eagenda:talk:{schedule.pk}:{submission_code}:{int(featured)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    data = schedule.build_data(
        enrich=False,
        submission_codes={submission_code},
        include_featured_speaker_metadata=featured,
    )
    result = escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))

    if schedule.version:
        cache.set(cache_key, result, 300)
    return result


def build_speaker_schedule_json(request: HttpRequest, speaker_code: str) -> str:
    """Build a minimal non-enriched schedule JSON scoped to a single speaker.

    Only the speaker's visible talk slots are included.  Speaker biography and
    avatar are present without enrichment so the ``SpeakerDetail`` Vue component
    can render immediately from inline data without a separate widget fetch.
    Speaker calendar export URLs are computed client-side by ``speakerExportOptions``
    in ``SessionModal.vue``, so ``enrich=False`` is safe here.
    """
    schedule = request.event.current_schedule
    if not schedule:
        return '{}'

    featured = are_featured_submissions_visible(request.user, request.event)
    if schedule.version:
        cache_key = f'eagenda:speaker:{schedule.pk}:{speaker_code}:{int(featured)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    talk_codes = set(
        schedule.talks.filter(
            submission__speakers__code__iexact=speaker_code,
            is_visible=True,
        ).values_list('submission__code', flat=True)
    )

    data = schedule.build_data(
        enrich=False,
        submission_codes=talk_codes,
        include_featured_speaker_metadata=featured,
    )

    # Ensure the speaker appears in the payload even when they have no visible
    # sessions (e.g. accepted but not yet scheduled).
    if not any(s['code'].lower() == speaker_code.lower() for s in data.get('speakers', [])):
        user = User.objects.filter(code__iexact=speaker_code).first()
        if user:
            profile = SpeakerProfile.objects.filter(
                event=request.event, user=user
            ).select_related('user').first()
            include_avatar = request.event.cfp.request_avatar
            data.setdefault('speakers', []).append({
                'code': user.code,
                'name': user.fullname or None,
                'biography': getattr(profile, 'biography', ''),
                'avatar': user.get_avatar_url(event=request.event) if include_avatar else None,
                'avatar_thumbnail_default': (
                    user.get_avatar_url(event=request.event, thumbnail='default') if include_avatar else None
                ),
                'avatar_thumbnail_tiny': (
                    user.get_avatar_url(event=request.event, thumbnail='tiny') if include_avatar else None
                ),
                'is_featured': bool(getattr(profile, 'is_featured', False)),
                'featured_position': getattr(profile, 'position', None),
            })

    result = escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))

    if schedule.version:
        cache.set(cache_key, result, 300)
    return result


def is_email_like(value: str) -> bool:
    value = (value or '').strip()
    if '@' not in value:
        return False
    local_part, _, domain = value.partition('@')
    if not local_part or not domain:
        return False
    return True


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
        expiry_dt = datetime.fromtimestamp(exp_ts, tz=UTC)
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
    exporter lists in both UIs.  Result is cached for 5 minutes per
    (event.pk, version) to avoid firing Django signals on every request.
    """
    cache_key = f'eagenda:exporters:{event.pk}:{version or ""}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

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
        'google-calendar': 0,
        'webcal': 1,
        'schedule.ics': 10,
        'schedule.json': 11,
        'schedule.xml': 12,
        'schedule.xcal': 13,
        'faved.ics': 14,
        'my-google-calendar': 100,
        'my-webcal': 101,
        'schedule-my.ics': 110,
        'schedule-my.json': 111,
        'schedule-my.xml': 112,
        'schedule-my.xcal': 113,
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
        result.append(
            {
                'identifier': exporter.identifier,
                'verbose_name': force_str(exporter.verbose_name),
                'icon': getattr(exporter, 'icon', ''),
                'export_url': url,
                'qrcode_svg': str(exporter.get_qrcode()) if getattr(exporter, 'show_qrcode', False) else '',
            }
        )
    cache.set(cache_key, result, 300)
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
            exporter.talk_ids = set(request.GET.get('talks').split(','))
        else:
            return HttpResponseRedirect(request.event.urls.login)
    if token and '-my' in exporter.identifier:
        user_id = parse_ics_token(token, event=request.event)
        if not user_id:
            return
        talk_ids = set(
            SubmissionFavourite.objects.filter(
                user_id=user_id,
                submission__event=request.event,
            ).values_list('submission__code', flat=True)
        )
        if talk_ids:
            exporter.talk_ids = talk_ids
    elif '-my' in exporter.identifier:
        talk_ids = set(
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
