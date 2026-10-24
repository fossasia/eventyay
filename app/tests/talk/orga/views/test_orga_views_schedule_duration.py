import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import IntegrityError, OperationalError, connection, connections, transaction
from django.db.models import QuerySet
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now
from django_scopes import scope
from eventyay.api.serializers.schedule import TalkSlotOrgaSerializer
from eventyay.api.serializers.submission import SubmissionSerializer
from eventyay.base.models import Schedule, Submission, SubmissionStates, TalkSlot
from eventyay.cfp.views.user import SubmissionsEditView
from eventyay.orga.forms.cfp import SubmissionTypeForm
from eventyay.orga.forms.submission import SubmissionForm
from eventyay.submission.forms.submission import InfoForm
from rest_framework.exceptions import ValidationError as APIValidationError


@pytest.mark.django_db
def test_duration_refresh_batches_draft_slot_updates(event, accepted_submission, room):
    """Resize scheduled draft slots in one write, preserving unscheduled and released slots."""
    with scope(event=event):
        draft = event.wip_schedule
        slots = []
        for offset in range(3):
            start = now() + dt.timedelta(hours=offset)
            slots.append(draft.talks.create(
                submission=accepted_submission, room=room, start=start,
                end=start + dt.timedelta(minutes=30),
            ))
        unscheduled = draft.talks.create(submission=accepted_submission)
        released = event.schedules.create(version='batch-test', published=now())
        published = released.talks.create(
            submission=accepted_submission, room=room, start=slots[0].start, end=slots[0].end,
        )
        accepted_submission.duration = 75
        accepted_submission.save(update_fields=['duration'])
        with CaptureQueriesContext(connection) as queries:
            accepted_submission.update_duration()
        writes = [
            query['sql'] for query in queries
            if query['sql'].startswith(f'UPDATE "{TalkSlot._meta.db_table}"')
        ]
        assert len(writes) == 1
        for slot in slots:
            previous_updated = slot.updated
            slot.refresh_from_db()
            assert slot.end == slot.start + dt.timedelta(minutes=75)
            assert slot.room_id == room.pk
            assert slot.updated >= previous_updated
        unscheduled.refresh_from_db()
        published.refresh_from_db()
        assert unscheduled.start is None and unscheduled.end is None
        assert published.end == published.start + dt.timedelta(minutes=30)


@pytest.mark.django_db
@pytest.mark.parametrize('fail_slot', (False, True))
@pytest.mark.parametrize('save_form', (False, True))
def test_review_type_default_save_propagates_atomically(event, accepted_submission, mocker, fail_slot, save_form):
    """Saving the default must propagate slots or roll back both default and slot writes."""
    with scope(event=event):
        submission_type = accepted_submission.submission_type
        old_duration = submission_type.default_duration
        slot = accepted_submission.slots.get(schedule=event.wip_schedule)
        slot.start = now()
        slot.end = slot.start + dt.timedelta(minutes=old_duration)
        slot.save()
        if fail_slot:
            mocker.patch.object(Submission, 'update_duration', side_effect=IntegrityError('Propagation failed'))
        submission_type.default_duration = old_duration + 15
        if save_form:
            form = SubmissionTypeForm(event=event, instance=submission_type, data={
                'name_0': str(submission_type.name), 'default_duration': old_duration + 15,
            })
            assert form.is_valid(), form.errors
        if fail_slot:
            with pytest.raises(IntegrityError, match='Propagation failed'):
                if save_form:
                    form.save()
                else:
                    submission_type.save(update_fields=['default_duration'])
        elif save_form:
            form.save()
        else:
            submission_type.save(update_fields=['default_duration'])
        submission_type.refresh_from_db()
        slot.refresh_from_db()
        expected = old_duration if fail_slot else old_duration + 15
        assert submission_type.default_duration == expected
        assert slot.end == slot.start + dt.timedelta(minutes=expected)


