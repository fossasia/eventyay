import pytest
from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import CachedTicket, Event, Order, OrderPosition, Organizer
from eventyay.base.services.cleanup import clean_cached_tickets

@pytest.fixture
def cleanup_event():
    o = Organizer.objects.create(name='Dummy Cleanup', slug='dummy-cleanup')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer,eventyay.plugins.ticketoutputpdf',
    )
    with scope(organizer=o):
        yield event

@pytest.mark.django_db
def test_clean_cached_tickets(cleanup_event):
    # Ensure the setting exists and is a timedelta
    assert hasattr(settings, 'CACHE_TICKETS_MAX_AGE')
    assert isinstance(settings.CACHE_TICKETS_MAX_AGE, timedelta)

    with scope(organizer=cleanup_event.organizer):
        product = cleanup_event.products.create(
            name='Early-bird ticket', category=None, default_price=23, admission=True
        )
        order = Order.objects.create(
            code='FOO',
            event=cleanup_event,
            email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=14,
            locale='en',
        )
        order_position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=14,
        )

        # Create a cached ticket that is older than the max age
        old_ticket = CachedTicket.objects.create(
            order_position=order_position,
            provider='pdf',
            type='pdf',
            extension='pdf',
            file=None,
        )
        # Using save(update_fields=['created']) to bypass auto_now_add if it exists, or just update it
        CachedTicket.objects.filter(pk=old_ticket.pk).update(
            created=now() - settings.CACHE_TICKETS_MAX_AGE - timedelta(days=1)
        )

        # Create a cached ticket that is newer than the max age
        new_ticket = CachedTicket.objects.create(
            order_position=order_position,
            provider='pdf',
            type='pdf',
            extension='pdf',
            file=None,
        )

        clean_cached_tickets(None)

        # Old ticket should be deleted, new ticket should remain
        assert not CachedTicket.objects.filter(pk=old_ticket.pk).exists()
        assert CachedTicket.objects.filter(pk=new_ticket.pk).exists()
