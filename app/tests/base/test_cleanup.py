import pytest
from datetime import timedelta
from django.conf import settings
from django.utils.timezone import now

from eventyay.base.models import CachedCombinedTicket, CachedTicket
from eventyay.base.services.cleanup import clean_cached_tickets


@pytest.mark.django_db
def test_clean_cached_tickets(event, order, order_position):
    # Ensure the setting exists and is a timedelta
    assert hasattr(settings, 'CACHE_TICKETS_MAX_AGE')
    assert isinstance(settings.CACHE_TICKETS_MAX_AGE, timedelta)

    # Create a cached ticket that is older than the max age
    old_ticket = CachedTicket.objects.create(
        order_position=order_position,
        provider='pdf',
        file='test.pdf'
    )
    old_ticket.created = now() - settings.CACHE_TICKETS_MAX_AGE - timedelta(days=1)
    old_ticket.save()

    # Create a cached ticket that is newer than the max age
    new_ticket = CachedTicket.objects.create(
        order_position=order_position,
        provider='pdf',
        file='test2.pdf'
    )

    clean_cached_tickets(None)

    # Old ticket should be deleted, new ticket should remain
    assert not CachedTicket.objects.filter(pk=old_ticket.pk).exists()
    assert CachedTicket.objects.filter(pk=new_ticket.pk).exists()
