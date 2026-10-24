import pytest
from django.db.models import ProtectedError
from django.test import override_settings
from django.urls import reverse

from eventyay.base.models.auth import StaffSession
from eventyay.base.models.privacy import ThirdPartyService


@pytest.fixture
def admin_client(db, staff_client, staff_user):
    """Staff client in admin mode, which the global settings require."""
    session = staff_client.session
    session.save()
    StaffSession.objects.create(user=staff_user, session_key=session.session_key, comment='test')
    return staff_client


@pytest.fixture
def youtube(db):
    return ThirdPartyService.objects.create(name='youtube', title='YouTube', provider='Google', category='embed')


def service_data(**overrides):
    return {
        'title': 'Google Analytics',
        'name': 'google-analytics',
        'provider': 'Google',
        'purpose': 'Visitor statistics',
        'category': 'analytics',
        'enabled': 'on',
        'privacy_policy_url': 'https://policies.google.com/privacy',
        'cookie_names': '_ga\n^_ga_',
        **overrides,
    }


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_privacy_page_lets_admins_manage_services(admin_client, youtube):
    response = admin_client.get(reverse('eventyay_admin:admin.global.privacy'))

    assert response.status_code == 200
    html = response.content.decode()
    assert reverse('eventyay_admin:admin.global.privacy.service.add') in html
    assert reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': youtube.pk}) in html
    assert reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': youtube.pk}) in html


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_admin_can_add_a_service(admin_client):
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(), follow=True)

    assert response.redirect_chain[-1][0] == reverse('eventyay_admin:admin.global.privacy')
    assert [str(m) for m in response.context['messages']] == ['The service has been added.']
    service = ThirdPartyService.objects.get(name='google-analytics')
    assert service.title == 'Google Analytics'
    assert service.category == 'analytics'
    assert service.enabled
    assert service.cookie_name_list == ['_ga', '^_ga_']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_service_needs_a_category(admin_client):
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(category=''))

    assert response.status_code == 200
    assert 'category' in response.context['form'].errors
    assert not ThirdPartyService.objects.exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_service_identifier_must_be_unique(admin_client, youtube):
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(name='youtube'))

    assert response.status_code == 200
    assert 'name' in response.context['form'].errors
    assert ThirdPartyService.objects.count() == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_admin_can_assign_a_category_to_an_unclassified_service(admin_client):
    service = ThirdPartyService.objects.create(name='hubspot', title='HubSpot')
    url = reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': service.pk})
    response = admin_client.post(url, service_data(name='hubspot', title='HubSpot', category='marketing'), follow=True)

    assert [str(m) for m in response.context['messages']] == ['Your changes have been saved.']
    service.refresh_from_db()
    assert service.category == 'marketing'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_admin_can_remove_a_service(admin_client, youtube):
    url = reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': youtube.pk})
    response = admin_client.post(url, follow=True)

    assert [str(m) for m in response.context['messages']] == ['The service has been removed.']
    assert not ThirdPartyService.objects.filter(pk=youtube.pk).exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('name', ['Google-Analytics', 'google analytics', 'google.analytics'])
