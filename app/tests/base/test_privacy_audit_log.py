import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import LogEntry, User
from eventyay.base.models.privacy import ConsentCategory, ConsentProvider, ThirdPartyService
from eventyay.base.services.privacy_audit import PRIVACY_ACTION_PREFIX
from eventyay.base.settings import GlobalSettingsObject


@pytest.fixture
def admin(client):
    # The banner can't be enabled without a Cookie Policy, so every form post
    # below sends one. Store it up front so it isn't logged as a change.
    GlobalSettingsObject().settings.set('privacy_cookie_policy_url', 'https://example.org/cookies')
    user = User.objects.create_user('admin@example.com', 'dummy', is_staff=True)
    client.force_login(user)
    user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return user


def _privacy_log():
    return list(
        LogEntry.objects.filter(action_type__startswith=PRIVACY_ACTION_PREFIX).order_by('pk')
    )


def _settings_data(**overrides):
    data = {
        'privacy_consent_provider': ConsentProvider.DISABLED,
        'privacy_cmp_provider_name': '',
        'privacy_cmp_script_url': '',
        'privacy_policy_url': '',
        'privacy_cookie_policy_url': 'https://example.org/cookies',
    }
    data.update(overrides)
    return data


def _service_data(**overrides):
    data = {
        'title': 'Matomo',
        'name': 'matomo',
        'category': ConsentCategory.ANALYTICS,
        'enabled': 'on',
        'dpa_status': 'not_required',
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_changing_the_consent_provider_is_logged(client, admin):
    client.post(reverse('eventyay_admin:admin.global.privacy'), _settings_data(privacy_consent_provider='klaro'))

    [entry] = _privacy_log()
    assert entry.action_type == 'eventyay.privacy.provider.changed'
    assert entry.user == admin
    assert entry.parsed_data == {'old': 'disabled', 'new': 'klaro'}
    assert 'klaro' in str(entry.display())


@pytest.mark.django_db
def test_turning_a_category_on_is_logged(client, admin):
    client.post(
        reverse('eventyay_admin:admin.global.privacy'),
        _settings_data(privacy_category_analytics_enabled='on'),
    )

    [entry] = _privacy_log()
    assert entry.action_type == 'eventyay.privacy.category.enabled'
    assert entry.parsed_data == {'category': 'analytics'}


@pytest.mark.django_db
def test_external_cmp_changes_are_logged_with_old_and_new_values(client, admin):
    client.post(
        reverse('eventyay_admin:admin.global.privacy'),
        _settings_data(
            privacy_consent_provider='external',
            privacy_cmp_script_url='https://cmp.example.org/loader.js',
        ),
    )

    actions = [entry.action_type for entry in _privacy_log()]
    assert actions == ['eventyay.privacy.provider.changed', 'eventyay.privacy.cmp.changed']
    changes = _privacy_log()[1].parsed_data['changes']
    assert changes['privacy_cmp_script_url'] == {'old': '', 'new': 'https://cmp.example.org/loader.js'}


@pytest.mark.django_db
def test_saving_without_changes_logs_nothing(client, admin):
    """Unset settings read back as None but save as '', which is not a change."""
    client.post(reverse('eventyay_admin:admin.global.privacy'), _settings_data())

    assert _privacy_log() == []


@pytest.mark.django_db
def test_service_lifecycle_is_logged(client, admin):
    client.post(reverse('eventyay_admin:admin.global.privacy.service.add'), _service_data())
    service = ThirdPartyService.objects.get(name='matomo')
    edit_url = reverse('eventyay_admin:admin.global.privacy.service.edit', kwargs={'pk': service.pk})

    client.post(edit_url, _service_data(region='EU'))
    client.post(edit_url, _service_data(region='EU', enabled=''))
    client.post(reverse('eventyay_admin:admin.global.privacy.service.delete', kwargs={'pk': service.pk}))

    entries = _privacy_log()
    assert [entry.action_type for entry in entries] == [
        'eventyay.privacy.service.added',
        'eventyay.privacy.service.changed',
        'eventyay.privacy.service.disabled',
        'eventyay.privacy.service.deleted',
    ]
    assert entries[1].parsed_data['changes'] == {'region': {'old': '', 'new': 'EU'}}
    assert all(entry.user == admin for entry in entries)


@pytest.mark.django_db
def test_audit_log_page_lists_privacy_changes(client, admin):
    client.post(reverse('eventyay_admin:admin.global.privacy'), _settings_data(privacy_consent_provider='klaro'))

    response = client.get(reverse('eventyay_admin:admin.global.privacy.audit'))

    assert response.status_code == 200
    assert response.context['entries'][0].action_type == 'eventyay.privacy.provider.changed'
    assert 'admin@example.com' in response.content.decode()


@pytest.mark.django_db
def test_audit_log_needs_an_admin_session(client):
    user = User.objects.create_user('orga@example.com', 'dummy')
    client.force_login(user)

    response = client.get(reverse('eventyay_admin:admin.global.privacy.audit'))

    assert response.status_code == 403
