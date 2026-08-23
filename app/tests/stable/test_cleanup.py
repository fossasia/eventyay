import pytest
from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import CachedTicket, Order, OrderPosition
from eventyay.base.services.cleanup import clean_cached_tickets


@pytest.mark.django_db
def test_clean_cached_tickets(event):
    # Ensure the setting exists and is a timedelta
    assert hasattr(settings, 'CACHE_TICKETS_MAX_AGE')
    assert isinstance(settings.CACHE_TICKETS_MAX_AGE, timedelta)

    with scope(organizer=event.organizer):
        item = event.items.create(name='Early-bird ticket', default_price=23)
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=14,
            locale='en',
        )
        order_position = OrderPosition.objects.create(
            order=order,
            item=item,
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
        old_ticket.created = now() - settings.CACHE_TICKETS_MAX_AGE - timedelta(days=1)
        old_ticket.save()

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
