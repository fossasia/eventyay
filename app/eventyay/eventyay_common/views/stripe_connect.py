import logging
import secrets

import stripe
from django.contrib import messages
from django.core.signing import BadSignature, SignatureExpired
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from eventyay.base.meetup import is_meetup_event
from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event
from eventyay.base.stripe_connect import (
    build_stripe_authorize_url,
    build_stripe_oauth_state,
    deauthorize_stripe_account,
    exchange_stripe_authorization_code,
    get_stripe_account_display_name,
    get_stripe_connect_credentials,
    load_stripe_oauth_state,
)
from eventyay.control.permissions import EventPermissionRequiredMixin


logger = logging.getLogger(__name__)

SESSION_STRIPE_OAUTH_NONCE_KEY = 'stripe_oauth_nonce'


class EventStripeConnectAuthorizeView(EventPermissionRequiredMixin, View):
    """Initiates the Stripe Connect OAuth authorization flow for a meetup event.

    Generates a cryptographically signed state token bound to a session nonce,
    and redirects the organizer to Stripe's authorization endpoint.
    """
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        """Handle GET request to initiate Stripe OAuth flow.

        Args:
            request: The current HttpRequest.
            *args: Positional arguments.
            **kwargs: Keyword arguments containing organizer and event slugs.

        Returns:
            HttpResponseRedirect to Stripe authorization endpoint or settings on error.
        """
        event = request.event
        if not is_meetup_event(event):
            raise Http404(_('Stripe Connect is only available for meetup events.'))

        next_url = reverse(
            'eventyay_common:event.update',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )

        creds = get_stripe_connect_credentials(event)
        if not creds['is_configured']:
            messages.error(
                request,
                _('Stripe Connect is not currently configured on this platform.'),
            )
            return redirect(next_url)

        nonce = secrets.token_urlsafe(32)
        request.session[SESSION_STRIPE_OAUTH_NONCE_KEY] = nonce

        state = build_stripe_oauth_state(
            event_id=event.pk,
            user_id=request.user.pk,
            next_url=next_url,
            nonce=nonce,
        )
        redirect_uri = request.build_absolute_uri(
            reverse(
                'eventyay_common:event.stripe.callback',
                kwargs={'organizer': event.organizer.slug, 'event': event.slug},
            )
        )

        try:
            authorize_url = build_stripe_authorize_url(
                redirect_uri=redirect_uri,
                state=state,
                event=event,
            )
        except ValueError as exc:
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='not_configured',
                event_id=event.pk,
            )
            messages.error(request, str(exc))
            return redirect(next_url)

        return redirect(authorize_url)


