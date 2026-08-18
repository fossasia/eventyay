"""Tests for the Two-Factor Authentication (2FA) account settings pages.

Covers device deletion, toggle switch status, enable/disable workflows,
and confirmation dialog rendering.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from django.template.loader import render_to_string
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from eventyay.common.consts import KEY_LAST_FORCE_LOGIN


@pytest.fixture
def recent_login_client(authenticated_client):
    """authenticated_client with KEY_LAST_FORCE_LOGIN seeded, satisfying RecentAuthenticationRequiredMixin."""
    session = authenticated_client.session
    session[KEY_LAST_FORCE_LOGIN] = int(time.time())
    session.save()
    return authenticated_client


def test_2fa_delete_template_rendering_and_urls(rf):
    """Template must not NoReverseMatch or show legacy branding."""
    request = rf.get('/account/2fa/totp/1/delete')
    request.user = MagicMock(is_authenticated=True, is_anonymous=False, is_administrator=False)
    request.LANGUAGE_CODE = 'en'
    request.session = {}

    class DummyDevice:
        name = 'Test Authenticator Device'
        pk = 1

    context = {'request': request, 'device': DummyDevice()}
    with (
        patch('eventyay.common.context_processors.GlobalSettings'),
        patch('eventyay.common.context_processors.add_events', return_value={}),
        patch('eventyay.orga.context_processors.orga_events', return_value={}),
        patch('eventyay.common.context_processors.system_information', return_value={}),
        patch('eventyay.presale.context._default_context', return_value={}),
    ):
        rendered_html = render_to_string('eventyay_common/account/2fa-delete.html', context, request=request)

    soup = BeautifulSoup(rendered_html, 'html.parser')
    heading = soup.find('h1')
    assert heading.get_text(strip=True) == 'Delete a two-factor authentication device'

    form = soup.select_one('form.form-horizontal')
    confirm_paragraph = form.find('p')
    assert 'Test Authenticator Device' in confirm_paragraph.get_text()

    branding_paragraph = form.select('p')[1]
    branding_text = branding_paragraph.get_text(strip=True)
    assert 'pretix' not in branding_text
    assert 'Eventyay' in branding_text

    cancel_link = form.select_one('a.btn-cancel')
    assert cancel_link is not None
    assert cancel_link['href'] == reverse('eventyay_common:account.2fa')


@pytest.mark.django_db
def test_2fa_delete_get_renders_for_real_device(recent_login_client, user):
    """Full-stack check: the real delete URL returns 200 with the correct device name and cancel link."""
    device = TOTPDevice.objects.create(user=user, confirmed=True, name='My Authenticator')
    url = reverse('eventyay_common:account.2fa.delete', kwargs={'devicetype': 'totp', 'device_id': device.pk})
    response = recent_login_client.get(url)

    assert response.status_code == 200
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    form = soup.select_one('form.form-horizontal')
    confirm_paragraph = form.find('p')
    assert 'My Authenticator' in confirm_paragraph.get_text()
    cancel_link = form.select_one('a.btn-cancel')
    assert cancel_link['href'] == reverse('eventyay_common:account.2fa')


@pytest.mark.django_db
def test_2fa_delete_post_removes_device_and_disables_2fa_when_last_device(recent_login_client, user):
    """Deleting the only remaining device removes it, disables require_2fa, and redirects to 2FA settings."""
    device = TOTPDevice.objects.create(user=user, confirmed=True, name='My Authenticator')
    user.require_2fa = True
    user.save()
    url = reverse('eventyay_common:account.2fa.delete', kwargs={'devicetype': 'totp', 'device_id': device.pk})
    response = recent_login_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse('eventyay_common:account.2fa')
    assert not TOTPDevice.objects.filter(pk=device.pk).exists()
    user.refresh_from_db()
    assert user.require_2fa is False


@pytest.mark.django_db
def test_2fa_main_settings_renders_disabled_toggle_when_no_devices(recent_login_client, user):
    """When no 2FA devices exist and 2FA is disabled, the toggle switch is disabled with guidance."""
    user.require_2fa = False
    user.save()
    url = reverse('eventyay_common:account.2fa')
    response = recent_login_client.get(url)

    assert response.status_code == 200
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    toggle = soup.select_one('.toggle-switch')
    assert toggle is not None
    assert toggle.has_attr('disabled')
    assert 'active' not in toggle.get('class', [])
    assert 'Two-factor authentication is currently disabled' in soup.get_text()
    assert 'To enable it, you need to configure at least one device below.' in soup.get_text()


@pytest.mark.django_db
def test_2fa_main_settings_renders_active_toggle_and_modal_when_enabled(recent_login_client, user):
    """When a device exists and 2FA is enabled, the toggle switch is active and triggers the confirm modal."""
    TOTPDevice.objects.create(user=user, confirmed=True, name='Authenticator App')
    user.require_2fa = True
    user.save()
    url = reverse('eventyay_common:account.2fa')
    response = recent_login_client.get(url)

    assert response.status_code == 200
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    toggle = soup.select_one('.toggle-switch')
    assert toggle is not None
    assert 'active' in toggle.get('class', [])
    assert toggle.get('data-toggle') == 'modal'
    assert toggle.get('data-target') == '#disable-2fa-modal'
    assert soup.find(id='disable-2fa-modal') is not None
    assert 'Two-factor authentication is currently enabled' in soup.get_text()


@pytest.mark.django_db
def test_2fa_main_settings_renders_enable_form_when_devices_exist(recent_login_client, user):
    """When a device exists and 2FA is disabled, the toggle switch submits the enable form."""
    TOTPDevice.objects.create(user=user, confirmed=True, name='Authenticator App')
    user.require_2fa = False
    user.save()
    url = reverse('eventyay_common:account.2fa')
    response = recent_login_client.get(url)

    assert response.status_code == 200
    soup = BeautifulSoup(response.content.decode(), 'html.parser')
    form = soup.select_one('form.inline-block-form')
    assert form is not None
    assert form['action'] == reverse('eventyay_common:account.2fa.enable')
    toggle = form.select_one('button.toggle-switch')
    assert toggle is not None
    assert 'active' not in toggle.get('class', [])
    assert not toggle.has_attr('disabled')
    assert 'Two-factor authentication is currently disabled' in soup.get_text()


@pytest.mark.django_db
def test_2fa_enable_view_post(recent_login_client, user):
    """Posting to 2FA enable activates require_2fa for the user and redirects to settings."""
    TOTPDevice.objects.create(user=user, confirmed=True, name='Authenticator App')
    user.require_2fa = False
    user.save()
    url = reverse('eventyay_common:account.2fa.enable')
    response = recent_login_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse('eventyay_common:account.2fa')
    user.refresh_from_db()
    assert user.require_2fa is True


@pytest.mark.django_db
def test_2fa_disable_view_post(recent_login_client, user):
    """Posting to 2FA disable deactivates require_2fa for the user and redirects to settings."""
    TOTPDevice.objects.create(user=user, confirmed=True, name='Authenticator App')
    user.require_2fa = True
    user.save()
    url = reverse('eventyay_common:account.2fa.disable')
    response = recent_login_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse('eventyay_common:account.2fa')
    user.refresh_from_db()
    assert user.require_2fa is False
