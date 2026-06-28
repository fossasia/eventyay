import hashlib
import json
import logging
import random
import string
from datetime import UTC, datetime

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.core import signing
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseNotModified, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.translation import activate, get_language, gettext_lazy as _
from django_context_decorator import context
from i18nfield.utils import I18nJSONEncoder

from eventyay.base.models import SpeakerProfile, TalkSlot, User
from eventyay.base.models.submission import SubmissionFavourite
from eventyay.common.exporter import BaseExporter
from eventyay.common.signals import register_data_exporters, register_my_data_exporters
from eventyay.common.text.path import safe_filename
from eventyay.schedule.exporters import FavedICalExporter, filter_featured_public_talk_slots
from eventyay.talk_rules.agenda import (
    can_list_released_schedule_speakers,
    can_view_public_schedule_sessions,
    has_public_featured_speakers,
    is_submission_visible_via_featured,
    pending_public_submission_codes_for_speaker,
    public_speakers_list_available,
    require_wip_schedule_access,
    speaker_may_show_pending_sessions,
)
from eventyay.talk_rules.submission import (
    are_featured_exports_available,
    are_featured_speakers_visible,
    are_featured_submissions_visible,
    can_use_featured_exports,
    featured_submissions_for_event,
    include_public_featured_speaker_metadata,
    schedule_widget_featured_cache_key_part,
)


# Same escaping Django applies inside json_script to prevent XSS in <script> tags.
JSON_SCRIPT_ESCAPES = {ord('>'): '\\u003E', ord('<'): '\\u003C', ord('&'): '\\u0026'}

CACHE_TTL = 600


def escape_json_for_script(json_str: str) -> str:
    """Escape a JSON string for safe embedding in an HTML ``<script>`` tag."""
    return json_str.translate(JSON_SCRIPT_ESCAPES)


def speaker_public_field_flags(event):
    """Return (include_avatar, include_biography) for public speaker pages."""
    try:
        cfp = event.cfp
    except ObjectDoesNotExist:
        return False, False
    include_avatar = cfp.request_avatar and cfp.public_avatar
    include_biography = getattr(cfp, 'public_biography', False)
    return include_avatar, include_biography


# --- Featured speaker widget payloads (pre-agenda public access) ---


def speaker_profile_display_order():
    """Order speaker profiles by orga position, then named speakers before unnamed."""
    from django.db.models import Case, F, IntegerField, OrderBy, Value, When

    return (
        OrderBy(F('position'), nulls_last=True),
        Case(
            When(user__fullname='', then=Value(1)),
            When(user__fullname__isnull=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        'user__fullname',
        'pk',
    )


def get_public_featured_speaker_profiles(event):
    """Return featured speaker profiles in public display order."""
    return list(
        SpeakerProfile.objects.filter(event=event, is_featured=True)
        .select_related('user')
        .order_by(*speaker_profile_display_order())
    )


def get_featured_speaker_profile_by_code(event, speaker_code):
    return (
        SpeakerProfile.objects.filter(
            event=event,
            user__code__iexact=speaker_code,
            is_featured=True,
        )
        .select_related('user')
        .first()
    )


def get_speaker_profile_by_code(event, speaker_code):
    return (
        SpeakerProfile.objects.filter(event=event, user__code__iexact=speaker_code)
        .select_related('user', 'event', 'event__organizer')
        .first()
    )


def load_public_featured_speaker_profiles(user, event):
    if not are_featured_speakers_visible(user, event):
        return []
    from django_scopes import scope

    with scope(event=event):
        return get_public_featured_speaker_profiles(event)


def public_featured_speaker_profiles_queryset(event):
    return SpeakerProfile.objects.filter(event=event, is_featured=True).select_related(
        'user',
        'event',
        'event__organizer',
    )


def speaker_dict_from_profile(
    event,
    profile,
    *,
    include_avatar=None,
    include_biography=None,
    include_featured_metadata=True,
):
    """Serialize a speaker profile for schedule-shaped widget payloads."""
    if not profile or not profile.user_id:
        return None
    if include_avatar is None or include_biography is None:
        avatar_flag, biography_flag = speaker_public_field_flags(event)
        if include_avatar is None:
            include_avatar = avatar_flag
        if include_biography is None:
            include_biography = biography_flag
    user = profile.user
    is_featured = bool(profile.is_featured) if include_featured_metadata else False
    return {
        'code': user.code,
        'name': user.fullname or None,
        'biography': (profile.biography or '') if include_biography else '',
        'avatar': user.get_avatar_url(event=event) if include_avatar else None,
        'avatar_thumbnail_default': (
            user.get_avatar_url(event=event, thumbnail='default') if include_avatar else None
        ),
        'avatar_thumbnail_tiny': (
            user.get_avatar_url(event=event, thumbnail='tiny') if include_avatar else None
        ),
        'is_featured': is_featured,
        'featured_position': profile.position if is_featured else None,
    }


def _empty_widget_schedule_meta(event, *, speakers_list_public=False):
    return {
        'tracks': [],
        'rooms': [],
        'version': '',
        'timezone': event.timezone,
        'event_start': event.date_from.isoformat(),
        'event_end': event.date_to.isoformat(),
        'content_locales': event.content_locales,
        'speakers_list_public': speakers_list_public,
        'feature_flags': event.schedule_client_feature_flags(),
    }


def serialize_widget_schedule_data(data, *, event=None, user=None):
    if event is not None and isinstance(data, dict):
        from django.contrib.auth.models import AnonymousUser

        data = dict(data)
        data['exports_disabled'] = (
            not are_featured_exports_available(event)
            or bool(data.get('exports_disabled'))
        )
        if 'speakers_list_public' not in data:
            data['speakers_list_public'] = can_list_released_schedule_speakers(AnonymousUser(), event)
    return escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))


