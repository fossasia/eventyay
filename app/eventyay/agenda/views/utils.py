import hashlib
import random
import string
import logging
from datetime import timezone as dt_timezone

from django.contrib import messages
from django.core import signing
from django.http import HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.utils.translation import gettext_lazy as _
from django.utils.translation import activate
from django.utils import timezone

from eventyay.common.signals import register_data_exporters, register_my_data_exporters
from eventyay.common.text.path import safe_filename
from eventyay.base.models.submission import SubmissionFavourite

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
            if not token_event_id or int(token_event_id) != int(event.pk):
                return None, None
        user_id = value['user_id']
        exp_ts = int(value['exp'])
        expiry_dt = timezone.datetime.fromtimestamp(exp_ts, tz=dt_timezone.utc)
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


def is_visible(exporter, request, public=False):
    if not public:
        return request.user.is_authenticated

    if not request.user.has_perm('base.list_schedule', request.event):
        return False

    try:
        is_public = exporter.is_public
    except AttributeError:
        return exporter.public

    try:
        return is_public(request=request)
    except Exception:
        logger.exception('Failed to use %s.is_public() for %s', exporter.identifier, request.event.slug)
        return exporter.public


def get_schedule_exporters(request, public=False):
    exporters = [exporter(request.event) for _, exporter in register_data_exporters.send_robust(request.event)]
    my_exporters = [exporter(request.event) for _, exporter in register_my_data_exporters.send_robust(request.event)]
    all_exporters = exporters + my_exporters
    return [
        exporter
        for exporter in all_exporters
        if (not isinstance(exporter, Exception) and is_visible(exporter, request, public=public))
    ]


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
        if not request.user.is_authenticated:
            return HttpResponseRedirect(request.event.urls.login)
        user_id = parse_ics_token(token, event=request.event)
        if not user_id or int(user_id) != int(request.user.id):
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
