"""Tests for the Two-Factor Authentication (2FA) account settings pages.

Covers device deletion, toggle switch status, enable/disable workflows,
and confirmation dialog rendering.
"""

import base64
import time
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from django.template.loader import render_to_string
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from eventyay.base.models import User, WebAuthnDevice
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN
from eventyay.helpers.u2f import websafe_decode, websafe_encode


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


@pytest.mark.django_db
def test_2fa_regenerate_emergency_codes_logs_displayable_action(recent_login_client, user):
    """The account history must show a sentence, not the raw action type."""
    response = recent_login_client.post(reverse('eventyay_common:account.2fa.regenemergency'))

    assert response.status_code == 302
    entry = user.all_logentries.order_by('-datetime', '-id').first()
    assert entry.action_type == 'eventyay.user.settings.2fa.regenemergency'
    # LogEntry.display() falls back to returning action_type when nothing renders it.
    assert str(entry.display()) == 'Your two-factor emergency codes have been regenerated.'


def _start_webauthn_registration(client, user, seed_session=True):
    """Create an unconfirmed WebAuthn device and seed the session as the confirm page's GET does."""
    device = WebAuthnDevice.objects.create(user=user, name='Security key', confirmed=False)
    if seed_session:
        session = client.session
        session['webauthn_challenge'] = base64.b64encode(b'challenge').decode()
        session['webauthn_register_ukey'] = base64.b64encode(b'ukey').decode()
        session.save()
    url = reverse('eventyay_common:account.2fa.confirm.webauthn', kwargs={'device_id': device.pk})
    return device, url


def _verified_registration(credential_id=b'credential-id'):
    return MagicMock(credential_id=credential_id, credential_public_key=b'public-key', sign_count=0)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'seed_session',
    [
        True,  # credential rejected by the webauthn library
        False,  # expired session, no challenge to verify against
    ],
)
def test_webauthn_confirm_failed_verification_keeps_device_unconfirmed(recent_login_client, user, seed_session):
    """Failures the narrowed handler is meant to catch still redirect back to the confirmation page."""
    device, url = _start_webauthn_registration(recent_login_client, user, seed_session=seed_session)

    response = recent_login_client.post(url, {'token': '{}'})

    assert response.status_code == 302
    assert response.url == url
    device.refresh_from_db()
    assert device.confirmed is False


@pytest.mark.django_db
def test_webauthn_confirm_does_not_swallow_errors_after_device_is_saved(recent_login_client, user):
    """Once the device is saved, a failure must not redirect to the confirmation page.

    That page only loads unconfirmed devices, so the user was told registration failed
    and then got a 404, while the device was actually registered.
    """
    device, url = _start_webauthn_registration(recent_login_client, user)

    with (
        patch('webauthn.verify_registration_response', return_value=_verified_registration()),
        patch.object(User, 'send_security_notice', side_effect=RuntimeError('mail backend down')),
        pytest.raises(RuntimeError),
    ):
        recent_login_client.post(url, {'token': '{}'})

    device.refresh_from_db()
    assert device.confirmed is True


@pytest.mark.django_db
def test_webauthn_confirm_rejects_credential_already_registered(recent_login_client, user):
    """A credential id stored for another device must be detected as a duplicate."""
    other = User.objects.create_user(email='other@example.com', password='testpass123')
    WebAuthnDevice.objects.create(
        user=other, name='Existing key', confirmed=True, credential_id=websafe_encode(b'credential-id')
    )
    device, url = _start_webauthn_registration(recent_login_client, user)

    with patch('webauthn.verify_registration_response', return_value=_verified_registration(b'credential-id')):
        response = recent_login_client.post(url, {'token': '{}'})

    assert response.status_code == 302
    assert response.url == url
    device.refresh_from_db()
    assert device.confirmed is False


def test_websafe_encode_round_trips_bytes():
    """WebAuthn credential ids and keys are bytes; encoding them used to return None."""
    raw = b'\xfb\xef\xff\x01'  # needs padding and uses the URL-safe '-' and '_' characters
    encoded = websafe_encode(raw)

    assert encoded == '--__AQ'
    assert websafe_decode(encoded) == raw
