import json
from datetime import timedelta

import pytest
from django_scopes import scope

from eventyay.api.filters.schedule import TalkSlotFilter
from eventyay.base.models import Room, Schedule, Submission, TalkSlot


@pytest.fixture
def invisible_slot(past_slot):
    past_slot.is_visible = False
    past_slot.save()
    return past_slot


@pytest.mark.django_db
def test_user_can_see_schedule(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content['count'] == 1


@pytest.mark.django_db
def test_user_cannot_see_wip_schedule_list(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content['count'] == 1
    for schedule_data in content['results']:
        assert schedule_data['version'] is not None


@pytest.mark.django_db
def test_user_cannot_see_schedule_if_not_public(client, slot, event):
    slot.submission.event.feature_flags['show_schedule'] = False
    slot.submission.event.save()
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_see_schedule(client, orga_user_token, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(
        slot.submission.event.api_urls.schedules,
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_orga_cannot_see_schedule_even_if_not_public(client, orga_user_token, slot, event):
    slot.submission.event.feature_flags['show_schedule'] = False
    slot.submission.event.save()
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(
        slot.submission.event.api_urls.schedules,
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content['count'] == 2


@pytest.mark.django_db
def test_orga_can_access_wip_schedule_shortcut(client, orga_user_token, event, slot):
    with scope(event=event):
        wip_schedule = event.wip_schedule
        assert wip_schedule is not None
        wip_schedule.talks.add(slot)

    response = client.get(
        event.api_urls.schedules + 'wip/',
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['version'] == event.wip_schedule.version_with_fallback


@pytest.mark.django_db
def test_user_cannot_access_wip_schedule_shortcut(client, event, slot):
    response = client.get(event.api_urls.schedules + 'wip/')
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_access_latest_schedule_shortcut(client, orga_user_token, event, slot, break_slot):
    with scope(event=event):
        assert event.current_schedule is not None
        current_schedule_version = event.current_schedule.version

    response = client.get(
        event.api_urls.schedules + 'latest/',
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['version'] == current_schedule_version
    assert len(content['slots']) == 2


@pytest.mark.django_db
def test_user_can_access_latest_schedule_shortcut_if_public(client, event, slot):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = True
        event.feature_flags['show_schedule'] = True
        event.save()
        current_schedule_version = event.current_schedule.version

    response = client.get(event.api_urls.schedules + 'latest/')
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['version'] == current_schedule_version


@pytest.mark.django_db
def test_user_cannot_access_latest_schedule_shortcut_if_schedule_not_public(client, event, slot):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = True
        event.feature_flags['show_schedule'] = False
        event.save()

    response = client.get(event.api_urls.schedules + 'latest/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_user_cannot_access_latest_schedule_shortcut_if_event_not_public(client, event, slot):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = False
        event.save()
    response = client.get(event.api_urls.schedules + 'latest/')
    assert response.status_code == 401


@pytest.mark.django_db
def test_latest_schedule_shortcut_404_if_no_current_schedule(client, orga_user_token, event):
    with scope(event=event):
        Schedule.objects.filter(event=event).delete()
        event.current_schedule = None
        event.save()
        event.schedules.create(version=None)

    response = client.get(
        event.api_urls.schedules + 'latest/',
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_redirect_version_success(client, event):
    with scope(event=event):
        schedule = event.wip_schedule
        schedule.freeze('v2.0')
    response = client.get(event.api_urls.schedules + 'by-version/?version=v2.0')
    assert response.status_code == 302
    assert response['Location'].endswith(f'/schedules/{schedule.pk}/')


@pytest.mark.django_db
def test_redirect_version_nonexistent_version(client, event):
    response = client.get(event.api_urls.schedules + 'by-version/?version=nonexistent_version_name')
    assert response.status_code == 401


@pytest.mark.django_db
def test_redirect_version_missing_query_param(client, event):
    response = client.get(event.api_urls.schedules + 'by-version/')
    assert response.status_code == 400


@pytest.mark.django_db
def test_redirect_version_followed_by_user_schedule_not_public(client, event):
    with scope(event=event):
        event.feature_flags['show_schedule'] = False
        event.save()
        schedule = event.wip_schedule
        schedule.freeze('v2.0')

    response = client.get(event.api_urls.schedules + 'by-version/?version=v2.0', follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_release_schedule(client, orga_user_write_token, event, slot):
    """Release a valid mixed-case version without changing its spelling."""
    with scope(event=event):
        initial_wip_schedule = event.wip_schedule
        assert initial_wip_schedule.version is None
        initial_wip_pk = initial_wip_schedule.pk
        initial_schedule_count = event.schedules.count()

    release_data = {'version': 'v_Test_Release', 'comment': 'A test release comment'}
    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps(release_data),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 201, response.text
    content = json.loads(response.text)

    with scope(event=event):
        assert content['version'] == release_data['version']
        assert content['comment']['en'] == release_data['comment']

        released_schedule = event.schedules.get(version=release_data['version'])
        assert released_schedule.pk == initial_wip_pk
        assert released_schedule.comment == release_data['comment']

        del event.wip_schedule
        new_wip_schedule = event.wip_schedule
        assert new_wip_schedule.pk != initial_wip_pk
        assert new_wip_schedule.version is None
        assert event.schedules.count() == initial_schedule_count + 1


@pytest.mark.django_db
def test_orga_can_release_breaks_only_schedule_via_api(client, orga_user_write_token, event, break_slot):
    with scope(event=event):
        event.wip_schedule.talks.filter(submission__isnull=False).delete()
        initial_schedule_count = event.schedules.count()

    release_data = {'version': 'v_breaks_only', 'comment': 'Breaks only release'}
    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps(release_data),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code in (200, 201), response.text
    with scope(event=event):
        assert event.schedules.count() == initial_schedule_count + 1
        assert event.schedules.filter(version='v_breaks_only').exists()


@pytest.mark.django_db
@pytest.mark.parametrize('version', ('v2.0', 'V2.0', ' V2.0 '))
def test_orga_cannot_release_schedule_with_existing_version(client, orga_user_write_token, event, version):
    """Return a version field error when a release name is already in use."""
    with scope(event=event):
        event.wip_schedule.freeze('v2.0')
        schedules = list(event.schedules.order_by('pk').values_list('pk', 'version', 'published'))
    release_data = {'version': version}
    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps(release_data),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert content['version'] == [f"A schedule with the version '{version.strip()}' already exists for this event."]
    with scope(event=event):
        assert list(event.schedules.order_by('pk').values_list('pk', 'version', 'published')) == schedules


@pytest.mark.django_db
@pytest.mark.parametrize(
    'version',
    ('wip', 'latest', ' wip ', ' latest ', 'WIP', 'Wip', 'LATEST', 'Latest', ' wIp ', ' LaTeSt '),
)
@pytest.mark.parametrize('has_wip', (True, False))
def test_orga_cannot_release_reserved_schedule_version(client, orga_user_write_token, event, slot, version, has_wip):
    """Reject reserved names without changing schedules, including a missing draft."""
    with scope(event=event):
        if not has_wip:
            draft = event.schedules.get(version__isnull=True)
            draft.talks.all().delete()
            draft.delete()
        assert event.schedules.filter(version__isnull=True).exists() is has_wip
        schedules = list(event.schedules.order_by('pk').values_list('pk', 'version', 'published'))
        original_slot = (slot.schedule_id, slot.start, slot.end, slot.room_id)
        mail_count = event.queued_mails.count()

    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps({'version': version}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )

    assert response.status_code == 400
    assert response.json()['version'] == ['This schedule version is reserved. Please choose a different name.']
    with scope(event=event):
        assert list(event.schedules.order_by('pk').values_list('pk', 'version', 'published')) == schedules
        slot.refresh_from_db()
        assert (slot.schedule_id, slot.start, slot.end, slot.room_id) == original_slot
        assert event.queued_mails.count() == mail_count


@pytest.mark.django_db
def test_orga_cannot_release_schedule_without_version_name(client, orga_user_write_token, event):
    """Require a version name even when the release includes a comment."""
    release_data = {'comment': 'Just a comment'}
    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps(release_data),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert 'version' in content


@pytest.mark.django_db
@pytest.mark.parametrize('via_api', (True, False))
@pytest.mark.parametrize('competing_action', ('release', 'reset'))
def test_release_reports_competing_release(
    client, orga_client, orga_user_write_token, event, slot, monkeypatch, via_api, competing_action
):
    """Report a stale release or reset target without rolling back another request's change."""
    original_freeze = Schedule.freeze
    with scope(event=event):
        if competing_action == 'reset':
            released, _ = event.wip_schedule.freeze('previous-release', notify_speakers=False)
        stale_draft = event.wip_schedule
        schedule_count = event.schedules.count()
        if competing_action == 'reset':
            released.unfreeze()
        else:
            competing_draft = Schedule.objects.get(pk=stale_draft.pk)
            original_freeze(competing_draft, 'competing-release', notify_speakers=False)
    error_message = 'draft no longer exists' if competing_action == 'reset' else 'already versioned'

    def freeze_after_competing_release(draft, *args, **kwargs):
        """Supply a stale target after the competing request's writes have completed."""
        with scope(event=draft.event):
            return original_freeze(stale_draft, *args, **kwargs)

    monkeypatch.setattr(Schedule, 'freeze', freeze_after_competing_release)
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])

    if via_api:
        response = client.post(
            event.api_urls.schedules + 'release/',
            data=json.dumps({'version': 'my-release'}),
            content_type='application/json',
            headers={'Authorization': f'Token {orga_user_write_token.token}'},
        )
        assert response.status_code == 400
        assert error_message in response.json()['version'][0]
    else:
        response = orga_client.post(event.orga_urls.release_schedule, data={'version': 'my-release'})
        assert response.status_code == 200
        assert response.text.count(error_message) == 1
        assert 'We had trouble saving your input' not in response.text
        assert 'You have to provide a new, unique schedule version!' not in response.text

    with scope(event=event):
        assert event.schedules.count() == schedule_count + (competing_action == 'release')
        preserved_version = 'previous-release' if competing_action == 'reset' else 'competing-release'
        assert event.schedules.filter(version=preserved_version).exists()
        assert not event.schedules.filter(version='my-release').exists()
        assert event.schedules.filter(version__isnull=True).count() == 1


@pytest.mark.django_db
def test_anonymous_user_cannot_release_schedule(client, event):
    release_data = {'version': 'v_anon_release'}
    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps(release_data),
        content_type='application/json',
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_readonly_user_cannot_release_schedule(client, orga_user_token, event):
    release_data = {'version': 'v_readonly_release'}
    response = client.post(
        event.api_urls.schedules + 'release/',
        data=json.dumps(release_data),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_can_download_slot_ical(client, slot, event):
    url = event.api_urls.slots + f'{slot.pk}/ical/'
    response = client.get(url, follow=True)

    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/calendar'
    expected_filename = f'attachment; filename="{event.slug}-{slot.submission.code}.ics"'
    assert response.headers['Content-Disposition'] == expected_filename
    content = response.text
    assert 'BEGIN:VCALENDAR' in content
    assert f'{slot.submission.code}' in content


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_slot_not_visible(client, slot, event):
    with scope(event=event):
        slot.is_visible = False
        slot.save()

    url = event.api_urls.slots + f'{slot.pk}/ical/'
    response = client.get(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_schedule_not_public(client, slot, event):
    with scope(event=event):
        event.feature_flags['show_schedule'] = False
        event.save()

    url = event.api_urls.slots + f'{slot.pk}/ical/'
    response = client.get(url, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_event_not_public(client, slot, event):
    with scope(event=event):
        event.is_public = False
        event.save()

    url = event.api_urls.slots + f'{slot.pk}/ical/'
    response = client.get(url, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_download_slot_ical_slot_without_submission(client, event, break_slot):
    with scope(event=event):
        assert break_slot.schedule == event.current_schedule
    url = event.api_urls.slots + f'{break_slot.pk}/ical/'
    response = client.get(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_list_slots_anonymous_event_not_public(client, event, slot):
    event.is_public = False
    event.save()
    response = client.get(event.api_urls.slots, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_not_public(client, event, slot):
    event.is_public = True
    event.feature_flags['show_schedule'] = False
    event.save()
    response = client.get(event.api_urls.slots, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_public_current_schedule_only(client, event, slot):
    with scope(event=event):
        code = slot.submission.code
    response = client.get(event.api_urls.slots, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['id'] == slot.pk
    assert 'is_visible' not in content['results'][0]
    assert content['results'][0]['submission'] == code


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_public_only_visible(client, event, slot, invisible_slot):
    with scope(event=event):
        slot_pk = event.current_schedule.talks.get(submission=slot.submission).pk
    response = client.get(event.api_urls.slots, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content['count'] == 1
    assert content['results'][0]['id'] == slot_pk


@pytest.mark.django_db
def test_list_slots_orga_sees_slots_in_current_schedule_by_default(
    client, orga_user_token, event, slot, invisible_slot
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.first()
        current_schedule_slot_ids = set(event.current_schedule.talks.values_list('pk', flat=True))

    response = client.get(
        event.api_urls.slots,
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200

    assert content['count'] == len(current_schedule_slot_ids)

    slot_ids_in_response = {r['id'] for r in content['results']}
    assert slot.pk in slot_ids_in_response
    assert invisible_slot.pk in slot_ids_in_response
    assert wip_slot.pk not in slot_ids_in_response


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_pk(client, orga_user_token, event, slot):
    with scope(event=event):
        event.wip_schedule.freeze('v2.0')
        current_schedule_id = slot.schedule.pk
        code = slot.submission.code

    response = client.get(
        f'{event.api_urls.slots}?schedule={current_schedule_id}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] >= 1
    assert slot.pk in [s['id'] for s in content['results']]

    response = client.get(
        f'{event.api_urls.slots}?submission={code}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content['count'] == 1
    with scope(event=event):
        expected_slot_pk = event.current_schedule.talks.get(submission__code=code).pk
    assert content['results'][0]['id'] == expected_slot_pk


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_room(client, orga_user_token, event, slot, room):
    with scope(event=event):
        other_room = Room.objects.create(event=event, name='Other Room', position=9)
        other_slot = TalkSlot.objects.create(
            schedule=slot.schedule,
            submission=slot.submission,
            room=other_room,
            is_visible=True,
            start=event.datetime_from,
            end=event.datetime_from + timedelta(minutes=30),
        )

    response = client.get(
        event.api_urls.slots + f'?room={room.pk}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == 1
    assert slot.pk in [s['id'] for s in content['results']]
    assert other_slot.pk not in [s['id'] for s in content['results']]

    response = client.get(
        event.api_urls.slots + f'?room={other_room.pk}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == 1
    assert content['results'][0]['id'] == other_slot.pk

    # Invalid room returns 400
    response_invalid = client.get(
        event.api_urls.slots + '?room=99999',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response_invalid.status_code == 400
    assert 'room' in response_invalid.json()


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_version(client, orga_user_token, event, slot, room):
    with scope(event=event):
        versioned_schedule = event.schedules.create(version='v2-filter')
        slot.schedule = versioned_schedule
        slot.save()
        expected_pks = {slot.pk}

    response = client.get(
        event.api_urls.slots + '?schedule_version=v2-filter',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == len(expected_pks)
    assert {s['id'] for s in content['results']} == expected_pks


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_version_wip(client, orga_user_token, event, slot):
    with scope(event=event):
        wip_pks = set(event.wip_schedule.talks.values_list('pk', flat=True))
        assert wip_pks

    response = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == len(wip_pks)
    assert {s['id'] for s in content['results']} == wip_pks

    # Case-insensitive "WIP"
    response_upper = client.get(
        event.api_urls.slots + '?schedule_version=WIP',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content_upper = json.loads(response_upper.text)
    assert response_upper.status_code == 200, content_upper
    assert content_upper['count'] == len(wip_pks)
    assert {s['id'] for s in content_upper['results']} == wip_pks


@pytest.mark.django_db
def test_list_slots_anonymous_cannot_filter_by_schedule_version_wip(client, event, slot):
    response = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == 0


@pytest.mark.django_db
def test_retrieve_slot_anonymous_not_visible(client, event, invisible_slot):
    response = client.get(event.api_urls.slots + f'{invisible_slot.pk}/', follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_slot_anonymous_visible_schedule_public(client, event, slot):
    with scope(event=event):
        code = slot.submission.code
    response = client.get(event.api_urls.slots + f'{slot.pk}/', follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['id'] == slot.pk
    assert 'is_visible' not in content
    assert content['submission'] == code


@pytest.mark.django_db
def test_retrieve_slot_anonymous_schedule_not_public(client, event, slot):
    with scope(event=event):
        event.is_public = True
        event.feature_flags['show_schedule'] = False
        event.save()
    response = client.get(event.api_urls.slots + f'{slot.pk}/', follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_retrieve_slot_orga_can_see_invisible_slot(client, orga_user_token, event, invisible_slot):
    response = client.get(
        event.api_urls.slots + f'{invisible_slot.pk}/',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['id'] == invisible_slot.pk


@pytest.mark.django_db
def test_retrieve_slot_without_submission_orga(client, orga_user_token, event, room, break_slot):
    url = event.api_urls.slots + f'{break_slot.pk}/'
    response = client.get(
        url,
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )

    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['id'] == break_slot.pk
    assert content['submission'] is None
    assert content['room'] == room.pk


@pytest.mark.django_db
def test_retrieve_slot_without_submission(client, event, room, break_slot):
    with scope(event=event):
        assert break_slot.schedule == event.current_schedule

    url = event.api_urls.slots + f'{break_slot.pk}/'
    response = client.get(url, follow=True)

    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['id'] == break_slot.pk
    assert content['submission'] is None
    assert content['room'] == room.pk


@pytest.mark.django_db
def test_retrieve_slot_nonexistent(client, event, slot):
    response = client.get(event.api_urls.slots + '99999/', follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_update_slot_anonymous(client, event, slot):
    response = client.patch(
        event.api_urls.slots + f'{slot.pk}/',
        data=json.dumps({'is_visible': False}),
        content_type='application/json',
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_update_slot_orga_readonly_token(client, event, slot, orga_user_token):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()

    response = client.patch(
        event.api_urls.slots + f'{wip_slot.pk}/',
        data=json.dumps({'room': None}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 403
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room is not None


@pytest.mark.django_db
def test_update_slot_orga_write_token_cannot_change_visibility(client, event, slot, orga_user_write_token):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
    initial_visibility = wip_slot.is_visible
    response = client.patch(
        event.api_urls.slots + f'{wip_slot.pk}/',
        data=json.dumps({'is_visible': not initial_visibility}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['is_visible'] == initial_visibility
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.is_visible == initial_visibility


@pytest.mark.django_db
def test_update_slot_orga_write_token_change_room(client, event, slot, orga_user_write_token, room, other_room):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        assert wip_slot.room == room
    response = client.patch(
        event.api_urls.slots + f'{wip_slot.pk}/',
        data=json.dumps({'room': other_room.pk}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room == other_room


@pytest.mark.django_db
def test_update_slot_orga_write_token_clear_room(client, event, slot, orga_user_write_token, room):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        assert wip_slot.room == room
    response = client.patch(
        event.api_urls.slots + f'{wip_slot.pk}/',
        data=json.dumps({'room': None}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room is None


@pytest.mark.django_db
def test_update_slot_orga_write_token_change_room_non_wip(client, event, slot, other_room, orga_user_write_token):
    assert slot.schedule.version is not None
    assert slot.room != other_room
    response = client.patch(
        event.api_urls.slots + f'{slot.pk}/',
        data=json.dumps({'room': other_room.pk}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    assert response.status_code == 403


@pytest.mark.parametrize('has_submission', (True, False))
@pytest.mark.django_db
def test_update_slot_orga_write_submission_fields(
    client, event, slot, other_room, orga_user_write_token, has_submission
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        if not has_submission:
            wip_slot.submission = None
            wip_slot.save()
    response = client.patch(
        event.api_urls.slots + f'{wip_slot.pk}/',
        data=json.dumps({'description': 'test', 'end': wip_slot.end.isoformat()}),
        content_type='application/json',
        headers={'Authorization': f'Token {orga_user_write_token.token}'},
    )
    content = json.loads(response.text)
    if has_submission:
        assert response.status_code == 400
        assert 'end' in content
        assert 'description' in content
    else:
        assert content['description']['en'] == 'test'


@pytest.mark.django_db
def test_talk_slot_expand_parameters(client, orga_user_token, event, slot):
    url = event.api_urls.slots + f'{slot.pk}/'
    base_headers = {'Authorization': f'Token {orga_user_token.token}'}

    with scope(event=event):
        submission_code = slot.submission.code
        room_pk = slot.room.pk
        speaker = slot.submission.speakers.first().code

    response = client.get(url, headers=base_headers)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content['submission'] == submission_code
    assert content['room'] == room_pk
    assert content['schedule'] == slot.schedule_id

    response = client.get(
        url + '?expand=room,schedule,submission,submission.speakers',
        headers=base_headers,
    )
    assert response.status_code == 200
    content = json.loads(response.text)

    assert isinstance(content['room'], dict)
    assert content['room']['id'] == room_pk
    assert content['room']['name']['en'] == slot.room.name

    assert isinstance(content['submission'], dict)
    assert content['submission']['code'] == submission_code
    assert isinstance(content['submission']['speakers'], list)

    assert isinstance(content['submission']['speakers'], list)
    speaker_data = content['submission']['speakers'][0]
    assert speaker_data['code'] == speaker


@pytest.mark.django_db
def test_schedule_expand_slots(client, event, slot, track):
    with scope(event=event):
        submission = slot.submission
        room = slot.room
        speaker = slot.submission.speakers.first()
        submission_type = slot.submission.submission_type
        slot.submission.track = track
        slot.submission.save()
        profile = speaker.event_profile(event)
        event.feature_flags['use_tracks'] = True
        event.save()
    response = client.get(
        event.api_urls.schedules
        + 'latest/?expand=slots.room,slots.submission.speakers,slots.submission.track,slots.submission.submission_type',
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert isinstance(content['slots'], list)
    assert len(content['slots']) > 0
    assert all(isinstance(s, dict) for s in content['slots'])
    expanded_slot = [s for s in content['slots'] if s['id'] == slot.pk][0]
    assert expanded_slot is not None
    assert 'start' in expanded_slot
    assert 'end' in expanded_slot
    assert expanded_slot['room']['id'] == room.id
    assert expanded_slot['room']['name']['en'] == room.name
    submission_content = expanded_slot['submission']
    assert submission_content['code'] == submission.code
    assert submission_content['title'] == submission.title
    assert submission_content['track']['name']['en'] == track.name
    assert submission_content['submission_type']['name']['en'] == submission_type.name
    assert isinstance(submission_content['speakers'], list)
    speaker_data = submission_content['speakers'][0]
    assert speaker_data['code'] == speaker.code
    assert speaker_data['name'] == speaker.fullname
    assert speaker_data['biography'] == profile.biography


@pytest.mark.django_db
def test_talk_slot_filter_fallback_and_direct_instantiation(client, orga_user_token, event, slot, room):
    with scope(event=event):
        code = slot.submission.code
        current_slot = event.current_schedule.talks.filter(room=room).first()
        wip_slot = event.wip_schedule.talks.filter(room=room).first()
        old_schedule = event.schedules.create(version='v1.0')
        old_slot = TalkSlot.objects.create(
            schedule=old_schedule,
            submission=slot.submission,
            room=room,
            is_visible=True,
            start=event.datetime_from,
            end=event.datetime_from + timedelta(minutes=30),
        )
        invisible_current_slot = TalkSlot.objects.create(
            schedule=event.current_schedule,
            submission=slot.submission,
            room=None,
            is_visible=False,
            start=event.datetime_from + timedelta(minutes=35),
            end=event.datetime_from + timedelta(minutes=65),
        )
        assert current_slot is not None
        assert wip_slot is not None
        assert old_slot is not None
        assert invisible_current_slot is not None

    # 1. Non-schedule filters remain restricted to current schedule
    # Room filter excludes historical and WIP slots
    response = client.get(
        event.api_urls.slots + f'?room={room.pk}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == 1
    assert content['results'][0]['id'] == current_slot.pk

    # Submission filter excludes historical and WIP slots
    response = client.get(
        event.api_urls.slots + f'?submission={code}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == 2
    assert {s['id'] for s in content['results']} == {current_slot.pk, invisible_current_slot.pk}

    # is_visible filter excludes historical, WIP, and invisible current slots
    response = client.get(
        event.api_urls.slots + '?is_visible=true',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    returned_ids = [s['id'] for s in content['results']]
    assert current_slot.pk in returned_ids
    assert invisible_current_slot.pk not in returned_ids
    assert wip_slot.pk not in returned_ids
    assert old_slot.pk not in returned_ids

    # Empty schedule_version falls back to current schedule
    response_empty = client.get(
        event.api_urls.slots + '?schedule_version=',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content_empty = json.loads(response_empty.text)
    assert response_empty.status_code == 200, content_empty
    returned_empty = [s['id'] for s in content_empty['results']]
    assert current_slot.pk in returned_empty
    assert old_slot.pk not in returned_empty
    assert wip_slot.pk not in returned_empty

    # 2. Explicit schedule filters bypass current schedule fallback
    response = client.get(
        event.api_urls.slots + f'?schedule={old_schedule.pk}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert {s['id'] for s in content['results']} == {old_slot.pk}

    response = client.get(
        event.api_urls.slots + '?schedule_version=v1.0',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert {s['id'] for s in content['results']} == {old_slot.pk}

    # 3. Anonymous ?schedule=<wip_pk> returns NO WIP slots (choice validation failure)
    response = client.get(
        event.api_urls.slots + f'?schedule={event.wip_schedule.pk}',
        follow=True,
    )
    content = json.loads(response.text)
    assert response.status_code == 400, content
    assert 'schedule' in content

    # Organizer positive control: organizer CAN access WIP slots by schedule pk
    response = client.get(
        event.api_urls.slots + f'?schedule={event.wip_schedule.pk}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] > 0
    assert wip_slot.pk in [s['id'] for s in content['results']]

    # 4. Direct TalkSlotFilter instantiation preserves event
    with scope(event=event):
        f = TalkSlotFilter(
            data={'schedule_version': 'v1.0'},
            queryset=TalkSlot.objects.filter(schedule__event=event),
            event=event,
        )
        assert f.event == event
        assert f.filters['schedule'].queryset.count() == event.schedules.count()
        assert f.filters['submission'].queryset.count() == event.submissions.count()
        assert f.filters['room'].queryset.count() == event.rooms.count()
        assert old_slot in f.qs


@pytest.mark.django_db
def test_list_slots_team_api_token_wip_access(client, event, slot):
    from eventyay.base.models import Team, TeamAPIToken

    with scope(event=event):
        organizer = getattr(event, 'organizer', None)
        team_auth = Team.objects.create(
            organizer=organizer,
            name='Submission Editors',
            can_change_submissions=True,
            all_events=True,
        )
        token_auth = TeamAPIToken.objects.create(team=team_auth, name='Editor Token')
        wip_pks = set(event.wip_schedule.talks.values_list('pk', flat=True))
        assert wip_pks

        team_unauth = Team.objects.create(
            organizer=organizer,
            name='Read Only Team',
            can_change_submissions=False,
            all_events=True,
        )
        token_unauth = TeamAPIToken.objects.create(team=team_unauth, name='Unauth Token')

    # 1. Authorized token receives WIP slots
    response = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
        headers={'Authorization': f'Token {token_auth.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == len(wip_pks)
    assert {s['id'] for s in content['results']} == wip_pks

    # 2. Unauthorized token receives 0 WIP slots
    response = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
        headers={'Authorization': f'Token {token_unauth.token}'},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    assert content['count'] == 0
    assert content['results'] == []


@pytest.mark.django_db
def test_talk_slot_filter_anonymous_cannot_enumerate_private_submissions(client, event, slot, orga_user_token):
    with scope(event=event):
        private_sub = Submission.objects.create(
            event=event,
            title='Private Draft Talk',
            submission_type=event.cfp.default_type,
        )
        private_slot = TalkSlot.objects.create(
            schedule=event.wip_schedule,
            submission=private_sub,
            room=slot.room,
            is_visible=True,
            start=slot.start,
            end=slot.end,
        )

    # 1. Anonymous filtering by visible slot submission succeeds
    response_vis = client.get(
        event.api_urls.slots + f'?submission={slot.submission.code}',
        follow=True,
    )
    assert response_vis.status_code == 200
    content_vis = json.loads(response_vis.text)
    assert slot.pk in [s['id'] for s in content_vis['results']]

    # 2. Anonymous filtering by private submission without visible slot returns 400
    response_priv = client.get(
        event.api_urls.slots + f'?submission={private_sub.code}',
        follow=True,
    )
    assert response_priv.status_code == 400
    assert 'submission' in response_priv.json()

    # 3. Anonymous filtering by non-existent submission returns 400 identically
    response_nonexist = client.get(
        event.api_urls.slots + '?submission=NONEXISTENT123',
        follow=True,
    )
    assert response_nonexist.status_code == 400
    assert 'submission' in response_nonexist.json()

    # 4. Organizer can filter by private submission and retrieves exact slot
    response_orga = client.get(
        event.api_urls.slots + f'?submission={private_sub.code}&schedule_version=wip',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response_orga.status_code == 200
    content_orga = json.loads(response_orga.text)
    assert {s['id'] for s in content_orga['results']} == {private_slot.pk}


@pytest.mark.django_db
def test_reviewer_who_can_see_speaker_names_cannot_access_wip_or_orga_fields(
    client, event, slot, review_user, orga_user_token
):
    from eventyay.base.models import ReviewPhase

    with scope(event=event):
        wip_pks = set(event.wip_schedule.talks.values_list('pk', flat=True))
        assert wip_pks
        if not event.active_review_phase:
            event.active_review_phase = ReviewPhase.objects.create(
                event=event,
                name='Review Phase',
                can_see_speaker_names=True,
            )
        else:
            event.active_review_phase.can_see_speaker_names = True
            event.active_review_phase.save()

    # 1. Reviewer who can see speaker names cannot access WIP schedule slots
    client.force_login(review_user)
    response_rev_wip = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
    )
    assert response_rev_wip.status_code == 200, response_rev_wip.text
    content_rev_wip = json.loads(response_rev_wip.text)
    assert content_rev_wip['count'] == 0
    assert content_rev_wip['results'] == []

    # 2. Reviewer cannot obtain organizer-only serializer fields (e.g. is_visible)
    response_rev_slots = client.get(
        event.api_urls.slots,
        follow=True,
    )
    assert response_rev_slots.status_code == 200, response_rev_slots.text
    content_rev_slots = json.loads(response_rev_slots.text)
    assert content_rev_slots['count'] > 0
    for s in content_rev_slots['results']:
        assert 'is_visible' not in s

    # 3. Organizer retains legitimate WIP schedule access and organizer-only fields
    client.logout()
    response_orga_wip = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response_orga_wip.status_code == 200, response_orga_wip.text
    content_orga_wip = json.loads(response_orga_wip.text)
    assert content_orga_wip['count'] == len(wip_pks)
    assert {s['id'] for s in content_orga_wip['results']} == wip_pks

    response_orga_slots = client.get(
        event.api_urls.slots,
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response_orga_slots.status_code == 200, response_orga_slots.text
    content_orga_slots = json.loads(response_orga_slots.text)
    assert 'is_visible' in content_orga_slots['results'][0]

    # 4. Anonymous cannot access WIP schedule slots
    client.logout()
    response_anon = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
    )
    assert response_anon.status_code == 200, response_anon.text
    content_anon = json.loads(response_anon.text)
    assert content_anon['count'] == 0
    assert content_anon['results'] == []