def featured_schedule_talk_slots(schedule):
    """Featured talk slots that match public schedule visibility rules."""
    if not schedule:
        return TalkSlot.objects.none()
    return filter_featured_public_talk_slots(schedule.talks.filter(is_visible=True))


def event_has_public_featured_schedule_talks(event):
    """Whether the event has featured sessions displayable on the public schedule."""
    if not event.current_schedule:
        return False
    return featured_schedule_talk_slots(event.current_schedule).exists()


def build_featured_only_schedule_data_from_profiles(event, profiles, *, speakers_list_public=False):
    speakers = []
    for profile in profiles:
        speaker_data = speaker_dict_from_profile(event, profile)
        if speaker_data:
            speakers.append(speaker_data)
    if not speakers:
        return None
    return {
        'talks': [],
        'speakers': speakers,
        **_empty_widget_schedule_meta(event, speakers_list_public=speakers_list_public),
    }


def build_featured_only_schedule_data(event, *, extra_speakers=None):
    """Build schedule-shaped data containing featured speakers and no talk slots."""
    data = build_featured_only_schedule_data_from_profiles(
        event,
        get_public_featured_speaker_profiles(event),
    )
    if not data:
        speakers = [speaker for speaker in (extra_speakers or []) if isinstance(speaker, dict)]
        if not speakers:
            return None
        return {'talks': [], 'speakers': speakers, **_empty_widget_schedule_meta(event, speakers_list_public=False)}
    if extra_speakers:
        seen_codes = {speaker.get('code') for speaker in data['speakers'] if speaker.get('code')}
        for speaker in extra_speakers:
            if isinstance(speaker, dict) and speaker.get('code') not in seen_codes:
                data['speakers'].append(speaker)
                seen_codes.add(speaker['code'])
    return data


def merge_featured_speakers_into_schedule_data(event, schedule_data, featured_profiles):
    schedule_speakers = list(schedule_data.get('speakers', []) or [])
    speakers_by_code = {
        speaker.get('code'): speaker
        for speaker in schedule_speakers
        if isinstance(speaker, dict) and speaker.get('code')
    }
    for profile in featured_profiles:
        if not profile.user_id:
            continue
        speaker_data = speaker_dict_from_profile(event, profile)
        if not speaker_data:
            continue
        code = profile.user.code
        existing = speakers_by_code.get(code)
        if existing:
            existing['is_featured'] = True
            existing['featured_position'] = profile.position
            if speaker_data.get('biography') and not existing.get('biography'):
                existing['biography'] = speaker_data['biography']
            for field in ('avatar', 'avatar_thumbnail_default', 'avatar_thumbnail_tiny'):
                if speaker_data.get(field) and not existing.get(field):
                    existing[field] = speaker_data[field]
            continue
        schedule_speakers.append(speaker_data)
        speakers_by_code[code] = speaker_data
    schedule_data['speakers'] = schedule_speakers
    return schedule_data


