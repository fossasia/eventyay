import datetime as dt
import logging
from typing import TypedDict

from django.conf import settings as django_settings
from django.db import DataError, IntegrityError, OperationalError, transaction
from django.utils.dateparse import parse_datetime
from django.utils.crypto import get_random_string
from django.utils.timezone import is_naive, make_aware
from django.utils.timezone import now
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
from eventyay.base.models.question import TalkQuestion, TalkQuestionVariant
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


@app.task(base=ProfiledEventTask, throws=(ImportExecutionError,))
def import_speakers(event: Event, fileid: str, settings: dict, locale: str, user_id) -> ImportResult:
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

                created = 0
                updated = 0
                skipped = 0
                errors = []

                for row_num, record in enumerate(parsed, start=2):
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


def _apply_user_optional_fields(user, *, locale_val, avatar_source, avatar_license, identifier):
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


def _import_speaker_row(event, settings, record, acting_user):
    full_name = _resolve_csv(settings.get('full_name'), record)
    first_name = _resolve_csv(settings.get('first_name'), record)
    last_name = _resolve_csv(settings.get('last_name'), record)
    email = _resolve_csv(settings.get('email'), record)
    biography = _resolve_csv(settings.get('biography'), record)
    identifier = _resolve_csv(settings.get('identifier'), record)
    locale_val = _resolve_csv(settings.get('locale'), record)
    linked_submissions = _resolve_csv(settings.get('linked_submissions'), record)
    avatar_source = _resolve_csv(settings.get('avatar_source'), record)
    avatar_license = _resolve_csv(settings.get('avatar_license'), record)

    if not email:
        raise ImportExecutionError(_('Missing email address.'))

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
        user = User.objects.filter(email__iexact=email).first()

    with transaction.atomic():
        if user:
            user.fullname = name
            extra = _apply_user_optional_fields(user, **optional_kwargs)
            user.save(update_fields=['fullname', *extra])
        else:
            user = User.objects.create_user(
                password=get_random_string(32),
                email=email.lower().strip(),
                fullname=name,
                code=normalized_identifier or None,
                pw_reset_token=get_random_string(32),
                pw_reset_time=now() + dt.timedelta(days=60),
            )
            extra = _apply_user_optional_fields(user, **optional_kwargs)
            if extra:
                user.save(update_fields=extra)

        profile, profile_created = SpeakerProfile.objects.get_or_create(
            user=user,
            event=event,
        )
        if biography:
            profile.biography = biography
            profile.save(update_fields=['biography'])

        # Link to submissions
        if linked_submissions:
            for ref in linked_submissions.split(','):
                sub = _find_submission_by_ref(event, ref)
                if sub:
                    SpeakerRole.objects.get_or_create(submission=sub, user=user)

        event.log_action(
            'eventyay.speaker.imported',
            data={'email': email, 'name': name},
            user=acting_user,
        )

    return profile_created


@app.task(base=ProfiledEventTask, throws=(ImportExecutionError,))
def import_submissions(event: Event, fileid: str, settings: dict, locale: str, user_id) -> ImportResult:
    cf = CachedFile.objects.get(id=fileid)
    try:
        acting_user = User.objects.get(pk=user_id)
        with language(locale, event.settings.region):
            with scope(event=event):
                parsed = parse_csv(cf.file, django_settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV])
                if parsed is None:
                    raise ImportExecutionError(_('Could not parse the CSV file.'))

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
                            _('Row {row}: A database error occurred while importing this session.').format(
                                row=row_num
                            )
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

    if not title:
        raise ImportExecutionError(_('Missing session title.'))
    title = title[:200]

    normalized_code = code.strip().upper() if code else ''
    if normalized_code and len(normalized_code) > SUBMISSION_CODE_MAX_LENGTH:
        normalized_code = ''

    # Resolve submission type (use pre-fetched cache to avoid per-row DB queries)
    sub_type = _resolve_submission_type(sub_type_val, caches) if sub_type_val and caches else None
    if not sub_type:
        sub_type = caches['default_sub_type'] if caches else event.submission_types.first()
    if not sub_type:
        raise ImportExecutionError(_('No session type found for this event.'))

    # Resolve track (use pre-fetched cache)
    track = _resolve_track(track_val, caches) if track_val and caches else None

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
                room = _resolve_or_create_room(room_val, event, caches)
                if room and slot and slot.room_id != room.pk:
                    slot.room = room
                    slot.save(update_fields=['room'])

            # Link speakers
            if speaker_cache is None:
                speaker_cache = {}
            all_speaker_refs = []
            if linked_speakers:
                all_speaker_refs.extend(linked_speakers.split(','))
            if speakers_val:
                all_speaker_refs.extend(speakers_val.split(','))
            for ref in all_speaker_refs:
                stripped_ref = ref.strip()
                if not stripped_ref:
                    continue
                cache_key = stripped_ref.lower()
                if cache_key not in speaker_cache:
                    speaker_cache[cache_key] = _find_user_for_speaker(event, stripped_ref)
                speaker_user = speaker_cache[cache_key]
                if speaker_user:
                    SpeakerRole.objects.get_or_create(submission=submission, user=speaker_user)
                    SpeakerProfile.objects.get_or_create(user=speaker_user, event=event)

            # Question answers
            question_mappings = caches.get('question_mappings') if caches else []
            question_cache = caches.get('question_cache') if caches else None
            for question_id, mapping_value in question_mappings:
                answer_text = _resolve_csv(mapping_value, record)
                if answer_text:
                    _set_question_answer(submission, question_id, answer_text, question_cache)

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


def _resolve_or_create_room(room_val: str, event: Event, caches: dict | None) -> Room | None:
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
        return room

    room = Room.objects.create(event=event, name=normalized_name, description='')
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


def _set_question_answer(submission, question_id, answer_text, question_cache=None):
    question = None
    option_lookup = None

    if question_cache is not None:
        cached_question = question_cache.get(question_id)
        if not cached_question:
            return
        question, option_lookup = cached_question
    else:
        try:
            question = TalkQuestion.objects.get(pk=question_id, event=submission.event)
        except TalkQuestion.DoesNotExist:
            return

    if question.variant == TalkQuestionVariant.BOOLEAN:
        answer_text = 'True' if _truthy(answer_text) else 'False'

    answer, _ = Answer.objects.update_or_create(
        submission=submission,
        question=question,
        defaults={'answer': answer_text, 'person': None},
    )

    if question.variant in (TalkQuestionVariant.CHOICES, TalkQuestionVariant.MULTIPLE, TalkQuestionVariant.SELECT):
        answer.options.clear()
        if option_lookup is None:
            option_lookup = {
                str(option.answer).strip().casefold(): option for option in question.options.all()
            }
        for option_text in answer_text.split(','):
            stripped_option = option_text.strip()
            if not stripped_option:
                continue
            option = option_lookup.get(stripped_option.casefold())
            if option:
                answer.options.add(option)
