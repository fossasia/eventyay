import datetime as dt
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.agenda.feedback_access import (
    TicketCheckResult,
    feedback_period_open,
    user_can_give_feedback,
    user_has_event_ticket,
)
from eventyay.base.models import Order, OrderPosition, User


@pytest.mark.django_db
def test_feedback_period_closed_by_default_use_feedback_disabled(past_slot, event):
    """Verify feedback period is closed when use_feedback is disabled by default."""
    with scope(event=event):
        assert event.get_feature_flag('use_feedback') is False
        assert feedback_period_open(past_slot.submission) is False


@pytest.mark.django_db
def test_feedback_period_open_after_session_finished(past_slot, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_enable_time'] = 'finished'
        event.feature_flags['feedback_close_after_days'] = 0
        event.save(update_fields=['feature_flags'])
        assert feedback_period_open(past_slot.submission) is True


@pytest.mark.django_db
def test_feedback_period_closed_after_deadline(past_slot, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_enable_time'] = 'finished'
        event.feature_flags['feedback_close_after_days'] = 1
        event.save(update_fields=['feature_flags'])
        past_slot.end = now() - dt.timedelta(days=2)
        past_slot.save(update_fields=['end'])
        past_slot.submission.refresh_from_db()
        assert feedback_period_open(past_slot.submission) is False


@pytest.mark.django_db
def test_feedback_period_closed_before_session_ends(slot, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_enable_time'] = 'finished'
        event.save(update_fields=['feature_flags'])
        slot.start = now() + dt.timedelta(hours=1)
        slot.end = now() + dt.timedelta(hours=2)
        slot.save()
        assert feedback_period_open(slot.submission) is False


@pytest.mark.django_db
def test_user_without_ticket_cannot_give_feedback(past_slot, user, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_who_can_comment'] = 'attendees'
        event.feature_flags['feedback_close_after_days'] = 0
        event.save(update_fields=['feature_flags'])
        assert user_has_event_ticket(user, event) == TicketCheckResult.NO_TICKET
        assert user_can_give_feedback(user, past_slot.submission) is False


@pytest.mark.django_db
def test_user_with_ticket_can_give_feedback(past_slot, user, event, monkeypatch):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_who_can_comment'] = 'attendees'
        event.feature_flags['feedback_close_after_days'] = 0
        event.save(update_fields=['feature_flags'])

    monkeypatch.setattr(
        'eventyay.agenda.feedback_access.user_has_event_ticket',
        lambda _user, _event: TicketCheckResult.HAS_TICKET,
    )
    assert user_can_give_feedback(user, past_slot.submission) is True


@pytest.mark.django_db
def test_registered_user_can_give_feedback_without_ticket(past_slot, user, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_who_can_comment'] = 'registered'
        event.feature_flags['feedback_close_after_days'] = 0
        event.save(update_fields=['feature_flags'])
        assert user_can_give_feedback(user, past_slot.submission) is True


@pytest.mark.django_db
def test_talk_page_shows_closed_message_after_deadline(django_assert_num_queries, past_slot, client, user, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_who_can_comment'] = 'registered'
        event.feature_flags['feedback_close_after_days'] = 1
        event.save(update_fields=['feature_flags'])
        past_slot.end = now() - dt.timedelta(days=2)
        past_slot.save(update_fields=['end'])
    client.force_login(user)
    with django_assert_num_queries(50):
        response = client.get(past_slot.submission.urls.public, follow=True)
    assert response.status_code == 200
    assert 'Add a comment...' not in response.text
    assert 'Comments are closed for this session.' in response.text


@pytest.mark.django_db
def test_talk_page_hides_comment_form_for_non_attendee(django_assert_num_queries, past_slot, client, user, event):
    with scope(event=event):
        event.feature_flags['use_feedback'] = True
        event.feature_flags['feedback_who_can_comment'] = 'attendees'
        event.feature_flags['feedback_close_after_days'] = 0
        event.save(update_fields=['feature_flags'])
    client.force_login(user)
    with django_assert_num_queries(50):
        response = client.get(past_slot.submission.urls.public, follow=True)
    assert response.status_code == 200
    assert 'Add a comment...' not in response.text
    assert 'Only attendees with a valid ticket' in response.text


@pytest.mark.django_db
def test_user_has_event_ticket_attendee_email(event):
    """Verify attendee can access tickets purchased by another user (issue #6005) and purchaser access is preserved."""
    with scopes_disabled():
        alice = User.objects.create_user(email='alice@example.com', password='testpassw0rd!')
        bob = User.objects.create_user(email='bob@example.com', password='testpassw0rd!')
        product = event.products.create(name='Admission Ticket', default_price=Decimal('10.00'), admission=True)
        order = Order.objects.create(
            code='TKT01',
            event=event,
            email='alice@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + dt.timedelta(days=1),
            total=Decimal('10.00'),
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            attendee_email='bob@example.com',
        )

    # Attendee (bob) receives HAS_TICKET
    assert user_has_event_ticket(bob, event) == TicketCheckResult.HAS_TICKET

    # Purchaser (alice) also receives HAS_TICKET
    assert user_has_event_ticket(alice, event) == TicketCheckResult.HAS_TICKET


@pytest.mark.django_db
def test_user_has_event_ticket_attendee_email_case_insensitive(event):
    """Verify attendee email matching is case-insensitive."""
    with scopes_disabled():
        bob = User.objects.create_user(email='Bob@Example.COM', password='testpassw0rd!')
        product = event.products.create(name='Admission Ticket', default_price=Decimal('10.00'), admission=True)
        order = Order.objects.create(
            code='TKT02',
            event=event,
            email='alice@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + dt.timedelta(days=1),
            total=Decimal('10.00'),
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            attendee_email='bob@example.com',
        )

    assert user_has_event_ticket(bob, event) == TicketCheckResult.HAS_TICKET


@pytest.mark.django_db
def test_user_has_event_ticket_attendee_email_restricted_products(event):
    """Verify attendee ticket access when venueless_all_products is False."""
    with scopes_disabled():
        bob = User.objects.create_user(email='bob@example.com', password='testpassw0rd!')
        product = event.products.create(name='Admission Ticket', default_price=Decimal('10.00'), admission=True)
        other_product = event.products.create(
            name='Other Ticket',
            default_price=Decimal('10.00'),
            admission=True,
        )
        order = Order.objects.create(
            code='TKT03',
            event=event,
            email='alice@example.com',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + dt.timedelta(days=1),
            total=Decimal('10.00'),
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            attendee_email='bob@example.com',
        )

    with scope(event=event):
        event.settings.set('venueless_all_products', False)
        event.settings.set('venueless_products', [product.id])
    assert user_has_event_ticket(bob, event) == TicketCheckResult.HAS_TICKET

    with scope(event=event):
        event.settings.set('venueless_products', [other_product.id])
    assert user_has_event_ticket(bob, event) == TicketCheckResult.NO_TICKET

