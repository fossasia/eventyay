import pytest
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
@pytest.mark.parametrize('client_fixture', ['staff_client', 'organizer_client'])
def test_only_admins_can_manage_services(request, client_fixture, youtube):
    """Staff outside admin mode and organizers cannot change the registry."""
    client = request.getfixturevalue(client_fixture)

    client.post(reverse('eventyay_admin:admin.global.privacy.service.add'), service_data())
    client.post(
        reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': youtube.pk}),
        service_data(name='youtube', title='Changed'),
    )
    client.post(reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': youtube.pk}))

    assert list(ThirdPartyService.objects.values_list('name', 'title')) == [('youtube', 'YouTube')]
