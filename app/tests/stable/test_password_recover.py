"""
Tests for the password recovery link handling.
"""
import pytest

from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse


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