def filter_schedule_data_to_featured_speakers(schedule_data, featured_speaker_user_codes):
    featured_codes = {(code or '').lower() for code in featured_speaker_user_codes if code}
    filtered_talks = [
        talk
        for talk in schedule_data.get('talks', []) or []
        if featured_codes.intersection({(code or '').lower() for code in talk.get('speakers') or []})
    ]
    schedule_data['talks'] = filtered_talks
    track_ids = {talk.get('track') for talk in filtered_talks if talk.get('track') is not None}
    room_ids = {talk.get('room') for talk in filtered_talks if talk.get('room') is not None}
    schedule_data['tracks'] = [
        track for track in schedule_data.get('tracks', []) if track.get('id') in track_ids
    ]
    schedule_data['rooms'] = [
        room for room in schedule_data.get('rooms', []) if room.get('id') in room_ids
    ]
    schedule_data['speakers'] = [
        speaker
        for speaker in schedule_data.get('speakers', []) or []
        if isinstance(speaker, dict) and (speaker.get('code') or '').lower() in featured_codes
    ]
    return schedule_data


def _ordered_featured_speakers_from_profiles(event, featured_profiles, schedule_speakers_by_code=None):
    schedule_speakers_by_code = schedule_speakers_by_code or {}
    ordered_speakers = []
    for profile in featured_profiles:
        speaker_data = speaker_dict_from_profile(event, profile)
        if not speaker_data:
            continue
        schedule_speaker = schedule_speakers_by_code.get(speaker_data['code'])
        if schedule_speaker:
            speaker_data = {
                **schedule_speaker,
                **speaker_data,
                'is_featured': True,
                'featured_position': profile.position,
            }
        ordered_speakers.append(speaker_data)
    return ordered_speakers


def build_landing_featured_speakers_widget_schedule(event, user, featured_profiles):
    """Build widget schedule payload for the event landing page featured speakers block."""
    from django_scopes import scope

    featured_speaker_user_codes = {profile.user.code for profile in featured_profiles if profile.user_id}
    speakers_list_public = public_speakers_list_available(user, event)
    base_data = build_featured_only_schedule_data_from_profiles(
        event,
        featured_profiles,
        speakers_list_public=speakers_list_public,
    )
    if not base_data:
        return None

    schedule = event.current_schedule or getattr(event, 'wip_schedule', None)
    show_public_times = can_view_public_schedule_sessions(user, event, schedule)
    featured = include_public_featured_speaker_metadata(user, event)

    if show_public_times and schedule:
        with scope(event=event):
            schedule_data = schedule.build_data(
                all_talks=not schedule.version,
                include_featured_speaker_metadata=featured,
                respect_public_visibility=True,
            )
        schedule_data = merge_featured_speakers_into_schedule_data(event, schedule_data, featured_profiles)
        filtered = filter_schedule_data_to_featured_speakers(schedule_data, featured_speaker_user_codes)
        base_data['talks'] = filtered.get('talks', [])
        base_data['tracks'] = filtered.get('tracks', [])
        base_data['rooms'] = filtered.get('rooms', [])
    else:
        filtered = _apply_pending_speaker_talks(
            base_data,
            event,
            user,
            schedule,
            featured_speaker_user_codes,
            featured=featured,
        )

    schedule_speakers_by_code = {
        speaker['code']: speaker
        for speaker in filtered.get('speakers', [])
        if isinstance(speaker, dict) and speaker.get('code')
    }
    base_data['speakers'] = _ordered_featured_speakers_from_profiles(
        event,
        featured_profiles,
        schedule_speakers_by_code,
    )
    base_data['speakers_list_public'] = speakers_list_public
    return base_data