@pytest.mark.django_db
@pytest.mark.parametrize('change', ('duration', 'move', 'release', 'reset'))
def test_review_slot_edit_rechecks_current_draft(event, accepted_submission, room, change):
    """A slot edit must use current timings and reject a published or deleted target."""
    with scope(event=event):
        slot = accepted_submission.slots.get(schedule=event.wip_schedule)
        slot.start = now()
        slot.end = slot.start + dt.timedelta(minutes=accepted_submission.get_duration())
        slot.save()
        data = {'room': room.pk}
        if change == 'move':
            data['start'] = slot.start + dt.timedelta(hours=1)
        serializer = TalkSlotOrgaSerializer(
            instance=slot, data=data, partial=True,
            context={'request': SimpleNamespace(event=event, query_params=QueryDict())},
        )
        assert serializer.is_valid(), serializer.errors
        if change in ('duration', 'move'):
            accepted_submission.duration = 75
            accepted_submission.save(update_fields=['duration'])
            accepted_submission.update_duration()
            serializer.save()
            slot.refresh_from_db()
            assert slot.end == slot.start + dt.timedelta(minutes=75)
            assert slot.room_id == room.pk
        else:
            released, draft = event.release_schedule('slot-review', notify_speakers=False)
            if change == 'reset':
                slot = draft.talks.get(submission=accepted_submission)
                serializer.instance = slot
                released.unfreeze()
            with pytest.raises(APIValidationError):
                serializer.save()


@pytest.mark.django_db
@pytest.mark.parametrize('channel', ('orga', 'cfp'))
@pytest.mark.parametrize('stale_field', ('description', 'submission_type_id', 'content_locale'))
def test_review_form_preserves_unmodified_saved_fields(event, submission, speaker_client, mocker, channel, stale_field):
    """A stale bound form must merge its edits with newer fields from the database."""
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        if channel == 'cfp' and stale_field == 'submission_type_id':
            event.cfp.deadline = None
            event.cfp.save(update_fields=['deadline'])
            event.submission_types.exclude(pk=submission.submission_type_id).update(requires_access_code=True)
        data = {
            'title': 'Edited title', 'abstract': submission.abstract, 'description': submission.description,
            'notes': submission.notes, 'content_locale': submission.content_locale,
            'submission_type': submission.submission_type_id, 'duration': '', 'slot_count': submission.slot_count,
        }
        form_class = SubmissionForm if channel == 'orga' else InfoForm
        form = form_class(event=event, instance=submission, data=data)
        assert form.is_valid(), form.errors
        if channel == 'cfp' and stale_field == 'submission_type_id':
            assert 'submission_type' in form.default_values
        if stale_field == 'submission_type_id':
            saved_value = event.submission_types.create(
                name='Restricted concurrent type', default_duration=90, requires_access_code=True,
            ).pk
        else:
            saved_value = 'New concurrent description' if stale_field == 'description' else 'de'
        Submission.all_objects.filter(pk=submission.pk).update(**{stale_field: saved_value})
        if channel == 'orga':
            form.save()
        else:
            mocker.patch.object(SubmissionsEditView, 'get_form', return_value=form)
            response = speaker_client.post(submission.urls.user_base, data={
                'resource-TOTAL_FORMS': 0, 'resource-INITIAL_FORMS': 0,
            })
            assert response.status_code == 302
        submission.refresh_from_db()
        assert submission.title == 'Edited title'
        assert getattr(submission, stale_field) == saved_value


@pytest.mark.django_db
@pytest.mark.parametrize('override', (None, 30, 45))
def test_review_api_roundtrip_preserves_duration_override(event, submission, orga_user, override):
    """Effective duration output must not turn inherited durations into explicit overrides."""
    with scope(event=event):
        submission.duration = override
        submission.save(update_fields=['duration'])
        new_type = event.submission_types.create(name='Roundtrip type', default_duration=90)
        context = {'request': SimpleNamespace(event=event, user=orga_user, query_params=QueryDict())}
        representation = SubmissionSerializer(instance=submission, context=context).data
        data = {
            key: representation[key]
            for key in ('title', 'abstract', 'content_locale', 'duration', 'duration_override')
            if key in representation
        }
        data['submission_type'] = new_type.pk
        serializer = SubmissionSerializer(instance=submission, data=data, context=context)
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        submission.refresh_from_db()
        assert submission.duration == override
        assert submission.get_duration() == (override if override is not None else 90)


@pytest.mark.django_db
@pytest.mark.parametrize('data,expected', (({'duration': 50}, 50), ({'duration_override': 50}, 50),
                                         ({'duration': 45, 'duration_override': None}, None)))
