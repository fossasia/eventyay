import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_orders_list_htmx(authenticated_client, event):
    """Test that HTMX requests return the fragment template instead of the full page."""
    url = reverse('common:orders')

    # Test standard request - full page
    response = authenticated_client.get(url)
    if response.status_code == 302:
        pytest.fail(f"Standard request redirected to {response.url} (validation fail?)")
    assert response.status_code == 200
    template_names = [t.name for t in response.templates]
    assert 'eventyay_common/orders/orders.html' in template_names
    assert 'eventyay_common/base.html' in template_names

    # Test HTMX request - partial template
    # Support both new Django (headers) and old (HTTP_ convention) for safety
    headers = {'HTTP_HX_REQUEST': 'true', 'headers': {'HX-Request': 'true'}}
    response = authenticated_client.get(url, **headers)
    
    if response.status_code == 302:
        pytest.fail(f"HTMX request redirected to {response.url} - Form validation failed?")
        
    assert response.status_code == 200
    template_names = [t.name for t in response.templates]
    
    assert 'eventyay_common/orders/fragment_orders_list.html' in template_names, \
        f"Expected fragment template, got: {template_names}"
    
    # Full-page template should NOT be used for HTMX requests
    assert 'eventyay_common/orders/orders.html' not in template_names
