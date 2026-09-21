import pytest
from django.urls import reverse

from eventyay.api.models import OAuthApplication
from eventyay.base.models import LogEntry, User


def make_application(user):
    return OAuthApplication.objects.create(
        name='Demo App',
        client_type='confidential',
        authorization_grant_type='authorization-code',
        redirect_uris='https://example.org/callback',
        user=user,
        active=True,
    )


@pytest.mark.django_db
def test_disabling_an_application_keeps_the_row_and_clears_active(client):
    user = User.objects.create_user(email='oauth_disable@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    response = client.post(reverse('eventyay_common:account.oauth.own-app.disable', kwargs={'pk': app.pk}))

    assert response.status_code == 302
    app.refresh_from_db()
    assert app.active is False
    assert not app.is_usable(None)


@pytest.mark.django_db
def test_disabling_an_application_referenced_by_a_logentry_does_not_error(client):
    """LogEntry.oauth_application is on_delete=PROTECT, so a hard delete raises."""
    user = User.objects.create_user(email='oauth_protected@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    user.log_action('eventyay.user.settings.changed', user=user)
    entry = LogEntry.objects.filter(action_type='eventyay.user.settings.changed').first()
    entry.oauth_application = app
    entry.save(update_fields=['oauth_application'])

    response = client.post(reverse('eventyay_common:account.oauth.own-app.disable', kwargs={'pk': app.pk}))

    assert response.status_code == 302
    app.refresh_from_db()
    assert app.active is False
    entry.refresh_from_db()
    assert entry.oauth_application_id == app.pk


@pytest.mark.django_db
def test_disabled_application_is_hidden_from_the_list(client):
    user = User.objects.create_user(email='oauth_hidden@example.org', password='password123')
    client.force_login(user)
    app = make_application(user)

    client.post(reverse('eventyay_common:account.oauth.own-app.disable', kwargs={'pk': app.pk}))

    response = client.get(reverse('eventyay_common:account.oauth.own-apps'))
    assert response.status_code == 200
    assert 'Demo App' not in response.content.decode('utf-8')
