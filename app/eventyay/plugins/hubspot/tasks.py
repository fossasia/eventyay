import logging

import requests
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Order
from eventyay.base.services.tasks import TransactionAwareTask
from eventyay.celery_app import app

logger = logging.getLogger(__name__)

# HubSpot API endpoint for upserting contacts
HUBSPOT_CONTACTS_API_URL = 'https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert'


# TODO: In a future PR, add a mapping UI that allows configuring field mappings
# between OrderPosition attendee data and HubSpot contact properties.
# For now, we use a hardcoded minimal mapping:
#   attendee_email -> hs_email (identifier)
#   attendee first/last name -> firstname / lastname

def _map_attendee_to_hubspot_contact(position):
    """
    Map OrderPosition attendee data to HubSpot contact properties.
    
    TODO: Replace with configurable mapping from UI in future PR.
    
    Returns dict with HubSpot contact properties, or None if email is missing.
    """
    if not position.attendee_email:
        return None
    
    first_name = ''
    last_name = ''
    
    if position.attendee_name_parts:
        parts = position.attendee_name_parts
        if 'first_name' in parts:
            first_name = parts['first_name']
        if 'last_name' in parts:
            last_name = parts['last_name']
    
    return {
        'email': position.attendee_email.lower(),
        'firstname': first_name,
        'lastname': last_name,
    }


def _sync_contact_batch(contacts, api_key):
    """
    Upsert a batch of contacts to HubSpot.
    
    contacts: list of dicts with email, firstname, lastname
    api_key: HubSpot API key
    
    Returns tuple (success_count, failed_emails)
    """
    if not contacts:
        return 0, []
    
    # HubSpot batch upsert payload
    payload = {
        'inputs': [
            {
                'id': contact['email'],
                'properties': {
                    'email': contact['email'],
                    'firstname': contact['firstname'],
                    'lastname': contact['lastname'],
                },
            }
            for contact in contacts
        ]
    }
    
    headers = {
        'Authorization': 'Bearer ' + api_key,
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.post(
            HUBSPOT_CONTACTS_API_URL,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        
        result = response.json()
        
        # HubSpot returns results for each contact
        success_count = len(result.get('results', []))
        
        # Extract emails that had errors
        failed_emails = []
        for error in result.get('errors', []):
            if 'id' in error:
                failed_emails.append(error['id'])
        
        return success_count, failed_emails
        
    except requests.RequestException as e:
        logger.exception('HubSpot API request failed')
        raise


@app.task(
    base=TransactionAwareTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(requests.RequestException,),
)
def sync_attendees_to_hubspot(self, order_pk, event_pk):
    """
    Celery task to sync attendees from an order to HubSpot.
    
    This task runs asynchronously and does not block order confirmation.
    
    order_pk: Order primary key
    event_pk: Event primary key
    
    Failures are logged but do not affect the order flow.
    """
    try:
        with scopes_disabled():
            order = Order.objects.get(pk=order_pk)
            event = Event.objects.get(pk=event_pk)
        
        api_key = event.settings.get('plugin_hubspot_api_key', '')
        if not api_key:
            logger.warning(
                'HubSpot sync requested but no API key for event %s',
                event.slug,
            )
            return
        
        # Map attendees to HubSpot contacts
        contacts = []
        skipped_count = 0
        
        with scope(organizer=event.organizer):
            for position in order.positions.all():
                contact = _map_attendee_to_hubspot_contact(position)
                if contact:
                    contacts.append(contact)
                else:
                    skipped_count += 1
        
        if not contacts:
            logger.info(
                'No attendees with email to sync for order %s (skipped %d)',
                order.code,
                skipped_count,
            )
            return
        
        # Sync to HubSpot
        success_count, failed_emails = _sync_contact_batch(contacts, api_key)
        
        if failed_emails:
            logger.warning(
                'HubSpot sync completed for order %s: synced %d, failed %d, skipped %d. Failed emails: %s',
                order.code,
                success_count,
                len(failed_emails),
                skipped_count,
                failed_emails,
            )
        else:
            logger.info(
                'HubSpot sync completed for order %s: synced %d, failed %d, skipped %d',
                order.code,
                success_count,
                len(failed_emails),
                skipped_count,
            )
            
    except Order.DoesNotExist:
        logger.warning('Order %d not found', order_pk)
    except Event.DoesNotExist:
        logger.warning('Event %d not found', event_pk)
