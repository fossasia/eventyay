import datetime as dt
from collections import defaultdict
from logging import getLogger
from typing import cast

from allauth.account.forms import ResetPasswordForm
from allauth.socialaccount import providers
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import activate
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView, TemplateView, UpdateView, View
from django_scopes import scopes_disabled

from eventyay.base.forms.user import UserSettingsForm
from eventyay.base.models import Event, LogEntry, NotificationSetting, User
from eventyay.base.notifications import get_all_notification_types

from ...navigation import get_account_navigation
from .common import AccountMenuMixIn


logger = getLogger(__name__)
PASSWORD_RESET_INTENT = 'password_reset'

# Pre-computed set of valid language codes for efficient validation
VALID_LANGUAGE_CODES = {code for code, __ in settings.LANGUAGES}


def get_social_account_provider_label(user: User) -> str:
    """
    Get the social account provider label for the given user.
    If the user does not have a social account, return an empty string.
    """
    social_account = SocialAccount.objects.filter(user=user).order_by('-pk').first()
    provider_id = social_account.provider if social_account else None
    if not provider_id:
        return ''
    # Get the first matching provider name from django-allauth's registry.
    return next((name for pid, name in providers.registry.as_choices() if pid == provider_id), provider_id)


# Copied from src/pretix/control/views/user.py and modified.
class GeneralSettingsView(LoginRequiredMixin, AccountMenuMixIn, UpdateView):
    model = User
    # This view will use two forms: UserSettingsForm and ResetPasswordForm.
    form_class = UserSettingsForm
    template_name = 'eventyay_common/account/general-settings.html'

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        requires_reset = not request.user.has_usable_password()

        # The password reset form was submitted
        if PASSWORD_RESET_INTENT in request.POST and requires_reset:
            reset_form = ResetPasswordForm(data=request.POST)
            if reset_form.is_valid():
                reset_form.save(request)
                messages.success(request, _('We have emailed you a link to set your password.'))
                return redirect(self.get_success_url())

            user_form = self.form_class(
                instance=self.request.user,
                user=self.request.user,
                require_password_reset=requires_reset,
            )
            return self.render_to_response(self.get_context_data(form=user_form, password_reset_form=reset_form))

        return super().post(request, *args, **kwargs)

    def get_object(self, queryset=None):
        self._old_email = self.request.user.email
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        user = self.request.user
        kwargs['user'] = user
        kwargs['require_password_reset'] = not user.has_usable_password()
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes could not be saved. See below for details.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))

        data = {}
        for k in form.changed_data:
            if k not in ('old_pw', 'new_pw_repeat'):
                if k == 'new_pw':
                    data['new_pw'] = True
                else:
                    data[k] = form.cleaned_data[k]

        msgs = []

        if 'new_pw' in form.changed_data:
            msgs.append(_('Your password has been changed.'))

        email_addr = form.cleaned_data['email']
        if 'email' in form.changed_data:
            msgs.append(_('Your email address has been changed to {email}.').format(email=email_addr))

        if msgs:
            self.request.user.send_security_notice(msgs, email=email_addr)
            if self._old_email != email_addr:
                self.request.user.send_security_notice(msgs, email=self._old_email)

        sup = super().form_valid(form)
        self.request.user.log_action('eventyay.user.settings.changed', user=self.request.user, data=data)

        update_session_auth_hash(self.request, self.request.user)

        new_locale = form.cleaned_data.get('locale')
        if new_locale:
            activate(new_locale)
            max_age = dt.timedelta(seconds=10 * 365 * 24 * 60 * 60)
            expires = dt.datetime.now(dt.UTC) + max_age
            sup.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                new_locale,
                max_age=int(max_age.total_seconds()),
                expires=expires.strftime('%a, %d-%b-%Y %H:%M:%S GMT'),
                domain=settings.SESSION_COOKIE_DOMAIN,
            )
        return sup

    def get_success_url(self):
        return reverse('eventyay_common:account')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        # This page requires login, so we can safely cast.
        user = cast(User, request.user)
        ctx['nav_items'] = get_account_navigation(request)
        requires_reset = not user.has_usable_password()
        ctx['requires_password_reset'] = requires_reset
        provider_label = get_social_account_provider_label(user)
        ctx['password_reset_message'] = build_password_reset_message(requires_reset, provider_label)

        # Get the primary email or fallback to first email or user email
        primary_email = user.primary_email
        ctx['primary_email'] = primary_email

        # Passed by the post() method when the password reset form was submitted.
        password_reset_form = kwargs.get('password_reset_form')
        # If this form is present, it means we need to render it with errors,
        # otherwise, create a new blank form for password reset.
        if not password_reset_form and requires_reset:
            ctx['password_reset_form'] = ResetPasswordForm(initial={'email': primary_email})
            return ctx
        return ctx