def build_pending_speaker_schedule_json(event, user, speaker_code, featured):
    """Build speaker-scoped schedule JSON with coming-soon sessions before public release."""
    profile = get_speaker_profile_by_code(event, speaker_code)
    if not profile:
        return '{}'
    data = build_featured_only_schedule_data_from_profiles(event, [profile])
    if not data:
        return '{}'

    schedule = event.current_schedule or getattr(event, 'wip_schedule', None)
    _apply_pending_speaker_talks(data, event, user, schedule, {speaker_code}, featured=featured)
    data['exports_disabled'] = True
    return serialize_widget_schedule_data(data, event=event)


def _serialize_schedule_build_data(schedule, **build_kwargs) -> str:
    return serialize_widget_schedule_data(schedule.build_data(**build_kwargs), event=schedule.event)


def build_schedule_meta_json(event, schedule) -> str:
    """Build escaped JSON for the pretalx-schedule-meta inline script tag."""
    version = schedule.version if schedule else None
    released = list(
        event.schedules.filter(version__isnull=False)
        .order_by('-published')
        .values_list('version', flat=True)
    )
    base_schedule_url = str(event.urls.schedule)
    current_version = event.current_schedule.version if event.current_schedule else None
    versions = [
        {'version': v, 'url': f'{base_schedule_url}v/{v}/', 'isCurrent': v == current_version} for v in released
    ]
    meta = {
        'version': version or '',
        'is_current': schedule == event.current_schedule if schedule else False,
        'changelog_url': str(event.urls.changelog),
        'current_schedule_url': base_schedule_url if event.current_schedule else '',
        'versions': versions,
        'exporters': build_public_schedule_exporters(event, version=version),
    }
    return escape_json_for_script(json.dumps(meta))


def _featured_exporter_url(url: str) -> str:
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}featured=true'


def build_featured_schedule_meta_json(event, schedule) -> str:
    version = schedule.version if schedule else None
    featured_exporters = []
    if are_featured_exports_available(event):
        featured_exporters = [
            {**exporter, 'export_url': _featured_exporter_url(exporter['export_url'])}
            for exporter in build_public_schedule_exporters(event, version=version)
        ]
    meta = {
        'version': version or '',
        'is_current': schedule == event.current_schedule if schedule else False,
        'changelog_url': '',
        'current_schedule_url': '',
        'versions': [],
        'exporters': featured_exporters,
    }
    return escape_json_for_script(json.dumps(meta))


def build_enriched_schedule_json(request: HttpRequest, *, wip_preview: bool = False) -> str:
    """Serialize schedule data for inline first-party agenda views.

    Public talk/speaker pages embed the released schedule. WIP preview pages
    (``schedule/v/wip/...``) embed the editable WIP schedule without public
    visibility filters.

    The result is cached for 5 minutes (keyed on schedule PK so invalidation is
    automatic when a new version is published).  WIP schedules are never cached.
    """
    event = request.event
    if wip_preview:
        require_wip_schedule_access(request)
        schedule = event.wip_schedule
    else:
        schedule = event.current_schedule
    if not schedule:
        return '{}'

    featured = include_public_featured_speaker_metadata(request.user, event)
    if schedule.version:
        cache_key = f'eagenda:enriched:{schedule.pk}:{int(featured)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    result = _serialize_schedule_build_data(
        schedule,
        all_talks=wip_preview or not schedule.version,
        enrich=True,
        include_featured_speaker_metadata=featured,
        respect_public_visibility=not wip_preview,
    )

    if schedule.version:
        cache.set(cache_key, result, CACHE_TTL)
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

    featured = include_public_featured_speaker_metadata(request.user, request.event)
    settings_part = schedule_widget_featured_cache_key_part(request.event)
    if schedule.version:
        cache_key = f'eagenda:schedule:{schedule.pk}:{int(featured)}:{settings_part}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    result = _serialize_schedule_build_data(
        schedule,
        all_talks=not bool(schedule.version),
        enrich=False,
        include_featured_speaker_metadata=featured,
    )

    if schedule.version:
        cache.set(cache_key, result, CACHE_TTL)
    return result


