"""Tests for the tickets dashboard (control:event.index), one section per block below."""

import re
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.meetup import EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE
from eventyay.base.models import (
    Event,
    Order,
    OrderPayment,
    OrderRefund,
    Organizer,
    Team,
    User,
)
from eventyay.base.models.event import RequiredAction
from eventyay.base.models.orders import CancellationRequest


@pytest.fixture
def env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=organizer,
            name='Conference 2026',
            slug='dummy',
            date_from=now(),
            currency='USD',
            live=True,
        )
        user = User.objects.create_user('with_perm@example.com', 'dummy')
        team = Team.objects.create(
            organizer=organizer,
            can_change_event_settings=True,
            can_view_orders=True,
            can_change_orders=True,
            all_events=True,
        )
        team.members.add(user)

        return {
            'organizer': organizer,
            'event': event,
            'user': user,
        }


def _url(env, name='control:event.index', **kwargs):
    return reverse(name, kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug, **kwargs})


def _header_extra(content):
    """Return the inner text of the header's ``dashboard-header-extra`` element.

    Asserting against this element (rather than the whole page) keeps the tests
    from passing on content that merely appears elsewhere, e.g. the page title
    or the "Meetup organizer" panel.
    """
    match = re.search(r'<div class="text-muted dashboard-header-extra">(.*?)</div>', content, re.DOTALL)
    assert match is not None, 'dashboard-header-extra element not found'
    return match.group(1)


# --- Page header -------------------------------------------------------------


