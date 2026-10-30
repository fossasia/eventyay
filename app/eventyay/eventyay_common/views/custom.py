from __future__ import annotations

from functools import cached_property
from typing import Any

from allauth.account.internal.decorators import login_not_required
from allauth.account.internal.flows.email_verification import send_verification_email_at_login
from allauth.account.models import Login
from allauth.account.stages import EmailVerificationStage, LoginStageController
from allauth.account.views import ConfirmEmailView as _ConfirmEmailView
from allauth.account.views import EmailVerificationSentView as _EmailVerificationSentView
from allauth.account.views import SignupView as _SignupView
from django import forms
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from eventyay.base.models.page import Page
from eventyay.base.services.turnstile import (
    TURNSTILE_ERROR_MESSAGE,
    TURNSTILE_FAILED_MESSAGE,
    TURNSTILE_MISCONFIGURED_MESSAGE,
    get_turnstile_settings,
    is_turnstile_enabled_for_action,
    verify_turnstile_token,
)
from eventyay.helpers.http import get_client_ip


class SignupConfirmationForm(forms.Form):
    confirmation_pages_accepted = forms.BooleanField(required=False)

    def __init__(self, *args, has_required_pages: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_required_pages = has_required_pages

    def clean(self):
        cleaned_data = super().clean()
        if self.has_required_pages and not cleaned_data.get('confirmation_pages_accepted'):
            raise forms.ValidationError(_('You must agree with the required pages before creating an account.'))
        return cleaned_data


class ConfirmEmailView(_ConfirmEmailView):
    """Custom email confirmation view that separates HTML from translatable strings."""

    # Explicitly use the Jinja template override located in jinja-templates/account/
    template_name = 'account/email_confirm.jinja'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Build message components separately for better translation
        if context.get('confirmation'):
            confirmation = context['confirmation']
            email = confirmation.email_address.email
            user_display = confirmation.email_address.user.get_full_name() or confirmation.email_address.user.email

            # Store components separately for the template
            context['confirmation_email'] = email
            context['confirmation_user'] = user_display
            email_link = format_html('<a href="mailto:{0}">{0}</a>', email)
            context['confirmation_message'] = mark_safe(
                _('Please confirm that %(email)s is an email address for user %(user)s.')
                % {'email': email_link, 'user': conditional_escape(user_display)}
            )
            context['already_confirmed_message'] = _(
                'Unable to confirm %(email)s because it is already confirmed by a different account.'
            ) % {'email': email}

        email_url = reverse('eventyay_common:account.email')
        context['email_url'] = email_url

        # Build invalid/expired link message without embedding HTML in translatable strings
        if not context.get('confirmation'):
            action_text = _('issue a new email confirmation request')
            link_html = f'<a href="{email_url}">{action_text}</a>'
            message = _(
                'This email confirmation link expired or is invalid. Please %(email_action_link)s.'
            ) % {'email_action_link': link_html}
            context['invalid_confirmation_message'] = mark_safe(message)

        return context


# Shown after signup (or a login with an unverified address). Allauth keeps the pending
# login in the session, which lets us show the target address and offer a resend.
# A signup with an already registered address yields a login without a user (enumeration
# prevention); it must look and behave exactly like a real one, so both go through allauth's
# send_verification_email_at_login().
@method_decorator(login_not_required, name='dispatch')
class EmailVerificationSentView(_EmailVerificationSentView):
    template_name = 'account/verification_sent.jinja'

    @cached_property
    def pending_login(self) -> Login | None:
        stage = LoginStageController.enter(self.request, EmailVerificationStage.key)
        return stage.login if stage else None

    @cached_property
    def pending_email(self) -> str | None:
        login = self.pending_login
        if not login:
            return None
        return login.email or (login.user.email if login.user else None)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        login = self.pending_login
        # On success allauth adds its own "sent" message; within the cooldown it silently skips sending.
        if login and self.pending_email and not send_verification_email_at_login(request, login):
            messages.error(
                request,
                _('A verification email was sent recently. Please wait a few minutes before requesting another one.'),
            )
        return HttpResponseRedirect(reverse('account_email_verification_sent'))

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['pending_email'] = self.pending_email
        context['messages'] = messages.get_messages(self.request)
        return context


# Override to provide additional context for the signup page, such as pages that require confirmation.
class SignupView(_SignupView):
    # Explicitly use the Jinja template override located in jinja-templates/account/
    template_name = 'account/signup.jinja'

    @cached_property
    def confirmation_pages(self) -> tuple[Page, ...]:
        return tuple(Page.objects.filter(confirmation_required=True))

    def form_valid(self, form):
        has_required_pages = bool(self.confirmation_pages)
        confirmation_form = SignupConfirmationForm(self.request.POST, has_required_pages=has_required_pages)
        if not confirmation_form.is_valid():
            for error in confirmation_form.non_field_errors():
                form.add_error(None, error)
            return self.form_invalid(form)

        if is_turnstile_enabled_for_action('registration', self.request):
            cfg = get_turnstile_settings()
            if not cfg['site_key'] or not cfg['secret_key']:
                form.add_error(
                    None,
                    forms.ValidationError(TURNSTILE_MISCONFIGURED_MESSAGE, code='turnstile_misconfigured'),
                )
                return self.form_invalid(form)

            token = self.request.POST.get('cf-turnstile-response')
            if not token:
                form.add_error(None, forms.ValidationError(TURNSTILE_ERROR_MESSAGE, code='turnstile_missing'))
                return self.form_invalid(form)
            client_ip = get_client_ip(self.request)
            valid, error_code = verify_turnstile_token(
                token,
                remote_ip=client_ip,
                expected_action='registration',
            )
            if not valid:
                if error_code == 'missing-secret':
                    form.add_error(
                        None,
                        forms.ValidationError(TURNSTILE_MISCONFIGURED_MESSAGE, code='turnstile_misconfigured'),
                    )
                else:
                    form.add_error(None, forms.ValidationError(TURNSTILE_FAILED_MESSAGE, code='turnstile_invalid'))
                return self.form_invalid(form)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['confirmation_pages'] = self.confirmation_pages
        # TODO: django-allauth uses the "remember" field; migrate to that (in both login flow and signup flow)
        # instead of posting "keep_logged_in" directly.
        ctx['show_keep_logged_in'] = settings.EVENTYAY_LONG_SESSIONS
        return ctx
