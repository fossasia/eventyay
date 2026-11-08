"""
Tests for the password recovery link handling.
"""

import logging
from unittest import mock

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail as djmail
from django.test import RequestFactory, override_settings
from django.urls import reverse


def _send_reset_and_capture_logs(user, caplog):
    # The eventyay logger does not propagate to root, so attach caplog to it directly.
    eventyay_logger = logging.getLogger('eventyay')
    eventyay_logger.addHandler(caplog.handler)
    try:
        with (
            caplog.at_level(logging.DEBUG, logger='eventyay'),
            mock.patch.object(default_token_generator, 'make_token', return_value='synthetic-reset-token'),
        ):
            user.send_password_reset(RequestFactory().get('/'), sync_send=True)
    finally:
        eventyay_logger.removeHandler(caplog.handler)

    assert len(djmail.outbox) == 1
    assert 'synthetic-reset-token' in djmail.outbox[0].body
    return caplog.text


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_password_reset_token_is_not_logged_in_production(user, caplog):
    assert 'synthetic-reset-token' not in _send_reset_and_capture_logs(user, caplog)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_password_reset_link_is_logged_in_debug(user, caplog):
    assert 'synthetic-reset-token' in _send_reset_and_capture_logs(user, caplog)


@pytest.mark.django_db
class TestPasswordRecoverInvalidLink:
    """An unusable reset link sends the user back to the Lost password page."""

    def test_used_token_redirects_to_forgot(self, client, user):
        recover_url = '{}?id={}&token={}'.format(
            reverse('eventyay_common:auth.forgot.recover'), user.pk, default_token_generator.make_token(user)
        )
        response = client.post(recover_url, {'password': 'N3w-Passw0rd!X', 'password_repeat': 'N3w-Passw0rd!X'})
        assert response.status_code == 302
        assert response.url == reverse('auth.login')

        response = client.get(recover_url)
        assert response.status_code == 302
        assert response.url == reverse('eventyay_common:auth.forgot')

    def test_tampered_token_redirects_to_forgot(self, client, user):
        response = client.get(reverse('eventyay_common:auth.forgot.recover'), {'id': user.pk, 'token': 'tampered'})
        assert response.status_code == 302
        assert response.url == reverse('eventyay_common:auth.forgot')

    def test_unknown_user_redirects_to_forgot(self, client, user):
        token = default_token_generator.make_token(user)
        response = client.get(reverse('eventyay_common:auth.forgot.recover'), {'id': user.pk + 1000, 'token': token})
        assert response.status_code == 302
        assert response.url == reverse('eventyay_common:auth.forgot')

    def test_invalid_link_shows_message_on_forgot_page(self, client, user):
        response = client.get(
            reverse('eventyay_common:auth.forgot.recover'),
            {'id': user.pk, 'token': 'tampered'},
            follow=True,
        )
        assert response.status_code == 200
        assert response.redirect_chain[-1][0] == reverse('eventyay_common:auth.forgot')
        assert 'You clicked on an invalid link' in response.content.decode()
