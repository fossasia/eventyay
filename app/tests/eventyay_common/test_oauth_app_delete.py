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
def test_deleting_an_application_keeps_the_row_and_clears_active(client):
    user = User.objects.create_user(email='oauth_delete@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    response = client.post(delete_url(app))

    assert response.status_code == 302
    app.refresh_from_db()
    assert app.active is False
    assert not app.is_usable(None)


@pytest.mark.django_db
def test_deleting_an_application_referenced_by_a_logentry_keeps_the_reference(client):
    """LogEntry.oauth_application is PROTECT, so a hard delete would raise ProtectedError."""
    user = User.objects.create_user(email='oauth_logged@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    user.log_action('eventyay.user.settings.changed', user=user)
    entry = LogEntry.objects.filter(action_type='eventyay.user.settings.changed').first()
    entry.oauth_application = app
    entry.save(update_fields=['oauth_application'])

    response = client.post(delete_url(app))

    assert response.status_code == 302
    entry.refresh_from_db()
    assert entry.oauth_application_id == app.pk


@pytest.mark.django_db
def test_deleting_an_application_revokes_its_tokens(client):
    """Bearer validation ignores the active flag, so the tokens have to be revoked."""
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
    refresh_token = OAuthRefreshToken.objects.create(
        user=user,
        application=app,
        token='refresh-token-value',
        access_token=access_token,
    )

    client.post(delete_url(app))

    access_token.refresh_from_db()
    refresh_token.refresh_from_db()
    assert not access_token.is_valid(['read'])
    assert refresh_token.revoked is not None
    assert refresh_token.access_token_id is None


@pytest.mark.django_db
def test_deleted_application_is_hidden_from_the_list(client):
    user = User.objects.create_user(email='oauth_hidden@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    client.post(delete_url(app))

    response = client.get(reverse('eventyay_common:account.oauth.own-apps'))
    assert response.status_code == 200
    assert 'Demo App' not in response.content.decode('utf-8')


@pytest.mark.django_db
def test_users_cannot_delete_someone_elses_application(client):
    owner = User.objects.create_user(email='oauth_owner@example.org', password='password123')
    other = User.objects.create_user(email='oauth_other@example.org', password='password123')
    app = make_application(owner)
    client.force_login(other)

    response = client.post(delete_url(app))

    assert response.status_code == 404
    app.refresh_from_db()
    assert app.active is True
