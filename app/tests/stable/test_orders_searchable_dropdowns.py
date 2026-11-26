import pytest
from bs4 import BeautifulSoup
from django.templatetags.static import static
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_order_search_has_searchable_provider_select(organizer_client):
    url = reverse('control:search.orders')
    response = organizer_client.get(url, follow=True)
    assert response.status_code == 200
    doc = BeautifulSoup(response.content.decode(), 'html.parser')

    expected_css_url = static('common/css/searchable-select.css')
    expected_js_url = static('common/js/searchable-select.js')
    assert any(link.get('href') == expected_css_url for link in doc.select('link[rel=stylesheet]'))
    assert any(s.get('src') == expected_js_url for s in doc.select('script'))

    provider_select = doc.select('[name="provider"]')
    assert provider_select, 'provider select not found in order search'
    assert 'data-searchable-select' in provider_select[0].attrs
    assert provider_select[0].attrs.get('data-search-placeholder') == 'Search'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refunds_list_has_searchable_provider_select(organizer_client, event):
    url = reverse(
        'control:event.orders.refunds',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
        },
    )
    response = organizer_client.get(url, follow=True)
    assert response.status_code == 200
    doc = BeautifulSoup(response.content.decode(), 'html.parser')

    expected_css_url = static('common/css/searchable-select.css')
    expected_js_url = static('common/js/searchable-select.js')
    assert any(link.get('href') == expected_css_url for link in doc.select('link[rel=stylesheet]'))
    assert any(s.get('src') == expected_js_url for s in doc.select('script'))

    provider_select = doc.select('[name="provider"]')
    assert provider_select, 'provider select not found in refunds list'
    assert 'data-searchable-select' in provider_select[0].attrs
    assert provider_select[0].attrs.get('data-search-placeholder') == 'Search'
