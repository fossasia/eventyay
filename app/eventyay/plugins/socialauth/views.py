import logging
from enum import StrEnum
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from pydantic import ValidationError

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.eventyay_common.views.auth import process_login_and_set_cookie
from eventyay.helpers.urls import build_absolute_uri

from .schemas.login_providers import LoginProviders
from .schemas.oauth2_params import OAuth2Params
from .utils import validate_login_providers, set_preferred_provider

logger = logging.getLogger(__name__)
adapter = get_adapter()


class OAuthLoginView(View):
    def get(self, request: HttpRequest, provider: str) -> HttpResponse:
        self.set_oauth2_params(request)

        # Store the 'next' URL in session for redirecting the user back after login.
        next_url = request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            request.session['socialauth_next_url'] = next_url

        gs = GlobalSettingsObject()
        raw_providers = gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)

        # Validate the requested provider against the schema's known fields before
        # accessing any attributes. This prevents traversal to unintended attributes
        # such as 'providers' or 'model_dump'.
        if provider not in LoginProviders.model_fields:
            logger.warning(
                "Unknown provider '%s' requested. Valid providers: %s",
                provider,
                list(LoginProviders.model_fields.keys())
            )
            messages.error(request, _('Invalid login provider.'))
            return redirect('eventyay_common:auth.login')

        # At this point the provider name is guaranteed to be a valid schema field.
        provider_config = getattr(providers, provider, None)

        # Reject the attempt if the provider is disabled in global settings. This
        # prevents users from bypassing the admin's enable/disable control by
        # manually requesting /oauth_login/<provider>/.
        if not provider_config or not provider_config.state:
            logger.warning(
                "Login attempt for disabled provider '%s' rejected.",
                provider,
            )
            messages.error(request, _('This login method is currently disabled.'))
            return redirect('eventyay_common:auth.login')

        is_preferred = provider_config.is_preferred
        client_id = provider_config.client_id

        if is_preferred:
            request.session['socialauth_preferred_login'] = True
        else:
            request.session.pop('socialauth_preferred_login', None)

        provider_instance = adapter.get_provider(request, provider, client_id=client_id)

        base_url = provider_instance.get_login_url(request)
        query_params = {'next': build_absolute_uri('plugins:socialauth:social.oauth.return')}
        parsed_url = urlparse(base_url)
        updated_url = parsed_url._replace(query=urlencode(query_params))
        return redirect(urlunparse(updated_url))

    @staticmethod
    def set_oauth2_params(request: HttpRequest) -> None:
        """
        Handle Login with SSO button from other components.
        Sets 'oauth2_params' in the session for use by oauth2_callback.
        """
        next_url = request.GET.get('next', '')
        if not next_url:
            return

        parsed = urlparse(next_url)

        # Reject absolute URLs to prevent open redirect via the next parameter.
        if parsed.netloc or parsed.scheme:
            return

        params = parse_qs(parsed.query)
        sanitized_params = {k: v[0] for k, v in params.items() if k in OAuth2Params.model_fields.keys()}

        try:
            oauth2_params = OAuth2Params.model_validate(sanitized_params)
            request.session['oauth2_params'] = oauth2_params.model_dump()
        except ValidationError as e:
            logger.warning('Ignoring invalid OAuth2 parameters: %s.', e)


class OAuthReturnView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        try:
            user = self.get_or_create_user(request)

            keep_logged_in = request.session.pop('socialauth_preferred_login', False)

            # Check for OAuth2 params first to handle Talk module integration.
            oauth2_params = request.session.pop('oauth2_params', {})
            if oauth2_params:
                try:
                    oauth2_params = OAuth2Params.model_validate(oauth2_params)
                    query_string = urlencode(oauth2_params.model_dump())
                    auth_url = reverse('eventyay_common:oauth2_provider.authorize')

                    # For OAuth2 integration (Talk module), the redirect target is set
                    # explicitly in the session so that process_login can forward the
                    # user to the authorize endpoint after login or after 2FA completion.
                    next_url = f'{auth_url}?{query_string}'
                    request.session['socialauth_next_url'] = next_url

                    response = process_login_and_set_cookie(request, user, keep_logged_in)
                    return response
                except ValidationError as e:
                    logger.warning('Ignoring invalid OAuth2 parameters: %s.', e)

            # Re-validate the stored next URL as a defence against session tampering.
            next_url = request.session.pop('socialauth_next_url', None)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
                request.session['socialauth_next_url'] = next_url

            response = process_login_and_set_cookie(request, user, keep_logged_in)
            return response
        except AttributeError as e:
            messages.error(request, _('Error while authorizing: no email address available.'))
            logger.error('Error while authorizing: %s', e)
            return redirect('eventyay_common:auth.login')

    @staticmethod
    def get_or_create_user(request: HttpRequest) -> User:
        """
        Retrieve or create a local user account from social auth information.
        """
        social_account = request.user.socialaccount_set.filter(
            provider='mediawiki'
        ).last()  # Use only the most recently authenticated Wikimedia account.
        wikimedia_username = ''

        if social_account:
            extra_data = social_account.extra_data
            wikimedia_username = extra_data.get('username', extra_data.get('realname', ''))

        user, created = User.objects.get_or_create(
            email=request.user.email,
            defaults={
                'locale': getattr(request, 'LANGUAGE_CODE', settings.LANGUAGE_CODE),
                'timezone': getattr(request, 'timezone', settings.TIME_ZONE),
                'auth_backend': 'native',
                'password': '',
                'wikimedia_username': wikimedia_username,
            },
        )

        # Sync the Wikimedia username for existing users who predate this field,
        # and for users who have since changed their username on Wikimedia.
        if not created and (not user.wikimedia_username or user.wikimedia_username != wikimedia_username):
            user.wikimedia_username = wikimedia_username
            user.save()

        return user