def build_featured_schedule_json(request: HttpRequest) -> str:
    """Build schedule JSON for the featured page, including unscheduled featured sessions."""
    event = request.event
    featured_qs = featured_submissions_for_event(event)
    if not featured_qs.exists():
        return '{}'

    featured = are_featured_submissions_visible(request.user, event)
    featured_by_code = {sub.code: sub for sub in featured_qs}
    published = event.current_schedule

    if published:
        scheduled_codes = set(
            featured_schedule_talk_slots(published).values_list('submission__code', flat=True)
        )
        if scheduled_codes:
            data = published.build_data(
                all_talks=False,
                enrich=False,
                submission_codes=scheduled_codes,
                include_featured_speaker_metadata=featured,
            )
        else:
            data = _empty_featured_schedule_data(event)
    else:
        wip = event.wip_schedule
        if wip and featured_by_code:
            data = wip.build_data(
                all_talks=True,
                enrich=False,
                submission_codes=set(featured_by_code.keys()),
                include_featured_speaker_metadata=featured,
                respect_public_visibility=False,
            )
            for talk in data['talks']:
                _mark_talk_schedule_pending(talk)
        else:
            data = _empty_featured_schedule_data(event)

    _append_missing_featured_submissions(data, featured_by_code, event)
    _ensure_schedule_speakers(data, event, featured)
    data['exports_disabled'] = not are_featured_exports_available(event)
    return escape_json_for_script(json.dumps(data, cls=I18nJSONEncoder))


def _pending_submission_codes_for_speakers(event, user, speaker_user_codes):
    pending_codes = set()
    for speaker_code in speaker_user_codes:
        pending_codes.update(pending_public_submission_codes_for_speaker(event, user, speaker_code))
    return pending_codes


def _load_pending_speaker_talks(event, user, schedule, speaker_user_codes, *, featured):
    from django_scopes import scope

    pending_codes = _pending_submission_codes_for_speakers(event, user, speaker_user_codes)
    if not schedule or not pending_codes:
        return {'talks': [], 'tracks': [], 'rooms': [], 'speakers': []}
    with scope(event=event):
        schedule_data = schedule.build_data(
            all_talks=False,
            submission_codes=pending_codes,
            include_featured_speaker_metadata=featured,
            respect_public_visibility=False,
        )
    filtered = filter_schedule_data_to_featured_speakers(schedule_data, speaker_user_codes)
    for talk in filtered.get('talks', []):
        _mark_talk_schedule_pending(talk)
    return filtered


def _append_missing_pending_submissions(data, event, user, speaker_user_codes):
    """Add coming-soon talk entries for pending sessions missing from schedule data."""
    if not speaker_user_codes:
        return
    present_codes = {talk.get('code') for talk in data.get('talks', []) if talk.get('code')}
    missing_codes = _pending_submission_codes_for_speakers(event, user, speaker_user_codes) - present_codes
    if not missing_codes:
        return
    from django_scopes import scope

    with scope(event=event):
        submissions = (
            event.submissions.filter(code__in=missing_codes)
            .select_related('submission_type', 'event', 'event__organizer')
            .prefetch_related('speakers')
            .order_by('title')
        )
    for submission in submissions:
        data['talks'].append(_pending_featured_talk_data(submission, event))


def _apply_pending_speaker_talks(data, event, user, schedule, speaker_user_codes, *, featured):
    filtered = _load_pending_speaker_talks(event, user, schedule, speaker_user_codes, featured=featured)
    data['talks'] = filtered.get('talks', [])
    data['tracks'] = filtered.get('tracks', [])
    data['rooms'] = filtered.get('rooms', [])
    _append_missing_pending_submissions(data, event, user, speaker_user_codes)
    return filtered


def _append_missing_featured_submissions(data, featured_by_code, event):
    present_codes = {talk.get('code') for talk in data.get('talks', [])}
    for code, submission in sorted(featured_by_code.items(), key=lambda item: str(item[1].title)):
        if code not in present_codes:
            data['talks'].append(_pending_featured_talk_data(submission, event))


