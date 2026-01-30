import logging

from django.dispatch import receiver
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.signals import order_paid
from eventyay.control.signals import nav_event_settings

from .tasks import sync_attendees_to_hubspot

logger = logging.getLogger(__name__)


@receiver(order_paid, dispatch_uid='hubspot_order_paid')
def on_order_paid(sender, order=None, **kwargs):
    """
    Queue a Celery task to sync attendees to HubSpot when an order is paid.
    
    sender: Event instance
    order: Order instance
    
    This runs asynchronously and does not block order confirmation.
    """
    event = sender
    
    # Check if HubSpot plugin is enabled for this event
    if not event.settings.get('plugin_hubspot_enabled', as_type=bool):
        return
    
    # Get API key
    api_key = event.settings.get('plugin_hubspot_api_key', '')
    if not api_key:
        logger.warning(
            'HubSpot plugin enabled but no API key configured for event %s',
            event.slug,
        )
        return
    
    # Queue async task
    sync_attendees_to_hubspot.delay(
        order_pk=order.pk,
        event_pk=event.pk,
    )


@receiver(nav_event_settings, dispatch_uid='hubspot_nav_settings')
def navbar_settings(sender, request, **kwargs):
    """
    Add HubSpot settings link to event settings navigation.
    """
    url = resolve(request.path_info)
    if not request.user.has_event_permission(
        request.organizer,
        request.event,
        'can_change_settings',
        request=request,
    ):
        return []
    return [
        {
            'label': _('HubSpot CRM'),
            'url': reverse(
                'plugins:hubspot:settings',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.organizer.slug,
                },
            ),
            'active': url.namespace == 'plugins:hubspot',
        }
    ]
