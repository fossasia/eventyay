import re
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

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
            organizer=organizer, name='Conference 2026', slug='dummy', date_from=now(), currency='USD', live=True
        )
        user = User.objects.create_user('with_perm@example.com', 'dummy')
        Team.objects.create(
            organizer=organizer,
            can_change_event_settings=True,
            can_view_orders=True,
            can_change_orders=True,
            all_events=True,
        ).members.add(user)
    return {'organizer': organizer, 'event': event, 'user': user}


def _url(env, name='control:event.index', **kwargs):
    return reverse(name, kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug, **kwargs})


def _section(content):
    """Inner HTML of the Action required section, or None when it is not rendered."""
    m = re.search(
        r'<section class="td-section" aria-labelledby="td-action-required-title">(.*?)</section>', content, re.DOTALL
    )
    return m.group(1) if m else None


def _cards(section):
    return re.findall(r'<article class="td-action-card ([^"]*)">(.*?)</article>', section, re.DOTALL)


def _order(env, status=Order.STATUS_PAID, total='25.00', **kwargs):
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
    _order(env).payments.create(amount=Decimal('50.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')


def _pending_but_paid(env):
    o = _order(env, status=Order.STATUS_PENDING)
    o.payments.create(amount=Decimal('25.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')


def _pending_refund(env):
    o = _order(env)
    o.payments.create(amount=Decimal('25.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')
    o.refunds.create(
        amount=Decimal('25.00'),
        state=OrderRefund.REFUND_STATE_CREATED,
        source=OrderRefund.REFUND_SOURCE_ADMIN,
        provider='manual',
    )


def _cancellation_request(env):
    o = _order(env)
    o.payments.create(amount=Decimal('25.00'), state=OrderPayment.PAYMENT_STATE_CONFIRMED, provider='manual')
    CancellationRequest.objects.create(order=o, cancellation_fee=Decimal('0.00'))


def _pending_approval(env):
    _order(env, status=Order.STATUS_PENDING, require_approval=True)


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
    section = _section(response.content.decode())
    assert section is not None
    # Exactly one card, with its title, severity and a button to the matching list.
    [(classes, card)] = _cards(section)
    assert severity in classes.split()
    assert f'<h3 class="td-action-title">{title}</h3>' in card
    assert f'href="{_url(env, url_name)}{query}"' in card
    assert 'class="td-action-btn"' in card


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_action_required_notifications(client, env):
    with scope(organizer=env['organizer'], event=env['event']):
        action = RequiredAction.objects.create(event=env['event'], action_type='test.action')

    client.force_login(env['user'])
    section = _section(client.get(_url(env)).content.decode())
    assert section is not None
    [(classes, card)] = _cards(section)
    assert 'td-action-notifications' in classes.split()
    assert 'test.action' in card
    # Hiding posts to the discard view and is a secondary button, not the main action style.
    discard = _url(env, 'control:event.requiredaction.discard', id=action.pk)
    assert re.search(rf'<form method="post" action="{re.escape(discard)}">', card)
    assert 'csrfmiddlewaretoken' in card
    assert 'class="btn btn-default btn-xs">Hide message</button>' in card
    assert 'td-action-btn' not in card
    # "Show more" names what it opens for screen readers.
    assert re.search(
        rf'href="{re.escape(_url(env, "control:event.requiredactions"))}"\s+class="td-view-all-link"\s+'
        r'aria-describedby="td-notifications-title"',
        card,
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_action_required_hidden(client, env):
    # Nothing to do: no section at all.
    client.force_login(env['user'])
    assert _section(client.get(_url(env)).content.decode()) is None

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
    assert _section(response.content.decode()) is None
