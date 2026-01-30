import pytest
from django.urls import reverse
from eventyay.control.navigation import get_event_navigation

@pytest.mark.django_db
def test_event_navigation_order(organizer_client, event, organizer, settings):
    # Mocking request object for get_event_navigation
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
    
    from django.urls import resolve
    request.resolver_match = resolve(request.path)

    # Simulate permission middleware sets
    request.eventpermset = {'can_change_event_settings', 'can_change_items', 'can_view_orders', 'can_change_orders'}
    request.orgapermset = {}

    nav = get_event_navigation(request)
    
    # Find Orders menu by icon and URL fragment (locale-independent)
    orders_menu = None
    for item in nav:
        if item.get('icon') == 'shopping-cart' and 'orders' in (item.get('url') or ''):
            orders_menu = item
            break
            
    assert orders_menu is not None
    
    # Check core items relative order using indices
    indices = {str(child['label']): i for i, child in enumerate(orders_menu['children'])}
    
    # Note: Using gettext to match the actual labels in English (default in tests)
    from django.utils.translation import gettext as _
    
    # Assert relative order for key items
    assert indices[_('Overview')] < indices[_('All orders')]
    assert indices[_('All orders')] < indices[_('Waiting list')]
    assert indices[_('Waiting list')] < indices[_('Refunds')]
    assert indices[_('Import')] < indices[_('Export')]
    
    # Verify exact position of the first item
    assert str(orders_menu['children'][0]['label']) == _('Overview')
