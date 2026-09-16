import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import TalkSlot


@pytest.mark.django_db()
def test_can_create_feedback(django_assert_num_queries, past_slot, client, event, user):
    """An attendee (non-speaker) can leave feedback on the session page."""
    with scope(event=event):
        assert past_slot.submission.speakers.count() == 1

    # Log in as an attendee (the `user` fixture), not a speaker
    client.force_login(user)

    response = client.post(
        past_slot.submission.urls.public, {"review": "cool!", "rating": 5}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        feedback = past_slot.submission.feedback.first()
        assert feedback is not None
        assert feedback.review == "cool!"
        assert past_slot.submission.title in str(feedback)


@pytest.mark.django_db()
def test_can_create_feedback_for_multiple_speakers(
    django_assert_num_queries, past_slot, client, other_speaker, speaker, event, user
):
    """An attendee can leave feedback on a session with multiple speakers."""
    with scope(event=event):
        past_slot.submission.speakers.add(other_speaker)
        past_slot.submission.speakers.add(speaker)
        assert past_slot.submission.speakers.count() == 2

    # Log in as an attendee, not a speaker
    client.force_login(user)

    response = client.post(
        past_slot.submission.urls.public, {"review": "cool!", "rating": 5}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        feedback = past_slot.submission.feedback.first()
        assert feedback is not None
        assert feedback.review == "cool!"
        assert past_slot.submission.title in str(feedback)


@pytest.mark.django_db()
def test_cannot_create_feedback_before_talk(
    django_assert_num_queries, slot, client, event, user
):
    """Feedback cannot be submitted before the talk has started."""
    _now = now()
    with scope(event=event):
        TalkSlot.objects.filter(submission__event=slot.event).update(
            start=_now + dt.timedelta(minutes=30),
            end=_now + dt.timedelta(minutes=60),
        )
    client.force_login(user)
    response = client.post(
        slot.submission.urls.public, {"review": "cool!", "rating": 5}, follow=True
    )
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.feedback.count() == 0
        assert slot.submission.speakers.count() == 1


@pytest.mark.django_db()
def test_can_see_feedback(django_assert_num_queries, feedback, client):
    """Speakers can view feedback on their session via the feedback URL."""
    client.force_login(feedback.talk.speakers.first())
    with django_assert_num_queries(17):
        response = client.get(feedback.talk.urls.feedback)
    assert response.status_code == 200
    assert feedback.review in response.text


@pytest.mark.django_db()
def test_non_speaker_redirected_from_feedback_url(past_slot, client, user):
    """Non-speakers visiting the old feedback URL are redirected to the session page."""
    client.force_login(user)
    response = client.get(past_slot.submission.urls.feedback)
    assert response.status_code == 302
    assert response.url == past_slot.submission.urls.public + '#feedback'


@pytest.mark.django_db()
def test_anonymous_redirected_from_feedback_url(past_slot, client):
    """Anonymous visitors visiting the old feedback URL are redirected to the session page."""
    response = client.get(past_slot.submission.urls.feedback, follow=True)
    assert response.status_code == 200


@pytest.mark.django_db()
def test_anonymous_post_to_feedback_returns_405(client, past_slot):
    """Anonymous POST to the old /feedback/ endpoint returns 405 and stores nothing."""
    response = client.post(past_slot.submission.urls.feedback, {"review": "cool!"})
    assert response.status_code == 405
    with scope(event=past_slot.submission.event):
        assert past_slot.submission.feedback.count() == 0
