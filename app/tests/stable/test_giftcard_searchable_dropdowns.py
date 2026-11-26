import pytest
from bs4 import BeautifulSoup
from django.templatetags.static import static
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_giftcard_add_has_searchable_currency_select(organizer_client, organizer):
    url = reverse('control:organizer.giftcard.add', kwargs={'organizer': organizer.slug})
    response = organizer_client.get(url, follow=True)
    assert response.status_code == 200
    doc = BeautifulSoup(response.content.decode(), 'html.parser')

    expected_css_url = static('common/css/searchable-select.css')
    expected_js_url = static('common/js/searchable-select.js')
    assert any(link.get('href') == expected_css_url for link in doc.select('link[rel=stylesheet]'))
    assert any(s.get('src') == expected_js_url for s in doc.select('script'))

    currency_select = doc.select('[name="currency"]')
    assert currency_select, 'currency select not found'
    assert 'data-searchable-select' in currency_select[0].attrs
    assert currency_select[0].attrs.get('data-search-placeholder') == 'Search'