class SocialLoginView(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'socialauth/social_auth_settings.html'

    class SettingState(StrEnum):
        ENABLED = 'enabled'
        DISABLED = 'disabled'
        CREDENTIALS = 'credentials'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gs = GlobalSettingsObject()
        self.set_initial_state()

    def set_initial_state(self):
        """
        Write default provider configuration on first run if none exists.

        This method only runs once when no configuration has been saved yet.
        It does not normalize or persist on subsequent GET requests to avoid
        unintended database writes on every page load. Normalization is handled
        in post() when the admin explicitly submits the form.
        """
        raw_providers = self.gs.settings.get('login_providers', as_type=dict)
        if raw_providers is None:
            self.gs.settings.set('login_providers', LoginProviders().model_dump())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # validate_login_providers handles missing or invalid data gracefully,
        # returning defaults without writing to the database.
        raw_providers = self.gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)

        # Only consider enabled providers when determining preferred status.
        context['any_preferred'] = any(
            provider.state and provider.is_preferred
            for provider in providers.providers().values()
        )

        context['has_enabled_providers'] = any(
            provider.state
            for provider in providers.providers().values()
        )

        context['login_providers'] = providers.model_dump()

        # Strip trailing slash so templates can safely append paths like /github/...
        context['tickets_domain'] = urljoin(settings.SITE_URL, settings.BASE_PATH).rstrip("/")
        return context

    def post(self, request, *args, **kwargs):
        raw_providers = self.gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)

        setting_state = request.POST.get('save_credentials', '').lower()

        for provider_name in LoginProviders.model_fields.keys():
            if setting_state == self.SettingState.CREDENTIALS:
                self.update_credentials(request, provider_name, providers)
            else:
                self.update_provider_state(request, provider_name, providers)

        # Centralise preferred provider selection through the utility function
        # so the single-preferred-provider invariant is enforced in one place.
        preferred_provider = request.POST.get('preferred_provider', '')
        providers = set_preferred_provider(providers, preferred_provider)

        try:
            # Persist the validated and normalised configuration. This is the
            # only place provider normalisation is written to the database.
            self.gs.settings.set('login_providers', providers.model_dump())
        except Exception as e:
            logger.error('Error while saving login providers: %s', e)
            messages.error(request, _('Failed to save provider configuration. Please try again.'))
            return self.render_to_response(self.get_context_data())

        return redirect(self.get_success_url())

    def update_credentials(self, request: HttpRequest, provider: str, providers: LoginProviders):
        """
        Update the OAuth client ID and secret for a provider.

        Args:
            request: The current request containing POST data with the
                     provider's client_id and secret values.
            provider: Name of the provider being updated (e.g. 'github').
            providers: LoginProviders instance to update in place.
        """
        client_id_value = request.POST.get(f'{provider}_client_id', '')
        secret_value = request.POST.get(f'{provider}_secret', '')

        if client_id_value and secret_value:
            provider_config = getattr(providers, provider)
            updated_config = provider_config.model_copy(
                update={"client_id": client_id_value, "secret": secret_value}
            )
            setattr(providers, provider, updated_config)

            # Keep the django-allauth SocialApp record in sync with the stored credentials.
            SocialApp.objects.update_or_create(
                provider=provider,
                defaults={
                    'client_id': client_id_value,
                    'secret': secret_value,
                },
            )

    def update_provider_state(self, request: HttpRequest, provider: str, providers: LoginProviders):
        """
        Update the enabled/disabled state of a provider.

        The schema validator (ensure_single_preferred) automatically clears
        is_preferred when a provider is disabled, so that case does not need
        to be handled here. Invariant enforcement is centralised in the schema.

        Args:
            request: The current request containing POST data with the
                     provider's login state.
            provider: Name of the provider being updated (e.g. 'github').
            providers: LoginProviders instance to update in place.
        """
        setting_state = request.POST.get(f'{provider}_login', '').lower()
        if setting_state in [s.value for s in self.SettingState]:
            is_enabled = setting_state == self.SettingState.ENABLED

            provider_config = getattr(providers, provider)
            updated_config = provider_config.model_copy(update={"state": is_enabled})
            setattr(providers, provider, updated_config)

    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