def test_service_identifier_is_lowercase_letters_digits_and_dashes(admin_client, name):
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(name=name))

    assert response.status_code == 200
    assert 'name' in response.context['form'].errors
    assert not ThirdPartyService.objects.exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_service_identifier_cannot_be_changed(admin_client, youtube):
    """Embeds and stored consent refer to the service by its name."""
    url = reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': youtube.pk})
    assert admin_client.get(url).context['form'].fields['name'].disabled

    admin_client.post(url, service_data(name='renamed', title='YouTube'))

    youtube.refresh_from_db()
    assert youtube.name == 'youtube'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_service_with_an_older_identifier_can_still_be_edited(admin_client):
    """A name saved before the format was enforced does not block other changes."""
    service = ThirdPartyService.objects.create(name='Matomo', title='Matomo', category='analytics')
    url = reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': service.pk})
    response = admin_client.post(url, service_data(title='Matomo Analytics'), follow=True)

    assert [str(m) for m in response.context['messages']] == ['Your changes have been saved.']
    service.refresh_from_db()
    assert (service.name, service.title) == ('Matomo', 'Matomo Analytics')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_service_form_explains_the_cookie_name_format(admin_client):
    response = admin_client.get(reverse('eventyay_admin:admin.global.privacy.service.add'))

    assert 'One cookie name per line' in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_comma_separated_cookie_names_are_split(admin_client):
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    admin_client.post(url, service_data(cookie_names='  _ga, _gid ,_gat\n\n ^_ga_.{1,3} \n'))

    service = ThirdPartyService.objects.get(name='google-analytics')
    assert service.cookie_name_list == ['_ga', '_gid', '_gat', '^_ga_.{1,3}']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    'pattern', ['^_ga_(', '^_ga_[', '^*_ga'], ids=['unterminated-group', 'unterminated-set', 'nothing-to-repeat']
)
def test_invalid_cookie_pattern_is_rejected(admin_client, pattern):
    """Klaro compiles ^ lines in the browser, where an invalid one stops it from clearing cookies."""
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(cookie_names='_ga\n' + pattern))

    assert response.status_code == 200
    errors = response.context['form'].errors['cookie_names']
    assert len(errors) == 1
    assert errors[0].startswith(f'"{pattern}" is not a valid regular expression: ')
    assert not ThirdPartyService.objects.exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    ('line', 'pattern'),
    [('_ga, ^_ga_(', '^_ga_('), ('_ga ^(?P<cookie>_ga_)', '^(?P<cookie>_ga_)')],
    ids=['after-a-comma', 'after-a-space'],
)
def test_invalid_cookie_pattern_split_off_a_line_is_rejected(admin_client, line, pattern):
    """A pattern after a cookie name on the same line is saved as its own entry, so it is checked too."""
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(cookie_names=line))

    assert response.status_code == 200
    errors = response.context['form'].errors['cookie_names']
    assert len(errors) == 1
    assert errors[0].startswith(f'"{pattern}" is not a valid regular expression: ')
    assert not ThirdPartyService.objects.exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    ('pattern', 'syntax'),
    [
        ('^(?P<cookie>_ga_)', '(?P'),
        ('^_ga_(?#comment)', '(?#'),
        ('^(?i:_ga_)', '(?i'),
        ('^(?>_ga_)', '(?>'),
        ('^(_ga)?(?(1)_x|_y)', '(?('),
        ('^_ga_.*+', '*+'),
        ('^_ga_.{1,3}+', '}+'),
        ('^(?<=_)?ga', ')?'),
        ('^[]_ga]', '[]'),
    ],
)
def test_cookie_pattern_only_python_accepts_is_rejected(admin_client, pattern, syntax):
    """These compile with Python's re, but new RegExp() throws on them in the browser."""
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    response = admin_client.post(url, service_data(cookie_names=pattern))

    assert response.status_code == 200
    assert response.context['form'].errors['cookie_names'] == [
        f'"{pattern}" is not a valid regular expression: browsers do not support "{syntax}".'
    ]
    assert not ThirdPartyService.objects.exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_cookie_patterns_browsers_accept_are_kept(admin_client):
    patterns = ['^_ga_.{1,3}', '^(?:_ga|_gid)$', '^_ga(?=_)', '^(?<=_)ga', '^[*+]_x', '^_pk_.*?$']
    url = reverse('eventyay_admin:admin.global.privacy.service.add')
    admin_client.post(url, service_data(cookie_names='\n'.join(patterns)))

    assert ThirdPartyService.objects.get(name='google-analytics').cookie_name_list == patterns


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_service_form_explains_strictly_necessary(admin_client):
    """Services in that category run without consent, so the form says what it is for."""
    response = admin_client.get(reverse('eventyay_admin:admin.global.privacy.service.add'))

    assert 'only for services the site cannot work without' in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_protected_service_is_not_removed(admin_client, youtube, monkeypatch):
    """When other data still refers to the service, the admin is told so instead of getting an error page."""

    def protected(self, *args, **kwargs):
        raise ProtectedError('referenced', {self})

    monkeypatch.setattr(ThirdPartyService, 'delete', protected)
    url = reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': youtube.pk})
    response = admin_client.post(url, follow=True)

    assert response.redirect_chain[-1][0] == reverse('eventyay_admin:admin.global.privacy')
    assert [str(m) for m in response.context['messages']] == [
        'The service could not be removed as other data (e.g. created by plug-ins) still refers to it.'
    ]
    assert ThirdPartyService.objects.filter(pk=youtube.pk).exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('method', ['get', 'post'])
@pytest.mark.parametrize(
    ('client_fixture', 'redirect_to'),
    [
        ('client', 'auth.login'),
        ('staff_client', 'control:user.sudo'),
        ('organizer_client', None),
    ],
    ids=['anonymous', 'staff-outside-admin-mode', 'organizer'],
)
def test_only_admins_can_manage_services(request, client_fixture, redirect_to, method, youtube):
    """Visitors are sent to log in, staff to enter admin mode, and organizers are refused."""
    client = request.getfixturevalue(client_fixture)
    pages = [
        (reverse('eventyay_admin:admin.global.privacy.service.add'), service_data()),
        (
            reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': youtube.pk}),
            service_data(name='youtube', title='Changed'),
        ),
        (reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': youtube.pk}), {}),
    ]

    for url, data in pages:
        response = client.post(url, data) if method == 'post' else client.get(url)
        if redirect_to:
            assert response.status_code == 302
            assert response.url == reverse(redirect_to) + '?next=' + url
        else:
            assert response.status_code == 403

    assert list(ThirdPartyService.objects.values_list('name', 'title')) == [('youtube', 'YouTube')]
