import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import TalkSlot


def enable_feedback(event):
    """Turn feedback on and let any logged-in user comment.

    The default ``feedback_who_can_comment`` value is ``attendees``, which
    requires a paid ticket. These tests only care about the feedback flow
    itself, so they use ``registered`` to authorise the attendee.
    """
    event.feature_flags['use_feedback'] = True
    event.feature_flags['feedback_who_can_comment'] = 'registered'
    event.save(update_fields=['feature_flags'])


@pytest.mark.django_db()
def test_can_create_feedback(past_slot, client, event, user):
    """An attendee (non-speaker) can leave feedback on the session page."""
    with scope(event=event):
        enable_feedback(event)
        assert past_slot.submission.speakers.count() == 1

    # Log in as an attendee (the `user` fixture), not a speaker
    client.force_login(user)

    response = client.post(past_slot.submission.urls.public, {'review': 'cool!', 'rating': 5}, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        feedback = past_slot.submission.feedback.first()
        assert feedback is not None
        assert feedback.review == 'cool!'
        assert feedback.author == user
        assert feedback.speaker == past_slot.submission.speakers.first()
        assert past_slot.submission.title in str(feedback)


@pytest.mark.django_db()
def test_can_create_feedback_for_multiple_speakers(past_slot, client, other_speaker, speaker, event, user):
    """An attendee can leave feedback on a session with multiple speakers."""
    with scope(event=event):
        enable_feedback(event)
        past_slot.submission.speakers.add(other_speaker)
        past_slot.submission.speakers.add(speaker)
        assert past_slot.submission.speakers.count() == 2

    # Log in as an attendee, not a speaker
    client.force_login(user)

    response = client.post(past_slot.submission.urls.public, {'review': 'cool!', 'rating': 5}, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        feedback = past_slot.submission.feedback.first()
        assert feedback is not None
        assert feedback.review == 'cool!'
        assert not feedback.speaker
        assert past_slot.submission.title in str(feedback)


@pytest.mark.django_db()
def test_cannot_create_feedback_before_talk(slot, client, event, user):
    """Feedback cannot be submitted before the talk has started."""
    _now = now()
    with scope(event=event):
        enable_feedback(event)
        TalkSlot.objects.filter(submission__event=slot.event).update(
            start=_now + dt.timedelta(minutes=30),
            end=_now + dt.timedelta(minutes=60),
        )
    client.force_login(user)
    response = client.post(slot.submission.urls.public, {'review': 'cool!', 'rating': 5}, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.feedback.count() == 0
        assert slot.submission.speakers.count() == 1


@pytest.mark.django_db()
def test_cannot_create_feedback_when_feedback_disabled(past_slot, client, event, user):
    """Verify feedback cannot be created when feedback is disabled by default."""
    with scope(event=event):
        assert event.get_feature_flag('use_feedback') is False
    client.force_login(user)
    response = client.post(past_slot.submission.urls.public, {'review': 'cool!', 'rating': 5}, follow=True)
    assert response.status_code == 200
    with scope(event=event):
        assert past_slot.submission.feedback.count() == 0


@pytest.mark.django_db()
def test_anonymous_cannot_create_feedback(past_slot, client, event):
    """Anonymous visitors cannot submit feedback through the session page."""
    with scope(event=event):
        enable_feedback(event)
    response = client.post(past_slot.submission.urls.public, {'review': 'cool!', 'rating': 5})
    assert response.status_code == 403
    with scope(event=event):
        assert past_slot.submission.feedback.count() == 0


@pytest.mark.django_db()
def test_can_see_feedback(django_assert_num_queries, feedback, client):
    """Speakers can view feedback on their session via the feedback URL."""
    feedback.talk.event.feature_flags['use_feedback'] = True
    feedback.talk.event.save(update_fields=['feature_flags'])
    client.force_login(feedback.talk.speakers.first())
    with django_assert_num_queries(17):
        response = client.get(feedback.talk.urls.feedback)
    assert response.status_code == 200
    assert feedback.review in response.text


@pytest.mark.django_db()
def test_non_speaker_redirected_from_feedback_url(past_slot, client, event, user):
    """Non-speakers visiting the old feedback URL are redirected to the session page."""
    with scope(event=event):
        enable_feedback(event)
    client.force_login(user)
    response = client.get(past_slot.submission.urls.feedback)
    assert response.status_code == 302
    assert response.url == past_slot.submission.urls.public + '#feedback'


@pytest.mark.django_db()
def test_anonymous_redirected_from_feedback_url(past_slot, client, event):
    """Anonymous visitors visiting the old feedback URL are redirected to the session page."""
    with scope(event=event):
        enable_feedback(event)
    response = client.get(past_slot.submission.urls.feedback)
    assert response.status_code == 302
    assert response.url == past_slot.submission.urls.public + '#feedback'


@pytest.mark.django_db()
def test_anonymous_post_to_feedback_returns_405(past_slot, client, event):
    """Anonymous POST to the old /feedback/ endpoint returns 405 and stores nothing."""
    with scope(event=event):
        enable_feedback(event)
    response = client.post(past_slot.submission.urls.feedback, {'review': 'cool!'})
    assert response.status_code == 405
    with scope(event=event):
        assert past_slot.submission.feedback.count() == 0