class EventStripeConnectCallbackView(EventPermissionRequiredMixin, View):
    """Handles the redirect callback from Stripe Connect OAuth.

    Validates cryptographic state signature, session nonce, and event/user ownership
    before exchanging the authorization code and securely storing account credentials.
    """
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        """Handle GET callback from Stripe OAuth redirect.

        Args:
            request: The current HttpRequest.
            *args: Positional arguments.
            **kwargs: Keyword arguments containing organizer and event slugs.

        Returns:
            HttpResponseRedirect back to event settings page.
        """
        event = request.event
        if not is_meetup_event(event):
            raise Http404(_('Stripe Connect is only available for meetup events.'))

        next_url = reverse(
            'eventyay_common:event.update',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )

        error = request.GET.get('error')
        if error:
            error_desc = request.GET.get('error_description') or error
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='oauth_denied',
                event_id=event.pk,
            )
            messages.error(
                request,
                _('Stripe authorization was denied or failed: %(error)s') % {'error': error_desc},
            )
            return redirect(next_url)

        code = request.GET.get('code')
        state = request.GET.get('state')
        if not code or not state:
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='missing_code',
                event_id=event.pk,
            )
            messages.error(request, _('Missing authorization response from Stripe.'))
            return redirect(next_url)

        try:
            payload = load_stripe_oauth_state(state)
        except (BadSignature, SignatureExpired):
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='invalid_state',
                event_id=event.pk,
            )
            messages.error(request, _('The Stripe authorization session expired. Please try again.'))
            return redirect(next_url)

        if payload.get('event_id') != event.pk or payload.get('user_id') != request.user.pk:
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='state_mismatch',
                event_id=event.pk,
            )
            messages.error(request, _('The Stripe authorization session is invalid for this event.'))
            return redirect(next_url)

        stored_nonce = request.session.pop(SESSION_STRIPE_OAUTH_NONCE_KEY, None)
        state_nonce = payload.get('nonce')
        if not stored_nonce or not state_nonce or not secrets.compare_digest(stored_nonce, state_nonce):
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='nonce_mismatch',
                event_id=event.pk,
            )
            messages.error(request, _('The Stripe authorization session is invalid or expired. Please try again.'))
            return redirect(next_url)

        try:
            token_resp = exchange_stripe_authorization_code(code=code, event=event)
        except stripe.error.StripeError as exc:
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='token_exchange_stripe_error',
                event_id=event.pk,
            )
            logger.exception('Stripe error during OAuth code exchange for event %s', event.slug)
            messages.error(
                request,
                _('Could not connect Stripe account: %(error)s') % {'error': getattr(exc, 'user_message', str(exc))},
            )
            return redirect(next_url)
        except (ValueError, KeyError) as exc:
            log_event(
                'payment',
                'connection.stripe_connect',
                OUTCOME_FAILURE,
                error_code='token_exchange_failed',
                event_id=event.pk,
            )
            logger.exception('Failed to process Stripe OAuth callback for event %s', event.slug)
            messages.error(
                request,
                _('Could not connect Stripe account: %(error)s') % {'error': str(exc)},
            )
            return redirect(next_url)

        stripe_user_id = token_resp.get('stripe_user_id')
        if not stripe_user_id:
            messages.error(request, _('Stripe did not return a valid connected account ID.'))
            return redirect(next_url)

        publishable_key = token_resp.get('stripe_publishable_key', '')
        account_name = get_stripe_account_display_name(stripe_user_id, event=event)

        with transaction.atomic():
            event.settings.set('payment_stripe_connect_user_id', stripe_user_id)
            if publishable_key:
                event.settings.set('payment_stripe_connect_publishable_key', publishable_key)
            if account_name:
                event.settings.set('payment_stripe_connect_account_name', account_name)
            event.settings.set('payment_stripe__enabled', True)

        messages.success(request, _('Your Stripe account has been connected successfully.'))
        return redirect(next_url)


class EventStripeConnectDisconnectView(EventPermissionRequiredMixin, View):
    """Disconnects and revokes the connected Stripe account from a meetup event.

    Revokes platform authorization through Stripe OAuth deauthorization API
    before deleting local connection settings to avoid orphaned authorizations.
    """
    permission = 'can_change_event_settings'

    def post(self, request, *args, **kwargs):
        """Handle POST request to disconnect Stripe Connect account.

        Args:
            request: The current HttpRequest.
            *args: Positional arguments.
            **kwargs: Keyword arguments containing organizer and event slugs.

        Returns:
            HttpResponseRedirect back to event settings page.
        """
        event = request.event
        if not is_meetup_event(event):
            raise Http404(_('Stripe Connect is only available for meetup events.'))

        next_url = reverse(
            'eventyay_common:event.update',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )

        stripe_user_id = event.settings.get('payment_stripe_connect_user_id')
        if not stripe_user_id:
            messages.info(request, _('No active Stripe Connect account found.'))
            return redirect(next_url)

        try:
            deauthorize_stripe_account(stripe_user_id=stripe_user_id, event=event)
        except stripe.error.StripeError as exc:
            error_msg = str(exc).lower()
            # If account is already deauthorized or not found on Stripe, permit clearing local settings
            is_revoked = (
                'already_deauthorized' in error_msg
                or 'not authorized' in error_msg
                or 'does not exist' in error_msg
            )
            if is_revoked:
                logger.info('Stripe account %s was already deauthorized on Stripe: %s', stripe_user_id, exc)
            else:
                logger.error('Failed to deauthorize Stripe account %s: %s', stripe_user_id, exc)
                messages.error(
                    request,
                    _('Could not disconnect Stripe account: %(error)s. Please try again.')
                    % {'error': getattr(exc, 'user_message', str(exc))},
                )
                return redirect(next_url)
        except ValueError as exc:
            logger.warning('Missing platform credentials for deauthorization: %s', exc)
            messages.error(
                request,
                _('Stripe Connect platform credentials are missing. The account was not disconnected.'),
            )
            return redirect(next_url)

        with transaction.atomic():
            event.settings.delete('payment_stripe_connect_user_id')
            event.settings.delete('payment_stripe_connect_publishable_key')
            event.settings.delete('payment_stripe_connect_account_name')

            # If no manual secret key is configured, disable Stripe
            if not event.settings.get('payment_stripe_secret_key'):
                event.settings.set('payment_stripe__enabled', False)

        messages.success(request, _('Your Stripe account has been disconnected.'))
        return redirect(next_url)
