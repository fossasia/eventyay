import pytest
from django.urls import reverse
from django_scopes import scope
from eventyay.control.navigation import get_event_navigation

@pytest.mark.django_db
def test_event_navigation_order(orga_client, event, organizer, settings):
    # Mocking request object is tricky, using orga_client context might be better 
    # but get_event_navigation requires a request object.
    # We'll use a request factory or rely on orga_client to set up the request
    from django.test import RequestFactory
    from eventyay.base.models import User
    
    # Setup user with permissions
    user = User.objects.create_user('test@example.com', 'test')
    # Grant permissions
    team = organizer.teams.create(can_change_event_settings=True, can_change_items=True, can_view_orders=True, can_change_orders=True)
    team.members.add(user)
    team.limit_events.add(event)

    factory = RequestFactory()
    request = factory.get(reverse('control:event.settings', kwargs={'event': event.slug, 'organizer': organizer.slug}))
    request.user = user
    request.event = event
    request.organizer = organizer
    
    # We need to simulate the permission middleware which sets eventpermset
    # But usually middleware does this.
    # Let's manually set permissions for the test
    request.eventpermset = {'can_change_event_settings', 'can_change_items', 'can_view_orders', 'can_change_orders'}
    request.orgapermset = {}

    nav = get_event_navigation(request)
    
    # Find Orders menu
    orders_menu = None
    for item in nav:
        if 'Orders' in str(item['label']):
            orders_menu = item
            break
            
    assert orders_menu is not None
    
    # Expected order labels substring matching
    expected_order = [
        'Overview', 
        # 'Statistics', # Plugin might not be loaded in this test context
        'All orders', 
        'Waiting list', 
        'Refunds', 
        'Import', 
        'Export'
    ]
    
    # Extract labels from children
    actual_labels = [str(child['label']) for child in orders_menu['children']]
    
    # Verify order
    # Note: Statistics might be missing if plugin is not active in test env, 
    # so we filter expected_order to what's actually present if we just want to verify relative order of core items.
    
    # Check core items relative order
    filtered_actual = [l for l in actual_labels if l in expected_order]
    
    # There might be extra items or missing items (like Statistics)
    # Let's check indices
    
    indices = {label: i for i, label in enumerate(actual_labels)}
    
    assert indices['Overview'] < indices['All orders']
    assert indices['All orders'] < indices['Waiting list']
    assert indices['Waiting list'] < indices['Refunds']
    assert indices['Import'] < indices['Export']
    
    # Verify exact positions if possible
    # We moved Overview to 0 (or 1 if something else is there)
    # In our implementation: 1. Overview
    
    assert actual_labels[0] == 'Overview'
    assert actual_labels[1] == 'All orders' # Statistics is 2, but if missing, All orders becomes 2 (index 1)
    
    # Wait, if Statistics is missing, All orders is index 1.
    # If Statistics is present, All orders is index 2.
    
    print("Actual labels:", actual_labels)
