import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import User
from eventyay.base.models.privacy import (
    ConsentCategory,
    ConsentProvider,
    DPAStatus,
    ThirdPartyService,
)
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.templatetags.privacy_consent import build_consent_config
from eventyay.control.forms.global_settings import PrivacySettingsForm


@pytest.fixture
def admin_client(client):
    user = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.fixture
def service():
    return ThirdPartyService.objects.create(
        name='google-analytics',
        title='Google Analytics',
        provider='Google',
        category=ConsentCategory.ANALYTICS,
    )


def _service_data(**overrides):
    data = {
        'title': 'Matomo',
        'name': 'matomo',
        'provider': 'InnoCraft',
        'purpose': 'Visitor statistics',
        'category': ConsentCategory.ANALYTICS,
        'enabled': 'on',
        'privacy_policy_url': 'https://matomo.org/privacy-policy/',
        'cookie_names': '_pk_id\n_pk_ses',
        'data_processed': 'IP address, page views',
        'region': 'EU',
        'dpa_status': DPAStatus.SIGNED,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_admin_can_add_a_service(admin_client):
    response = admin_client.post(reverse('eventyay_admin:admin.global.privacy.service.add'), _service_data())

    assert response.status_code == 302
    service = ThirdPartyService.objects.get(name='matomo')
    assert service.category == ConsentCategory.ANALYTICS
    assert service.region == 'EU'
    assert service.dpa_status == DPAStatus.SIGNED
    assert service.cookie_name_list == ['_pk_id', '_pk_ses']


@pytest.mark.django_db
def test_a_service_needs_a_consent_category(admin_client):
    """Without a category the service never reaches the banner, so it would never be blocked."""
    response = admin_client.post(
        reverse('eventyay_admin:admin.global.privacy.service.add'),
        _service_data(category=''),
    )

    assert response.status_code == 200
    assert 'category' in response.context['form'].errors
    assert not ThirdPartyService.objects.filter(name='matomo').exists()


@pytest.mark.django_db
def test_admin_can_edit_a_service(admin_client, service):
    response = admin_client.post(
        reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': service.pk}),
        _service_data(title='GA4', name='google-analytics', category=ConsentCategory.MARKETING, enabled=''),
    )

    assert response.status_code == 302
    service.refresh_from_db()
    assert service.title == 'GA4'
    assert service.category == ConsentCategory.MARKETING
    assert service.enabled is False


@pytest.mark.django_db
def test_service_without_a_category_can_still_be_edited(admin_client):
    """Older services may have no category; the admin must be able to open and fix them."""
    legacy = ThirdPartyService.objects.create(name='legacy', title='Legacy', category='')

    response = admin_client.post(
        reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': legacy.pk}),
        _service_data(title='Legacy tracker', name='legacy', category=''),
    )

    assert response.status_code == 302
    legacy.refresh_from_db()
    assert legacy.title == 'Legacy tracker'


@pytest.mark.django_db
def test_identifier_cannot_be_renamed_after_creation(admin_client, service):
    """Blocked scripts are matched on the identifier, so renaming would stop blocking them."""
    admin_client.post(
        reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': service.pk}),
        _service_data(name='renamed'),
    )

    service.refresh_from_db()
    assert service.name == 'google-analytics'


@pytest.mark.django_db
def test_admin_can_delete_a_service(admin_client, service):
    response = admin_client.post(
        reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': service.pk})
    )

    assert response.status_code == 302
    assert not ThirdPartyService.objects.filter(pk=service.pk).exists()


@pytest.mark.django_db
def test_added_service_reaches_the_consent_banner(admin_client):
    gs = GlobalSettingsObject()
    gs.settings.set('privacy_consent_provider', ConsentProvider.KLARO)
    gs.settings.set('privacy_cookie_policy_url', 'https://example.org/cookies')
    gs.settings.set('privacy_category_analytics_enabled', True)

    admin_client.post(reverse('eventyay_admin:admin.global.privacy.service.add'), _service_data())

    names = [service['name'] for service in build_consent_config()['services']]
    assert 'matomo' in names


@pytest.mark.django_db
@pytest.mark.parametrize(
    'url_name, needs_pk',
    [
        ('admin.global.privacy.service.add', False),
        ('admin.global.privacy.service.edit', True),
        ('admin.global.privacy.service.delete', True),
    ],
)
def test_service_pages_need_an_admin_session(client, service, url_name, needs_pk):
    user = User.objects.create_user('orga@example.com', 'dummy')
    client.force_login(user)
    kwargs = {'pk': service.pk} if needs_pk else {}

    response = client.post(reverse(f'eventyay_admin:{url_name}', kwargs=kwargs), _service_data())

    assert response.status_code == 403
    assert ThirdPartyService.objects.count() == 1


def _privacy_settings_data(**overrides):
    data = {
        'privacy_consent_provider': ConsentProvider.EXTERNAL,
        'privacy_cmp_provider_name': 'Example CMP',
        'privacy_cmp_script_url': 'https://cdn.example.org/cmp.js',
        'privacy_policy_url': 'https://example.org/privacy',
        'privacy_cookie_policy_url': 'https://example.org/cookies',
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_external_cmp_script_must_use_https():
    """An http:// script is blocked on https:// pages, leaving the site with no consent manager."""
    form = PrivacySettingsForm(data=_privacy_settings_data(privacy_cmp_script_url='http://cdn.example.org/cmp.js'))

    assert not form.is_valid()
    assert form.errors['privacy_cmp_script_url'] == ['The script URL must use HTTPS.']


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['privacy_policy_url', 'privacy_cookie_policy_url'])
def test_policy_links_must_be_urls(field):
    form = PrivacySettingsForm(data=_privacy_settings_data(**{field: 'not a url'}))

    assert not form.is_valid()
    assert form.errors[field] == ['Enter a valid URL.']


@pytest.mark.django_db
def test_valid_privacy_settings_are_accepted():
    form = PrivacySettingsForm(data=_privacy_settings_data())

    assert form.is_valid(), form.errors
