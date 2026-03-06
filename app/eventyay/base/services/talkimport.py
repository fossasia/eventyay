import datetime as dt
import logging
from typing import TypedDict

from django.conf import settings as django_settings
from django.db import IntegrityError, transaction
from django.utils.crypto import get_random_string
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
from eventyay.base.models.question import AnswerOption, TalkQuestion, TalkQuestionVariant
from eventyay.base.models.submission import SpeakerRole, SubmissionStates
from eventyay.base.models.type import SubmissionType
from eventyay.base.services.orderimport import parse_csv
from eventyay.base.services.tasks import ProfiledEventTask
from eventyay.celery_app import app
from eventyay.consts import SizeKey


logger = logging.getLogger(__name__)


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


def _find_submission_by_ref(event, ref):
    ref = ref.strip()
    if not ref:
        return None
    qs = Submission.objects.filter(event=event)
    sub = qs.filter(code__iexact=ref).first()
    if sub:
        return sub
    try:
        return qs.filter(pk=int(ref)).first()
    except (ValueError, TypeError):
        return None


def _find_user_for_speaker(event, ref):
    ref = ref.strip()
    if not ref:
        return None
    profile = SpeakerProfile.objects.filter(event=event, user__code__iexact=ref).select_related('user').first()
    if profile:
        return profile.user
    user = User.objects.filter(email__iexact=ref).first()
    if user:
        return user
    profile = SpeakerProfile.objects.filter(event=event, user__fullname__iexact=ref).select_related('user').first()
    if profile:
        return profile.user
    return None


@app.task(base=ProfiledEventTask, throws=(ImportExecutionError,))
def import_speakers(event: Event, fileid: str, settings: dict, locale: str, user_id) -> ImportResult:
    cf = CachedFile.objects.get(id=fileid)
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
                    except (ImportExecutionError, IntegrityError) as e:
                        skipped += 1
                        errors.append(_('Row {row}: {error}').format(row=row_num, error=e))

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
        normalized = identifier.strip()
        if (
            normalized
            and not user.code
            and not User.objects.filter(
                code__iexact=normalized,
            )
            .exclude(pk=user.pk)
            .exists()
        ):
            user.code = normalized
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

    optional_kwargs = dict(
        locale_val=locale_val,
        avatar_source=avatar_source,
        avatar_license=avatar_license,
        identifier=identifier,
    )

    # Upsert user: try by identifier/code first, then by email
    user = None
    if identifier:
        profile = (
            SpeakerProfile.objects.filter(event=event, user__code__iexact=identifier).select_related('user').first()
        )
        if profile:
            user = profile.user

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
                    except (ImportExecutionError, IntegrityError) as e:
                        skipped += 1
                        errors.append(_('Row {row}: {error}').format(row=row_num, error=e))

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
        sub.content_locale = content_locale
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
    linked_speakers = _resolve_csv(settings.get('linked_speakers'), record)
    speakers_val = _resolve_csv(settings.get('speakers'), record)
    room_val = _resolve_csv(settings.get('room'), record)

    if not title:
        raise ImportExecutionError(_('Missing session title.'))

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
    state = state_val.lower() if state_val and state_val.lower() in valid_states else SubmissionStates.SUBMITTED

    # Upsert by code
    was_created = False
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
    if code:
        submission = Submission.objects.filter(event=event, code__iexact=code).first()
    if submission is None:
        submission = Submission.objects.filter(event=event, title__iexact=title).first()
    was_created = submission is None

    if was_created:
        submission = Submission(event=event, title=title, submission_type=sub_type, state=state)
        # Always assign a fresh code. Submission.code has a global unique constraint across all
        # events, so using a CSV code from another event's export would cause an IntegrityError
        # on every single row. The CSV code is only used for the deduplication lookup above.
        # assign_code() must run outside any transaction: its IntegrityError retry loop issues
        # DB queries after catching the error, which triggers TransactionManagementError inside
        # an enclosing PostgreSQL transaction.
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
    except IntegrityError as exc:
        raise ImportExecutionError(
            _('Database error for session "{title}": {error}').format(title=title, error=exc)
        ) from exc

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
                    stripped_tag = tag_name.strip()
                    if stripped_tag:
                        tag, _created = Tag.objects.get_or_create(event=event, tag=stripped_tag)
                        submission.tags.add(tag)

            # Room assignment (via slot if schedule exists; use pre-fetched cache)
            if room_val:
                room = (
                    _resolve_room(room_val, caches)
                    if caches
                    else (
                        Room.objects.filter(event=event, name__icontains=room_val).first()
                        or Room.objects.filter(event=event, pk__in=_safe_int(room_val)).first()
                    )
                )
                if room:
                    slot = submission.slots.filter(schedule=event.wip_schedule).first()
                    if slot:
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
            for key, value in settings.items():
                if key.startswith('question_') and value:
                    try:
                        question_id = int(key.split('_', 1)[1])
                    except (ValueError, IndexError):
                        continue
                    answer_text = _resolve_csv(value, record)
                    if answer_text:
                        _set_question_answer(submission, question_id, answer_text)

            event.log_action(
                'eventyay.submission.imported',
                data={'title': title, 'code': submission.code},
                user=acting_user,
            )
    except IntegrityError as exc:
        if was_created and submission.pk:
            try:
                submission.delete()
            except Exception:
                logger.exception('Failed to clean up submission after import error: %s', submission.pk)
        raise ImportExecutionError(
            _('Database error while finalizing session "{title}": {error}').format(title=title, error=exc)
        ) from exc

    return was_created


def _safe_int(value):
    try:
        return [int(value)]
    except (ValueError, TypeError):
        return []


def _resolve_submission_type(sub_type_val: str, caches: dict) -> 'SubmissionType | None':
    """Find a SubmissionType by name (case-insensitive contains) or pk using pre-fetched list."""
    val_lower = sub_type_val.lower()
    for st in caches['submission_types']:
        if val_lower in str(st.name).lower():
            return st
    try:
        pk = int(sub_type_val)
        for st in caches['submission_types']:
            if st.pk == pk:
                return st
    except (ValueError, TypeError):
        pass
    return None


def _resolve_track(track_val: str, caches: dict) -> 'Track | None':
    """Find a Track by name (case-insensitive contains) or pk using pre-fetched list."""
    val_lower = track_val.lower()
    for t in caches['tracks']:
        if val_lower in str(t.name).lower():
            return t
    try:
        pk = int(track_val)
        for t in caches['tracks']:
            if t.pk == pk:
                return t
    except (ValueError, TypeError):
        pass
    return None


def _resolve_room(room_val: str, caches: dict) -> 'Room | None':
    """Find a Room by name (case-insensitive contains) or pk using pre-fetched list."""
    val_lower = room_val.lower()
    for r in caches['rooms']:
        if val_lower in str(r.name).lower():
            return r
    try:
        pk = int(room_val)
        for r in caches['rooms']:
            if r.pk == pk:
                return r
    except (ValueError, TypeError):
        pass
    return None


def _set_question_answer(submission, question_id, answer_text):
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

    if question.variant in (TalkQuestionVariant.CHOICES, TalkQuestionVariant.MULTIPLE):
        answer.options.clear()
        for option_text in answer_text.split(','):
            stripped_option = option_text.strip()
            if not stripped_option:
                continue
            option = AnswerOption.objects.filter(
                question=question,
                answer__icontains=stripped_option,
            ).first()
            if option:
                answer.options.add(option)
