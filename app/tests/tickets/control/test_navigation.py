import pytest
from django.urls import resolve
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.control.navigation import get_event_navigation


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Dummy', slug='dummy')


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now(),
    )


def _nav_includes_vouchers(nav) -> bool:
    for item in nav:
        if 'vouchers' in item.get('url', ''):
            return True
        for child in item.get('children', []):
            if 'vouchers' in child.get('url', ''):
                return True
    return False


def _find_products_nav(nav):
    for item in nav:
        if str(item.get('label')) == 'Products':
            return item
    return None


def _find_orders_nav(nav):
    for item in nav:
        if str(item.get('label')) == 'Orders':
            return item
    return None


@pytest.mark.django_db
def test_voucher_only_navigation_shows_vouchers(event, rf):
    user = User.objects.create_user('voucher@example.com', 'dummy')
    team = Team.objects.create(organizer=event.organizer, can_view_vouchers=True, all_events=True)
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)

    assert _nav_includes_vouchers(nav)
    assert _find_products_nav(nav) is None


@pytest.mark.django_db
def test_product_and_voucher_navigation_keeps_vouchers_under_products(event, rf):
    user = User.objects.create_user('products@example.com', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_change_items=True,
        can_view_vouchers=True,
        all_events=True,
    )
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)

    products = _find_products_nav(nav)
    assert products is not None
    assert _nav_includes_vouchers([products])
    assert not any(str(item.get('label')) == 'Vouchers' for item in nav)


@pytest.mark.django_db
def test_orders_parent_nav_links_to_overview(event, rf):
    user = User.objects.create_user('orders@example.com', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_view_orders=True,
        all_events=True,
    )
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)
    orders = _find_orders_nav(nav)

    assert orders is not None
    assert orders['url'].endswith('/orders/overview/')
    assert any(str(child.get('label')) == 'Overview' for child in orders.get('children', []))


@pytest.mark.django_db
def test_banktransfer_only_navigation_shows_import_export(event, rf):
    event.plugins = 'eventyay.plugins.banktransfer'
    event.save()
    user = User.objects.create_user('bank@example.com', 'dummy')
    team = Team.objects.create(
        organizer=event.organizer,
        can_manage_bank_transfers=True,
        all_events=True,
    )
    team.members.add(user)

    request = rf.get(f'/control/event/{event.organizer.slug}/{event.slug}/')
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.eventpermset = user.get_event_permission_set(event.organizer, event)
    request.resolver_match = resolve(
        f'/control/event/{event.organizer.slug}/{event.slug}/'
    )

    nav = get_event_navigation(request)
    orders_nav = None
    for item in nav:
        if str(item.get('label')) == 'Orders':
            orders_nav = item
            break

    assert orders_nav is not None
    assert any(str(child.get('label')) == 'Import / Export' for child in orders_nav.get('children', []))
    assert not any(str(child.get('label')) == 'Overview' for child in orders_nav.get('children', []))
    assert not any(str(child.get('label')) == 'All orders' for child in orders_nav.get('children', []))

