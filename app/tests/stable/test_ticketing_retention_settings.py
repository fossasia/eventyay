import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.settings import GlobalSettingsObject


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    staff_user.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    return client


@pytest.mark.django_db
def test_ticketing_retention_settings(staff_client):
    url = reverse('eventyay_admin:admin.global.ticketing')
    page = staff_client.get(url)
    assert page.status_code == 200
    old_url = reverse('eventyay_admin:admin.global.ticketing.retention')
    assert staff_client.get(old_url).url == url + '#tab-data-retention'
    defaults = page.context['form'].initial
    assert defaults['ticketing_retention_manual_min_days'] == 14
    assert defaults['ticketing_retention_periods'] == '30, 60, 90, 180, 365'
    assert defaults['ticketing_retention_warning_days'] == 14
    assert defaults['ticketing_retention_trash_days'] == 30
    assert defaults['ticketing_retention_postpone_cap_days'] is None
    assert defaults['ticketing_retention_allow_trash']
    data = {
        'reservation_time': '30',
        'max_products_per_order': '0',
        'ticketing_retention_manual_min_days': '21',
        'ticketing_retention_warning_days': '7',
        'ticketing_retention_periods': '60, 30, 60',
        'ticketing_retention_trash_days': '15',
        'ticketing_retention_postpone_cap_days': '10',
    }
    assert staff_client.post(url, data).status_code == 302
    settings = GlobalSettingsObject().settings
    assert settings.ticketing_retention_manual_min_days == 21
    assert settings.ticketing_retention_warning_days == 7
    assert settings.ticketing_retention_periods == [30, 60]
    assert settings.ticketing_retention_allow_trash is False
    assert settings.ticketing_retention_trash_days == 15
    assert settings.ticketing_retention_postpone_cap_days == 10
    data['ticketing_retention_periods'] = '90, -1'
    assert 'ticketing_retention_periods' in staff_client.post(url, data).context['form'].errors
    assert GlobalSettingsObject().settings.ticketing_retention_periods == [30, 60]


@pytest.mark.django_db
def test_ticketing_retention_requires_staff_session(client, staff_user):
    client.force_login(staff_user)
    url = reverse('eventyay_admin:admin.global.ticketing')
    assert client.get(url).status_code in (302, 403)
    assert client.post(url, {}).status_code in (302, 403)
