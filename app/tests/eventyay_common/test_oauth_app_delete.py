from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.api.models import OAuthAccessToken, OAuthApplication, OAuthRefreshToken
from eventyay.base.models import LogEntry, User


def make_application(user):
    return OAuthApplication.objects.create(
        name='Demo App',
        client_type='confidential',
        authorization_grant_type='authorization-code',
        redirect_uris='https://example.org/callback',
        user=user,
    )


def delete_url(app):
    return reverse('eventyay_common:account.oauth.own-app.delete', kwargs={'pk': app.pk})


@pytest.mark.django_db
def test_deleting_an_application_removes_it(client):
    user = User.objects.create_user(email='oauth_delete@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    response = client.post(delete_url(app))

    assert response.status_code == 302
    assert not OAuthApplication.objects.filter(pk=app.pk).exists()


@pytest.mark.django_db
def test_deleting_an_application_referenced_by_a_logentry_keeps_the_entry(client):
    """Used to fail with ProtectedError, because LogEntry.oauth_application was PROTECT."""
    user = User.objects.create_user(email='oauth_logged@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    user.log_action('eventyay.user.settings.changed', user=user)
    entry = LogEntry.objects.filter(action_type='eventyay.user.settings.changed').first()
    entry.oauth_application = app
    entry.save(update_fields=['oauth_application'])

    response = client.post(delete_url(app))

    assert response.status_code == 302
    assert not OAuthApplication.objects.filter(pk=app.pk).exists()
    entry.refresh_from_db()
    assert entry.oauth_application_id is None


@pytest.mark.django_db
def test_deleting_an_application_removes_its_tokens(client):
    user = User.objects.create_user(email='oauth_tokens@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)
    access_token = OAuthAccessToken.objects.create(
        user=user,
        application=app,
        token='access-token-value',
        expires=now() + timedelta(hours=24),
        scope='read',
    )
    OAuthRefreshToken.objects.create(
        user=user,
        application=app,
        token='refresh-token-value',
        access_token=access_token,
    )

    client.post(delete_url(app))

    assert not OAuthAccessToken.objects.filter(application_id=app.pk).exists()
    assert not OAuthRefreshToken.objects.filter(application_id=app.pk).exists()


@pytest.mark.django_db
def test_users_cannot_delete_someone_elses_application(client):
    owner = User.objects.create_user(email='oauth_owner@example.org', password='password123')
    other = User.objects.create_user(email='oauth_other@example.org', password='password123')
    app = make_application(owner)
    client.force_login(other)

    response = client.post(delete_url(app))

    assert response.status_code == 404
    assert OAuthApplication.objects.filter(pk=app.pk).exists()
