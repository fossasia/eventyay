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