def _empty_featured_schedule_data(event):
    schedule = event.wip_schedule
    data = schedule.build_data(
        all_talks=True,
        enrich=False,
        submission_codes=set(),
        include_featured_speaker_metadata=True,
        respect_public_visibility=False,
    )
    data['talks'] = []
    return data


def _pending_featured_talk_data(submission, event):
    cfp = event.cfp
    show_abstract = cfp.public_abstract
    show_do_not_record = cfp.request_do_not_record
    show_content_locale = cfp.public_content_locale
    talk_speakers = list(submission.speakers.all())
    return {
        'code': submission.code,
        'id': submission.code,
        'title': submission.title,
        'abstract': submission.abstract if show_abstract else '',
        'description': '',
        'speakers': [speaker.code for speaker in talk_speakers],
        'track': submission.track_id,
        'start': None,
        'end': None,
        'room': None,
        'duration': submission.get_duration(),
        'updated': submission.updated.isoformat() if submission.updated else None,
        'state': None,
        'fav_count': 0,
        'do_not_record': submission.do_not_record if show_do_not_record else None,
        'tags': submission.get_tag(),
        'session_type': submission.submission_type.name,
        'content_locale': submission.content_locale if show_content_locale else '',
        'schedule_pending': True,
    }


def _mark_talk_schedule_pending(talk_data):
    talk_data['start'] = None
    talk_data['end'] = None
    talk_data['room'] = None
    talk_data['schedule_pending'] = True
    return talk_data


def _ensure_schedule_speakers(data, event, include_featured_speaker_metadata):
    existing = {speaker['code'] for speaker in data.get('speakers', [])}
    needed_codes = {
        code
        for talk in data.get('talks', [])
        for code in talk.get('speakers') or []
        if code not in existing
    }
    if not needed_codes:
        return

    users = User.objects.filter(code__in=needed_codes)
    profiles = {
        profile.user_id: profile
        for profile in SpeakerProfile.objects.filter(event=event, user__in=users).select_related('user')
    }
    include_avatar, include_biography = speaker_public_field_flags(event)

    for user in users:
        profile = profiles.get(user.pk)
        speaker_data = {
            'code': user.code,
            'name': user.fullname or None,
            'biography': getattr(profile, 'biography', '') if include_biography else '',
            'avatar': user.get_avatar_url(event=event) if include_avatar else None,
            'avatar_thumbnail_default': (
                user.get_avatar_url(event=event, thumbnail='default') if include_avatar else None
            ),
            'avatar_thumbnail_tiny': (
                user.get_avatar_url(event=event, thumbnail='tiny') if include_avatar else None
            ),
            'is_featured': bool(getattr(profile, 'is_featured', False)),
            'featured_position': getattr(profile, 'position', None),
        }
        if not include_featured_speaker_metadata:
            speaker_data['is_featured'] = False
            speaker_data['featured_position'] = None
        data.setdefault('speakers', []).append(speaker_data)


def _schedule_json_includes_talk(schedule_json: str, submission_code: str) -> bool:
    try:
        data = json.loads(schedule_json)
    except json.JSONDecodeError:
        return False
    code = (submission_code or '').lower()
    if not code:
        return False
    for talk in data.get('talks', []) or []:
        if isinstance(talk, dict) and (talk.get('code') or '').lower() == code:
            return True
    return False


def build_pre_agenda_featured_talk_schedule_json(event, user, submission_code):
    """Build talk detail JSON for featured sessions before a schedule is released."""
    from eventyay.talk_rules.agenda import is_submission_visible_via_featured

    submission = (
        event.submissions.filter(code__iexact=submission_code)
        .select_related('submission_type')
        .prefetch_related('speakers')
        .first()
    )
    if not submission or not is_submission_visible_via_featured(user, submission):
        return '{}'

    featured = include_public_featured_speaker_metadata(user, event)
    data = _empty_featured_schedule_data(event)
    data['talks'] = [_pending_featured_talk_data(submission, event)]
    _ensure_schedule_speakers(data, event, featured)
    return serialize_widget_schedule_data(data, event=event)


