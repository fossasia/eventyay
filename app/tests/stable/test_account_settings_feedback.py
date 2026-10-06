"""
Tests for the success and error messages shown on the account settings pages.
"""
import pytest

from django.contrib.messages import get_messages
from django.urls import reverse

from eventyay.api.models import OAuthApplication


def message_texts(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def application_data(application, **extra):
    data = {
        'name': application.name,
        'client_id': application.client_id,
        'client_secret': application.client_secret,
        'redirect_uris': application.redirect_uris,
    }
    data.update(extra)
    return data


def general_settings_data(**extra):
    data = {'fullname': 'Test User', 'locale': 'en', 'timezone': 'UTC'}
    data.update(extra)
    return data


@pytest.fixture
def application(user):
    return OAuthApplication.objects.create(
        name='Demo App',
        client_type='confidential',
        authorization_grant_type='authorization-code',
        redirect_uris='https://example.org/callback',
        user=user,
    )


@pytest.mark.django_db
class TestGeneralSettingsFeedback:
    def test_password_change_shows_specific_confirmation(self, client, user):
        client.force_login(user)
        response = client.post(
            reverse('eventyay_common:account.general'),
            general_settings_data(old_pw='testpass123', new_pw='N3w-Passw0rd!X', new_pw_repeat='N3w-Passw0rd!X'),
        )
        assert response.status_code == 302
        assert message_texts(response) == ['Your password has been changed successfully.']
        user.refresh_from_db()
        assert user.check_password('N3w-Passw0rd!X')

    def test_other_changes_show_generic_confirmation(self, client, user):
        client.force_login(user)
        response = client.post(reverse('eventyay_common:account.general'), general_settings_data(fullname='Renamed'))
        assert response.status_code == 302
        assert message_texts(response) == ['Your changes have been saved.']

    def test_wrong_current_password_is_only_reported_on_the_field(self, client, user):
        client.force_login(user)
        response = client.post(
            reverse('eventyay_common:account.general'),
            general_settings_data(old_pw='not-my-password', new_pw='N3w-Passw0rd!X', new_pw_repeat='N3w-Passw0rd!X'),
        )
        assert response.status_code == 200
        form = response.context['form']
        assert form.errors['old_pw'] == ['The current password you entered was not correct.']
        assert form.non_field_errors() == []
        assert message_texts(response) == ['Your changes could not be saved. See below for details.']
        user.refresh_from_db()
        assert user.check_password('testpass123')

    def test_missing_current_password_is_still_reported(self, client, user):
        client.force_login(user)
        response = client.post(
            reverse('eventyay_common:account.general'),
            general_settings_data(new_pw='N3w-Passw0rd!X', new_pw_repeat='N3w-Passw0rd!X'),
        )
        assert response.status_code == 200
        assert response.context['form'].non_field_errors() == [
            'Please enter your current password if you want to change your password.'
        ]


@pytest.mark.django_db
class TestOAuthApplicationFeedback:
    def test_register_shows_confirmation(self, client, user):
        client.force_login(user)
        response = client.post(
            reverse('eventyay_common:account.oauth.own-app.register'),
            {'name': 'New App', 'redirect_uris': 'https://example.org/callback'},
        )
        assert response.status_code == 302
        assert OAuthApplication.objects.filter(user=user, name='New App').exists()
        assert message_texts(response) == ['The application has been registered.']

    def test_register_with_invalid_data_shows_error(self, client, user):
        client.force_login(user)
        response = client.post(reverse('eventyay_common:account.oauth.own-app.register'), {'name': ''})
        assert response.status_code == 200
        assert response.context['form'].errors
        assert message_texts(response) == ['The application could not be registered. See below for details.']

    def test_update_shows_confirmation(self, client, user, application):
        client.force_login(user)
        response = client.post(
            reverse('eventyay_common:account.oauth.own-app', kwargs={'pk': application.pk}),
            application_data(application, name='Renamed App'),
        )
        assert response.status_code == 302
        application.refresh_from_db()
        assert application.name == 'Renamed App'
        assert message_texts(response) == ['Your changes have been saved.']

    def test_update_with_invalid_data_shows_error(self, client, user, application):
        client.force_login(user)
        response = client.post(
            reverse('eventyay_common:account.oauth.own-app', kwargs={'pk': application.pk}),
            application_data(application, name=''),
        )
        assert response.status_code == 200
        application.refresh_from_db()
        assert application.name == 'Demo App'
        assert message_texts(response) == ['Your changes could not be saved. See below for details.']

    def test_delete_shows_confirmation(self, client, user, application):
        client.force_login(user)
        response = client.post(reverse('eventyay_common:account.oauth.own-app.delete', kwargs={'pk': application.pk}))
        assert response.status_code == 302
        assert message_texts(response) == ['The application has been deleted.']
