import pytest
from django.urls import reverse


DASHBOARD = '/common/'
SAFE_NEXT = '/common/organizers/'
URL_NAMES = ['eventyay_common:auth.forgot', 'eventyay_common:auth.forgot.recover']


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', URL_NAMES)
@pytest.mark.parametrize('next_url', ['https://example.org/fake-login', '//example.org/x'])
def test_authenticated_external_next_falls_back_to_dashboard(authenticated_client, url_name, next_url):
    """A logged-in user with an off-site `next` is sent to the dashboard."""
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
