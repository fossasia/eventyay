import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Room, Schedule, Submission, TalkSlot
from eventyay.base.models.auth import User


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
    assert content["count"] == 1


@pytest.mark.django_db
def test_user_cannot_see_wip_schedule_list(client, slot, event):
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(slot.submission.event.api_urls.schedules, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    for schedule_data in content["results"]:
        assert schedule_data["version"] is not None


@pytest.mark.django_db
def test_user_cannot_see_schedule_if_not_public(client, slot, event):
    slot.submission.event.feature_flags["show_schedule"] = False
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
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2


@pytest.mark.django_db
def test_orga_cannot_see_schedule_even_if_not_public(
    client, orga_user_token, slot, event
):
    slot.submission.event.feature_flags["show_schedule"] = False
    slot.submission.event.save()
    with scope(event=event):
        assert slot.submission.event.schedules.count() == 2
    response = client.get(
        slot.submission.event.api_urls.schedules,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)

    assert response.status_code == 200
    assert content["count"] == 2


@pytest.mark.django_db
def test_orga_can_access_wip_schedule_shortcut(client, orga_user_token, event, slot):
    with scope(event=event):
        wip_schedule = event.wip_schedule
        assert wip_schedule is not None
        wip_schedule.talks.add(slot)

    response = client.get(
        event.api_urls.schedules + "wip/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["version"] == event.wip_schedule.version_with_fallback


@pytest.mark.django_db
def test_user_cannot_access_wip_schedule_shortcut(client, event, slot):
    response = client.get(event.api_urls.schedules + "wip/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_orga_can_access_latest_schedule_shortcut(
    client, orga_user_token, event, slot, break_slot
):
    with scope(event=event):
        assert event.current_schedule is not None
        current_schedule_version = event.current_schedule.version

    response = client.get(
        event.api_urls.schedules + "latest/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["version"] == current_schedule_version
    assert len(content["slots"]) == 2


@pytest.mark.django_db
def test_user_can_access_latest_schedule_shortcut_if_public(client, event, slot):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = True
        event.feature_flags["show_schedule"] = True
        event.save()
        current_schedule_version = event.current_schedule.version

    response = client.get(event.api_urls.schedules + "latest/")
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["version"] == current_schedule_version


@pytest.mark.django_db
def test_user_cannot_access_latest_schedule_shortcut_if_schedule_not_public(
    client, event, slot
):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = True
        event.feature_flags["show_schedule"] = False
        event.save()

    response = client.get(event.api_urls.schedules + "latest/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_user_cannot_access_latest_schedule_shortcut_if_event_not_public(
    client, event, slot
):
    with scope(event=event):
        assert event.current_schedule is not None
        event.is_public = False
        event.save()
    response = client.get(event.api_urls.schedules + "latest/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_latest_schedule_shortcut_404_if_no_current_schedule(
    client, orga_user_token, event
):
    with scope(event=event):
        Schedule.objects.filter(event=event).delete()
        event.current_schedule = None
        event.save()
        event.schedules.create(version=None)

    response = client.get(
        event.api_urls.schedules + "latest/",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_redirect_version_success(client, event):
    with scope(event=event):
        schedule = event.wip_schedule
        schedule.freeze("v2.0")
    response = client.get(event.api_urls.schedules + "by-version/?version=v2.0")
    assert response.status_code == 302
    assert response["Location"].endswith(f"/schedules/{schedule.pk}/")


@pytest.mark.django_db
def test_redirect_version_nonexistent_version(client, event):
    response = client.get(
        event.api_urls.schedules + "by-version/?version=nonexistent_version_name"
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_redirect_version_missing_query_param(client, event):
    response = client.get(event.api_urls.schedules + "by-version/")
    assert response.status_code == 400


@pytest.mark.django_db
def test_redirect_version_followed_by_user_schedule_not_public(client, event):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()
        schedule = event.wip_schedule
        schedule.freeze("v2.0")

    response = client.get(
        event.api_urls.schedules + "by-version/?version=v2.0", follow=True
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_can_release_schedule(client, orga_user_write_token, event, slot):
    """Release a valid mixed-case version without changing its spelling."""
    with scope(event=event):
        initial_wip_schedule = event.wip_schedule
        assert initial_wip_schedule.version is None
        initial_wip_pk = initial_wip_schedule.pk
        initial_schedule_count = event.schedules.count()

    release_data = {"version": "v_Test_Release", "comment": "A test release comment"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 201, response.text
    content = json.loads(response.text)

    with scope(event=event):
        assert content["version"] == release_data["version"]
        assert content["comment"]["en"] == release_data["comment"]

        released_schedule = event.schedules.get(version=release_data["version"])
        assert released_schedule.pk == initial_wip_pk
        assert released_schedule.comment == release_data["comment"]

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
def test_orga_cannot_release_schedule_with_existing_version(
    client, orga_user_write_token, event, version
):
    """Return a version field error when a release name is already in use."""
    with scope(event=event):
        event.wip_schedule.freeze("v2.0")
        schedules = list(event.schedules.order_by('pk').values_list('pk', 'version', 'published'))
    release_data = {"version": version}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert content['version'] == [f"A schedule with the version '{version.strip()}' already exists for this event."]
    with scope(event=event):
        assert list(event.schedules.order_by('pk').values_list('pk', 'version', 'published')) == schedules


@pytest.mark.django_db
@pytest.mark.parametrize(
    'version', ('wip', 'latest', ' wip ', ' latest ', 'WIP', 'Wip', 'LATEST', 'Latest', ' wIp ', ' LaTeSt '),
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
def test_orga_cannot_release_schedule_without_version_name(
    client, orga_user_write_token, event
):
    """Require a version name even when the release includes a comment."""
    release_data = {"comment": "Just a comment"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 400
    content = json.loads(response.text)
    assert "version" in content


@pytest.mark.django_db
@pytest.mark.parametrize('via_api', (True, False))
@pytest.mark.parametrize('competing_action', ('release', 'reset'))
def test_release_reports_competing_release(
    client, orga_client, orga_user_write_token, event, slot, monkeypatch, via_api, competing_action
):
    """Report a competing release or reset through both interfaces without overwriting it."""
    original_freeze = Schedule.freeze
    with scope(event=event):
        if competing_action == 'reset':
            released, _ = event.wip_schedule.freeze('previous-release', notify_speakers=False)
    error_message = 'draft no longer exists' if competing_action == 'reset' else 'already versioned'

    def freeze_after_competing_release(draft, *args, **kwargs):
        """Complete another request after this request has loaded its draft."""
        with scope(event=draft.event):
            if competing_action == 'reset':
                released.unfreeze()
            else:
                competing_draft = Schedule.objects.get(pk=draft.pk)
                original_freeze(competing_draft, 'competing-release', notify_speakers=False)
            return original_freeze(draft, *args, **kwargs)

    monkeypatch.setattr(Schedule, 'freeze', freeze_after_competing_release)
    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])
        schedule_count = event.schedules.count()

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
    release_data = {"version": "v_anon_release"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_orga_readonly_user_cannot_release_schedule(client, orga_user_token, event):
    release_data = {"version": "v_readonly_release"}
    response = client.post(
        event.api_urls.schedules + "release/",
        data=json.dumps(release_data),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_can_download_slot_ical(client, slot, event):
    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/calendar"
    expected_filename = (
        f'attachment; filename="{event.slug}-{slot.submission.code}.ics"'
    )
    assert response.headers["Content-Disposition"] == expected_filename
    content = response.text
    assert "BEGIN:VCALENDAR" in content
    assert f"{slot.submission.code}" in content


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_slot_not_visible(client, slot, event):
    with scope(event=event):
        slot.is_visible = False
        slot.save()

    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_schedule_not_public(client, slot, event):
    with scope(event=event):
        event.feature_flags["show_schedule"] = False
        event.save()

    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_user_cannot_download_slot_ical_if_event_not_public(client, slot, event):
    with scope(event=event):
        event.is_public = False
        event.save()

    url = event.api_urls.slots + f"{slot.pk}/ical/"
    response = client.get(url, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_download_slot_ical_slot_without_submission(client, event, break_slot):
    with scope(event=event):
        assert break_slot.schedule == event.current_schedule
    url = event.api_urls.slots + f"{break_slot.pk}/ical/"
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
    event.feature_flags["show_schedule"] = False
    event.save()
    response = client.get(event.api_urls.slots, follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_public_current_schedule_only(
    client, event, slot
):
    with scope(event=event):
        code = slot.submission.code
    response = client.get(event.api_urls.slots, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["id"] == slot.pk
    assert "is_visible" not in content["results"][0]
    assert content["results"][0]["submission"] == code


@pytest.mark.django_db
def test_list_slots_anonymous_schedule_public_only_visible(
    client, event, slot, invisible_slot
):
    with scope(event=event):
        slot_pk = event.current_schedule.talks.get(submission=slot.submission).pk
    response = client.get(event.api_urls.slots, follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 1
    assert content["results"][0]["id"] == slot_pk


@pytest.mark.django_db
def test_list_slots_orga_sees_slots_in_current_schedule_by_default(
    client, orga_user_token, event, slot, invisible_slot
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.first()
        current_schedule_slot_ids = set(
            event.current_schedule.talks.values_list("pk", flat=True)
        )

    response = client.get(
        event.api_urls.slots,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200

    assert content["count"] == len(current_schedule_slot_ids)

    slot_ids_in_response = {r["id"] for r in content["results"]}
    assert slot.pk in slot_ids_in_response
    assert invisible_slot.pk in slot_ids_in_response
    assert wip_slot.pk not in slot_ids_in_response


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_pk(
    client, orga_user_token, event, slot
):
    with scope(event=event):
        event.wip_schedule.freeze("v2.0")
        current_schedule_id = slot.schedule.pk
        code = slot.submission.code

    response = client.get(
        f"{event.api_urls.slots}?schedule={current_schedule_id}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content["count"] >= 1
    assert slot.pk in [s["id"] for s in content["results"]]

    response = client.get(
        f"{event.api_urls.slots}?submission={code}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200
    assert content["count"] == 3


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_room(
    client, orga_user_token, event, slot, room
):
    with scope(event=event):
        other_room = Room.objects.create(event=event, name="Other Room", position=9)
        other_slot = TalkSlot.objects.create(
            schedule=slot.schedule,
            submission=slot.submission,
            room=other_room,
            is_visible=True,
            start=event.datetime_from,
            end=event.datetime_from + timedelta(minutes=30),
        )
        wip_slot_pk = TalkSlot.objects.get(
            submission=slot.submission, schedule=event.wip_schedule
        ).pk

    response = client.get(
        event.api_urls.slots,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    # Without filters, the current-schedule default still applies and the
    # wip slot is excluded.
    assert set(s["id"] for s in content["results"]) == {slot.pk, other_slot.pk}
    assert wip_slot_pk not in {s["id"] for s in content["results"]}

    response = client.get(
        event.api_urls.slots + f"?room={room.pk}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    # Room filtering spans schedules; the other room's slot is excluded.
    assert content["count"] == 2
    assert slot.pk in [s["id"] for s in content["results"]]
    assert other_slot.pk not in [s["id"] for s in content["results"]]

    response = client.get(
        event.api_urls.slots + f"?room={other_room.pk}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content["count"] == 1
    assert content["results"][0]["id"] == other_slot.pk


@pytest.mark.django_db
def test_list_slots_orga_filter_invalid_room(client, orga_user_token, event):
    response = client.get(
        event.api_urls.slots + "?room=99999",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 400
    assert "room" in response.json()


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_speaker(client, orga_user_token, event, slot):
    with scope(event=event):
        speaker_code = slot.submission.speakers.first().code
        submission_code = slot.submission.code

    response = client.get(
        event.api_urls.slots + f"?speaker={speaker_code}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content["count"] >= 1
    assert {s["submission"] for s in content["results"]} == {submission_code}


@pytest.mark.django_db
def test_list_slots_filter_unknown_speaker(client, orga_user_token, event):
    response = client.get(
        event.api_urls.slots + "?speaker=unknownguest",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 400
    assert "speaker" in response.json()


@pytest.mark.django_db
def test_list_slots_cannot_filter_by_speaker_from_other_event(
    client, orga_user_token, event, other_event
):
    with scopes_disabled():
        outsider = User.objects.create_user(
            password="outsiderpwd1!",
            fullname="Outside Speaker",
            email="outside@example.com",
        )
    with scope(event=other_event):
        outside_submission = Submission.objects.create(
            title="Talk in another event",
            event=other_event,
            submission_type=other_event.cfp.default_type,
            description="Description",
            abstract="Abstract",
            notes="Notes",
            content_locale="en",
        )
        outside_submission.speakers.add(outsider)

    response = client.get(
        event.api_urls.slots + f"?speaker={outsider.code}",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 400
    assert "speaker" in response.json()


@pytest.mark.django_db
def test_list_slots_filter_by_room_of_unscheduled_room(client, event, room, break_slot):
    with scope(event=event):
        other_room = Room.objects.create(event=event, name="Other Room")
        other_slot = TalkSlot.objects.create(
            description="Other Break",
            schedule=break_slot.schedule,
            is_visible=True,
            start=room.event.datetime_from + timedelta(minutes=130),
            end=room.event.datetime_from + timedelta(minutes=160),
            room=other_room,
        )
        room.is_unscheduled = True
        room.save()
        break_slot_pk = break_slot.pk
        other_slot_pk = other_slot.pk

    response = client.get(event.api_urls.slots + f"?room={room.pk}", follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200, content
    result_ids = [s["id"] for s in content["results"]]
    assert break_slot_pk in result_ids
    assert other_slot_pk not in result_ids


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_version(
    client, orga_user_token, event, slot, room
):
    with scope(event=event):
        event.wip_schedule.freeze("v2-filter")
        versioned_schedule = event.schedules.get(version="v2-filter")
        expected_pks = set(
            versioned_schedule.talks.values_list("pk", flat=True)
        )
        assert expected_pks

    response = client.get(
        event.api_urls.slots + "?schedule_version=v2-filter",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content["count"] == len(expected_pks)
    assert {s["id"] for s in content["results"]} == expected_pks


@pytest.mark.django_db
def test_list_slots_anonymous_cannot_enumerate_private_proposal_speaker(
    client, orga_user_token, event
):
    with scopes_disabled():
        private_speaker = User.objects.create_user(
            password='privatespeakerpwd1!',
            fullname='Private Speaker',
            email='privatespeaker@example.com',
        )
    with scope(event=event):
        private_submission = Submission.objects.create(
            title='Private Rejected Proposal',
            event=event,
            submission_type=event.cfp.default_type,
            description='Description',
            abstract='Abstract',
            notes='Notes',
            content_locale='en',
            state='rejected',
        )
        private_submission.speakers.add(private_speaker)

    # Anonymous caller gets 400, unable to distinguish from non-existent speaker
    response = client.get(
        event.api_urls.slots + f'?speaker={private_speaker.code}',
        follow=True,
    )
    assert response.status_code == 400
    assert 'speaker' in response.json()

    # Organizer retains access and can filter by this speaker
    response = client.get(
        event.api_urls.slots + f'?speaker={private_speaker.code}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_list_slots_anonymous_can_filter_by_public_speaker(client, event, slot, other_slot):
    with scope(event=event):
        speaker_code = slot.submission.speakers.first().code
        expected_pk = slot.pk
        other_pk = other_slot.pk

    response = client.get(
        event.api_urls.slots + f'?speaker={speaker_code}',
        follow=True,
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    result_ids = [s['id'] for s in content['results']]
    assert expected_pk in result_ids
    assert other_pk not in result_ids


@pytest.mark.django_db
def test_list_slots_anonymous_can_filter_by_speaker_with_deleted_room_slot(client, event, slot):
    with scope(event=event):
        deleted_room = Room.objects.create(event=event, name='Removed room', deleted=True)
        # The WIP slot is non-public because its schedule has no version. Its
        # deleted room must not hide the released public slot of the same talk.
        updated = TalkSlot.objects.filter(
            submission=slot.submission,
            schedule__version__isnull=True,
        ).update(room=deleted_room)
        assert updated > 0
        speaker_code = slot.submission.speakers.first().code
        public_slot_pk = slot.pk

    response = client.get(event.api_urls.slots + f'?speaker={speaker_code}', follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert public_slot_pk in [s['id'] for s in content['results']]


@pytest.mark.django_db
def test_list_slots_anonymous_cannot_enumerate_speaker_with_only_deleted_room_slots(client, event, slot):
    with scope(event=event):
        deleted_room = Room.objects.create(event=event, name='Removed room', deleted=True)
        updated = TalkSlot.objects.filter(submission=slot.submission).update(room=deleted_room)
        assert updated > 0
        speaker_code = slot.submission.speakers.first().code

    response = client.get(event.api_urls.slots + f'?speaker={speaker_code}', follow=True)
    assert response.status_code == 400
    assert 'speaker' in response.json()


@pytest.mark.django_db
def test_list_slots_anonymous_can_filter_by_speaker_with_unassigned_room(client, event, slot):
    with scope(event=event):
        updated = TalkSlot.objects.filter(pk=slot.pk).update(room=None)
        assert updated > 0
        speaker_code = slot.submission.speakers.first().code
        public_slot_pk = slot.pk

    response = client.get(event.api_urls.slots + f'?speaker={speaker_code}', follow=True)
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert public_slot_pk in [s['id'] for s in content['results']]


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_speaker_with_only_deleted_room_slots(
    client, orga_user_token, event, slot, other_slot
):
    with scope(event=event):
        deleted_room = Room.objects.create(event=event, name='Removed room', deleted=True)
        updated = TalkSlot.objects.filter(submission=slot.submission).update(room=deleted_room)
        assert updated > 0
        speaker_code = slot.submission.speakers.first().code
        expected_pks = set(TalkSlot.objects.filter(submission=slot.submission).values_list('pk', flat=True))
        other_pk = other_slot.pk

    response = client.get(
        event.api_urls.slots + f'?speaker={speaker_code}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    result_pks = {s['id'] for s in content['results']}
    assert expected_pks.issubset(result_pks)
    assert other_pk not in result_pks


@pytest.mark.django_db
def test_list_slots_orga_can_filter_by_schedule_version_wip(
    client, orga_user_token, event, slot
):
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
def test_list_slots_anonymous_cannot_filter_by_schedule_version_wip(
    client, event, slot
):
    response = client.get(
        event.api_urls.slots + '?schedule_version=wip',
        follow=True,
    )
    content = json.loads(response.text)
    assert response.status_code == 200, content
    assert content['count'] == 0


@pytest.mark.django_db
def test_retrieve_slot_anonymous_not_visible(client, event, invisible_slot):
    response = client.get(event.api_urls.slots + f"{invisible_slot.pk}/", follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_retrieve_slot_anonymous_visible_schedule_public(client, event, slot):
    with scope(event=event):
        code = slot.submission.code
    response = client.get(event.api_urls.slots + f"{slot.pk}/", follow=True)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == slot.pk
    assert "is_visible" not in content
    assert content["submission"] == code


@pytest.mark.django_db
def test_retrieve_slot_anonymous_schedule_not_public(client, event, slot):
    with scope(event=event):
        event.is_public = True
        event.feature_flags["show_schedule"] = False
        event.save()
    response = client.get(event.api_urls.slots + f"{slot.pk}/", follow=True)
    assert response.status_code == 401


@pytest.mark.django_db
def test_retrieve_slot_orga_can_see_invisible_slot(
    client, orga_user_token, event, invisible_slot
):
    response = client.get(
        event.api_urls.slots + f"{invisible_slot.pk}/",
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == invisible_slot.pk


@pytest.mark.django_db
def test_retrieve_slot_without_submission_orga(
    client, orga_user_token, event, room, break_slot
):
    url = event.api_urls.slots + f"{break_slot.pk}/"
    response = client.get(
        url,
        follow=True,
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )

    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == break_slot.pk
    assert content["submission"] is None
    assert content["room"] == room.pk


@pytest.mark.django_db
def test_retrieve_slot_without_submission(client, event, room, break_slot):
    with scope(event=event):
        assert break_slot.schedule == event.current_schedule

    url = event.api_urls.slots + f"{break_slot.pk}/"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["id"] == break_slot.pk
    assert content["submission"] is None
    assert content["room"] == room.pk


@pytest.mark.django_db
def test_retrieve_slot_nonexistent(client, event, slot):
    response = client.get(event.api_urls.slots + "99999/", follow=True)
    assert response.status_code == 404


@pytest.mark.django_db
def test_update_slot_anonymous(client, event, slot):
    response = client.patch(
        event.api_urls.slots + f"{slot.pk}/",
        data=json.dumps({"is_visible": False}),
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_update_slot_orga_readonly_token(client, event, slot, orga_user_token):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()

    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"room": None}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_token.token}"},
    )
    assert response.status_code == 403
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room is not None


@pytest.mark.django_db
def test_update_slot_orga_write_token_cannot_change_visibility(
    client, event, slot, orga_user_write_token
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
    initial_visibility = wip_slot.is_visible
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"is_visible": not initial_visibility}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["is_visible"] == initial_visibility
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.is_visible == initial_visibility


@pytest.mark.django_db
def test_update_slot_orga_write_token_change_room(
    client, event, slot, orga_user_write_token, room, other_room
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        assert wip_slot.room == room
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"room": other_room.pk}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room == other_room


@pytest.mark.django_db
def test_update_slot_orga_write_token_clear_room(
    client, event, slot, orga_user_write_token, room
):
    with scope(event=event):
        wip_slot = event.wip_schedule.talks.filter(submission=slot.submission).first()
        assert wip_slot.room == room
    response = client.patch(
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"room": None}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 200
    with scope(event=event):
        wip_slot.refresh_from_db()
        assert wip_slot.room is None


@pytest.mark.django_db
def test_update_slot_orga_write_token_change_room_non_wip(
    client, event, slot, other_room, orga_user_write_token
):
    assert slot.schedule.version is not None
    assert slot.room != other_room
    response = client.patch(
        event.api_urls.slots + f"{slot.pk}/",
        data=json.dumps({"room": other_room.pk}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("has_submission", (True, False))
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
        event.api_urls.slots + f"{wip_slot.pk}/",
        data=json.dumps({"description": "test", "end": wip_slot.end.isoformat()}),
        content_type="application/json",
        headers={"Authorization": f"Token {orga_user_write_token.token}"},
    )
    content = json.loads(response.text)
    if has_submission:
        assert response.status_code == 400
        assert "end" in content
        assert "description" in content
    else:
        assert content["description"]["en"] == "test"


@pytest.mark.django_db
def test_talk_slot_expand_parameters(client, orga_user_token, event, slot):
    url = event.api_urls.slots + f"{slot.pk}/"
    base_headers = {"Authorization": f"Token {orga_user_token.token}"}

    with scope(event=event):
        submission_code = slot.submission.code
        room_pk = slot.room.pk
        speaker = slot.submission.speakers.first().code

    response = client.get(url, headers=base_headers)
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content["submission"] == submission_code
    assert content["room"] == room_pk
    assert content["schedule"] == slot.schedule_id

    response = client.get(
        url + "?expand=room,schedule,submission,submission.speakers",
        headers=base_headers,
    )
    assert response.status_code == 200
    content = json.loads(response.text)

    assert isinstance(content["room"], dict)
    assert content["room"]["id"] == room_pk
    assert content["room"]["name"]["en"] == slot.room.name

    assert isinstance(content["submission"], dict)
    assert content["submission"]["code"] == submission_code
    assert isinstance(content["submission"]["speakers"], list)

    assert isinstance(content["submission"]["speakers"], list)
    speaker_data = content["submission"]["speakers"][0]
    assert speaker_data["code"] == speaker


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
        event.feature_flags["use_tracks"] = True
        event.save()
    response = client.get(
        event.api_urls.schedules
        + "latest/?expand=slots.room,slots.submission.speakers,slots.submission.track,slots.submission.submission_type",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert isinstance(content["slots"], list)
    assert len(content["slots"]) > 0
    assert all(isinstance(s, dict) for s in content["slots"])
    expanded_slot = [s for s in content["slots"] if s["id"] == slot.pk][0]
    assert expanded_slot is not None
    assert "start" in expanded_slot
    assert "end" in expanded_slot
    assert expanded_slot["room"]["id"] == room.id
    assert expanded_slot["room"]["name"]["en"] == room.name
    submission_content = expanded_slot["submission"]
    assert submission_content["code"] == submission.code
    assert submission_content["title"] == submission.title
    assert submission_content["track"]["name"]["en"] == track.name
    assert submission_content["submission_type"]["name"]["en"] == submission_type.name
    assert isinstance(submission_content["speakers"], list)
    speaker_data = submission_content["speakers"][0]
    assert speaker_data["code"] == speaker.code
    assert speaker_data["name"] == speaker.fullname
    assert speaker_data["biography"] == profile.biography


@pytest.mark.django_db
def test_track_limited_user_cannot_enumerate_disallowed_track_speakers(
    client, event, review_user, review_user_token, slot, other_slot, track, other_track
):
    with scope(event=event):
        slot.submission.track = track
        slot.submission.save()
        other_slot.submission.track = other_track
        other_slot.submission.save()

        review_user.teams.filter(is_reviewer=True).first().limit_tracks.add(track)

        allowed_speaker_code = slot.submission.speakers.first().code
        disallowed_speaker_code = other_slot.submission.speakers.first().code
        allowed_slot_pk = slot.pk
        disallowed_slot_pk = other_slot.pk

    headers = {'Authorization': f'Token {review_user_token.token}'}

    # Accessible speaker on allowed track returns 200 with matching slot
    response = client.get(event.api_urls.slots + f'?speaker={allowed_speaker_code}', follow=True, headers=headers)
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    result_ids = [s['id'] for s in content['results']]
    assert allowed_slot_pk in result_ids
    assert disallowed_slot_pk not in result_ids

    # Disallowed-track speaker cannot be enumerated (returns 400 validation error)
    response = client.get(event.api_urls.slots + f'?speaker={disallowed_speaker_code}', follow=True, headers=headers)
    assert response.status_code == 400
    assert 'speaker' in response.json()

    # Anonymous user has no track limits, so both speakers are public
    anon_resp = client.get(event.api_urls.slots + f'?speaker={disallowed_speaker_code}', follow=True)
    assert anon_resp.status_code == 200
    anon_content = json.loads(anon_resp.text)
    assert disallowed_slot_pk in [s['id'] for s in anon_content['results']]


@pytest.mark.django_db
def test_track_limited_user_sees_only_accessible_slots_for_multi_track_speaker(
    client, event, review_user, review_user_token, slot, track, other_track
):
    with scope(event=event):
        slot.submission.track = track
        slot.submission.save()

        speaker = slot.submission.speakers.first()
        second_sub = Submission.objects.create(
            title="Second Talk Disallowed Track",
            event=event,
            submission_type=event.cfp.default_type,
            track=other_track,
            state="confirmed",
        )
        second_sub.speakers.add(speaker)
        second_slot = TalkSlot.objects.create(
            submission=second_sub,
            schedule=slot.schedule,
            is_visible=True,
            start=slot.start + timedelta(hours=2),
            end=slot.end + timedelta(hours=2),
            room=slot.room,
        )

        review_user.teams.filter(is_reviewer=True).first().limit_tracks.add(track)
        allowed_slot_pk = slot.pk
        disallowed_slot_pk = second_slot.pk
        speaker_code = speaker.code

    headers = {'Authorization': f'Token {review_user_token.token}'}
    response = client.get(event.api_urls.slots + f'?speaker={speaker_code}', follow=True, headers=headers)
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    result_ids = [s['id'] for s in content['results']]
    assert allowed_slot_pk in result_ids
    assert disallowed_slot_pk not in result_ids


@pytest.mark.django_db
def test_empty_schedule_version_falls_back_to_current_schedule(
    client, orga_user_token, event, slot, other_confirmed_submission, room
):
    with scope(event=event):
        event.wip_schedule.freeze('v1')
        v1_schedule = event.schedules.get(version='v1')
        v1_slot_pk = v1_schedule.talks.first().pk

        TalkSlot.objects.filter(
            submission=other_confirmed_submission,
            schedule=event.wip_schedule,
        ).update(
            room=room,
            is_visible=True,
            start=room.event.datetime_from + timedelta(hours=1),
            end=room.event.datetime_from + timedelta(hours=2),
        )
        event.wip_schedule.freeze('v2')
        v2_schedule = event.schedules.get(version='v2')
        v2_slot_pks = set(v2_schedule.talks.filter(is_visible=True).values_list('pk', flat=True))
        assert v1_slot_pk not in v2_slot_pks

    resp = client.get(event.api_urls.slots, follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert {s['id'] for s in content['results']} == v2_slot_pks

    resp = client.get(event.api_urls.slots + '?schedule_version=', follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert {s['id'] for s in content['results']} == v2_slot_pks

    resp = client.get(event.api_urls.slots + '?schedule_version=%20%20', follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert {s['id'] for s in content['results']} == v2_slot_pks

    resp = client.get(event.api_urls.slots + '?schedule_version=v1', follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert v1_slot_pk in [s['id'] for s in content['results']]
    assert not v2_slot_pks.intersection({s['id'] for s in content['results']})

    resp = client.get(event.api_urls.slots + '?schedule_version=wip', follow=True)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    assert content['results'] == []

    headers = {'Authorization': f'Token {orga_user_token.token}'}
    resp = client.get(event.api_urls.slots + '?schedule_version=wip', follow=True, headers=headers)
    assert resp.status_code == 200
    content = json.loads(resp.text)
    with scope(event=event):
        expected_wip_pks = set(event.wip_schedule.talks.values_list('pk', flat=True))
    assert {s['id'] for s in content['results']} == expected_wip_pks


@pytest.mark.django_db
def test_talk_slot_search_filters_by_title_and_speaker(
    client, orga_user_token, event, schedule, slot, other_slot
):
    with scope(event=event):
        slot.submission.title = "Unique Schedule Talk Alpha"
        slot.submission.save()
        other_slot.submission.title = "Another Session Beta"
        other_slot.submission.save()
        speaker = other_slot.submission.speakers.first()
        speaker.fullname = "SpeakerGammaName"
        speaker.save()

    # Public search by title keyword
    resp = client.get(event.api_urls.slots + "?search=Alpha", follow=True)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    pks = [s["id"] for s in content["results"]]
    assert slot.pk in pks
    assert other_slot.pk not in pks

    # Public search by speaker name
    resp = client.get(event.api_urls.slots + "?search=SpeakerGammaName", follow=True)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    pks = [s["id"] for s in content["results"]]
    assert other_slot.pk in pks
    assert slot.pk not in pks

    # Search combined with filter backend
    resp = client.get(
        event.api_urls.slots + f"?room={slot.room_id}&search=Alpha",
        follow=True,
    )
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    pks = [s["id"] for s in content["results"]]
    assert slot.pk in pks


@pytest.mark.django_db
def test_talk_slot_filter_choices_restricted_for_anonymous(
    client, orga_user_token, event, schedule, slot, rejected_submission, room
):
    with scope(event=event):
        wip_id = event.wip_schedule.pk
        rejected_code = rejected_submission.code

        # Create a deleted room
        deleted_room = event.rooms.create(name="Deleted Room", deleted=True)
        deleted_room_id = deleted_room.pk

    headers = {"Authorization": f"Token {orga_user_token.token}"}

    # 1. Anonymous cannot filter by WIP schedule primary key -> 400
    resp = client.get(event.api_urls.slots + f"?schedule={wip_id}", follow=True)
    assert resp.status_code == 400, resp.text
    assert "schedule" in resp.json()

    # Organizer CAN filter by WIP schedule primary key -> 200
    resp = client.get(
        event.api_urls.slots + f"?schedule={wip_id}",
        follow=True,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # 2. Anonymous cannot filter by rejected submission code -> 400
    resp = client.get(event.api_urls.slots + f"?submission={rejected_code}", follow=True)
    assert resp.status_code == 400, resp.text
    assert "submission" in resp.json()

    # Organizer CAN filter by rejected submission code -> 200
    resp = client.get(
        event.api_urls.slots + f"?submission={rejected_code}",
        follow=True,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # 3. Anonymous cannot filter by deleted room -> 400
    resp = client.get(event.api_urls.slots + f"?room={deleted_room_id}", follow=True)
    assert resp.status_code == 400, resp.text
    assert "room" in resp.json()

    # Organizer CAN filter by deleted room -> 200
    resp = client.get(
        event.api_urls.slots + f"?room={deleted_room_id}",
        follow=True,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.django_db
def test_talk_slot_filter_submission_with_multiple_released_schedules_no_duplicate_error(
    client, event, slot, room
):
    with scope(event=event):
        event.wip_schedule.freeze('v1')
        # Schedule the slot again in a new schedule version
        event.wip_schedule.talks.filter(submission=slot.submission).update(
            room=room,
            is_visible=True,
            start=room.event.datetime_from + timedelta(hours=3),
            end=room.event.datetime_from + timedelta(hours=4),
        )
        event.wip_schedule.freeze('v2')

    # Anonymous filters by submission code present in multiple released schedules
    resp = client.get(event.api_urls.slots + f"?submission={slot.submission.code}", follow=True)
    assert resp.status_code == 200, resp.text
    content = json.loads(resp.text)
    assert len(content["results"]) >= 1


@pytest.mark.django_db
def test_blank_query_parameters_retain_current_schedule_default(
    client, event, slot, room
):
    with scope(event=event):
        event.wip_schedule.freeze('v1')
        current_slots = set(event.current_schedule.talks.filter(is_visible=True).values_list('pk', flat=True))

    resp_default = client.get(event.api_urls.slots, follow=True)
    assert resp_default.status_code == 200
    expected_ids = {s['id'] for s in resp_default.json()['results']}
    assert expected_ids == current_slots

    params = (
        'room=',
        'room=%20',
        'speaker=',
        'submission=',
        'schedule=',
        'schedule_version=',
        'schedule_version=%20',
    )
    for param in params:
        resp = client.get(event.api_urls.slots + f'?{param}', follow=True)
        assert resp.status_code == 200, f'Failed for {param}: {resp.text}'
        actual_ids = {s['id'] for s in resp.json()['results']}
        assert actual_ids == expected_ids, f'Mismatch for {param}'


@pytest.mark.django_db
def test_talk_slots_filter_key_normalizes_all_blank_parameters(event):
    from django.test import RequestFactory

    from eventyay.api.filters.schedule import TalkSlotFilter
    from eventyay.base.services.stale_cache import talk_slots_filter_key

    rf = RequestFactory()
    filter_fields = TalkSlotFilter.get_fields().keys()

    base_req = rf.get('/api/v1/events/test/slots/')
    base_key = talk_slots_filter_key(base_req, filter_fields)

    params = (
        'room=',
        'room=%20',
        'speaker=',
        'submission=',
        'schedule=',
        'schedule_version=',
    )
    for param in params:
        req = rf.get(f'/api/v1/events/test/slots/?{param}')
        key = talk_slots_filter_key(req, filter_fields)
        assert key == base_key, f'Cache key difference for {param}: {key} != {base_key}'


@pytest.mark.django_db
def test_talk_slots_filter_key_fields_and_omit_normalization():
    from django.test import RequestFactory

    from eventyay.api.filters.schedule import TalkSlotFilter
    from eventyay.base.services.stale_cache import talk_slots_filter_key

    rf = RequestFactory()
    filter_fields = TalkSlotFilter.get_fields().keys()

    base_req = rf.get('/api/v1/events/test/slots/')
    base_key = talk_slots_filter_key(base_req, filter_fields)

    # Blank search/ordering produce default key, while blank fields/omit isolate sparse responses
    assert talk_slots_filter_key(rf.get('/api/v1/events/test/slots/?search=%20%20&ordering=%20'), filter_fields) == base_key
    assert talk_slots_filter_key(rf.get('/api/v1/events/test/slots/?fields=&omit='), filter_fields) != base_key

    # Distinct fields produce distinct cache keys
    key_fields_id = talk_slots_filter_key(rf.get('/api/v1/events/test/slots/?fields=id'), filter_fields)
    assert key_fields_id != base_key

    # Token order in fields/omit is normalized
    key_ab = talk_slots_filter_key(rf.get('/api/v1/events/test/slots/?fields=id,room'), filter_fields)
    key_ba = talk_slots_filter_key(rf.get('/api/v1/events/test/slots/?fields=room,id'), filter_fields)
    assert key_ab == key_ba

    # Distinct omit produce distinct cache keys
    key_omit_room = talk_slots_filter_key(rf.get('/api/v1/events/test/slots/?omit=room'), filter_fields)
    assert key_omit_room != base_key


@pytest.mark.django_db
def test_schedule_expand_fields_key_normalization():
    from django.test import RequestFactory

    from eventyay.api.views.schedule import schedule_expand_fields_key

    rf = RequestFactory()
    assert schedule_expand_fields_key(rf.get('/')) == ''
    assert schedule_expand_fields_key(rf.get('/?expand=&fields=&omit=')) == 'expand=&fields=&omit='

    # Sorted tokens
    assert schedule_expand_fields_key(rf.get('/?expand=slots.room,slots')) == 'expand=slots,slots.room'
    assert schedule_expand_fields_key(rf.get('/?expand=slots,slots.room')) == 'expand=slots,slots.room'

    # fields and omit included
    key = schedule_expand_fields_key(rf.get('/?expand=slots&fields=version,slots&omit=comment'))
    assert key == 'expand=slots&fields=slots,version&omit=comment'


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_talk_slots_cache_fields_and_omit_response_isolation(client, slot):
    cache.clear()
    event = slot.event
    with scope(event=event):
        assert event.current_schedule is not None

    # Step 1: Warm cache with sparse ?fields=id
    resp_sparse = client.get(event.api_urls.slots + '?fields=id', follow=True)
    assert resp_sparse.status_code == 200
    item_sparse = resp_sparse.json()['results'][0]
    assert 'id' in item_sparse
    assert 'room' not in item_sparse

    # Step 2: Request without fields; must return full object, not sparse cached response
    resp_full = client.get(event.api_urls.slots, follow=True)
    assert resp_full.status_code == 200
    item_full = resp_full.json()['results'][0]
    assert 'id' in item_full
    assert 'room' in item_full

    # Step 3: Warm cache with ?omit=room
    resp_omit = client.get(event.api_urls.slots + '?omit=room', follow=True)
    assert resp_omit.status_code == 200
    item_omit = resp_omit.json()['results'][0]
    assert 'room' not in item_omit

    # Step 4: Request without omit; room must be present
    resp_full2 = client.get(event.api_urls.slots, follow=True)
    assert resp_full2.status_code == 200
    assert 'room' in resp_full2.json()['results'][0]


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_talk_slots_whitespace_and_blank_cache_isolation(client, slot):
    cache.clear()
    event = slot.event
    with scope(event=event):
        assert event.current_schedule is not None

    # Step 1: Query with ?fields=id,room
    resp_exact = client.get(event.api_urls.slots + '?fields=id,room', follow=True)
    assert resp_exact.status_code == 200
    item_exact = resp_exact.json()['results'][0]
    assert 'id' in item_exact
    assert 'room' in item_exact

    # Step 2: Query with ?fields=id, room (unstripped whitespace token)
    # FlexFields preserves the leading space for ' room', which does not match field 'room'.
    resp_spaced = client.get(event.api_urls.slots + '?fields=id,%20room', follow=True)
    assert resp_spaced.status_code == 200
    item_spaced = resp_spaced.json()['results'][0]
    assert 'id' in item_spaced
    assert 'room' not in item_spaced

    # Step 3: Query with ?fields= (blank value)
    # FlexFields treats blank as sparse empty list, returning empty dict per item
    resp_blank = client.get(event.api_urls.slots + '?fields=', follow=True)
    assert resp_blank.status_code == 200
    item_blank = resp_blank.json()['results'][0]
    assert item_blank == {}

    # Step 4: Normal request without fields must still return full object
    resp_full = client.get(event.api_urls.slots, follow=True)
    assert resp_full.status_code == 200
    item_full = resp_full.json()['results'][0]
    assert 'id' in item_full
    assert 'room' in item_full


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_schedule_detail_cache_fields_and_omit_isolation(client, schedule):
    cache.clear()
    event = schedule.event
    assert schedule.version is not None

    # Step 1: Warm cache with ?fields=version
    resp_sparse = client.get(f'{event.api_urls.schedules}{schedule.pk}/?fields=version', follow=True)
    assert resp_sparse.status_code == 200
    data_sparse = resp_sparse.json()
    assert 'version' in data_sparse
    assert 'slots' not in data_sparse

    # Step 2: Request without fields; full schedule with slots must be returned
    resp_full = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_full.status_code == 200
    data_full = resp_full.json()
    assert 'version' in data_full
    assert 'slots' in data_full


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_schedule_detail_organizer_cache_bypass_and_isolation(
    client, orga_user_token, schedule, slot
):
    cache.clear()
    event = schedule.event
    assert schedule.version is not None

    # Create a hidden slot on this schedule and ensure schedule is public
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.schedule = schedule
        slot.is_visible = False
        slot.save()

    # Step 1: Organizer request
    resp_orga = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert resp_orga.status_code == 200
    data_orga = resp_orga.json()
    # Organizer must see hidden slot
    assert slot.pk in data_orga['slots']

    # Step 2: Anonymous request; must NOT see hidden slot via cache contamination
    resp_anon = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_anon.status_code == 200
    data_anon = resp_anon.json()
    assert slot.pk not in data_anon['slots']

    # Step 3: Reverse order verification - warm anonymous cache, then query as organizer
    resp_anon2 = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_anon2.status_code == 200
    assert slot.pk not in resp_anon2.json()['slots']

    resp_orga2 = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert resp_orga2.status_code == 200
    assert slot.pk in resp_orga2.json()['slots']


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_talk_slots_expand_whitespace_and_blank_cache_isolation(client, slot):
    cache.clear()
    event = slot.event
    with scope(event=event):
        assert event.current_schedule is not None
        slot.is_visible = True
        slot.save()

    # Step 1: Query with ?expand=submission,room
    resp_expanded = client.get(event.api_urls.slots + '?expand=submission,room', follow=True)
    assert resp_expanded.status_code == 200
    item_expanded = resp_expanded.json()['results'][0]
    assert isinstance(item_expanded['submission'], dict)
    assert isinstance(item_expanded['room'], dict)

    # Step 2: Query with ?expand=submission,%20room (whitespace preserved, unstripped)
    resp_spaced = client.get(event.api_urls.slots + '?expand=submission,%20room', follow=True)
    assert resp_spaced.status_code == 200
    item_spaced = resp_spaced.json()['results'][0]
    assert isinstance(item_spaced['submission'], dict)
    assert not isinstance(item_spaced['room'], dict)

    # Step 3: Query with ?expand= (blank expand)
    resp_blank = client.get(event.api_urls.slots + '?expand=', follow=True)
    assert resp_blank.status_code == 200
    item_blank = resp_blank.json()['results'][0]
    assert not isinstance(item_blank['submission'], dict)
    assert not isinstance(item_blank['room'], dict)

    # Step 4: Normal request without expand must still return unexpanded
    resp_absent = client.get(event.api_urls.slots, follow=True)
    assert resp_absent.status_code == 200
    item_absent = resp_absent.json()['results'][0]
    assert not isinstance(item_absent['submission'], dict)
    assert not isinstance(item_absent['room'], dict)


def test_talk_slots_cache_key_delimiter_collision():
    from unittest.mock import MagicMock
    from eventyay.api.views.schedule import schedule_expand_fields_key
    from eventyay.base.services.stale_cache import talk_slots_filter_key

    req1 = MagicMock()
    req1.query_params = {'fields': 'a|page=2'}
    req1.GET = req1.query_params

    req2 = MagicMock()
    req2.query_params = {'fields': 'a', 'page': '2'}
    req2.GET = req2.query_params

    key1 = talk_slots_filter_key(req1, [])
    key2 = talk_slots_filter_key(req2, [])
    assert key1 != key2

    req3 = MagicMock()
    req3.query_params = {'expand': 'a,b'}
    req3.GET = req3.query_params

    req4 = MagicMock()
    req4.query_params = {'expand': 'a%2Cb'}
    req4.GET = req4.query_params

    key3 = schedule_expand_fields_key(req3)
    key4 = schedule_expand_fields_key(req4)
    assert key3 != key4

    req5 = MagicMock()
    req5.query_params = {'fields': 'a,b'}
    req5.GET = req5.query_params

    req6 = MagicMock()
    req6.query_params = {'fields': 'a%2Cb'}
    req6.GET = req6.query_params

    key5 = talk_slots_filter_key(req5, [])
    key6 = talk_slots_filter_key(req6, [])
    assert key5 != key6

    req7 = MagicMock()
    req7.query_params = {'room': '1|submission=b', 'submission': 'c'}
    req7.GET = req7.query_params

    req8 = MagicMock()
    req8.query_params = {'room': '1', 'submission': 'b|submission=c'}
    req8.GET = req8.query_params

    key7 = talk_slots_filter_key(req7, ['room', 'submission'])
    key8 = talk_slots_filter_key(req8, ['room', 'submission'])
    assert key7 != key8


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_talk_slots_pagination_cache_isolation(client, slot, monkeypatch):
    cache.clear()
    monkeypatch.setattr('rest_framework.pagination.PageNumberPagination.page_size', 1)
    event = slot.event
    with scope(event=event):
        sub2 = Submission.objects.create(
            event=event,
            title='Second Slot Talk',
            state='confirmed',
            submission_type=event.submission_types.first(),
        )
        slot2 = TalkSlot.objects.create(
            schedule=event.current_schedule,
            submission=sub2,
            is_visible=True,
            start=slot.start,
            end=slot.end,
        )

    # Query page 1
    resp_p1 = client.get(event.api_urls.slots + '?page=1', follow=True)
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert data_p1['count'] >= 2
    assert len(data_p1['results']) == 1
    slot1_id = data_p1['results'][0]['id']

    # Query page 2 -> must return a different slot and not return cached page 1
    resp_p2 = client.get(event.api_urls.slots + '?page=2', follow=True)
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2['results']) == 1
    slot2_id = data_p2['results'][0]['id']
    assert slot1_id != slot2_id

    # Re-query page 1 -> must still return slot 1 from cache
    resp_p1_re = client.get(event.api_urls.slots + '?page=1', follow=True)
    assert resp_p1_re.status_code == 200
    assert resp_p1_re.json()['results'][0]['id'] == slot1_id

    # Default request without page parameter must also return page 1 (slot 1)
    resp_default = client.get(event.api_urls.slots, follow=True)
    assert resp_default.status_code == 200
    assert resp_default.json()['results'][0]['id'] == slot1_id


@pytest.mark.django_db
def test_talk_slot_reviewer_search_and_filter_cannot_leak_speakers_in_anonymised_phase(
    client, orga_user_token, review_user, event, slot, speaker
):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()
        team = review_user.teams.first()
        team.all_events = True
        team.save()
        slot.submission.speakers.add(speaker)
        slot.is_visible = True
        slot.schedule = event.current_schedule
        slot.save()

    from eventyay.base.models.auth_token import UserApiToken
    token = UserApiToken.objects.create(name='reviewer_token_slot', user=review_user)
    token.events.set([event])
    token.endpoints = {'slots': ['list', 'retrieve'], 'submissions': ['list', 'retrieve']}
    token.save()

    # Step 1: Reviewer searching for speaker name -> search_fields dynamically excludes speakers__fullname
    resp_rev = client.get(
        event.api_urls.slots + f'?search={speaker.fullname}',
        follow=True,
        headers={'Authorization': f'Token {token.token}'},
    )
    assert resp_rev.status_code == 200
    assert resp_rev.json()['count'] == 0

    # Step 2: Reviewer filtering by speaker ID -> rejected because speaker filter queryset is User.objects.none()
    resp_rev_filt = client.get(
        event.api_urls.slots + f'?speaker={speaker.pk}',
        follow=True,
        headers={'Authorization': f'Token {token.token}'},
    )
    assert resp_rev_filt.status_code == 400
    assert 'speaker' in resp_rev_filt.json()

    # Step 3: Reviewer searching by title -> matches slot
    resp_rev_title = client.get(
        event.api_urls.slots + f'?search={slot.submission.title}',
        follow=True,
        headers={'Authorization': f'Token {token.token}'},
    )
    assert resp_rev_title.status_code == 200
    assert resp_rev_title.json()['count'] >= 1
    assert resp_rev_title.json()['results'][0]['id'] == slot.id

    # Step 4: Organizer search for speaker name -> matches slot
    resp_orga = client.get(
        event.api_urls.slots + f'?search={speaker.fullname}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert resp_orga.status_code == 200
    assert resp_orga.json()['count'] >= 1
    assert resp_orga.json()['results'][0]['id'] == slot.id


@pytest.mark.django_db
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_schedule_detail_team_api_token_sees_hidden_slots_and_bypasses_cache(
    client, schedule, slot
):
    cache.clear()
    event = schedule.event
    assert schedule.version is not None

    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.schedule = schedule
        slot.is_visible = False
        slot.save()

        from eventyay.base.models import TeamAPIToken
        team = event.organizer.teams.first()
        team.all_events = True
        team.can_change_submissions = True
        team.can_change_event_settings = True
        team.save()
        team_token = TeamAPIToken.objects.create(team=team, name='TestTeamToken')

    resp_team = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers={'Authorization': f'Token {team_token.token}'},
    )
    assert resp_team.status_code == 200
    assert slot.pk in resp_team.json()['slots']

    resp_anon = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_anon.status_code == 200
    assert slot.pk not in resp_anon.json()['slots']

    # Cross-event / track limit isolation: if team does not have access to this event, token cannot see hidden slots
    with scope(event=event):
        team.all_events = False
        team.save()
        team.limit_events.clear()

    resp_unauth = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers={'Authorization': f'Token {team_token.token}'},
    )
    assert resp_unauth.status_code == 200
    assert slot.pk not in resp_unauth.json()['slots']


@pytest.mark.django_db
def test_schedule_serializer_slots_representation_expanded_vs_unexpanded(
    client, schedule, slot
):
    event = schedule.event
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.schedule = schedule
        slot.is_visible = True
        slot.save()

    resp_unexpanded = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_unexpanded.status_code == 200
    slots_unexpanded = resp_unexpanded.json()['slots']
    assert isinstance(slots_unexpanded, list)
    assert len(slots_unexpanded) >= 1
    assert all(isinstance(x, int) for x in slots_unexpanded)
    assert slot.pk in slots_unexpanded

    resp_expanded = client.get(f'{event.api_urls.schedules}{schedule.pk}/?expand=slots', follow=True)
    assert resp_expanded.status_code == 200
    slots_expanded = resp_expanded.json()['slots']
    assert isinstance(slots_expanded, list)
    assert len(slots_expanded) >= 1
    assert all(isinstance(x, dict) for x in slots_expanded)
    expanded_pks = [x['id'] for x in slots_expanded]
    assert slot.pk in expanded_pks


@pytest.mark.django_db
def test_talk_slot_filter_padded_submission_value_no_cache_collision(client, event, slot):
    from django.core.cache import cache
    from eventyay.base.services.stale_cache import talk_slots_filter_key

    cache.clear()
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.is_visible = True
        slot.save()
        code = slot.submission.code

    # 1. Warm cache with exact code -> 200
    resp_exact = client.get(f"{event.api_urls.slots}?submission={code}", follow=True)
    assert resp_exact.status_code == 200
    assert len(resp_exact.json()["results"]) == 1

    # 2. Padded submission code: ?submission=%20<code> -> must return 400 (not cached 200)
    resp_padded = client.get(f"{event.api_urls.slots}?submission=%20{code}", follow=True)
    assert resp_padded.status_code == 400

    # 3. Cache key distinction verification:
    class DummyReq:
        def __init__(self, val):
            self.query_params = {'submission': val}

    k1 = talk_slots_filter_key(DummyReq(code), ['submission'])
    k2 = talk_slots_filter_key(DummyReq(f' {code}'), ['submission'])
    assert k1 != k2


@pytest.mark.django_db
def test_cached_vs_uncached_json_response_equality(client, schedule, slot):
    from django.core.cache import cache

    event = schedule.event
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.schedule = schedule
        slot.is_visible = True
        slot.save()

    cache.clear()
    # Schedule detail: uncached (loader) then cached (stale_cache)
    resp_uncached_sched = client.get(f"{event.api_urls.schedules}{schedule.pk}/", follow=True)
    assert resp_uncached_sched.status_code == 200
    data_uncached_sched = resp_uncached_sched.json()

    resp_cached_sched = client.get(f"{event.api_urls.schedules}{schedule.pk}/", follow=True)
    assert resp_cached_sched.status_code == 200
    data_cached_sched = resp_cached_sched.json()
    assert data_cached_sched == data_uncached_sched

    # Talk slot list: uncached then cached
    cache.clear()
    resp_uncached_slots = client.get(event.api_urls.slots, follow=True)
    assert resp_uncached_slots.status_code == 200
    data_uncached_slots = resp_uncached_slots.json()

    resp_cached_slots = client.get(event.api_urls.slots, follow=True)
    assert resp_cached_slots.status_code == 200
    data_cached_slots = resp_cached_slots.json()
    assert data_cached_slots == data_uncached_slots


@pytest.mark.django_db
def test_talk_slot_filter_is_orga_parity(client, event, orga_user_token, slot):
    from django.contrib.auth.models import AnonymousUser
    from eventyay.api.filters.schedule import TalkSlotFilter, check_is_orga

    class MockReq:
        def __init__(self, user, ev, auth=None):
            self.user = user
            self.event = ev
            self.auth = auth
            self.query_params = {}

    req_orga = MockReq(orga_user_token.user, event)
    assert check_is_orga(req_orga, event) is True

    filt_orga = TalkSlotFilter(request=req_orga, event=event)
    assert filt_orga.is_orga is True

    req_anon = MockReq(AnonymousUser(), event)
    assert check_is_orga(req_anon, event) is False

    filt_anon = TalkSlotFilter(request=req_anon, event=event)
    assert filt_anon.is_orga is False


@pytest.mark.django_db
def test_is_orga_principal_matrix_invariants(
    client, event, schedule, slot, orga_user_token, review_user
):
    from django.core.cache import cache
    from eventyay.base.models import TeamAPIToken, Team

    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.schedule = schedule
        slot.is_visible = False  # Hidden slot!
        slot.save()

        # 1. Organizer user token (has orga_view_schedule)
        orga_headers = {'Authorization': f'Token {orga_user_token.token}'}

        # 2. Team token WITH schedule permissions
        team_with_perm = event.organizer.teams.create(
            name='TeamWithPerm',
            all_events=True,
            can_change_submissions=True,
            can_change_event_settings=True,
        )
        token_with_perm = TeamAPIToken.objects.create(team=team_with_perm, name='TokenWithPerm')
        token_with_headers = {'Authorization': f'Token {token_with_perm.token}'}

        # 3. Team token WITHOUT schedule permissions
        team_no_perm = event.organizer.teams.create(
            name='TeamNoPerm',
            all_events=True,
            can_change_submissions=False,
            can_change_event_settings=False,
        )
        token_no_perm = TeamAPIToken.objects.create(team=team_no_perm, name='TokenNoPerm')
        token_no_headers = {'Authorization': f'Token {token_no_perm.token}'}

        # 4. Reviewer user token (under anonymised phase -> cannot view WIP/hidden slots)
        event.active_review_phase.can_see_speaker_names = False
        event.active_review_phase.save()
        from eventyay.base.models.auth_token import UserApiToken
        reviewer_token = UserApiToken.objects.create(name='ReviewerToken', user=review_user)
        reviewer_token.events.set([event])
        reviewer_token.endpoints = {'schedules': ['list', 'retrieve'], 'slots': ['list', 'retrieve']}
        reviewer_token.save()
        reviewer_headers = {'Authorization': f'Token {reviewer_token.token}'}

    # 1. Anonymous user requests schedule -> hidden slot NOT visible, response cached
    cache.clear()
    resp_anon = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_anon.status_code == 200
    assert slot.pk not in resp_anon.json()['slots']

    # 2. Team token WITHOUT schedule permissions -> hidden slot NOT visible
    resp_token_no = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers=token_no_headers,
    )
    assert resp_token_no.status_code == 200
    assert slot.pk not in resp_token_no.json()['slots']

    # 3. Reviewer token -> hidden slot NOT visible
    resp_rev = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers=reviewer_headers,
    )
    assert resp_rev.status_code == 200
    assert slot.pk not in resp_rev.json()['slots']

    # 4. Organizer user -> hidden slot IS visible, bypasses cache
    resp_orga = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers=orga_headers,
    )
    assert resp_orga.status_code == 200
    assert slot.pk in resp_orga.json()['slots']

    # 5. Team token WITH schedule permissions -> hidden slot IS visible, bypasses cache
    resp_token_with = client.get(
        f'{event.api_urls.schedules}{schedule.pk}/',
        follow=True,
        headers=token_with_headers,
    )
    assert resp_token_with.status_code == 200
    assert slot.pk in resp_token_with.json()['slots']

    # Invariant Check: subsequent anonymous request must NOT receive hidden slot from cache
    resp_anon_post = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp_anon_post.status_code == 200
    assert slot.pk not in resp_anon_post.json()['slots']

    # WIP Schedule filtering:
    # Anonymous and unprivileged cannot filter by WIP version
    resp_anon_wip = client.get(f'{event.api_urls.slots}?schedule_version=wip', follow=True)
    assert resp_anon_wip.status_code == 200
    assert resp_anon_wip.json()['count'] == 0

    resp_token_no_wip = client.get(
        f'{event.api_urls.slots}?schedule_version=wip',
        follow=True,
        headers=token_no_headers,
    )
    assert resp_token_no_wip.status_code == 200
    assert resp_token_no_wip.json()['count'] == 0

    # Privileged principals CAN filter by WIP schedule version
    resp_orga_wip = client.get(
        f'{event.api_urls.slots}?schedule_version=wip',
        follow=True,
        headers=orga_headers,
    )
    assert resp_orga_wip.status_code == 200

    resp_token_with_wip = client.get(
        f'{event.api_urls.slots}?schedule_version=wip',
        follow=True,
        headers=token_with_headers,
    )
    assert resp_token_with_wip.status_code == 200


@pytest.mark.django_db
def test_schedule_detail_cache_schema_isolation(client, event, schedule):
    from django.core.cache import cache
    from eventyay.base.services.stale_cache import (
        SCHEDULE_DETAIL_CACHE_SCHEMA,
        get_schedule_cache_version,
        schedule_detail_cache_keys,
    )

    cache.clear()
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()

    version = get_schedule_cache_version(event.pk)
    # Construct legacy cache key (pre-schema bump: no ':s{SCHEMA}:' segment)
    legacy_hot_key = f'api:schedule:{event.pk}:v{version}:{schedule.pk}:public:all::hot'
    legacy_payload = {'payload': {'version': 'LEGACY_OBSOLETE_DATA', 'slots': []}, 'etag': 'legacy_etag'}
    cache.set(legacy_hot_key, legacy_payload, 300)

    # Verify that the new schedule_detail_cache_keys produces a schema-scoped key
    hot_key, _ = schedule_detail_cache_keys(event.pk, schedule.pk, '', 'public', 'all')
    assert f':s{SCHEDULE_DETAIL_CACHE_SCHEMA}:' in hot_key
    assert hot_key != legacy_hot_key

    # A client request under the current implementation must NOT return the legacy obsolete data
    resp = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp.status_code == 200
    assert resp.json().get('version') != 'LEGACY_OBSOLETE_DATA'
    assert resp.json().get('version') == schedule.version


@pytest.mark.django_db
def test_normal_user_and_token_permission_parity_event_settings_only(
    client, event, schedule, slot
):
    from django.core.cache import cache
    from eventyay.base.models import TeamAPIToken, User
    from eventyay.base.models.auth_token import UserApiToken

    cache.clear()
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()
        slot.schedule = schedule
        slot.is_visible = False  # Hidden slot
        slot.save()

        # 1. User with ONLY can_change_event_settings (no can_change_submissions)
        team_event_only = event.organizer.teams.create(
            name='TeamUserEventOnly',
            all_events=True,
            can_change_event_settings=True,
            can_change_submissions=False,
        )
        user_event_only = User.objects.create(email='usereventonly@example.com')
        team_event_only.members.add(user_event_only)
        token_user_event_only = UserApiToken.objects.create(name='TokenUserEventOnly', user=user_event_only)
        token_user_event_only.events.set([event])
        token_user_event_only.endpoints = {'schedules': ['list', 'retrieve'], 'slots': ['list', 'retrieve']}
        token_user_event_only.save()
        headers_user_event_only = {'Authorization': f'Token {token_user_event_only.token}'}

        # 2. Team token with ONLY can_change_event_settings (no can_change_submissions)
        team_token_event_only = event.organizer.teams.create(
            name='TeamTokenEventOnly',
            all_events=True,
            can_change_event_settings=True,
            can_change_submissions=False,
        )
        token_event_only = TeamAPIToken.objects.create(team=team_token_event_only, name='TokenEventOnly')
        headers_token_event_only = {'Authorization': f'Token {token_event_only.token}'}

        # 3. User with ONLY can_change_submissions (no can_change_event_settings)
        team_user_sub_only = event.organizer.teams.create(
            name='TeamUserSubOnly',
            all_events=True,
            can_change_event_settings=False,
            can_change_submissions=True,
        )
        user_sub_only = User.objects.create(email='usersubonly@example.com')
        team_user_sub_only.members.add(user_sub_only)
        token_user_sub_only = UserApiToken.objects.create(name='TokenUserSubOnly', user=user_sub_only)
        token_user_sub_only.events.set([event])
        token_user_sub_only.endpoints = {'schedules': ['list', 'retrieve'], 'slots': ['list', 'retrieve']}
        token_user_sub_only.save()
        headers_user_sub_only = {'Authorization': f'Token {token_user_sub_only.token}'}

        # 4. Team token with ONLY can_change_submissions (no can_change_event_settings)
        team_token_sub_only = event.organizer.teams.create(
            name='TeamTokenSubOnly',
            all_events=True,
            can_change_event_settings=False,
            can_change_submissions=True,
        )
        token_sub_only = TeamAPIToken.objects.create(team=team_token_sub_only, name='TokenSubOnly')
        headers_token_sub_only = {'Authorization': f'Token {token_sub_only.token}'}

        # Verify base.orga_view_schedule permission contract:
        assert user_event_only.has_perm('base.orga_view_schedule', event) is False
        assert user_sub_only.has_perm('base.orga_view_schedule', event) is True

    # Parity check 1: User with only can_change_event_settings does NOT see hidden slots
    resp1 = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True, headers=headers_user_event_only)
    assert resp1.status_code == 200
    assert slot.pk not in resp1.json()['slots']

    # Parity check 2: Team token with only can_change_event_settings does NOT see hidden slots
    resp2 = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True, headers=headers_token_event_only)
    assert resp2.status_code == 200
    assert slot.pk not in resp2.json()['slots']

    # Parity check 3: User with only can_change_submissions DOES see hidden slots
    resp3 = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True, headers=headers_user_sub_only)
    assert resp3.status_code == 200
    assert slot.pk in resp3.json()['slots']

    # Parity check 4: Team token with only can_change_submissions DOES see hidden slots
    resp4 = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True, headers=headers_token_sub_only)
    assert resp4.status_code == 200
    assert slot.pk in resp4.json()['slots']


from django.test.utils import override_settings

@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-schedule-cache-warm',
        }
    }
)
def test_schedule_cache_warm_then_request(client, event, schedule):
    from django.core.cache import cache
    from eventyay.base.services.stale_cache import (
        SCHEDULE_DETAIL_CACHE_SCHEMA,
        bump_schedule_cache_version,
        get_cached_schedule_detail,
        get_schedule_cache_version,
        schedule_detail_cache_keys,
    )

    cache.clear()
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save()

    # 1. Warm schedule cache with canonical helper
    loader_called = False
    def warm_loader():
        nonlocal loader_called
        loader_called = True
        return {'version': schedule.version, 'comment': 'PRE_WARMED_CACHE_PAYLOAD', 'slots': []}

    version = get_schedule_cache_version(event.pk)
    hot_key, stale_key = schedule_detail_cache_keys(event.pk, schedule.pk, '', 'public', 'all')
    expected_hot_prefix = f'api:schedule:{event.pk}:s{SCHEDULE_DETAIL_CACHE_SCHEMA}:v{version}:{schedule.pk}:public:all:'
    assert hot_key == f'{expected_hot_prefix}:hot'
    assert stale_key == f'{expected_hot_prefix}:stale'
    assert f':s{SCHEDULE_DETAIL_CACHE_SCHEMA}:' == ':s1:'

    data, etag = get_cached_schedule_detail(
        event.pk,
        schedule.pk,
        expand_key='',
        user_scope='public',
        locale_key='all',
        loader=warm_loader,
    )
    assert loader_called is True
    assert data['comment'] == 'PRE_WARMED_CACHE_PAYLOAD'

    # 2. Perform request-time client request
    resp = client.get(f'{event.api_urls.schedules}{schedule.pk}/', follow=True)
    assert resp.status_code == 200
    assert resp.json().get('comment') == 'PRE_WARMED_CACHE_PAYLOAD'
    assert resp.headers.get('ETag') == f'"{etag}"'

    # 3. Mutation check 1: Isolation across user scopes
    scope_loader_called = False
    def scope_loader():
        nonlocal scope_loader_called
        scope_loader_called = True
        return {'version': schedule.version, 'comment': 'TRACK_ISOLATED_PAYLOAD', 'slots': []}

    scoped_data, _ = get_cached_schedule_detail(
        event.pk,
        schedule.pk,
        expand_key='',
        user_scope='tracks:999',
        locale_key='all',
        loader=scope_loader,
    )
    assert scope_loader_called is True
    assert scoped_data['comment'] == 'TRACK_ISOLATED_PAYLOAD'
    scoped_hot, _ = schedule_detail_cache_keys(event.pk, schedule.pk, '', 'tracks:999', 'all')
    assert scoped_hot != hot_key

    # 4. Mutation check 2: Isolation across cache version bump
    bump_schedule_cache_version(event.pk)
    new_version = get_schedule_cache_version(event.pk)
    assert new_version != version
    bumped_hot, _ = schedule_detail_cache_keys(event.pk, schedule.pk, '', 'public', 'all')
    assert bumped_hot != hot_key
    assert cache.get(bumped_hot) is None
