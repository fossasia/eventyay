import re

import pytest
from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse

from eventyay.base.forms.user import UserSettingsForm


def _select(content: str, field_name: str) -> str:
    """Extract the HTML <select> block for the given field name from response markup."""
    match = re.search(rf'<select[^>]*name="{field_name}"[^>]*>(.*?)</select>', content, re.S)
    assert match, f'Could not find <select name="{field_name}">'
    return match.group(0)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_account_general_dropdowns_are_searchable(authenticated_client, user):
    """Verify that language and default timezone dropdowns render with searchable select attributes."""
    url = reverse('eventyay_common:account.general')
    response = authenticated_client.get(url)
    assert response.status_code == 200

    content = response.content.decode()

    # Searchable select script and stylesheet must be present in the page
    assert 'common/js/searchable-select.js' in content
    assert 'common/css/searchable-select.css' in content

    # Language dropdown verification
    locale_html = _select(content, 'locale')
    locale_tag = locale_html.split('>', 1)[0]
    assert 'data-searchable-select' in locale_tag
    assert 'data-search-placeholder="Search"' in locale_tag
    assert 'data-empty-text="No results"' in locale_tag
    assert 'form-control' in locale_tag
    assert 'English' in locale_html
    assert 'German' in locale_html

    # Default timezone dropdown verification
    tz_html = _select(content, 'timezone')
    tz_tag = tz_html.split('>', 1)[0]
    assert 'data-searchable-select' in tz_tag
    assert 'data-search-placeholder="Search"' in tz_tag
    assert 'data-empty-text="No results"' in tz_tag
    assert 'form-control' in tz_tag
    assert 'UTC' in tz_html
    assert 'Pacific/Honolulu' in tz_html


@pytest.mark.django_db
def test_user_settings_form_searchable_widget_attributes(user):
    """Verify that UserSettingsForm explicitly assigns searchable select attributes to locale and timezone."""
    form = UserSettingsForm(instance=user, user=user)

    for field_name in ('locale', 'timezone'):
        field = form.fields[field_name]
        attrs = field.widget.attrs
        assert 'data-searchable-select' in attrs
        assert attrs['data-search-placeholder'] == 'Search'
        assert attrs['data-empty-text'] == 'No results'
        assert 'form-control' in attrs['class']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_account_general_saving_language_and_timezone(authenticated_client, user):
    """Verify that submitting new language and timezone values persists them correctly."""
    url = reverse('eventyay_common:account.general')

    # Update to German and Europe/Berlin
    post_data = {
        'fullname': user.fullname,
        'locale': 'de',
        'timezone': 'Europe/Berlin',
    }
    response = authenticated_client.post(url, post_data, follow=True)
    assert response.status_code == 200

    user.refresh_from_db()
    assert user.locale == 'de'
    assert user.timezone == 'Europe/Berlin'

    # Update to French and Pacific/Honolulu
    post_data2 = {
        'fullname': user.fullname,
        'locale': 'fr',
        'timezone': 'Pacific/Honolulu',
    }
    response2 = authenticated_client.post(url, post_data2, follow=True)
    assert response2.status_code == 200

    user.refresh_from_db()
    assert user.locale == 'fr'
    assert user.timezone == 'Pacific/Honolulu'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_account_general_retains_selected_values_after_reload(authenticated_client, user):
    """Verify that the account settings page retains and marks existing selected values correctly."""
    user.locale = 'de'
    user.timezone = 'Pacific/Honolulu'
    user.save()

    url = reverse('eventyay_common:account.general')
    response = authenticated_client.get(url)
    assert response.status_code == 200

    soup = BeautifulSoup(response.content, 'html.parser')

    locale_select = soup.find('select', attrs={'name': 'locale'})
    assert locale_select is not None
    selected_locale = locale_select.find('option', selected=True)
    assert selected_locale is not None
    assert selected_locale['value'] == 'de'

    tz_select = soup.find('select', attrs={'name': 'timezone'})
    assert tz_select is not None
    selected_tz = tz_select.find('option', selected=True)
    assert selected_tz is not None
    assert selected_tz['value'] == 'Pacific/Honolulu'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_account_general_unrelated_fields_unaffected(authenticated_client, user):
    """Verify that updating other fields leaves language and timezone intact, and vice versa."""
    user.locale = 'en'
    user.timezone = 'UTC'
    user.fullname = 'Original Name'
    user.save()

    url = reverse('eventyay_common:account.general')
    post_data = {
        'fullname': 'New Full Name',
        'locale': 'en',
        'timezone': 'UTC',
    }
    response = authenticated_client.post(url, post_data, follow=True)
    assert response.status_code == 200

    user.refresh_from_db()
    assert user.fullname == 'New Full Name'
    assert user.locale == 'en'
    assert user.timezone == 'UTC'
