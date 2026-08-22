import pytest
from django.urls import reverse

from eventyay.base.models import Feedback

@pytest.mark.django_db
def test_feedback_list_public(orga_client, event, talk, feedback):
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = orga_client.get(url + f'?talk={talk.code}')
    assert response.status_code == 200
    assert len(response.data['results']) == 1
    assert response.data['results'][0]['review'] == feedback.review

@pytest.mark.django_db
def test_feedback_create(client, event, talk, user):
    client.force_login(user)
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = client.post(
        url,
        {
            'talk': talk.code,
            'review': 'Great talk!',
            'is_public': True,
        },
    )
    assert response.status_code == 201
    assert Feedback.objects.count() == 1
    assert Feedback.objects.first().review == 'Great talk!'
    assert Feedback.objects.first().author == user

@pytest.mark.django_db
def test_feedback_create_unauthenticated(client, event, talk):
    url = reverse('api:feedback-list', kwargs={'event': event.slug})
    response = client.post(
        url,
        {
            'talk': talk.code,
            'review': 'Great talk!',
            'is_public': True,
        },
    )
    assert response.status_code == 403
