"""
Tests for API endpoints.
"""

import pytest
from django_scopes import scope

from eventyay.api.serializers.feedback import FeedbackSerializer
from eventyay.base.models import Feedback, Submission, SubmissionType, User


@pytest.mark.django_db
class TestAPIEndpoints:
    """Test API v1 endpoints."""

    def test_api_root_returns_401_without_auth(self, client):
        """Test that API root requires authentication."""
        response = client.get('/api/v1/')
        # Should require authentication
        assert response.status_code in [401, 403, 404]

    def test_api_docs_accessible(self, client):
        """Test that API documentation is accessible."""
        schema_response = client.get('/api/v1/schema/', HTTP_ACCEPT='application/json')
        swagger_response = client.get('/api/v1/docs/')
        swagger_script_response = client.get('/api/v1/docs/?script=')
        redoc_response = client.get('/api/v1/redoc/')

        assert schema_response.status_code == 200
        assert schema_response.json()['openapi'] == '3.0.3'
        assert swagger_response.status_code == 200
        assert swagger_script_response.status_code == 200
        assert swagger_script_response['Content-Type'].startswith('application/javascript')
        assert redoc_response.status_code == 200

    def test_api_organizers_requires_auth(self, client):
        """Test that organizers API requires authentication."""
        response = client.get('/api/v1/organizers/')
        assert response.status_code in [401, 403]

    def test_api_organizers_with_auth(self, authenticated_client):
        """Test that organizers API works with authentication."""
        response = authenticated_client.get('/api/v1/organizers/')
        # Should return list (might be empty) or forbidden based on permissions
        assert response.status_code in [200, 403]


@pytest.mark.django_db
class TestWebhooksAPI:
    """Test webhook-related API endpoints."""

    def test_webhook_endpoint_exists(self, client, organizer, event):
        """Test webhook endpoint pattern exists."""
        # Webhooks are typically POST endpoints
        url = f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/webhooks/'
        response = client.get(url)
        # Should require auth
        assert response.status_code in [401, 403, 404]


@pytest.fixture
def feedback_thread(event):
    author = User.objects.create_user(email='feedback-author@example.com')
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        submission = Submission.objects.create(event=event, title='Feedback privacy', submission_type=submission_type)
        parent = Feedback.objects.create(talk=submission, author=author, review='Public comment')
        public_reply = Feedback.objects.create(talk=submission, parent=parent, author=author, review='Public reply')
        private_reply = Feedback.objects.create(
            talk=submission, parent=parent, author=author, review='Private reply', is_public=False
        )
        for status in ('pending', 'hidden', 'deleted'):
            Feedback.objects.create(talk=submission, parent=parent, author=author, review=status, status=status)
    return parent, public_reply, private_reply


@pytest.mark.django_db
@pytest.mark.parametrize('endpoint', ['list', 'detail'])
@pytest.mark.parametrize('role', ['unrelated', 'author', 'speaker', 'organizer'])
def test_nested_replies_respect_feedback_permissions(
    authenticated_client, event, user, team, feedback_thread, endpoint, role
):
    parent, public_reply, private_reply = feedback_thread
    with scope(event=event):
        if role == 'author':
            private_reply.author = user
            private_reply.save(update_fields=['author'])
        elif role == 'speaker':
            parent.talk.speakers.add(user)
        elif role == 'organizer':
            team.can_change_submissions = True
            team.save(update_fields=['can_change_submissions'])

    url = f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/feedback/'
    response = authenticated_client.get(url if endpoint == 'list' else f'{url}{parent.pk}/')
    assert response.status_code == 200
    feedback = response.json()['results'][0] if endpoint == 'list' else response.json()
    expected_ids = [public_reply.pk, private_reply.pk] if role == 'organizer' else [public_reply.pk]
    assert [reply['id'] for reply in feedback['replies']] == expected_ids
    if role == 'organizer':
        assert feedback['replies'][1]['review'] == private_reply.review
        assert feedback['replies'][1]['author'] is None
    else:
        assert authenticated_client.get(f'{url}{private_reply.pk}/').status_code == 404
        assert private_reply.review not in response.content.decode()


@pytest.mark.django_db
def test_feedback_serializer_without_request_excludes_private_replies(event, feedback_thread):
    parent, public_reply, _ = feedback_thread
    with scope(event=event):
        data = FeedbackSerializer(parent).data
    assert [reply['id'] for reply in data['replies']] == [public_reply.pk]
