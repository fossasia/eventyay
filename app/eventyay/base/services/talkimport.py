import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import requests
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.utils.dateparse import parse_datetime
from django.db import DataError, IntegrityError, OperationalError, models, transaction
from django.utils.crypto import get_random_string
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, make_aware, now
from django.utils.translation import gettext as _
from django_scopes import scope

from eventyay.base.i18n import language
from eventyay.base.models import (
    Answer,
    CachedFile,
    Event,
    Room,
    SpeakerProfile,
    Submission,
    Tag,
    Track,
    User,
)
from eventyay.base.models.question import (
    TalkQuestion,
    TalkQuestionRequired,
    TalkQuestionTarget,
    TalkQuestionVariant,
)
from eventyay.base.models.resource import create_slide_resource, delete_slide_resources
from eventyay.base.models.submission import SpeakerRole, SubmissionStates
from eventyay.base.models.type import SubmissionType
from eventyay.base.services.orderimport import parse_csv
from eventyay.base.services.tasks import ProfiledEventTask
from eventyay.celery_app import app
from eventyay.consts import SizeKey


try:
    from pytz.exceptions import AmbiguousTimeError, NonExistentTimeError
except ImportError:

    class AmbiguousTimeError(ValueError):
        pass

    class NonExistentTimeError(ValueError):
        pass


logger = logging.getLogger(__name__)

USER_CODE_MAX_LENGTH = User._meta.get_field('code').max_length or 16
USER_FULLNAME_MAX_LENGTH = User._meta.get_field('fullname').max_length or 255
SUBMISSION_CODE_MAX_LENGTH = Submission._meta.get_field('code').max_length or 16
ROOM_NAME_MAX_LENGTH = Room._meta.get_field('name').max_length or 100
TRACK_NAME_MAX_LENGTH = Track._meta.get_field('name').max_length or 200