def test_review_api_duration_override_writes(event, submission, orga_user, data, expected):
    """Keep legacy duration writes and allow an explicit override to be cleared."""
    with scope(event=event):
        submission.duration = 45
        submission.save(update_fields=['duration'])
        serializer = SubmissionSerializer(
            instance=submission, data=data, partial=True,
            context={'request': SimpleNamespace(event=event, user=orga_user, query_params=QueryDict())},
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        submission.refresh_from_db()
        assert submission.duration == expected


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
@pytest.mark.parametrize('operation', (
    'slot', 'type', 'type_name', 'type_form_name', 'api_title', 'orga_title', 'cfp_title',
))
def test_review_event_lock_only_blocks_schedule_edits(request, mocker, operation):
    """Slot/type writes must wait for release, but independent title edits must not."""
    mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
    event = request.getfixturevalue('event')
    submission = request.getfixturevalue('submission')
    room = request.getfixturevalue('room')
    orga_user = request.getfixturevalue('orga_user') if operation == 'api_title' else None
    speaker_client = request.getfixturevalue('speaker_client') if operation == 'cfp_title' else None
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        slot = event.wip_schedule.talks.create(submission=submission)
        data = {
            'title': 'Independent title', 'abstract': submission.abstract, 'description': submission.description,
            'notes': submission.notes, 'content_locale': submission.content_locale,
            'submission_type': submission.submission_type_id, 'duration': '', 'slot_count': submission.slot_count,
            'resource-TOTAL_FORMS': 0, 'resource-INITIAL_FORMS': 0,
        }

        def edit():
            """Run a real save on a separate database connection with a short lock timeout."""
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '500ms'")
                with scope(event=event):
                    try:
                        if operation == 'type':
                            submission_type = event.submission_types.get(pk=submission.submission_type_id)
                            submission_type.default_duration += 15
                            submission_type.save(update_fields=['default_duration'])
                        elif operation in ('type_name', 'type_form_name'):
                            submission_type = event.submission_types.get(pk=submission.submission_type_id)
                            if operation == 'type_form_name':
                                form = SubmissionTypeForm(event=event, instance=submission_type, data={
                                    'name_0': 'Renamed type',
                                    'default_duration': submission_type.default_duration,
                                })
                                assert form.is_valid(), form.errors
                                form.save()
                            else:
                                submission_type.name = 'Renamed type'
                                submission_type.save()
                        elif operation == 'cfp_title':
                            response = speaker_client.post(submission.urls.user_base, data=data)
                            assert response.status_code == 302
                        else:
                            if operation == 'slot':
                                serializer = TalkSlotOrgaSerializer(
                                    instance=TalkSlot.objects.get(pk=slot.pk), data={'room': room.pk}, partial=True,
                                    context={'request': SimpleNamespace(event=event, user=orga_user,
                                                                        query_params=QueryDict())},
                                )
                            elif operation == 'api_title':
                                serializer = SubmissionSerializer(
                                    instance=Submission.all_objects.get(pk=submission.pk),
                                    data={'title': data['title']}, partial=True,
                                    context={'request': SimpleNamespace(event=event, user=orga_user,
                                                                        query_params=QueryDict())},
                                )
                            else:
                                serializer = SubmissionForm(
                                    event=event, instance=Submission.all_objects.get(pk=submission.pk), data=data,
                                )
                            assert serializer.is_valid(), serializer.errors
                            serializer.save()
                    except OperationalError as error:
                        return error.__cause__.sqlstate
                return 'saved'
            finally:
                connections.close_all()

        with transaction.atomic():
            type(event).objects.select_for_update(no_key=True).get(pk=event.pk)
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(edit).result(timeout=30)
        assert result == ('55P03' if operation in ('slot', 'type') else 'saved')


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
def test_review_type_propagation_holds_event_until_all_slots_finish(request, mocker):
    """A release cannot copy a half-updated group of inherited session durations."""
    mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
    event = request.getfixturevalue('event')
    first = request.getfixturevalue('accepted_submission')
    second = request.getfixturevalue('confirmed_submission')
    checked = []
    original_update = Submission.update_duration

    def release():
        """Attempt release while the first propagated submission has finished updating."""
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute("SET lock_timeout = '500ms'")
            with scope(event=event):
                try:
                    event.release_schedule('during-type-edit', notify_speakers=False)
                except OperationalError as error:
                    return error.__cause__.sqlstate
        finally:
            connections.close_all()

    def update_and_check(instance):
        """Check another connection after one slot update, before the next one."""
        original_update(instance)
        if not checked:
            with ThreadPoolExecutor(max_workers=1) as executor:
                checked.append(executor.submit(release).result(timeout=30))

    with scope(event=event):
        submission_type = first.submission_type
        second.submission_type = submission_type
        second.duration = None
        second.save(update_fields=['submission_type', 'duration'])
        mocker.patch.object(Submission, 'update_duration', update_and_check)
        submission_type.default_duration += 15
        submission_type.save(update_fields=['default_duration'])
        submission_type.update_duration()
        assert checked == ['55P03']


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('old_default', 'new_default', 'old_override', 'new_override', 'expected_duration'),
    (
        (30, 30, None, 123, 123),
        (30, 60, None, None, 60),
        (60, 30, None, None, 30),
        (30, 60, 45, 45, 45),
        (30, 60, 45, None, 60),
    ),
)
def test_orga_can_edit_submission_duration(
    orga_client, event, accepted_submission, room,
    old_default, new_default, old_override, new_override, expected_duration,
):
    """Apply duration edits to draft slots while preserving overrides and released slots."""
    with scope(event=event):
        accepted_submission.submission_type.default_duration = old_default
        accepted_submission.submission_type.save(update_fields=['default_duration'])
        accepted_submission.duration = old_override
        accepted_submission.save(update_fields=['duration'])
        new_type = event.submission_types.create(name='New type', default_duration=new_default)
        slot = accepted_submission.slots.filter(schedule=event.wip_schedule).first()
        original_start = now()
        original_end = original_start + dt.timedelta(minutes=accepted_submission.get_duration())
        slot.start = original_start
        slot.end = original_end
        slot.room = room
        slot.save()
        released = event.schedules.create(version='1.0', published=now())
        released_slot = released.talks.create(
            submission=accepted_submission, room=room, start=original_start, end=original_end,
        )

    response = orga_client.post(
        accepted_submission.orga_urls.edit,
        data={
            "abstract": "abstract",
            "content_locale": "en",
            "description": "description",
            "slot_count": 2,
            "notes": "notes",
            "speaker": "foo@bar.com",
            "speaker_name": "Foo Speaker",
            "duration": new_override if new_override is not None else '',
            "title": "title",
            "submission_type": new_type.pk,
            "resource-TOTAL_FORMS": 0,
            "resource-INITIAL_FORMS": 0,
        },
    )
    assert response.status_code == 302
    with scope(event=event):
        accepted_submission.refresh_from_db()
        slot.refresh_from_db()
        released_slot.refresh_from_db()
        assert accepted_submission.submission_type_id == new_type.pk
        assert accepted_submission.duration == new_override
        assert accepted_submission.get_duration() == expected_duration
        assert slot.start == original_start
        assert slot.end == original_start + dt.timedelta(minutes=expected_duration)
        assert slot.room_id == room.pk
        assert released_slot.start == original_start
        assert released_slot.end == original_end


