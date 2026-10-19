import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.api.models import OAuthApplication


SAVED = 'Your changes have been saved.'
PASSWORD_CHANGED = 'Your password has been changed successfully.'
WRONG_PASSWORD = 'The current password you entered was not correct.'
PASSWORD_MISSING = 'Please enter your current password if you want to change your password.'
NO_CHANGES = 'No changes were made.'


def save_general(client, **data):
    url = reverse('eventyay_common:account.general')
    return client.post(url, {'fullname': 'Test User', 'locale': 'en', 'timezone': 'UTC', **data}, follow=True)


def page_messages(response):
    return [str(message) for message in response.context['messages']]


@pytest.fixture
def app(user):
    with scopes_disabled():
        return OAuthApplication.objects.create(
            user=user,
            name='Reporting tool',
            redirect_uris='https://example.org/callback',
            client_type='confidential',
            authorization_grant_type='authorization-code',
        )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_saving_general_settings_confirms_the_changes(authenticated_client, user):
    response = save_general(authenticated_client, fullname='Peter Miller')

    assert page_messages(response) == [SAVED]
    user.refresh_from_db()
    assert user.fullname == 'Peter Miller'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_changing_the_password_confirms_the_password_change(authenticated_client, user):
    response = save_general(
        authenticated_client, old_pw='testpass123', new_pw='N3w-Passw0rd!', new_pw_repeat='N3w-Passw0rd!'
    )

    assert page_messages(response) == [PASSWORD_CHANGED]
    user.refresh_from_db()
    assert user.check_password('N3w-Passw0rd!')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_changing_the_password_and_other_settings_confirms_both(authenticated_client, user):
    response = save_general(
        authenticated_client,
        fullname='Peter Miller',
        old_pw='testpass123',
        new_pw='N3w-Passw0rd!',
        new_pw_repeat='N3w-Passw0rd!',
    )

    assert page_messages(response) == [PASSWORD_CHANGED, SAVED]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('data', [{}, {'old_pw': 'testpass123'}], ids=['nothing', 'current-password-only'])
def test_saving_without_changes_says_nothing_was_changed(authenticated_client, user, data):
    response = save_general(authenticated_client, **data)

    assert page_messages(response) == [NO_CHANGES]
    user.refresh_from_db()
    assert user.check_password('testpass123')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_wrong_current_password_is_shown_next_to_the_field_only(authenticated_client, user):
    response = save_general(authenticated_client, old_pw='wrong', new_pw='N3w-Passw0rd!', new_pw_repeat='N3w-Passw0rd!')

    form = response.context['form']
    assert form.errors['old_pw'] == [WRONG_PASSWORD]
    assert not form.non_field_errors()
    assert page_messages(response) == ['Your changes could not be saved. See below for details.']
    user.refresh_from_db()
    assert user.check_password('testpass123')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_missing_current_password_is_shown_next_to_the_field(authenticated_client, user):
    response = save_general(authenticated_client, new_pw='N3w-Passw0rd!', new_pw_repeat='N3w-Passw0rd!')

    form = response.context['form']
    assert form.errors['old_pw'] == [PASSWORD_MISSING]
    assert not form.non_field_errors()
    user.refresh_from_db()
    assert user.check_password('testpass123')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_registering_an_oauth_application_confirms_it(authenticated_client, user):
    url = reverse('eventyay_common:account.oauth.own-app.register')
    response = authenticated_client.post(
        url, {'name': 'Reporting tool', 'redirect_uris': 'https://example.org/callback'}, follow=True
    )

    assert page_messages(response) == ['The application has been registered.']
    with scopes_disabled():
        assert OAuthApplication.objects.filter(user=user, name='Reporting tool').exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_invalid_oauth_application_shows_an_error(authenticated_client, user):
    url = reverse('eventyay_common:account.oauth.own-app.register')
    response = authenticated_client.post(url, {'name': '', 'redirect_uris': 'https://example.org/callback'})

    assert page_messages(response) == ['The application could not be registered. See below for details.']
    assert 'name' in response.context['form'].errors


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_updating_an_oauth_application_confirms_the_changes(authenticated_client, app):
    url = reverse('eventyay_common:account.oauth.own-app', kwargs={'pk': app.pk})
    data = {
        'name': 'Renamed tool',
        'client_id': app.client_id,
        'client_secret': app.client_secret,
        'redirect_uris': 'https://example.org/callback',
    }
    response = authenticated_client.post(url, data, follow=True)

    assert page_messages(response) == [SAVED]
    app.refresh_from_db()
    assert app.name == 'Renamed tool'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_deleting_an_oauth_application_confirms_it(authenticated_client, app):
    url = reverse('eventyay_common:account.oauth.own-app.delete', kwargs={'pk': app.pk})
    response = authenticated_client.post(url, follow=True)

    assert page_messages(response) == ['The application has been deleted.']
    app.refresh_from_db()
    assert not app.active


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_rolling_the_client_secret_confirms_it(authenticated_client, app):
    old_secret = app.client_secret
    url = reverse('eventyay_common:account.oauth.own-app.roll', kwargs={'pk': app.pk})
    response = authenticated_client.post(url, follow=True)

    assert page_messages(response) == ['A new client secret has been generated and is now effective.']
    app.refresh_from_db()
    assert app.client_secret != old_secret
