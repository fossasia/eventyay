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
    
    # Early exit checks at signal level avoid queuing unnecessary tasks.
    # This is a performance optimization - queued tasks would just return early.
    # We check both plugin enabled state and API key presence.
    if not event.settings.get('plugin_hubspot_enabled', as_type=bool):
        return
    
    api_key = event.settings.get('plugin_hubspot_api_key', '')
    if not api_key:
        logger.warning(
            'HubSpot plugin enabled but no API key configured for event %s',
            event.slug,
        )
        return
    
    # Queue the Celery task asynchronously. The task will handle the actual
    # sync logic and retry behavior. We pass both order_pk and event_pk
    # because the task needs the event context to access settings and scope.
    sync_attendees_to_hubspot.delay(
        order_pk=order.pk,
        event_pk=event.pk,
    )


@receiver(nav_event_settings, dispatch_uid='hubspot_nav_settings')
def navbar_settings(sender, request, **kwargs):
    """
    Add HubSpot settings link to event settings navigation.
    
    This integrates the HubSpot plugin into the event settings sidebar.
    The signal receives the current request which contains user permissions
    and event context needed to conditionally show the settings link.
    """
    url = resolve(request.path_info)
    
    # Permission check ensures only users with settings access see the link.
    # This follows the principle of minimal privilege - even the nav item
    # is hidden from users who can't access the settings page.
    if not request.user.has_event_permission(
        request.organizer,
        request.event,
        'can_change_settings',
        request=request,
    ):
        return []
    
    # Return a list of nav items - in this case, just one HubSpot entry.
    # The 'active' flag uses namespace matching to highlight when on the page.
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
