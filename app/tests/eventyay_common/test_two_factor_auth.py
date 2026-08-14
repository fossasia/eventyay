"""Tests for the 2FA device delete page.

Issue: #4906 - 2fa-delete.html reversed a nonexistent url name (typo:
'eventay_common' instead of 'eventyay_common') and referred to "pretix"
instead of "Eventyay", causing a NoReverseMatch / incorrect branding.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from eventyay.common.consts import KEY_LAST_FORCE_LOGIN


def test_2fa_delete_template_rendering_and_urls(rf):
    """Template must not NoReverseMatch or show 'pretix' branding."""
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
    assert 'Delete a two-factor authentication device' in rendered_html
    assert 'Test Authenticator Device' in rendered_html
    assert reverse('eventyay_common:account.2fa') in rendered_html
    assert 'log in to pretix' not in rendered_html
    assert 'log in to Eventyay' in rendered_html


@pytest.mark.django_db
def test_2fa_delete_get_renders_for_real_device(authenticated_client, user):
    """Full-stack check: the real delete URL returns 200 with device name and a working cancel link."""
    device = TOTPDevice.objects.create(user=user, confirmed=True, name='My Authenticator')
    session = authenticated_client.session
    session[KEY_LAST_FORCE_LOGIN] = int(time.time())
    session.save()
    url = reverse('eventyay_common:account.2fa.delete', kwargs={'devicetype': 'totp', 'device_id': device.pk})
    response = authenticated_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'My Authenticator' in content
    assert reverse('eventyay_common:account.2fa') in content


@pytest.mark.django_db
def test_2fa_delete_post_removes_device_and_disables_2fa_when_last_device(authenticated_client, user):
    """Deleting the only remaining device removes it, disables require_2fa, and redirects to 2FA settings."""
    device = TOTPDevice.objects.create(user=user, confirmed=True, name='My Authenticator')
    user.require_2fa = True
    user.save()
    session = authenticated_client.session
    session[KEY_LAST_FORCE_LOGIN] = int(time.time())
    session.save()
    url = reverse('eventyay_common:account.2fa.delete', kwargs={'devicetype': 'totp', 'device_id': device.pk})
    response = authenticated_client.post(url)
    assert response.status_code == 302
    assert response.url == reverse('eventyay_common:account.2fa')
    assert not TOTPDevice.objects.filter(pk=device.pk).exists()
    user.refresh_from_db()
    assert user.require_2fa is False
