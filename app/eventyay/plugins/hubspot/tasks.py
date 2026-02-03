"""
HubSpot integration for syncing attendees to HubSpot contacts.

Uses static field mapping between attendee data and HubSpot contact properties.
Configurable field mappings will be added in a future release.
"""

import logging

import requests
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Order
from eventyay.base.services.tasks import TransactionAwareTask
from eventyay.celery_app import app

logger = logging.getLogger(__name__)

# HubSpot API endpoint for creating contacts (batch endpoint)
HUBSPOT_CONTACTS_API_URL = 'https://api.hubapi.com/crm/v3/objects/contacts/batch/create'


# TODO: In a future PR, add a mapping UI that allows configuring field mappings
# between OrderPosition attendee data and HubSpot contact properties.
# For now, we use a hardcoded minimal mapping:
#   attendee_email -> hs_email (identifier)
#   attendee first/last name -> firstname / lastname

def map_position_to_contact_properties(position, order_email=None):
    """
    Extract contact information from an attendee position for HubSpot.

    Takes an OrderPosition with attendee details and converts it to a format
    suitable for HubSpot contacts. Falls back to order email if position
    attendee email is empty.

    Args:
        position: OrderPosition instance containing attendee name and email
        order_email: Order contact email (used as fallback if position has no attendee_email)

    Returns:
        dict with keys 'email', 'firstname', 'lastname' suitable for HubSpot,
        or None if no email address is available
    """
    # First try to get email from position attendee_email
    email = position.attendee_email
    
    # Fall back to order email if position attendee_email is empty
    if not email and order_email:
        email = order_email
    
    # If still no email, we cannot sync this contact
    if not email:
        return None

    first_name = ''
    last_name = ''

    # Name parts come as a dictionary from the frontend. We extract individual
    # components to map to HubSpot's firstname/lastname properties.
    # Eventyay uses 'given_name' and 'family_name' keys.
    # Only use non-empty values
    if position.attendee_name_parts:
        parts = position.attendee_name_parts
        if 'given_name' in parts and parts['given_name']:
            first_name = parts['given_name']
        elif 'first_name' in parts and parts['first_name']:
            first_name = parts['first_name']
        if 'family_name' in parts and parts['family_name']:
            last_name = parts['family_name']
        elif 'last_name' in parts and parts['last_name']:
            last_name = parts['last_name']

    return {
        'email': email.lower(),
        'firstname': first_name,
        'lastname': last_name,
    }


def send_contacts_to_hubspot(contacts, api_key):
    """
    Send a batch of contacts to HubSpot via their batch create API.

    Makes an HTTP POST request to HubSpot's batch create endpoint.
    HubSpot internally deduplicates contacts based on the email property.

    Args:
        contacts: list of dicts, each with 'email', 'firstname', 'lastname' keys
        api_key: HubSpot private app access token for authentication

    Returns:
        tuple of (success_count: int, failed_emails: list of str)
        failed_emails contains email addresses that HubSpot rejected

    Raises:
        requests.RequestException: on network errors, timeouts, or HTTP errors.
        The caller should handle retries for transient failures.
    """
    if not contacts:
        return 0, []
    
    # HubSpot batch create endpoint expects a list of contacts with properties.
    # HubSpot internally deduplicates contacts based on the email property.
    # If a contact with the same email already exists, it will be skipped/ignored.
    # We only include non-empty fields to avoid HubSpot rejecting the request.
    inputs = []
    for contact in contacts:
        properties = {
            'email': contact['email'],
        }
        if contact.get('firstname'):
            properties['firstname'] = contact['firstname']
        if contact.get('lastname'):
            properties['lastname'] = contact['lastname']
        
        inputs.append({
            'properties': properties,
        })
    
    payload = {
        'inputs': inputs,
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
            timeout=10,  # Short timeout - HubSpot's batch API is fast when working
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Success count is based on results array returned by HubSpot
        success_count = len(result.get('results', []))
        
        # Errors array contains failed contacts. The 'id' field in the error
        # holds the email address that failed to create.
        # We track these for logging purposes.
        failed_emails = []
        for error in result.get('errors', []):
            if 'id' in error:
                failed_emails.append(error['id'])
        
        return success_count, failed_emails
        
    except requests.RequestException as e:
        # Log the full request details for debugging
        logger.exception('HubSpot API request failed')
        logger.error('HubSpot Request URL: %s', HUBSPOT_CONTACTS_API_URL)
        logger.error('HubSpot Request Headers: %s', headers)
        logger.error('HubSpot Request Payload: %s', payload)
        logger.error('HubSpot Response Status: %s', e.response.status_code if e.response else 'No response')
        logger.error('HubSpot Response Body: %s', e.response.text if e.response else 'No response')
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
    Background Celery task that syncs order attendees to HubSpot.

    This task runs asynchronously after order confirmation and does not delay
    the checkout process. It is triggered when the HubSpot plugin is enabled.

    Args:
        order_pk: primary key of the Order to sync attendees from
        event_pk: primary key of the Event the order belongs to

    Behavior:
        - Skips silently if HubSpot plugin or API key is not configured
        - Skips positions without email addresses
        - Retries automatically on transient network failures (up to 3 times)
        - Logs warnings but does not raise if order or event is not found

    Returns:
        None. Results are logged at info or warning level.
    """
    try:
        # Fetch order and event outside of organizer scope since we need
        # cross-organizer access to retrieve these objects.
        with scopes_disabled():
            order = Order.objects.get(pk=order_pk)
            event = Event.objects.get(pk=event_pk)

        # Re-check plugin enabled status - the task may have been queued
        # before the plugin was disabled. This is a cheap check that avoids
        # unnecessary work and API calls.
        if not event.settings.get('plugin_hubspot_enabled', False):
            return

        api_key = event.settings.get('plugin_hubspot_api_key', '')
        if not api_key:
            logger.warning(
                'HubSpot sync requested but no API key for event %s',
                event.slug,
            )
            return
        
        # Map attendees to HubSpot contacts - positions are scoped to the
        # organizer, which is required for proper permission checks and
        # multi-tenant data access patterns.
        contacts = []
        skipped_count = 0
        
        with scope(organizer=event.organizer):
            for position in order.positions.all():
                # Returns None for positions without email, which we count as skipped
                # Pass order_email as fallback if position attendee_email is empty
                contact = map_position_to_contact_properties(position, order.email)
                if contact:
                    contacts.append(contact)
                else:
                    skipped_count += 1
        
        # Early exit if no valid contacts to sync. This can happen when all
        # attendees provided incomplete information (missing email).
        if not contacts:
            logger.info(
                'No attendees with email to sync for order %s (skipped %d)',
                order.code,
                skipped_count,
            )
            return
        
        # Sync to HubSpot - this is the actual API call that may retry on failure
        success_count, failed_emails = send_contacts_to_hubspot(contacts, api_key)
        
        # Log outcome - failed emails are a partial success case (some synced, some failed)
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