@pytest.mark.django_db
def test_submission_duration_after_schedule_release(event, accepted_submission, room, monkeypatch):
    """Refresh a stale draft reference after release without changing the published slot."""
    monkeypatch.setattr('eventyay.agenda.tasks.warm_schedule_caches.apply_async', lambda **kwargs: None)
    with scope(event=event):
        cached_schedule = accepted_submission.event.wip_schedule
        slot = cached_schedule.talks.get(submission=accepted_submission)
        original_start = now()
        original_end = original_start + dt.timedelta(minutes=accepted_submission.get_duration())
        slot.start = original_start
        slot.end = original_end
        slot.room = room
        slot.save()

        released, draft = Schedule.objects.get(pk=cached_schedule.pk).freeze('1.0', notify_speakers=False)
        assert accepted_submission.event.wip_schedule.pk == cached_schedule.pk
        accepted_submission.duration = accepted_submission.get_duration() + 15
        accepted_submission.save(update_fields=['duration'])
        accepted_submission.update_duration()

        assert accepted_submission.event.wip_schedule.pk == draft.pk
        slot.refresh_from_db()
        draft_slot = draft.talks.get(submission=accepted_submission)
        assert slot.schedule_id == released.pk
        assert slot.end == original_end
        assert draft_slot.start == original_start
        assert draft_slot.room_id == room.pk
        assert draft_slot.end == original_start + dt.timedelta(minutes=accepted_submission.duration)


