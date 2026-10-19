import pytest
from django.urls import reverse
from django.utils.http import urlencode


DASHBOARD = '/common/'
SAFE_NEXT = '/common/organizers/'
URL_NAMES = ['eventyay_common:auth.forgot', 'eventyay_common:auth.forgot.recover']


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', URL_NAMES)
@pytest.mark.parametrize('next_url', ['https://example.org/fake-login', '//example.org/x'])
def test_authenticated_external_next_requires_confirmation(authenticated_client, url_name, next_url):
    """An off-site `next` never causes a silent external redirect."""
    response = authenticated_client.get(reverse(url_name), {'next': next_url})
    assert response.status_code == 302
    destination = 'http:' + next_url if next_url.startswith('//') else next_url
    assert response['Location'] == reverse('eventyay_common:external-link') + '?' + urlencode({'next': destination})


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', URL_NAMES)
@pytest.mark.parametrize('next_url', ['javascript:alert(1)', r'/\\example.org/', 'https://user@example.org/'])
def test_authenticated_unsafe_next_falls_back_to_dashboard(authenticated_client, url_name, next_url):
    response = authenticated_client.get(reverse(url_name), {'next': next_url})
    assert response.status_code == 302
    assert response['Location'] == DASHBOARD


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', URL_NAMES)
def test_authenticated_safe_next_is_honored(authenticated_client, url_name):
    """A logged-in user with a relative `next` is still sent there."""
    response = authenticated_client.get(reverse(url_name), {'next': SAFE_NEXT})
    assert response.status_code == 302
    assert response['Location'] == SAFE_NEXT


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', URL_NAMES)
def test_authenticated_without_next_goes_to_dashboard(authenticated_client, url_name):
    """A logged-in user without `next` is sent to the dashboard."""
    response = authenticated_client.get(reverse(url_name))
    assert response.status_code == 302
    assert response['Location'] == DASHBOARD


@pytest.mark.django_db
def test_anonymous_forgot_renders_form(client):
    """Anonymous visitors still get the form, even with an off-site `next`."""
    response = client.get(reverse('eventyay_common:auth.forgot'), {'next': 'https://example.org/x'})
    assert response.status_code == 200
    assert 'email' in response.context['form'].fields