class NotificationSettingsView(LoginRequiredMixin, AccountMenuMixIn, TemplateView):
    template_name = 'eventyay_common/account/notification-settings.html'

    @cached_property
    def event(self):
        if self.request.GET.get('event'):
            try:
                return (
                    self.request.user.get_events_with_any_permission()
                    .select_related('organizer')
                    .get(pk=self.request.GET.get('event'))
                )
            except Event.DoesNotExist:
                return None
        return None

    @cached_property
    def types(self):
        return get_all_notification_types(self.event)

    @cached_property
    def currently_set(self):
        set_per_method = defaultdict(dict)
        for n in self.request.user.notification_settings.filter(event=self.event):
            set_per_method[n.method][n.action_type] = n.enabled
        return set_per_method

    @cached_property
    def global_set(self):
        set_per_method = defaultdict(dict)
        for n in self.request.user.notification_settings.filter(event__isnull=True):
            set_per_method[n.method][n.action_type] = n.enabled
        return set_per_method

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if 'notifications_send' in request.POST:
            request.user.notifications_send = request.POST.get('notifications_send', '') == 'on'
            request.user.save()

            messages.success(request, _('Your notification settings have been saved.'))
            if request.user.notifications_send:
                self.request.user.log_action('eventyay.user.settings.notifications.disabled', user=self.request.user)
            else:
                self.request.user.log_action('eventyay.user.settings.notifications.enabled', user=self.request.user)
            dest = reverse('eventyay_common:account.notifications')
            if self.event:
                dest += f'?event={self.event.pk}'
            return redirect(dest)
        else:
            for method, __ in NotificationSetting.CHANNELS:
                old_enabled = self.currently_set[method]

                for at in self.types.keys():
                    val = request.POST.get(f'{method}:{at}')

                    # True → False
                    if old_enabled.get(at) is True and val == 'off':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).update(enabled=False)

                    # True/False → None
                    if old_enabled.get(at) is not None and val == 'global':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).delete()

                    # None → True/False
                    if old_enabled.get(at) is None and val in ('on', 'off'):
                        self.request.user.notification_settings.create(
                            event=self.event,
                            action_type=at,
                            method=method,
                            enabled=(val == 'on'),
                        )

                    # False → True
                    if old_enabled.get(at) is False and val == 'on':
                        self.request.user.notification_settings.filter(
                            event=self.event, action_type=at, method=method
                        ).update(enabled=True)

            messages.success(request, _('Your notification settings have been saved.'))
            self.request.user.log_action('eventyay.user.settings.notifications.changed', user=self.request.user)
            dest = reverse('eventyay_common:account.notifications')
            if self.event:
                dest += f'?event={self.event.pk}'
            return redirect(dest)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['events'] = self.request.user.get_events_with_any_permission().order_by('-date_from')
        ctx['types'] = [
            (
                tv,
                {k: a.get(t) for k, a in self.currently_set.items()},
                {k: a.get(t) for k, a in self.global_set.items()},
            )
            for t, tv in self.types.items()
        ]
        ctx['event'] = self.event
        if self.event:
            ctx['permset'] = self.request.user.get_event_permission_set(self.event.organizer, self.event)
        return ctx


class NotificationFlipOffView(TemplateView):
    template_name = 'eventyay_common/account/notification-flip-off.html'

    @scopes_disabled()
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = get_object_or_404(User, notifications_token=kwargs.get('token'), pk=kwargs.get('id'))
        user.notifications_send = False
        user.save()
        messages.success(request, _('Your notifications have been disabled.'))
        dest = (
            reverse('eventyay_common:account.notifications')
            if request.user.is_authenticated
            else reverse('eventyay_common:auth.login')
        )
        return redirect(dest)


class HistoryView(AccountMenuMixIn, ListView):
    template_name = 'eventyay_common/account/history.html'
    model = LogEntry
    context_object_name = 'logs'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(User), object_id=self.request.user.pk
            )
            .select_related('user', 'content_type', 'api_token', 'oauth_application', 'device')
            .order_by('-datetime')
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()

        class FakeClass:
            def top_logentries(self):
                return ctx['logs']

        ctx['fakeobj'] = FakeClass()
        return ctx


# This view is just a placeholder for the URL patterns that we haven't implemented views for yet.
class DummyView(TemplateView):
    template_name = 'eventyay_common/base.html'


def build_password_reset_message(requires_reset: bool, provider_label: str) -> str:
    if not requires_reset:
        return ''
    if provider_label:
        return _(
            'Your account was created via {provider} login and does not have a password yet. '
            'Send yourself a password setup link below.'
        ).format(provider=provider_label)
    return _('Your account does not have a password yet. Send yourself a password setup link below.')


class LanguageSwitchView(View):
    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = reverse('eventyay_common:dashboard')

        response = redirect(next_url)
        locale = request.POST.get('locale')
        if locale and locale in VALID_LANGUAGE_CODES:
            activate(locale)
            if request.user.is_authenticated:
                if request.user.locale != locale:
                    request.user.locale = locale
                    request.user.save(update_fields=['locale'])
            max_age = dt.timedelta(seconds=10 * 365 * 24 * 60 * 60)
            expires = dt.datetime.now(dt.UTC) + max_age
            response.set_cookie(
                settings.LANGUAGE_COOKIE_NAME,
                locale,
                max_age=max_age,
                expires=expires.strftime('%a, %d-%b-%Y %H:%M:%S GMT'),
                domain=settings.SESSION_COOKIE_DOMAIN,
            )
        return response