@pytest.mark.django_db
@pytest.mark.parametrize('channel', ('orga', 'cfp', 'cfp_draft', 'api'))
@pytest.mark.parametrize(('override', 'fail_slot'), ((None, False), (45, False), (None, True)))
def test_submission_edits_keep_draft_timing_consistent(
    request, event, submission, room, mocker, channel, override, fail_slot,
):
    """Keep inherited timings, explicit overrides and failed edits consistent across entry points."""
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        event.cfp.fields['duration']['visibility'] = 'optional'
        event.cfp.save(update_fields=['fields'])
        old_type = submission.submission_type
        old_type.default_duration = 30
        old_type.save(update_fields=['default_duration'])
        submission.duration = override
        if channel == 'cfp_draft':
            submission.state = SubmissionStates.DRAFT
        submission.save()
        new_type = event.submission_types.create(name='Longer type', default_duration=60)
        start = now()
        old_end = start + dt.timedelta(minutes=override or 30)
        slot = event.wip_schedule.talks.create(submission=submission, room=room, start=start, end=old_end)
        released = event.schedules.create(version='1.0', published=now())
        released_slot = released.talks.create(submission=submission, room=room, start=start, end=old_end)

    data = {
        'title': submission.title,
        'abstract': submission.abstract,
        'description': submission.description,
        'notes': submission.notes,
        'content_locale': submission.content_locale,
        'submission_type': new_type.pk,
        'duration': override if override is not None else '',
        'slot_count': submission.slot_count,
        'resource-TOTAL_FORMS': 0,
        'resource-INITIAL_FORMS': 0,
    }
    if channel == 'api':
        client = request.getfixturevalue('client')
        token = request.getfixturevalue('orga_user_write_token')
        url = event.api_urls.submissions + f'{submission.code}/'
        method = client.patch
        kwargs = {
            'data': json.dumps({'submission_type': new_type.pk}),
            'headers': {'Authorization': f'Token {token.token}', 'Content-Type': 'application/json'},
        }
    else:
        client = request.getfixturevalue('orga_client' if channel == 'orga' else 'speaker_client')
        url = submission.orga_urls.edit if channel == 'orga' else submission.urls.user_base
        method = client.post
        if channel == 'cfp_draft':
            data['action'] = 'draft'
        kwargs = {'data': data}

    if fail_slot:
        update_slots = QuerySet.update

        def fail_after_slot_update(queryset, **kwargs):
            """Fail after writing slots to verify that both writes roll back."""
            result = update_slots(queryset, **kwargs)
            if queryset.model is TalkSlot and 'end' in kwargs:
                raise IntegrityError('Slot propagation failed')
            return result

        mocker.patch.object(QuerySet, 'update', fail_after_slot_update)
        with pytest.raises(IntegrityError, match='Slot propagation failed'):
            method(url, **kwargs)
    else:
        response = method(url, **kwargs)
        assert response.status_code == (200 if channel == 'api' else 302)

    with scope(event=event):
        submission.refresh_from_db()
        slot.refresh_from_db()
        released_slot.refresh_from_db()
        expected_type = old_type if fail_slot else new_type
        assert submission.submission_type_id == expected_type.pk
        assert submission.duration == override
        assert slot.end == (old_end if fail_slot else start + dt.timedelta(minutes=override or 60))
        assert slot.start == released_slot.start == start
        assert slot.room_id == released_slot.room_id == room.pk
        assert released_slot.end == old_end


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
@pytest.mark.parametrize('entry_point', ('event', 'schedule'))
def test_schedule_release_locks_event_before_creating_draft(mocker, request, entry_point):
    """Release must wait before creating a draft and refresh a draft deleted by reset."""
    mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
    mocker.patch('eventyay.agenda.tasks.warm_schedule_caches.apply_async')
    event = request.getfixturevalue('event')
    submission = request.getfixturevalue('accepted_submission')
    with scope(event=event):
        released, draft = event.release_schedule('1.0', notify_speakers=False)
        assert event.wip_schedule.pk == draft.pk

        def release_schedule():
            """Attempt release on a separate connection while the event is locked."""
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '500ms'")
                with scope(event=event):
                    try:
                        if entry_point == 'event':
                            event.release_schedule('2.0', notify_speakers=False)
                        else:
                            draft.freeze('2.0', notify_speakers=False)
                    except OperationalError as error:
                        return error.__cause__.sqlstate
            finally:
                connections.close_all()

        with transaction.atomic():
            type(event).objects.select_for_update().get(pk=event.pk)
            if entry_point == 'event':
                Schedule.objects.get(pk=released.pk).unfreeze()
            save_schedule = mocker.spy(Schedule, 'save')
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(release_schedule).result(timeout=30) == '55P03'
            save_schedule.assert_not_called()

        if entry_point == 'event':
            next_release, next_draft = event.release_schedule('2.0', notify_speakers=False)
        else:
            next_release, next_draft = draft.freeze('2.0', notify_speakers=False)
        assert next_release.version == '2.0'
        assert event.schedules.filter(version__isnull=True).count() == 1
        assert next_draft.talks.filter(submission=submission).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('change', ('duration', 'submission_type', 'default_duration'))