def build_talk_schedule_json(request: HttpRequest, submission_code: str) -> str:
    """Build a minimal non-enriched schedule JSON scoped to a single talk.

    Only the target talk's slot is included.  Resources, answers, and exporters
    are intentionally omitted here; the Vue ``TalkDetail`` component fetches them
    from the submissions API endpoint so the inlined HTML payload stays tiny.
    """
    event = request.event
    user = request.user
    schedule = event.current_schedule
    featured = include_public_featured_speaker_metadata(user, event)

    if not schedule:
        return build_pre_agenda_featured_talk_schedule_json(event, user, submission_code)

    if schedule.version:
        cache_key = f'eagenda:talk:{schedule.pk}:{submission_code}:{int(featured)}'
        cached = cache.get(cache_key)
        if cached is not None and _schedule_json_includes_talk(cached, submission_code):
            return cached

    result = _serialize_schedule_build_data(
        schedule,
        enrich=False,
        submission_codes={submission_code},
        include_featured_speaker_metadata=featured,
    )

    if not _schedule_json_includes_talk(result, submission_code):
        featured_result = build_pre_agenda_featured_talk_schedule_json(event, user, submission_code)
        if featured_result != '{}':
            result = featured_result

    if schedule.version and _schedule_json_includes_talk(result, submission_code):
        cache.set(cache_key, result, CACHE_TTL)
    return result


def build_speaker_schedule_json_for_schedule(event, schedule, speaker_code, featured):
    """Build speaker-scoped schedule JSON without reading/writing the cache."""
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

    if not any(s['code'].lower() == speaker_code.lower() for s in data.get('speakers', [])):
        profile = get_speaker_profile_by_code(event, speaker_code)
        if profile:
            speaker_data = speaker_dict_from_profile(
                event,
                profile,
                include_featured_metadata=featured,
            )
            if speaker_data:
                data.setdefault('speakers', []).append(speaker_data)

    if not talk_codes:
        data['exports_disabled'] = True

    return serialize_widget_schedule_data(data, event=event)


def build_speaker_schedule_json(request: HttpRequest, speaker_code: str) -> str:
    """Build a minimal non-enriched schedule JSON scoped to a single speaker.

    Only the speaker's visible talk slots are included.  Speaker biography and
    avatar are present without enrichment so the ``SpeakerDetail`` Vue component
    can render immediately from inline data without a separate widget fetch.
    Speaker calendar export URLs are computed client-side by ``speakerExportOptions``
    in ``SessionModal.vue``, so ``enrich=False`` is safe here.
    """
    event = request.event
    featured = include_public_featured_speaker_metadata(request.user, event)
    schedule = event.current_schedule
    if schedule and can_view_public_schedule_sessions(request.user, event, schedule):
        if schedule.version:
            cache_key = f'eagenda:speaker:{schedule.pk}:{speaker_code}:{int(featured)}'
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        result = build_speaker_schedule_json_for_schedule(event, schedule, speaker_code, featured)

        if schedule.version:
            cache.set(cache_key, result, CACHE_TTL)
        return result

    if not speaker_may_show_pending_sessions(request.user, event, speaker_code):
        return '{}'
    return build_pending_speaker_schedule_json(event, request.user, speaker_code, featured)


def build_speakers_list_schedule_json(request: HttpRequest) -> str:
    """Build inline schedule JSON for the public speakers overview."""
    from django_scopes import scope

    event = request.event
    user = request.user
    if not can_list_released_schedule_speakers(user, event):
        return ''
    schedule = event.current_schedule
    featured = include_public_featured_speaker_metadata(user, event)
    with scope(event=event):
        data = schedule.build_data(
            all_talks=not schedule.version,
            include_featured_speaker_metadata=featured,
        )
    if not data:
        return ''
    return serialize_widget_schedule_data(data, event=event)