# A rotating palette of distinct colours used when auto-creating tracks during import.
_TRACK_AUTO_COLORS = [
    '#3498db',
    '#2ecc71',
    '#e67e22',
    '#9b59b6',
    '#e74c3c',
    '#1abc9c',
    '#f39c12',
    '#2980b9',
    '#27ae60',
    '#8e44ad',
]
NORMALIZED_SPEAKER_SETTINGS = {
    key: f'csv:{key}'
    for key in (
        'full_name',
        'first_name',
        'last_name',
        'email',
        'biography',
        'identifier',
        'locale',
        'linked_submissions',
        'avatar_url',
        'avatar_source',
        'avatar_license',
        'is_featured',
        'featured_position',
    )
}
NORMALIZED_SUBMISSION_SETTINGS = {
    key: f'csv:{key}'
    for key in (
        'title',
        'code',
        'abstract',
        'description',
        'submission_type',
        'track',
        'state',
        'tags',
        'duration',
        'content_locale',
        'do_not_record',
        'is_featured',
        'notes',
        'internal_notes',
        'start',
        'end',
        'linked_speakers',
        'speakers',
        'room',
        'slides_link',
        'slides_links',
    )
}
LEGACY_IMPORT_KEY_PREFIX = 'legacy-import'
LEGACY_PUBLIC_IMPORT_FIELDS = {'website', 'github', 'linkedin', 'twitter'}
LEGACY_PRIVATE_IMPORT_FIELDS = {
    'phone',
    'address',
    'city',
    'country',
    'location',
    'state',
    'zipcode',
    'zip',
}
LEGACY_IMPORT_QUESTION_DEFINITIONS = {
    TalkQuestionTarget.SPEAKER: {
        'website': {'label': _('Website'), 'variant': TalkQuestionVariant.URL, 'is_public': True},
        'github': {'label': _('GitHub'), 'variant': TalkQuestionVariant.URL, 'is_public': True},
        'linkedin': {'label': _('LinkedIn'), 'variant': TalkQuestionVariant.URL, 'is_public': True},
        'twitter': {'label': _('Twitter'), 'variant': TalkQuestionVariant.URL, 'is_public': True},
        'facebook': {'label': _('Facebook'), 'variant': TalkQuestionVariant.URL, 'is_public': False},
        'instagram': {'label': _('Instagram'), 'variant': TalkQuestionVariant.URL, 'is_public': False},
        'blog': {'label': _('Blog'), 'variant': TalkQuestionVariant.URL, 'is_public': False},
        'company': {'label': _('Company'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'job_title': {'label': _('Job title'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'phone': {'label': _('Phone'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'city': {'label': _('City'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'country': {'label': _('Country'), 'variant': TalkQuestionVariant.COUNTRY, 'is_public': False},
        'location': {'label': _('Location'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
    },
    TalkQuestionTarget.SUBMISSION: {
        'subtitle': {'label': _('Subtitle'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'level': {'label': _('Level'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'audience_level': {'label': _('Audience level'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'complexity': {'label': _('Complexity'), 'variant': TalkQuestionVariant.STRING, 'is_public': False},
        'room_notes': {'label': _('Room notes'), 'variant': TalkQuestionVariant.TEXT, 'is_public': False},
    },
}


class ImportExecutionError(Exception):
    pass


class ImportResult(TypedDict):
    created: int
    updated: int
    skipped: int
    errors: list[str]


def _resolve_csv(mapping_value, record):
    if not mapping_value:
        return ''
    if mapping_value.startswith('csv:'):
        return (record.get(mapping_value[4:]) or '').strip()
    if mapping_value.startswith('static:'):
        return mapping_value[7:]
    return ''


def _truthy(value):
    return value.lower() in ('yes', 'true', '1', 'ja', 'oui', 'y')


def _normalize_import_value(value, *, key=None):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (list, tuple)):
        normalized_parts = [_normalize_import_value(item, key=key) for item in value]
        separator = '\n' if key == 'slides_links' else ', '
        return separator.join(part for part in normalized_parts if part)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    return str(value).strip()


def _normalize_import_record(record, settings):
    return {key: _normalize_import_value(record.get(key), key=key) for key in settings}


def _normalize_extra_key(key) -> str:
    return re.sub(r'[^a-z0-9]+', '_', str(key or '').strip().lower()).strip('_')


def _humanize_import_key(key: str) -> str:
    label_overrides = {
        'github': 'GitHub',
        'linkedin': 'LinkedIn',
        'twitter': 'Twitter',
        'facebook': 'Facebook',
        'instagram': 'Instagram',
    }
    if key in label_overrides:
        return label_overrides[key]
    return key.replace('_', ' ').strip().capitalize()


def _normalize_import_extras(extras) -> dict:
    if not isinstance(extras, dict):
        return {}

    normalized = {}
    for key, value in extras.items():
        normalized_key = _normalize_extra_key(key)
        if not normalized_key or value in (None, '', [], {}):
            continue
        normalized[normalized_key] = value
    return normalized


def _infer_question_variant(key: str, value) -> str:
    key = key.lower()
    if isinstance(value, bool):
        return TalkQuestionVariant.BOOLEAN
    if key in {'country'} or key.endswith('_country'):
        return TalkQuestionVariant.COUNTRY
    if key in {'website', 'github', 'linkedin', 'twitter', 'facebook', 'instagram', 'blog'}:
        return TalkQuestionVariant.URL
    if isinstance(value, str) and (value.strip().startswith('http://') or value.strip().startswith('https://')):
        return TalkQuestionVariant.URL
    if isinstance(value, str) and ('\n' in value or len(value.strip()) > 200):
        return TalkQuestionVariant.TEXT
    return TalkQuestionVariant.STRING


def _build_import_question_definition(target: str, key: str, value) -> dict:
    registry = LEGACY_IMPORT_QUESTION_DEFINITIONS.get(target, {})
    definition = registry.get(key, {})
    return {
        'label': definition.get('label') or _humanize_import_key(key),
        'variant': definition.get('variant') or _infer_question_variant(key, value),
        'is_public': definition.get('is_public', key in LEGACY_PUBLIC_IMPORT_FIELDS),
        'contains_personal_data': definition.get(
            'contains_personal_data',
            key in LEGACY_PRIVATE_IMPORT_FIELDS,
        ),
    }


def _build_import_question_key(target: str, key: str) -> str:
    return f'{LEGACY_IMPORT_KEY_PREFIX}:{target}:{key}'


def _next_import_question_position(event: Event, target: str, caches: dict) -> int:
    positions = caches.setdefault('import_question_positions', {})
    if target not in positions:
        positions[target] = (
            TalkQuestion.all_objects.filter(event=event, target=target).aggregate(position=models.Max('position'))[
                'position'
            ]
            or 0
        )
    positions[target] += 1
    return positions[target]


def _upsert_import_question(event: Event, target: str, key: str, value, caches: dict) -> TalkQuestion:
    cache_key = (target, key)
    question_cache = caches.setdefault('import_questions', {})
    if cache_key in question_cache:
        return question_cache[cache_key]

    question = TalkQuestion.all_objects.filter(
        event=event,
        target=target,
        import_key=_build_import_question_key(target, key),
    ).first()
    definition = _build_import_question_definition(target, key, value)

    if question is None:
        question = TalkQuestion.objects.create(
            event=event,
            target=target,
            import_key=_build_import_question_key(target, key),
            is_imported=True,
            active=True,
            question_required=TalkQuestionRequired.OPTIONAL,
            variant=definition['variant'],
            question=definition['label'],
            is_public=definition['is_public'],
            contains_personal_data=definition['contains_personal_data'],
            position=_next_import_question_position(event, target, caches),
        )
    else:
        update_fields = []
        desired_values = {
            'question': definition['label'],
            'variant': definition['variant'],
            'is_imported': True,
            'active': True,
            'question_required': TalkQuestionRequired.OPTIONAL,
            'contains_personal_data': definition['contains_personal_data'],
        }
        if not question.import_key:
            desired_values['import_key'] = _build_import_question_key(target, key)
        for field_name, field_value in desired_values.items():
            if getattr(question, field_name) != field_value:
                setattr(question, field_name, field_value)
                update_fields.append(field_name)
        if update_fields:
            question.save(update_fields=update_fields)

    question_cache[cache_key] = question
    return question


def _serialize_answer_value(value, variant: str) -> str:
    if variant == TalkQuestionVariant.BOOLEAN:
        if isinstance(value, bool):
            return 'True' if value else 'False'
        return 'True' if _truthy(str(value).strip().lower()) else 'False'

    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, (list, tuple)):
        return ', '.join(str(item).strip() for item in value if str(item).strip())

    answer_value = str(value).strip()
    if variant == TalkQuestionVariant.COUNTRY:
        return answer_value.upper()
    return answer_value


def _split_slide_links(value: str) -> list[str]:
    if not value:
        return []
    slide_links = []
    for line in value.splitlines():
        for item in line.split(','):
            cleaned = item.strip()
            if cleaned:
                slide_links.append(cleaned)
    return slide_links


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _is_pdf_link(value: str) -> bool:
    return Path(urlparse(value).path).suffix.lower() == '.pdf'


def import_speaker_records(event: Event, records, acting_user) -> ImportResult:
    created = 0
    updated = 0
    skipped = 0
    errors = []
    caches = {'import_questions': {}, 'import_question_positions': {}}

    with scope(event=event):
        for row_num, record in enumerate(records, start=1):
            try:
                normalized_record = _normalize_import_record(record, NORMALIZED_SPEAKER_SETTINGS)
                normalized_record['speaker_extras'] = record.get('speaker_extras') if isinstance(record, dict) else None
                was_created = _import_speaker_row(
                    event,
                    NORMALIZED_SPEAKER_SETTINGS,
                    normalized_record,
                    acting_user,
                    caches=caches,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except ImportExecutionError as error:
                skipped += 1
                errors.append(_('Row {row}: {error}').format(row=row_num, error=error))
            except (IntegrityError, DataError):
                skipped += 1
                logger.exception('Speaker import database error at row %s for event %s', row_num, event.slug)
                errors.append(
                    _('Row {row}: A database error occurred while importing this speaker.').format(row=row_num)
                )

    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}


def import_submission_records(event: Event, records, acting_user) -> ImportResult:
    submission_types = list(SubmissionType.objects.filter(event=event))
    tracks = list(Track.objects.filter(event=event))
    rooms = list(Room.objects.filter(event=event))
    caches = {
        'submission_types': submission_types,
        'tracks': tracks,
        'rooms': rooms,
        'valid_states': {choice[0] for choice in SubmissionStates.get_choices()},
        'default_sub_type': submission_types[0] if submission_types else None,
        'question_mappings': [],
        'question_cache': {},
        'import_questions': {},
        'import_question_positions': {},
    }
    speaker_cache = {}
    created = 0
    updated = 0
    skipped = 0
    errors = []

    with scope(event=event):
        for row_num, record in enumerate(records, start=1):
            try:
                normalized_record = _normalize_import_record(record, NORMALIZED_SUBMISSION_SETTINGS)
                if isinstance(record, dict):
                    normalized_record['submission_extras'] = record.get('submission_extras')
                    normalized_record['room_metadata'] = record.get('room_metadata')
                    normalized_record['scheduled_public'] = record.get('scheduled_public')
                was_created = _import_submission_row(
                    event,
                    NORMALIZED_SUBMISSION_SETTINGS,
                    normalized_record,
                    acting_user,
                    speaker_cache,
                    caches,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except ImportExecutionError as error:
                skipped += 1
                errors.append(_('Row {row}: {error}').format(row=row_num, error=error))
            except (IntegrityError, DataError):
                skipped += 1
                logger.exception('Session import database error at row %s for event %s', row_num, event.slug)
                errors.append(
                    _('Row {row}: A database error occurred while importing this session.').format(row=row_num)
                )

    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}


def _normalize_speaker_identifier(identifier: str) -> str:
    normalized = identifier.strip()
    if not normalized:
        return ''
    if len(normalized) > USER_CODE_MAX_LENGTH:
        return ''
    return normalized


def _find_submission_by_ref(event, ref):
    ref = ref.strip()
    if not ref:
        return None
    qs = Submission.objects.filter(event=event)
    sub = qs.filter(code__iexact=ref).first()
    if sub:
        return sub
    try:
        by_pk = qs.filter(pk=int(ref)).first()
        if by_pk:
            return by_pk
    except (ValueError, TypeError):
        pass
    return qs.filter(title__iexact=ref).first()


def _find_user_for_speaker(event, ref):
    ref = ref.strip()
    if not ref:
        return None
    profile = SpeakerProfile.objects.filter(event=event, user__code__iexact=ref).select_related('user').first()
    if profile:
        return profile.user
    user = User.objects.filter(code__iexact=ref).first()
    if user:
        return user
    user = User.objects.filter(email__iexact=ref).first()
    if user:
        return user
    profile = SpeakerProfile.objects.filter(event=event, user__fullname__iexact=ref).select_related('user').first()
    if profile:
        return profile.user
    return None


def _normalize_email_address(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return ''
    try:
        validate_email(normalized)
    except ValidationError:
        return ''
    return normalized


def _split_csv_values(raw_value: str) -> list[str]:
    if not raw_value:
        return []
    values = []
    for value in raw_value.split(','):
        stripped = value.strip()
        if stripped:
            values.append(stripped)
    return values


def _zip_speaker_refs_and_names(linked_speakers: str, speakers_val: str) -> list[tuple[str, str]]:
    refs = _split_csv_values(linked_speakers)
    names = _split_csv_values(speakers_val)
    if refs and names and len(refs) == len(names):
        return list(zip(refs, names, strict=True))
    pairs: list[tuple[str, str]] = []
    pairs.extend((ref, '') for ref in refs)
    pairs.extend(('', name) for name in names)
    return pairs


def _speaker_cache_key(speaker_ref: str, speaker_name: str) -> str:
    normalized_ref = speaker_ref.strip().lower()
    if normalized_ref:
        return f'ref:{normalized_ref}'
    normalized_name = speaker_name.strip().lower()
    if normalized_name:
        return f'name:{normalized_name}'
    return ''


def _upsert_session_speaker(event, speaker_ref: str, speaker_name: str):
    normalized_ref = speaker_ref.strip()
    normalized_name = speaker_name.strip()[:USER_FULLNAME_MAX_LENGTH] if speaker_name else ''

    user = None
    if normalized_ref:
        user = _find_user_for_speaker(event, normalized_ref)
    if not user and normalized_name:
        user = _find_user_for_speaker(event, normalized_name)

    normalized_email = _normalize_email_address(normalized_ref) if normalized_ref else ''
    normalized_identifier = ''
    if normalized_ref and not normalized_email:
        normalized_identifier = _normalize_speaker_identifier(normalized_ref)

    if user:
        update_fields = []
        if normalized_name and user.fullname != normalized_name:
            user.fullname = normalized_name
            update_fields.append('fullname')
        if (
            normalized_email
            and not user.email
            and not User.objects.filter(email__iexact=normalized_email).exclude(pk=user.pk).exists()
        ):
            user.email = normalized_email
            update_fields.append('email')
        if (
            normalized_identifier
            and not user.code
            and not User.objects.filter(code__iexact=normalized_identifier).exclude(pk=user.pk).exists()
        ):
            user.code = normalized_identifier
            update_fields.append('code')
        if update_fields:
            user.save(update_fields=update_fields)
    else:
        fallback_name = normalized_name
        if not fallback_name:
            fallback_name = normalized_identifier or (normalized_email.split('@', 1)[0] if normalized_email else '')
        if not fallback_name:
            return None
        # Pre-check explicit email/code values to avoid unique constraint violations during user creation.
        create_email = normalized_email or None
        existing_user = User.objects.filter(email__iexact=create_email).first() if create_email else None
        if existing_user:
            user = existing_user
        else:
            create_code = normalized_identifier or None
            if create_code and User.objects.filter(code__iexact=create_code).exists():
                create_code = None
            user = User.objects.create_user(
                password=get_random_string(32),
                email=create_email,
                fullname=fallback_name[:USER_FULLNAME_MAX_LENGTH],
                code=create_code,
                pw_reset_token=get_random_string(32),
                pw_reset_time=now() + dt.timedelta(days=60),
            )

    SpeakerProfile.objects.get_or_create(user=user, event=event)
    return user


@app.task(base=ProfiledEventTask, bind=True, throws=(ImportExecutionError,))
def import_speakers(self, event: Event, fileid: str, settings: dict, locale: str, user_id) -> ImportResult:
    try:
        cf = CachedFile.objects.get(id=fileid)
    except CachedFile.DoesNotExist:
        raise ImportExecutionError(
            _('The uploaded speaker file could not be found. Please upload it again and restart the import.')
        )
    try:
        acting_user = User.objects.get(pk=user_id)
        with language(locale, event.settings.region):
            with scope(event=event):
                parsed = parse_csv(cf.file, django_settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV])
                if parsed is None:
                    raise ImportExecutionError(_('Could not parse the CSV file.'))
                parsed = list(parsed)
                
                total = len(parsed)

                created = 0
                updated = 0
                skipped = 0
                errors = []

                for row_num, record in enumerate(parsed, start=2):
                    if total > 0 and (row_num - 2) % max(1, total // 10) == 0:
                        self.update_state(state='PROGRESS', meta={'value': round((row_num - 2) / total * 100)})
                    try:
                        was_created = _import_speaker_row(event, settings, record, acting_user)
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                    except ImportExecutionError as e:
                        skipped += 1
                        errors.append(_('Row {row}: {error}').format(row=row_num, error=e))
                    except (IntegrityError, DataError):
                        skipped += 1
                        logger.exception('Speaker import database error at row %s for event %s', row_num, event.slug)
                        errors.append(
                            _('Row {row}: A database error occurred while importing this speaker.').format(row=row_num)
                        )

                logger.info(
                    'Speaker import for event %s: created=%d, updated=%d, skipped=%d',
                    event.slug,
                    created,
                    updated,
                    skipped,
                )
    finally:
        cf.delete()
    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}


def _apply_user_optional_fields(user, *, locale_val, avatar_url, avatar_source, avatar_license, identifier):
    """Apply optional field updates to a User instance and return changed field names."""
    update_fields = []
    if locale_val:
        user.locale = locale_val
        update_fields.append('locale')
    if avatar_source:
        user.avatar_source = avatar_source
        update_fields.append('avatar_source')
    if avatar_license:
        user.avatar_license = avatar_license
        update_fields.append('avatar_license')
    update_fields.extend(_set_external_avatar_url(user, avatar_url))
    if identifier:
        if (
            identifier
            and not user.code
            and not User.objects.filter(
                code__iexact=identifier,
            )
            .exclude(pk=user.pk)
            .exists()
        ):
            user.code = identifier
            update_fields.append('code')
    return update_fields


def _normalize_avatar_url(value: str) -> str:
    avatar_url = (value or '').strip()
    if avatar_url.startswith('//'):
        avatar_url = f'https:{avatar_url}'
    parsed = urlparse(avatar_url)
    if parsed.scheme in {'http', 'https'} and parsed.netloc:
        return avatar_url
    return ''


def _set_external_avatar_url(user: User, avatar_url: str) -> list[str]:
    avatar_url = _normalize_avatar_url(avatar_url)
    if not avatar_url:
        return []

    # Skip if user already has a locally stored avatar
    if user.avatar:
        return []

    # Determine file extension from URL
    url_path = urlparse(avatar_url).path
    ext = Path(url_path).suffix.lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
        ext = '.jpg'

    try:
        # Disable redirects so we can validate the final destination URL before
        # following it; this prevents open-redirect-assisted SSRF.
        response = requests.get(
            avatar_url,
            timeout=(5, 10),  # (connect, read) seconds
            allow_redirects=False,
            stream=True,
        )
        # Follow at most one redirect, but re-validate the Location header.
        if response.is_redirect:
            location = response.headers.get('Location', '')
            location = _normalize_avatar_url(location)
            if not location:
                raise ValueError(f'Redirect to disallowed URL: {response.headers.get("Location")}')
            response = requests.get(location, timeout=(5, 10), allow_redirects=False, stream=True)

        response.raise_for_status()

        # Guard against huge files (10 MB cap)
        max_bytes = 10 * 1024 * 1024
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError('Avatar image exceeds 10 MB limit')
            chunks.append(chunk)
        content = b''.join(chunks)
        if not content:
            raise ValueError('Empty response body')
    except (requests.exceptions.RequestException, ValueError):
        logger.warning('Could not download avatar for user %s from %s', user.pk, avatar_url)
        # Fall back: store the external URL in profile so it can still be displayed
        profile = dict(user.profile or {})
        avatar = profile.get('avatar')
        avatar = dict(avatar) if isinstance(avatar, dict) else {}
        if avatar.get('url') == avatar_url:
            return []
        avatar['url'] = avatar_url
        profile['avatar'] = avatar
        user.profile = profile
        return ['profile']

    filename = f'avatar_{user.code or user.pk}{ext}'
    # save=False: we return ['avatar'] so the caller includes it in user.save(update_fields=...)
    # process_image must be called by the caller AFTER user.save() to avoid a race condition
    user.avatar.save(filename, ContentFile(content), save=False)
    return ['avatar']



def _parse_featured_position(value: str) -> int | None:
    if not value:
        return None
    try:
        position = int(value)
    except (TypeError, ValueError):
        return None
    return position if position >= 0 else None


def _sync_import_answers(*, event: Event, target: str, extras, caches: dict, submission=None, person=None):
    if extras is None:
        return

    normalized_extras = _normalize_import_extras(extras)
    import_keys = set()
    for key, value in normalized_extras.items():
        question = _upsert_import_question(event, target, key, value, caches)
        import_keys.add(question.import_key)
        _set_question_answer(
            question.pk,
            value,
            question_cache=caches.get('question_cache'),
            submission=submission,
            person=person,
            event=event,
        )

    if target == TalkQuestionTarget.SPEAKER and person is not None:
        stale_answers = person.answers.filter(
            question__event=event,
            question__target=target,
            question__is_imported=True,
        )
    elif target == TalkQuestionTarget.SUBMISSION and submission is not None:
        stale_answers = submission.answers.filter(
            question__event=event,
            question__target=target,
            question__is_imported=True,
        )
    else:
        return

    if import_keys:
        stale_answers = stale_answers.exclude(question__import_key__in=import_keys)
    for answer in stale_answers:
        answer.remove(force=True)


def _normalize_room_metadata(metadata) -> dict:
    if not isinstance(metadata, dict):
        return {}
    return {key: value for key, value in metadata.items() if value not in (None, '', [], {})}


def _build_room_description(metadata: dict) -> str:
    parts = []
    legacy_name = str(metadata.get('name') or '').strip()
    legacy_room = str(metadata.get('room') or '').strip()
    floor = str(metadata.get('floor') or '').strip()
    if legacy_name and legacy_name != legacy_room:
        parts.append(_('Legacy microlocation: {name}').format(name=legacy_name))
    if floor:
        parts.append(_('Floor: {floor}').format(floor=floor))
    return '\n'.join(parts)


def _apply_room_metadata(room: Room, room_metadata: dict):
    metadata = _normalize_room_metadata(room_metadata)
    if not metadata:
        return

    update_fields = []
    import_id = str(metadata.get('import_id') or metadata.get('id') or '').strip()
    if import_id and room.import_id != import_id:
        room.import_id = import_id
        update_fields.append('import_id')

    description = _build_room_description(metadata)
    if description and not room.description:
        room.description = description
        update_fields.append('description')

    speaker_info = str(metadata.get('speaker_info') or '').strip()
    if speaker_info and not room.speaker_info:
        room.speaker_info = speaker_info
        update_fields.append('speaker_info')

    schedule_data = dict(room.schedule_data or {})
    if schedule_data.get('legacy_microlocation') != metadata:
        schedule_data['legacy_microlocation'] = metadata
        room.schedule_data = schedule_data
        update_fields.append('schedule_data')

    if update_fields:
        room.save(update_fields=update_fields)


def _append_internal_note(existing: str, line: str) -> str:
    existing_text = (existing or '').strip()
    if line in existing_text.splitlines():
        return existing
    if not existing_text:
        return line
    return f'{existing_text}\n{line}'


def _import_speaker_row(event, settings, record, acting_user, caches=None):
    full_name = _resolve_csv(settings.get('full_name'), record)
    first_name = _resolve_csv(settings.get('first_name'), record)
    last_name = _resolve_csv(settings.get('last_name'), record)
    email = _resolve_csv(settings.get('email'), record)
    biography = _resolve_csv(settings.get('biography'), record)
    identifier = _resolve_csv(settings.get('identifier'), record)
    locale_val = _resolve_csv(settings.get('locale'), record)
    linked_submissions = _resolve_csv(settings.get('linked_submissions'), record)
    avatar_url = _resolve_csv(settings.get('avatar_url'), record)
    avatar_source = _resolve_csv(settings.get('avatar_source'), record)
    avatar_license = _resolve_csv(settings.get('avatar_license'), record)
    is_featured = _resolve_csv(settings.get('is_featured'), record)
    featured_position = _resolve_csv(settings.get('featured_position'), record)
    speaker_extras = record.get('speaker_extras') if isinstance(record, dict) else None

    if not email:
        raise ImportExecutionError(_('Missing email address.'))
    normalized_email = _normalize_email_address(email)
    if not normalized_email:
        raise ImportExecutionError(_('Invalid email address.'))

    name = full_name or f'{first_name} {last_name}'.strip()
    if not name:
        raise ImportExecutionError(_('Missing speaker name.'))
    if len(name) > USER_FULLNAME_MAX_LENGTH:
        raise ImportExecutionError(
            _('Speaker name is too long (maximum {max} characters).').format(max=USER_FULLNAME_MAX_LENGTH)
        )

    normalized_identifier = _normalize_speaker_identifier(identifier) if identifier else ''
    if identifier and identifier.strip() and not normalized_identifier:
        raise ImportExecutionError(
            _('Speaker identifier is too long (maximum {max} characters).').format(max=USER_CODE_MAX_LENGTH)
        )

    optional_kwargs = dict(
        locale_val=locale_val,
        avatar_url=avatar_url,
        avatar_source=avatar_source,
        avatar_license=avatar_license,
        identifier=normalized_identifier,
    )

    # Upsert user: try by identifier/code first, then by email
    user = None
    if normalized_identifier:
        profile = (
            SpeakerProfile.objects.filter(event=event, user__code__iexact=normalized_identifier)
            .select_related('user')
            .first()
        )
        if profile:
            user = profile.user
        else:
            user = User.objects.filter(code__iexact=normalized_identifier).first()

    if not user:
        user = User.objects.filter(email__iexact=normalized_email).first()
    if not user:
        profiles = list(
            SpeakerProfile.objects.filter(event=event, user__fullname__iexact=name)
            .select_related('user')[:2]
        )
        if len(profiles) == 1:
            user = profiles[0].user

    with transaction.atomic():
        if user:
            user.fullname = name
            extra = _apply_user_optional_fields(user, **optional_kwargs)
            update_fields = ['fullname', *extra]
            if (
                normalized_email
                and not user.email
                and not User.objects.filter(email__iexact=normalized_email).exclude(pk=user.pk).exists()
            ):
                user.email = normalized_email
                update_fields.append('email')
            user.save(update_fields=update_fields)
            if 'avatar' in update_fields:
                user.process_image('avatar', generate_thumbnail=True)
        else:
            user = User.objects.create_user(
                password=get_random_string(32),
                email=normalized_email,
                fullname=name,
                code=normalized_identifier or None,
                pw_reset_token=get_random_string(32),
                pw_reset_time=now() + dt.timedelta(days=60),
            )
            extra = _apply_user_optional_fields(user, **optional_kwargs)
            if extra:
                user.save(update_fields=extra)
            if 'avatar' in extra:
                user.process_image('avatar', generate_thumbnail=True)

        profile, profile_created = SpeakerProfile.objects.get_or_create(
            user=user,
            event=event,
        )
        profile_update_fields = []
        if biography:
            profile.biography = biography
            profile_update_fields.append('biography')
        if is_featured:
            profile.is_featured = _truthy(is_featured)
            profile_update_fields.append('is_featured')
        if featured_position:
            position = _parse_featured_position(featured_position)
            if position is not None:
                profile.position = position
                profile_update_fields.append('position')
        if profile_update_fields:
            profile.save(update_fields=profile_update_fields)

        # Link to submissions
        if linked_submissions:
            for ref in linked_submissions.split(','):
                sub = _find_submission_by_ref(event, ref)
                if sub:
                    SpeakerRole.objects.get_or_create(submission=sub, user=user)

        _sync_import_answers(
            event=event,
            target=TalkQuestionTarget.SPEAKER,
            extras=speaker_extras,
            caches=caches or {},
            person=user,
        )

        event.log_action(
            'eventyay.speaker.imported',
            data={'email': email, 'name': name},
            user=acting_user,
        )

    return profile_created


@app.task(base=ProfiledEventTask, bind=True, throws=(ImportExecutionError,))
def import_submissions(self, event: Event, fileid: str, settings: dict, locale: str, user_id) -> ImportResult:
    cf = CachedFile.objects.get(id=fileid)
    try:
        acting_user = User.objects.get(pk=user_id)
        with language(locale, event.settings.region):
            with scope(event=event):
                parsed = parse_csv(cf.file, django_settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV])
                if parsed is None:
                    raise ImportExecutionError(_('Could not parse the CSV file.'))
                parsed = list(parsed)
                
                total = len(parsed)

                # Pre-fetch per-event lookups once to avoid N+1 queries inside the row loop
                submission_types = list(SubmissionType.objects.filter(event=event))
                tracks = list(Track.objects.filter(event=event))
                rooms = list(Room.objects.filter(event=event))
                caches = {
                    'submission_types': submission_types,
                    'tracks': tracks,
                    'rooms': rooms,
                    'valid_states': {choice[0] for choice in SubmissionStates.get_choices()},
                    'default_sub_type': submission_types[0] if submission_types else None,
                }

                question_mappings = []
                for key, value in settings.items():
                    if key.startswith('question_') and value:
                        try:
                            question_id = int(key.split('_', 1)[1])
                        except (ValueError, IndexError):
                            continue
                        question_mappings.append((question_id, value))

                question_cache = {}
                if question_mappings:
                    question_ids = {question_id for question_id, _ in question_mappings}
                    questions = TalkQuestion.objects.filter(event=event, pk__in=question_ids).prefetch_related(
                        'options'
                    )
                    for question in questions:
                        option_lookup = None
                        if question.variant in (TalkQuestionVariant.CHOICES, TalkQuestionVariant.MULTIPLE, TalkQuestionVariant.SELECT):
                            option_lookup = {
                                str(option.answer).strip().casefold(): option for option in question.options.all()
                            }
                        question_cache[question.pk] = (question, option_lookup)

                caches['question_mappings'] = question_mappings
                caches['question_cache'] = question_cache

                created = 0
                updated = 0
                skipped = 0
                errors = []
                speaker_cache = {}

                for row_num, record in enumerate(parsed, start=2):
                    if total > 0 and (row_num - 2) % max(1, total // 10) == 0:
                        self.update_state(state='PROGRESS', meta={'value': round((row_num - 2) / total * 100)})
                    try:
                        was_created = _import_submission_row(
                            event, settings, record, acting_user, speaker_cache, caches
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                    except ImportExecutionError as e:
                        skipped += 1
                        errors.append(_('Row {row}: {error}').format(row=row_num, error=e))
                    except (IntegrityError, DataError):
                        skipped += 1
                        logger.exception('Session import database error at row %s for event %s', row_num, event.slug)
                        errors.append(
                            _('Row {row}: A database error occurred while importing this session.').format(row=row_num)
                        )

                logger.info(
                    'Session import for event %s: created=%d, updated=%d, skipped=%d',
                    event.slug,
                    created,
                    updated,
                    skipped,
                )
    finally:
        cf.delete()
    return {'created': created, 'updated': updated, 'skipped': skipped, 'errors': errors}


def _apply_submission_fields(
    sub,
    *,
    abstract,
    description,
    track,
    duration_val,
    content_locale,
    do_not_record,
    is_featured,
    notes,
    internal_notes,
):
    """Apply optional field values to a Submission instance (new or existing)."""
    if abstract:
        sub.abstract = abstract
    if description:
        sub.description = description
    if track:
        sub.track = track
    if duration_val:
        try:
            sub.duration = int(duration_val)
        except (ValueError, TypeError):
            pass
    if content_locale:
        sub.content_locale = content_locale[:32]
    if do_not_record:
        sub.do_not_record = _truthy(do_not_record)
    if is_featured:
        sub.is_featured = _truthy(is_featured)
    if notes:
        sub.notes = notes
    if internal_notes:
        sub.internal_notes = internal_notes


def _import_submission_row(event, settings, record, acting_user, speaker_cache=None, caches=None):
    title = _resolve_csv(settings.get('title'), record)
    code = _resolve_csv(settings.get('code'), record)
    abstract = _resolve_csv(settings.get('abstract'), record)
    description = _resolve_csv(settings.get('description'), record)
    sub_type_val = _resolve_csv(settings.get('submission_type'), record)
    track_val = _resolve_csv(settings.get('track'), record)
    state_val = _resolve_csv(settings.get('state'), record)
    tags_val = _resolve_csv(settings.get('tags'), record)
    duration_val = _resolve_csv(settings.get('duration'), record)
    content_locale = _resolve_csv(settings.get('content_locale'), record)
    do_not_record = _resolve_csv(settings.get('do_not_record'), record)
    is_featured = _resolve_csv(settings.get('is_featured'), record)
    notes = _resolve_csv(settings.get('notes'), record)
    internal_notes = _resolve_csv(settings.get('internal_notes'), record)
    start_val = _resolve_csv(settings.get('start'), record)
    end_val = _resolve_csv(settings.get('end'), record)
    linked_speakers = _resolve_csv(settings.get('linked_speakers'), record)
    speakers_val = _resolve_csv(settings.get('speakers'), record)
    room_val = _resolve_csv(settings.get('room'), record)
    slides_link = _resolve_csv(settings.get('slides_link'), record)
    slides_links_val = _resolve_csv(settings.get('slides_links'), record)
    submission_extras = record.get('submission_extras') if isinstance(record, dict) else None
    room_metadata = record.get('room_metadata') if isinstance(record, dict) else None
    scheduled_public = bool(record.get('scheduled_public')) if isinstance(record, dict) else False

    if not title:
        raise ImportExecutionError(_('Missing session title.'))
    title = title[:200]

    slide_links = []
    if slides_link:
        slide_links.append(slides_link)
    slide_links.extend(_split_slide_links(slides_links_val))
    slide_links = _dedupe_preserving_order(slide_links)
    for slide_link in slide_links:
        if not _is_pdf_link(slide_link):
            raise ImportExecutionError(_('Slides links must point to PDF files.'))

    normalized_code = code.strip().upper() if code else ''
    if normalized_code and len(normalized_code) > SUBMISSION_CODE_MAX_LENGTH:
        normalized_code = ''

    # Resolve submission type (use pre-fetched cache to avoid per-row DB queries)
    sub_type = _resolve_submission_type(sub_type_val, caches) if sub_type_val and caches else None
    if not sub_type:
        sub_type = caches['default_sub_type'] if caches else event.submission_types.first()
    if not sub_type:
        raise ImportExecutionError(_('No session type found for this event.'))

    # Resolve track (auto-create if not found)
    track = _resolve_or_create_track(track_val, event, caches) if track_val else None

    # Resolve state (use pre-fetched valid_states set)
    valid_states = caches['valid_states'] if caches else {choice[0] for choice in SubmissionStates.get_choices()}
    normalized_state = state_val.strip().lower() if state_val else ''
    state = normalized_state if normalized_state in valid_states else SubmissionStates.SUBMITTED

    # Upsert by code
    optional_fields = dict(
        abstract=abstract,
        description=description,
        track=track,
        duration_val=duration_val,
        content_locale=content_locale,
        do_not_record=do_not_record,
        is_featured=is_featured,
        notes=notes,
        internal_notes=internal_notes,
    )
    if scheduled_public and state == SubmissionStates.ACCEPTED:
        optional_fields['internal_notes'] = _append_internal_note(
            internal_notes,
            _('Legacy original state: accepted'),
        )
    # Upsert: match by code within this event first, then fall back to title.
    # The title fallback handles cross-event imports where the CSV carries codes
    # from a different event (those codes exist globally, so the first import
    # silently gets new auto-generated codes; subsequent imports must still deduplicate).
    submission = None
    if normalized_code:
        submission = Submission.objects.filter(event=event, code__iexact=normalized_code).first()
    if submission is None:
        submission = Submission.objects.filter(event=event, title__iexact=title).first()
    was_created = submission is None

    if was_created:
        submission = Submission(
            event=event,
            title=title,
            submission_type=sub_type,
            state=state,
            code=normalized_code or None,
        )
        if not submission.code:
            # assign_code() must run outside any transaction: its IntegrityError retry loop
            # issues DB queries after catching the error, which triggers
            # TransactionManagementError inside an enclosing PostgreSQL transaction.
            submission.assign_code()
    else:
        submission.title = title
        submission.submission_type = sub_type
        submission.state = state

    _apply_submission_fields(submission, **optional_fields)

    # submission.save() must stay OUTSIDE atomic(): GenerateCode's retry loop issues DB queries
    # after catching IntegrityError, which poisons any enclosing PostgreSQL transaction.
    try:
        submission.save()
    except (IntegrityError, DataError) as exc:
        logger.exception('Failed to save imported session "%s" for event %s', title, event.slug)
        raise ImportExecutionError(_('A database error occurred while saving this session.')) from exc

    # Wrap all post-save writes atomically so a failure in tags/speakers/questions rolls back
    # those side effects without affecting the already-committed submission row.
    # If the atomic block fails for a newly created submission, delete it so the DB stays
    # consistent with what the result counters report.
    try:
        with transaction.atomic():
            # Ensure TalkSlot exists in WIP schedule (required for schedule editor visibility)
            submission.update_talk_slots()

            # Tags
            if tags_val:
                for tag_name in tags_val.split(','):
                    stripped_tag = tag_name.strip()[:50]
                    if stripped_tag:
                        tag, _created = Tag.objects.get_or_create(event=event, tag=stripped_tag)
                        submission.tags.add(tag)

            # Room assignment (via slot if schedule exists; use pre-fetched cache)
            slot = submission.slots.filter(schedule=event.wip_schedule).first()

            # Schedule start/end import (best effort; only applied if a slot exists)
            start_dt = _parse_schedule_datetime(start_val, event)
            end_dt = _parse_schedule_datetime(end_val, event)
            if slot and (start_dt or end_dt):
                update_fields = []
                if start_dt:
                    slot.start = start_dt
                    update_fields.append('start')
                if end_dt:
                    slot.end = end_dt
                    update_fields.append('end')
                if update_fields:
                    slot.save(update_fields=update_fields)

            if room_val:
                room = _resolve_or_create_room(room_val, event, caches, room_metadata=room_metadata)
                if room and slot and slot.room_id != room.pk:
                    slot.room = room
                    slot.save(update_fields=['room'])

            # Link speakers
            if speaker_cache is None:
                speaker_cache = {}
            speaker_pairs = _zip_speaker_refs_and_names(linked_speakers, speakers_val)
            for speaker_ref, speaker_name in speaker_pairs:
                cache_key = _speaker_cache_key(speaker_ref, speaker_name)
                if not cache_key:
                    continue
                if cache_key not in speaker_cache:
                    speaker_cache[cache_key] = _upsert_session_speaker(
                        event=event,
                        speaker_ref=speaker_ref,
                        speaker_name=speaker_name,
                    )
                speaker_user = speaker_cache[cache_key]
                if speaker_user:
                    SpeakerRole.objects.get_or_create(submission=submission, user=speaker_user)

            if slide_links:
                delete_slide_resources(submission)
                for slide_link in slide_links:
                    create_slide_resource(submission, link=slide_link)

            # Question answers
            question_mappings = caches.get('question_mappings') if caches else []
            question_cache = caches.get('question_cache') if caches else None
            for question_id, mapping_value in question_mappings:
                answer_text = _resolve_csv(mapping_value, record)
                if answer_text:
                    _set_question_answer(
                        question_id,
                        answer_text,
                        question_cache=question_cache,
                        submission=submission,
                        event=event,
                    )

            _sync_import_answers(
                event=event,
                target=TalkQuestionTarget.SUBMISSION,
                extras=submission_extras,
                caches=caches or {},
                submission=submission,
            )

            if scheduled_public and submission.state == SubmissionStates.ACCEPTED and slot and slot.start:
                submission.confirm(person=acting_user, orga=True)

            event.log_action(
                'eventyay.submission.imported',
                data={'title': title, 'code': submission.code},
                user=acting_user,
            )
    except (IntegrityError, DataError) as exc:
        if was_created and submission.pk:
            try:
                submission.delete()
            except (IntegrityError, OperationalError):
                logger.exception('Failed to clean up submission after import error: %s', submission.pk)
        logger.exception('Failed to finalize imported session "%s" for event %s', title, event.slug)
        raise ImportExecutionError(_('A database error occurred while finalizing this session.')) from exc

    return was_created


def _resolve_submission_type(sub_type_val: str, caches: dict) -> 'SubmissionType | None':
    """Find a SubmissionType by name (case-insensitive contains) or pk using pre-fetched list."""
    normalized_value = sub_type_val.strip()
    if not normalized_value:
        return None
    val_lower = normalized_value.lower()
    for st in caches['submission_types']:
        if str(st.name).strip().lower() == val_lower:
            return st
    for st in caches['submission_types']:
        if val_lower in str(st.name).lower():
            return st
    try:
        pk = int(normalized_value)
        for st in caches['submission_types']:
            if st.pk == pk:
                return st
    except (ValueError, TypeError):
        pass
    return None


def _resolve_track(track_val: str, caches: dict) -> 'Track | None':
    """Find a Track by name (case-insensitive contains) or pk using pre-fetched list."""
    normalized_value = track_val.strip()
    if not normalized_value:
        return None
    val_lower = normalized_value.lower()
    for t in caches['tracks']:
        if str(t.name).strip().lower() == val_lower:
            return t
    for t in caches['tracks']:
        if val_lower in str(t.name).lower():
            return t
    try:
        pk = int(normalized_value)
        for t in caches['tracks']:
            if t.pk == pk:
                return t
    except (ValueError, TypeError):
        pass
    return None


def _resolve_or_create_track(
    track_val: str,
    event: Event,
    caches: dict | None,
) -> 'Track | None':
    """Find an existing Track by name or pk, or create one when not found."""
    normalized_name = track_val.strip() if track_val else ''
    if not normalized_name:
        return None
    normalized_name = str(normalized_name)[:TRACK_NAME_MAX_LENGTH]

    track = _resolve_track(normalized_name, caches) if caches else None
    if not track:
        track = Track.objects.filter(event=event, name__iexact=normalized_name).first()

    if track:
        return track

    # Auto-create the track with a colour from the rotating palette.
    existing_count = len(caches['tracks']) if caches else Track.objects.filter(event=event).count()
    color = _TRACK_AUTO_COLORS[existing_count % len(_TRACK_AUTO_COLORS)]
    track = Track.objects.create(event=event, name=normalized_name, color=color)
    if caches is not None:
        caches['tracks'].append(track)
    return track


def _resolve_room(room_val: str, caches: dict) -> 'Room | None':
    """Find a Room by name (case-insensitive contains) or pk using pre-fetched list."""
    normalized_value = room_val.strip()
    if not normalized_value:
        return None
    val_lower = normalized_value.lower()
    for r in caches['rooms']:
        if str(r.name).strip().lower() == val_lower:
            return r
    try:
        pk = int(normalized_value)
        for r in caches['rooms']:
            if r.pk == pk:
                return r
    except (ValueError, TypeError):
        pass
    for r in caches['rooms']:
        if val_lower in str(r.name).lower():
            return r
    return None


def _resolve_or_create_room(
    room_val: str,
    event: Event,
    caches: dict | None,
    room_metadata: dict | None = None,
) -> Room | None:
    normalized_name = room_val.strip()
    if not normalized_name:
        return None
    normalized_name = normalized_name[:ROOM_NAME_MAX_LENGTH]

    room = _resolve_room(normalized_name, caches) if caches else None
    if not room:
        room = Room.objects.filter(event=event, name__iexact=normalized_name).first()

    if room:
        if room.deleted:
            room.deleted = False
            room.save(update_fields=['deleted'])
        _apply_room_metadata(room, room_metadata)
        return room

    room = Room.objects.create(event=event, name=normalized_name, description='')
    _apply_room_metadata(room, room_metadata)
    if caches is not None:
        caches['rooms'].append(room)
    return room


def _parse_schedule_datetime(value: str, event: Event) -> dt.datetime | None:
    if not value:
        return None
    parsed = parse_datetime(value.strip())
    if not parsed:
        return None
    try:
        if is_naive(parsed):
            return make_aware(parsed, event.tz)
        return parsed.astimezone(event.tz)
    except (AmbiguousTimeError, NonExistentTimeError, OverflowError, ValueError):
        logger.warning('Skipping invalid schedule datetime "%s" for event %s', value, event.slug)
        return None


def _set_question_answer(
    question_id,
    answer_value,
    question_cache=None,
    *,
    submission=None,
    person=None,
    event=None,
):
    question = None
    option_lookup = None

    if question_cache is not None:
        cached_question = question_cache.get(question_id)
        if not cached_question:
            return
        question, option_lookup = cached_question
    else:
        try:
            question = TalkQuestion.objects.get(pk=question_id, event=event or submission.event)
        except TalkQuestion.DoesNotExist:
            return

    answer_text = _serialize_answer_value(answer_value, question.variant)
    if not answer_text and question.variant != TalkQuestionVariant.BOOLEAN:
        return

    lookup = {'question': question}
    defaults = {'answer': answer_text}
    if question.target == TalkQuestionTarget.SPEAKER:
        lookup['person'] = person
        defaults['person'] = person
        defaults['submission'] = None
    else:
        lookup['submission'] = submission
        defaults['submission'] = submission
        defaults['person'] = None

    answer, _ = Answer.objects.update_or_create(
        **lookup,
        defaults=defaults,
    )

    if question.variant in (TalkQuestionVariant.CHOICES, TalkQuestionVariant.MULTIPLE, TalkQuestionVariant.SELECT):
        answer.options.clear()
        if option_lookup is None:
            option_lookup = {
                str(option.answer).strip().casefold(): option for option in question.options.all()
            }

        if question.variant == TalkQuestionVariant.MULTIPLE:
            options_to_check = [opt.strip() for opt in answer_text.split(',')]
        else:
            options_to_check = [answer_text.strip()]

        for stripped_option in options_to_check:
            if not stripped_option:
                continue
            option = option_lookup.get(stripped_option.casefold())
            if option:
                answer.options.add(option)
