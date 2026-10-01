from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.api.models import OAuthAccessToken, OAuthApplication
from eventyay.base.models import Organizer, Team, User


REDIRECT_URI = 'https://example.org/callback'


@pytest.fixture
def user():
    user = User.objects.create_user(email='oauth_authorize@example.org', password='password123')
    organizer = Organizer.objects.create(name='Demo Org', slug='demoorg')
    team = Team.objects.create(organizer=organizer, name='Admins', all_events=True)
    team.members.add(user)
    return user


@pytest.fixture
def application(user):
    return OAuthApplication.objects.create(
        name='Badge Printer',
        client_type='confidential',
        authorization_grant_type='authorization-code',
        redirect_uris=REDIRECT_URI,
        user=user,
    )


@pytest.fixture
def token(user, application):
    return OAuthAccessToken.objects.create(
        user=user,
        application=application,
        token='access-token-value',
        expires=now() + timedelta(hours=24),
        scope='read',
    )


def authorize_url(application):
    params = {
        'client_id': application.client_id,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': 'read',
        'approval_prompt': 'force',
        'state': 'xyz',
    }
    return f'{reverse("api-v1:authorize")}?{urlencode(params)}'


@pytest.mark.django_db
def test_authorize_page_shows_consent_form(client, user, application):
    """Used to fail with TemplateDoesNotExist for pretixcontrol/auth/base.html."""
    client.force_login(user)

    response = client.get(authorize_url(application))

    assert response.status_code == 200
    assert 'Badge Printer' in response.content.decode()
    assert 'Demo Org' in response.content.decode()


@pytest.mark.django_db
def test_authorizing_redirects_back_with_a_code(client, user, application):
    client.force_login(user)
    organizer = Organizer.objects.get(slug='demoorg')

    response = client.post(
        authorize_url(application),
        data={
            'client_id': application.client_id,
            'response_type': 'code',
            'redirect_uri': REDIRECT_URI,
            'scope': 'read',
            'state': 'xyz',
            'organizers': [organizer.pk],
            'allow': 'Authorize',
        },
    )

    assert response.status_code == 302
    location = urlsplit(response['Location'])
    assert location.netloc == 'example.org'
    assert 'code' in parse_qs(location.query)


@pytest.mark.django_db
def test_authorized_apps_page_links_to_revoke(client, user, token):
    """Used to fail with NoReverseMatch for account.oauth.own-app.revoke."""
    client.force_login(user)

    response = client.get(reverse('eventyay_common:account.oauth.authorized-apps'))

    assert response.status_code == 200
    revoke_url = reverse('eventyay_common:account.oauth.authorized-app.revoke', kwargs={'pk': token.pk})
    assert revoke_url in response.content.decode()


@pytest.mark.django_db
def test_revoke_page_names_the_application(client, user, token):
    client.force_login(user)

    response = client.get(reverse('eventyay_common:account.oauth.authorized-app.revoke', kwargs={'pk': token.pk}))

    content = response.content.decode()
    assert response.status_code == 200
    assert 'for the application Badge Printer?' in content
    assert '%(application)s' not in content


@pytest.mark.django_db
def test_revoking_deletes_the_token(client, user, token):
    client.force_login(user)

    response = client.post(reverse('eventyay_common:account.oauth.authorized-app.revoke', kwargs={'pk': token.pk}))

    assert response.status_code == 302
    assert not OAuthAccessToken.objects.filter(pk=token.pk).exists()
