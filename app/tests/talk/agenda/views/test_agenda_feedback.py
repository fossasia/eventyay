import datetime as dt

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import TalkSlot


@pytest.mark.django_db()
def test_can_create_feedback(django_assert_num_queries, past_slot, client, event):
    with scope(event=event):
        assert past_slot.submission.speakers.count() == 1
    
    # Log in as an attendee to leave feedback on the session page
    client.force_login(past_slot.submission.speakers.first()) # Assuming a logged-in user, but ideally an attendee
    # We just need any logged-in user to post to the public page
    
    with django_assert_num_queries(45):
        # Post to the public session page instead of the old feedback URL
        response = client.post(
            past_slot.submission.urls.public, {"review": "cool!", "rating": 5}, follow=True
        )
    assert response.status_code == 200
    with scope(event=event):
        assert past_slot.submission.feedback.first().review == "cool!"
        assert (
            past_slot.submission.feedback.first().speaker
            == past_slot.submission.speakers.first()
        )
        assert past_slot.submission.title in str(past_slot.submission.feedback.first())


@pytest.mark.django_db()
def test_can_create_feedback_for_multiple_speakers(
    django_assert_num_queries, past_slot, client, other_speaker, speaker, event
):
    with scope(event=event):
        past_slot.submission.speakers.add(other_speaker)
        past_slot.submission.speakers.add(speaker)
        assert past_slot.submission.speakers.count() == 2
        
    client.force_login(speaker)
    
    with django_assert_num_queries(44):
        response = client.post(
            past_slot.submission.urls.public, {"review": "cool!", "rating": 5}, follow=True
        )
    assert response.status_code == 200
    with scope(event=event):
        assert past_slot.submission.feedback.first().review == "cool!"
        assert not past_slot.submission.feedback.first().speaker
        assert past_slot.submission.title in str(past_slot.submission.feedback.first())


@pytest.mark.django_db()
def test_cannot_create_feedback_before_talk(
    django_assert_num_queries, slot, client, event
):
    _now = now()
    with scope(event=event):
        TalkSlot.objects.filter(submission__event=slot.event).update(
            start=_now + dt.timedelta(minutes=30),
            end=_now + dt.timedelta(minutes=60),
        )
    client.force_login(slot.submission.speakers.first())
    with django_assert_num_queries(14):
        response = client.post(
            slot.submission.urls.public, {"review": "cool!", "rating": 5}, follow=True
        )
    assert response.status_code == 200
    with scope(event=event):
        assert slot.submission.feedback.count() == 0
        assert slot.submission.speakers.count() == 1


@pytest.mark.django_db()
def test_can_see_feedback(django_assert_num_queries, feedback, client):
    client.force_login(feedback.talk.speakers.first())
    with django_assert_num_queries(17):
        response = client.get(feedback.talk.urls.feedback)
    assert response.status_code == 200
    assert feedback.review in response.text


@pytest.mark.django_db()
def test_can_see_feedback_form(django_assert_num_queries, past_slot, client):
    # This should now redirect to the public page
    with django_assert_num_queries(13):
        response = client.get(past_slot.submission.urls.feedback, follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[0][0] == past_slot.submission.urls.public + '#feedback'


@pytest.mark.django_db()
def test_cannot_see_feedback_form_before_talk(django_assert_num_queries, slot, client):
    # This should now redirect to the public page
    with django_assert_num_queries(15):
        response = client.get(slot.submission.urls.feedback, follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[0][0] == slot.submission.urls.public + '#feedback'


@pytest.mark.django_db()
def test_anonymous_post_to_feedback_returns_405(client, past_slot):
    response = client.post(past_slot.submission.urls.feedback, {"review": "cool!"})
    assert response.status_code == 405
    assert past_slot.submission.feedback.count() == 0
