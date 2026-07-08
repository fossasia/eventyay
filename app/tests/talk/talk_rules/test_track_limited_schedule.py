import json

import pytest
from django_scopes import scope

from eventyay.base.models import TalkSlot


@pytest.mark.django_db
def test_track_limited_manager_api_slots_filtered(
    client,
    orga_user_token,
    orga_user,
    event,
    submission,
    other_submission,
    track,
    other_track,
    room,
):
    with scope(event=event):
        orga_user.teams.first().limit_tracks.add(track)
        submission.track = track
        submission.save()
        other_submission.track = other_track
        other_submission.save()
        schedule = event.wip_schedule
        TalkSlot.objects.create(
            schedule=schedule,
            room=room,
            submission=submission,
            start=event.datetime_from,
            end=event.datetime_from,
        )
        TalkSlot.objects.create(
            schedule=schedule,
            room=room,
            submission=other_submission,
            start=event.datetime_from,
            end=event.datetime_from,
        )

    response = client.get(
        event.api_urls.slots + f'?schedule={schedule.pk}',
        follow=True,
        headers={'Authorization': f'Token {orga_user_token.token}'},
    )
    assert response.status_code == 200, response.text
    content = json.loads(response.text)
    submission_ids = {slot['submission'] for slot in content['results'] if slot.get('submission')}
    assert submission.pk in submission_ids
    assert other_submission.pk not in submission_ids