# The control middleware redirects to SITE_URL unless it matches the test client's host.
@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_shows_tickets_dashboard_title_and_event_name(client, env):
    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()

    # Modern dashboard header with the "Tickets dashboard" title.
    assert 'modern-dashboard' in content
    assert '<h2>Tickets dashboard</h2>' in content

    # Event name and date range shown inside the header element itself.
    header_extra = _header_extra(content)
    assert 'Conference 2026' in header_extra
    with scope(organizer=env['organizer'], event=env['event']):
        date_range = env['event'].get_date_range_display()
    assert date_range in header_extra
    # The separator is decorative, so screen readers skip it.
    assert '<span aria-hidden="true">&middot;</span>' in header_extra


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_preserves_component_link_navigation(client, env):
    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()

    # The component_link navigation (Home / Tickets / ...) is still rendered,
    # with the Tickets entry marked active. Search only the header nav, so a
    # sidebar link to the same URL cannot satisfy the assertions.
    tickets_url = reverse(
        'control:event.index',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    nav = re.search(r'<nav id="event-nav".*?</nav>', content, re.DOTALL)
    assert nav is not None, '#event-nav not found'
    nav = nav.group(0)
    assert 'navigation-button' in nav

    # The Tickets entry must carry the "active" class on its anchor. Tokenize
    # the class list so a value like "inactive" does not satisfy the assertion.
    tickets_anchor = re.search(r'<a[^>]*href="' + re.escape(tickets_url) + r'"[^>]*>', nav)
    assert tickets_anchor is not None, 'Tickets navigation anchor not found in #event-nav'
    class_match = re.search(r'class="([^"]*)"', tickets_anchor.group(0))
    assert class_match is not None, 'Tickets anchor has no class attribute'
    assert 'active' in class_match.group(1).split()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_event_series_branch(client, env):
    with scope(organizer=env['organizer'], event=env['event']):
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()
    assert '<h2>Tickets dashboard</h2>' in content
    # Event series uses the "Event series" label instead of a date range.
    assert 'Event series' in _header_extra(content)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_meetup_branch(client, env):
    with scope(organizer=env['organizer'], event=env['event']):
        env['event'].settings.set(EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE)

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()
    assert '<h2>Tickets dashboard</h2>' in content
    # Meetup events use the "Meetup" label in the header (not just the
    # "Meetup organizer" panel elsewhere on the page).
    assert 'Meetup' in _header_extra(content)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_without_date_has_no_orphaned_separator(client, env, monkeypatch):
    # When there is no displayable date range, the header must not render a
    # dangling "&middot;" after the event name.
    monkeypatch.setattr(Event, 'get_date_range_display', lambda self, *a, **kw: '')

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()

    header_extra = _header_extra(content).strip()
    assert 'Conference 2026' in header_extra
    # No trailing separator when there is no date/metadata to show.
    assert '&middot;' not in header_extra
    assert '·' not in header_extra


# --- Action required --------------------------------------------------------


def _action_section(content):
    """Inner HTML of the Action required section, or None when it is not rendered."""
    m = re.search(
        r'<section class="td-section" aria-labelledby="td-action-required-title">(.*?)</section>', content, re.DOTALL
    )
    return m.group(1) if m else None


def _cards(section):
    return re.findall(r'<article class="td-action-card ([^"]*)">(.*?)</article>', section, re.DOTALL)


def _action_order(env, status=Order.STATUS_PAID, total='25.00', **kwargs):
    return Order.objects.create(
        event=env['event'],
        status=status,
        datetime=now(),
        expires=now(),
        total=Decimal(total),
        code=f'O{Order.objects.count():05d}',
        **kwargs,
    )


def _overpaid(env):
    _action_order(env).payments.create(
        amount=Decimal('50.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual'
    )


def _pending_but_paid(env):
    o = _action_order(env, status=Order.STATUS_PENDING)
    o.payments.create(amount=Decimal('25.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')


def _pending_refund(env):
    o = _action_order(env)
    o.payments.create(amount=Decimal('25.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')
    o.refunds.create(
        amount=Decimal('25.00'),
        state=OrderRefund.REFUND_STATE_CREATED,
        source=OrderRefund.REFUND_SOURCE_ADMIN,
        provider='manual',
    )


def _cancellation_request(env):
    o = _action_order(env)
    o.payments.create(amount=Decimal('25.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')
    CancellationRequest.objects.create(order=o, cancellation_fee=Decimal('0.00'))


def _pending_approval(env):
    _action_order(env, status=Order.STATUS_PENDING, require_approval=True)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    'make, title, url_name, query, severity',
    [
        (_overpaid, 'Overpaid', 'control:event.orders', '?status=overpaid', 'td-action-danger'),
        (
            _pending_but_paid,
            'Pending (but fully paid)',
            'control:event.orders',
            '?status=pendingpaid',
            'td-action-danger',
        ),
        (_pending_refund, 'Refunds', 'control:event.orders.refunds', '', 'td-action-warning'),
        (_cancellation_request, 'Cancellation requested', 'control:event.orders', '?status=rc', 'td-action-warning'),
        (_pending_approval, 'Approval pending', 'control:event.orders', '?status=pa', 'td-action-warning'),
    ],
)
def test_action_required_item(client, env, make, title, url_name, query, severity):
    with scope(organizer=env['organizer'], event=env['event']):
        make(env)

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    section = _action_section(response.content.decode())
    assert section is not None
    # Exactly one card, with its title, severity and a button to the matching list.
    [(classes, card)] = _cards(section)
    assert severity in classes.split()
    assert f'<h3 class="td-action-title">{title}</h3>' in card
    # Compare the button's full URL, so a malformed query string cannot pass.
    [button_href] = re.findall(r'href="([^"]*)"\s+class="td-action-btn"', card)
    assert button_href == f'{_url(env, url_name)}{query}'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_action_required_all_items_together(client, env):
    # Every item at once: all cards render together, in a fixed order, with notifications last.
    with scope(organizer=env['organizer'], event=env['event']):
        for make in (_overpaid, _pending_but_paid, _pending_refund, _cancellation_request, _pending_approval):
            make(env)
        action = RequiredAction.objects.create(event=env['event'], action_type='test.action')

    client.force_login(env['user'])
    section = _action_section(client.get(_url(env)).content.decode())
    assert section is not None
    cards = _cards(section)
    titles = [' '.join(re.search(r'<h3[^>]*>(.*?)</h3>', card, re.DOTALL).group(1).split()) for _, card in cards]
    assert titles[:5] == [
        'Overpaid',
        'Pending (but fully paid)',
        'Refunds',
        'Cancellation requested',
        'Approval pending',
    ]
    assert [classes.split()[0] for classes, _ in cards] == ['td-action-danger'] * 2 + ['td-action-warning'] * 3 + [
        'td-action-danger'
    ]

    classes, card = cards[-1]
    assert 'td-action-notifications' in classes.split()
    assert 'test.action' in card
    # Hiding posts to the discard view and is a secondary button, not the main action style.
    discard = _url(env, 'control:event.requiredaction.discard', id=action.pk)
    assert re.search(rf'<form method="post" action="{re.escape(discard)}">', card)
    assert 'csrfmiddlewaretoken' in card
    assert 'td-action-btn' not in card
    # Each Hide message button names its notification's time for screen readers.
    assert re.search(
        r'<button type="submit" class="btn btn-default btn-xs">\s*'
        r'Hide message<span class="sr-only"> [^<]+</span>\s*</button>',
        card,
    )
    # "Show more" names what it opens for screen readers.
    assert re.search(
        rf'href="{re.escape(_url(env, "control:event.requiredactions"))}"\s+class="td-view-all-link"\s+'
        r'aria-describedby="td-notifications-title"',
        card,
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_action_required_hidden(client, env):
    # Nothing to do: no section, but the empty wrapper keeps the page padding unchanged.
    client.force_login(env['user'])
    content = client.get(_url(env)).content.decode()
    assert _action_section(content) is None
    assert '<div class="td-dashboard p-0"></div>' in content

    # Without order permissions the items are not shown, so neither is the section.
    with scope(organizer=env['organizer'], event=env['event']):
        _pending_approval(env)
        RequiredAction.objects.create(event=env['event'], action_type='test.action')
    with scopes_disabled():
        viewer = User.objects.create_user('no_perm@example.com', 'dummy')
        Team.objects.create(
            organizer=env['organizer'], can_change_event_settings=True, can_view_orders=False, all_events=True
        ).members.add(viewer)
    client.force_login(viewer)
    response = client.get(_url(env))
    assert response.status_code == 200
    assert _action_section(response.content.decode()) is None
