import logging
from datetime import timedelta

from django.contrib import messages
from django.core.signing import BadSignature, SignatureExpired
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views import View
from requests import RequestException

from eventyay.base.gmail.models import GmailOAuthCredential
from eventyay.base.gmail.oauth import (
    build_authorization_url,
    build_oauth_state,
    exchange_authorization_code,
    fetch_sender_email,
    load_oauth_state,
)
from eventyay.control.permissions import AdministratorPermissionRequiredMixin, EventPermissionRequiredMixin


logger = logging.getLogger(__name__)


class GmailOAuthConnectView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        next_url = reverse('eventyay_admin:admin.global.settings')
        state = build_oauth_state(event_id=None, user_id=request.user.pk, next_url=next_url)
        redirect_uri = request.build_absolute_uri(reverse('eventyay_admin:admin.global.gmail.callback'))
        try:
            authorization_url = build_authorization_url(redirect_uri=redirect_uri, state=state)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(next_url)
        return redirect(authorization_url)


class GmailOAuthCallbackView(AdministratorPermissionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        error = request.GET.get('error')
        if error:
            messages.error(
                request,
                _('Google authorization was denied or failed: %(error)s') % {'error': error},
            )
            return redirect(reverse('eventyay_admin:admin.global.settings'))

        code = request.GET.get('code')
        state = request.GET.get('state')
        if not code or not state:
            messages.error(request, _('Missing authorization response from Google.'))
            return redirect(reverse('eventyay_admin:admin.global.settings'))

        try:
            payload = load_oauth_state(state)
        except (BadSignature, SignatureExpired):
            messages.error(request, _('The Google authorization session expired. Please try again.'))
            return redirect(reverse('eventyay_admin:admin.global.settings'))

        if payload.get('user_id') != request.user.pk:
            messages.error(request, _('The Google authorization session does not match the current user.'))
            return redirect(reverse('eventyay_admin:admin.global.settings'))

        redirect_uri = request.build_absolute_uri(reverse('eventyay_admin:admin.global.gmail.callback'))
        try:
            token_data = exchange_authorization_code(code=code, redirect_uri=redirect_uri)
            sender_email = fetch_sender_email(token_data['access_token'])
        except (RequestException, ValueError, KeyError) as exc:
            logger.exception('Gmail OAuth callback failed')
            messages.error(
                request,
                _('Could not connect Gmail account: %(error)s') % {'error': exc},
            )
            return redirect(payload.get('next_url') or reverse('eventyay_admin:admin.global.settings'))

        refresh_token = token_data.get('refresh_token')
        if not refresh_token:
            messages.error(
                request,
                _('Google did not return a refresh token. Disconnect the app in your Google account and try again.'),
            )
            return redirect(payload.get('next_url') or reverse('eventyay_admin:admin.global.settings'))

        expiry = None
        if token_data.get('expires_in'):
            expiry = now() + timedelta(seconds=int(token_data['expires_in']))

        from eventyay.base.gmail.crypto import encrypt_value
        with transaction.atomic():
            GmailOAuthCredential.deactivate_for_scope(event=None)
            credential = GmailOAuthCredential.objects.create(
                sender_email=sender_email,
                connected_by=request.user,
                encrypted_refresh_token=encrypt_value(refresh_token),
                encrypted_access_token=encrypt_value(token_data.get('access_token', '')) if token_data.get('access_token') else '',
                token_expiry=expiry,
            )
        messages.success(
            request,
            _('Gmail account %(email)s connected successfully.') % {'email': sender_email},
        )
        return redirect(payload.get('next_url') or reverse('eventyay_admin:admin.global.settings'))


class GmailOAuthDisconnectView(AdministratorPermissionRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        credential = GmailOAuthCredential.get_active_global()
        if credential:
            credential.disconnect()
            messages.success(request, _('Gmail account disconnected.'))
        else:
            messages.info(request, _('No active Gmail connection found.'))
        return redirect(reverse('eventyay_admin:admin.global.settings'))


class EventGmailOAuthConnectView(EventPermissionRequiredMixin, View):
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        event = request.event
        next_url = reverse(
            'eventyay_common:event.update',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        state = build_oauth_state(event_id=event.pk, user_id=request.user.pk, next_url=next_url)
        redirect_uri = request.build_absolute_uri(
            reverse(
                'eventyay_common:event.gmail.callback',
                kwargs={'organizer': event.organizer.slug, 'event': event.slug},
            )
        )
        try:
            authorization_url = build_authorization_url(redirect_uri=redirect_uri, state=state)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(next_url)
        return redirect(authorization_url)


class EventGmailOAuthCallbackView(EventPermissionRequiredMixin, View):
    permission = 'can_change_event_settings'

    def get(self, request, *args, **kwargs):
        event = request.event
        next_url = reverse(
            'eventyay_common:event.update',
            kwargs={'organizer': event.organizer.slug, 'event': event.slug},
        )
        error = request.GET.get('error')
        if error:
            messages.error(
                request,
                _('Google authorization was denied or failed: %(error)s') % {'error': error},
            )
            return redirect(next_url)

        code = request.GET.get('code')
        state = request.GET.get('state')
        if not code or not state:
            messages.error(request, _('Missing authorization response from Google.'))
            return redirect(next_url)

        try:
            payload = load_oauth_state(state)
        except (BadSignature, SignatureExpired):
            messages.error(request, _('The Google authorization session expired. Please try again.'))
            return redirect(next_url)

        if payload.get('event_id') != event.pk or payload.get('user_id') != request.user.pk:
            messages.error(request, _('The Google authorization session is invalid for this event.'))
            return redirect(next_url)

        redirect_uri = request.build_absolute_uri(
            reverse(
                'eventyay_common:event.gmail.callback',
                kwargs={'organizer': event.organizer.slug, 'event': event.slug},
            )
        )
        try:
            token_data = exchange_authorization_code(code=code, redirect_uri=redirect_uri)
            sender_email = fetch_sender_email(token_data['access_token'])
        except (RequestException, ValueError, KeyError) as exc:
            logger.exception('Event Gmail OAuth callback failed for event %s', event.slug)
            messages.error(
                request,
                _('Could not connect Gmail account: %(error)s') % {'error': exc},
            )
            return redirect(next_url)

        refresh_token = token_data.get('refresh_token')
        if not refresh_token:
            messages.error(
                request,
                _('Google did not return a refresh token. Disconnect the app in your Google account and try again.'),
            )
            return redirect(next_url)

        expiry = None
        if token_data.get('expires_in'):
            expiry = now() + timedelta(seconds=int(token_data['expires_in']))

        from eventyay.base.gmail.crypto import encrypt_value
        with transaction.atomic():
            GmailOAuthCredential.deactivate_for_scope(event=event)
            credential = GmailOAuthCredential.objects.create(
                event=event,
                sender_email=sender_email,
                connected_by=request.user,
                encrypted_refresh_token=encrypt_value(refresh_token),
                encrypted_access_token=encrypt_value(token_data.get('access_token', '')) if token_data.get('access_token') else '',
                token_expiry=expiry,
            )
        messages.success(
            request,
            _('Gmail account %(email)s connected for this event.') % {'email': sender_email},
        )
        return redirect(next_url)


class EventGmailOAuthDisconnectView(EventPermissionRequiredMixin, View):
    permission = 'can_change_event_settings'

    def post(self, request, *args, **kwargs):
        event = request.event
        credential = GmailOAuthCredential.get_active_for_event(event)
        if credential:
            credential.disconnect()
            messages.success(request, _('Gmail account disconnected for this event.'))
        else:
            messages.info(request, _('No active Gmail connection found for this event.'))
        return redirect(
            reverse(
                'eventyay_common:event.update',
                kwargs={'organizer': event.organizer.slug, 'event': event.slug},
            )
        )