def test_submission_duration_uses_saved_values(event, accepted_submission, room, change):
    """A stale submission or cached type must not overwrite the latest saved duration."""
    with scope(event=event):
        slot = event.wip_schedule.talks.get(submission=accepted_submission)
        slot.start = now()
        slot.end = slot.start + dt.timedelta(minutes=accepted_submission.get_duration())
        slot.room = room
        slot.save()
        new_duration = accepted_submission.get_duration() + 15
        if change == 'duration':
            event.submissions.filter(pk=accepted_submission.pk).update(duration=new_duration)
        elif change == 'submission_type':
            new_type = event.submission_types.create(name='Longer type', default_duration=new_duration)
            event.submissions.filter(pk=accepted_submission.pk).update(duration=None, submission_type=new_type)
        else:
            event.submissions.filter(pk=accepted_submission.pk).update(duration=None)
            event.submission_types.filter(pk=accepted_submission.submission_type_id).update(
                default_duration=new_duration,
            )

        accepted_submission.update_duration()

        slot.refresh_from_db()
        assert slot.end == slot.start + dt.timedelta(minutes=new_duration)
        assert slot.room_id == room.pk


@pytest.mark.django_db
def test_submission_duration_after_schedule_reset(event, accepted_submission, room, monkeypatch):
    """A duration update must replace a cached draft that a schedule reset deleted."""
    monkeypatch.setattr('eventyay.agenda.tasks.warm_schedule_caches.apply_async', lambda **kwargs: None)
    with scope(event=event):
        slot = event.wip_schedule.talks.get(submission=accepted_submission)
        slot.start = now()
        slot.end = slot.start + dt.timedelta(minutes=accepted_submission.get_duration())
        slot.room = room
        slot.save()
        released, draft = event.wip_schedule.freeze('1.0', notify_speakers=False)
        cached_event = accepted_submission.event
        assert cached_event.wip_schedule.pk == draft.pk
        _, reset_draft = Schedule.objects.get(pk=released.pk).unfreeze()
        accepted_submission.duration = accepted_submission.get_duration() + 15
        accepted_submission.save(update_fields=['duration'])

        accepted_submission.update_duration()

        assert cached_event.wip_schedule.pk == reset_draft.pk
        reset_slot = reset_draft.talks.get(submission=accepted_submission)
        assert reset_slot.end == slot.start + dt.timedelta(minutes=accepted_submission.duration)
        slot.refresh_from_db()
        assert slot.end != reset_slot.end


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row-lock contention.')
def test_schedule_reset_locks_draft_before_copying_slots(mocker, request):
    """A reset must wait for the draft lock before copying or deleting its slots."""
    mocker.patch('eventyay.base.models.cache.VersionedModel._set_cache_version_sync')
    mocker.patch('eventyay.agenda.tasks.warm_schedule_caches.apply_async')
    event = request.getfixturevalue('event')
    submission = request.getfixturevalue('accepted_submission')
    with scope(event=event):
        released, draft = event.wip_schedule.freeze('1.0', notify_speakers=False)
        copy_slot = mocker.spy(TalkSlot, 'copy_to_schedule')

        def reset_schedule():
            """Attempt a reset through an independent PostgreSQL connection."""
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '500ms'")
                with scope(event=event):
                    try:
                        Schedule.objects.get(pk=released.pk).unfreeze()
                    except OperationalError as error:
                        return error.__cause__.sqlstate
            finally:
                connections.close_all()

        with transaction.atomic():
            Schedule.objects.select_for_update().get(pk=draft.pk)
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(reset_schedule).result(timeout=30) == '55P03'
            copy_slot.assert_not_called()

        _, reset_draft = released.unfreeze()
        assert reset_draft.talks.filter(submission=submission).exists()
