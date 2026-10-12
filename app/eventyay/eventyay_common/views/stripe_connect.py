import logging

import stripe
from django.contrib import messages
from django.core.signing import BadSignature, SignatureExpired
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


class EventStripeConnectAuthorizeView(EventPermissionRequiredMixin, View):
    """
    Initiates Stripe Connect OAuth flow for a meetup event.
    """
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
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

        state = build_stripe_oauth_state(
            event_id=event.pk,
            user_id=request.user.pk,
            next_url=next_url,
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
    """
    Handles callback from Stripe Connect OAuth, validating state and saving credentials.
    """
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
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

        event.settings.set('payment_stripe_connect_user_id', stripe_user_id)
        if publishable_key:
            event.settings.set('payment_stripe_connect_publishable_key', publishable_key)
        if account_name:
            event.settings.set('payment_stripe_connect_account_name', account_name)
        event.settings.set('payment_stripe__enabled', True)

        messages.success(request, _('Your Stripe account has been connected successfully.'))
        return redirect(next_url)


class EventStripeConnectDisconnectView(EventPermissionRequiredMixin, View):
    """
    Disconnects the connected Stripe account from a meetup event.
    """
    permission = 'can_change_event_settings'

    def post(self, request, *args, **kwargs):
        event = request.event
        if not is_meetup_event(event):
            raise Http404(_('Stripe Connect is only available for meetup events.'))

        next_url = reverse(
            'eventyay_common:event.update',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )

        stripe_user_id = event.settings.get('payment_stripe_connect_user_id')
        if stripe_user_id:
            deauthorize_stripe_account(stripe_user_id=stripe_user_id, event=event)
            event.settings.delete('payment_stripe_connect_user_id')
            event.settings.delete('payment_stripe_connect_publishable_key')
            event.settings.delete('payment_stripe_connect_account_name')

            # If no manual secret key is configured, disable Stripe
            if not event.settings.get('payment_stripe_secret_key'):
                event.settings.set('payment_stripe__enabled', False)

            messages.success(request, _('Your Stripe account has been disconnected.'))
        else:
            messages.info(request, _('No active Stripe Connect account found.'))

        return redirect(next_url)