def warm_scoped_schedule_caches(schedule, *, featured):
    """Pre-warm per-talk and per-speaker inline JSON caches for a released schedule."""
    if not schedule.version:
        return

    submission_codes = schedule.talks.filter(
        is_visible=True,
        submission__isnull=False,
    ).values_list('submission__code', flat=True).distinct()
    for submission_code in submission_codes:
        cache_key = f'eagenda:talk:{schedule.pk}:{submission_code}:{int(featured)}'
        if cache.get(cache_key) is not None:
            continue
        cache.set(
            cache_key,
            _serialize_schedule_build_data(
                schedule,
                enrich=False,
                submission_codes={submission_code},
                include_featured_speaker_metadata=featured,
            ),
            CACHE_TTL,
        )

    speaker_codes = schedule.talks.filter(
        is_visible=True,
        submission__isnull=False,
    ).values_list('submission__speakers__code', flat=True).distinct()
    for speaker_code in speaker_codes:
        if not speaker_code:
            continue
        cache_key = f'eagenda:speaker:{schedule.pk}:{speaker_code}:{int(featured)}'
        if cache.get(cache_key) is not None:
            continue
        cache.set(
            cache_key,
            build_speaker_schedule_json_for_schedule(schedule.event, schedule, speaker_code, featured),
            CACHE_TTL,
        )


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


def redirect_when_public_speakers_unavailable(request):
    """Send visitors back to the info page with the same messaging as the schedule page."""
    return redirect_to_presale_with_warning(request, _('No published schedule.'))


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
    if has_public_featured_speakers(request.user, request.event):
        return False
    if can_list_released_schedule_speakers(request.user, request.event):
        return False
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
        if request.GET.get('featured') != 'true':
            return False
        return can_use_featured_exports(request.user, request.event)

    if isinstance(exporter, FavedICalExporter):
        return exporter.is_public(request=request)
    return bool(exporter.public)


def clear_featured_speakers_without_active_submissions(event, speakers):
    """Remove featured status from speakers who no longer have active submissions."""
    from eventyay.base.models import SpeakerProfile, Submission, SubmissionStates

    user_ids = [speaker.pk for speaker in speakers if speaker]
    if not user_ids:
        return

    inactive_states = SubmissionStates.terminal_states + (SubmissionStates.DRAFT,)
    active_speaker_ids = set(
        Submission.objects.filter(event=event, speakers__in=user_ids)
        .exclude(state__in=inactive_states)
        .values_list('speakers', flat=True)
        .distinct()
    )
    SpeakerProfile.objects.filter(event=event, user_id__in=user_ids, is_featured=True).exclude(
        user_id__in=active_speaker_ids
    ).update(is_featured=False)


def clear_schedule_caches(event, submission=None, speaker=None):
    """Clear all eagenda schedule caches for the event's schedules."""
    schedules = event.schedules.all()
    keys = []
    settings_part = schedule_widget_featured_cache_key_part(event)
    for schedule in schedules:
        for featured in (0, 1):
            keys.append(f'eagenda:schedule:{schedule.pk}:{featured}')
            keys.append(f'eagenda:schedule:{schedule.pk}:{featured}:{settings_part}')
            keys.append(f'eagenda:enriched:{schedule.pk}:{featured}')
            if submission:
                keys.append(f'eagenda:talk:{schedule.pk}:{submission.code}:{featured}')
            if speaker:
                keys.append(f'eagenda:speaker:{schedule.pk}:{speaker.code}:{featured}')
            elif submission:
                for sp in submission.speakers.all():
                    keys.append(f'eagenda:speaker:{schedule.pk}:{sp.code}:{featured}')

    cache.delete_many(keys)


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
    (event.pk, version, active language) to avoid firing Django signals on every request.
    """
    language = get_language() or ''
    cache_key = f'eagenda:exporters:{event.pk}:{version or ""}:{language}'
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
    cache.set(cache_key, result, CACHE_TTL)
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
    exporter.featured_only = request.GET.get('featured') == 'true'
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


class WipAgendaPreviewPageMixin:
    """Shared setup for first-party HTML pages under ``schedule/v/wip/``."""

    wip_preview = True

    def dispatch(self, request, *args, **kwargs):
        require_wip_schedule_access(request)
        return super().dispatch(request, *args, **kwargs)

    @context
    def schedule_version(self):
        return 'wip'
