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
from .utils import validate_login_providers

logger = logging.getLogger(__name__)
adapter = get_adapter()


class OAuthLoginView(View):
    def get(self, request: HttpRequest, provider: str) -> HttpResponse:
        self.set_oauth2_params(request)

        # Store the 'next' URL in session for redirecting user back after login
        next_url = request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            request.session['socialauth_next_url'] = next_url

        # VALIDATE LOGIN PROVIDERS 
        gs = GlobalSettingsObject()
        raw_providers = gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)

        # Get provider configuration safely
        provider_config = getattr(providers, provider, None)

        # Check if this provider is the preferred one.
        # A provider is considered preferred only when it exists, is enabled (state),
        # and is explicitly marked as preferred.
        is_preferred = (
            bool(provider_config)
            and getattr(provider_config, 'state', False)
            and getattr(provider_config, 'is_preferred', False)
        )

        # Get client_id for the provider
        client_id = provider_config.client_id if provider_config else None

        # Store in session that this is a preferred provider login
        if is_preferred:
            request.session['socialauth_preferred_login'] = True
        else:
            request.session.pop('socialauth_preferred_login', None)

        # Get provider instance with client_id
        provider_instance = adapter.get_provider(request, provider, client_id=client_id)

        base_url = provider_instance.get_login_url(request)
        query_params = {'next': build_absolute_uri('plugins:socialauth:social.oauth.return')}
        parsed_url = urlparse(base_url)
        updated_url = parsed_url._replace(query=urlencode(query_params))
        return redirect(urlunparse(updated_url))

    @staticmethod
    def set_oauth2_params(request: HttpRequest) -> None:
        """
        Handle Login with SSO button from other components
        This function will set 'oauth2_params' in session for oauth2_callback
        """
        next_url = request.GET.get('next', '')
        if not next_url:
            return

        parsed = urlparse(next_url)

        # Only allow relative URLs
        if parsed.netloc or parsed.scheme:
            return

        params = parse_qs(parsed.query)
        sanitized_params = {k: v[0] for k, v in params.items() if k in OAuth2Params.model_fields.keys()}

        try:
            oauth2_params = OAuth2Params.model_validate(sanitized_params)
            request.session['oauth2_params'] = oauth2_params.model_dump()
        except ValidationError as e:
            logger.warning('Ignore invalid OAuth2 parameters: %s.', e)


class OAuthReturnView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        try:
            user = self.get_or_create_user(request)

            # Check if this was a preferred provider login
            keep_logged_in = request.session.pop('socialauth_preferred_login', False)

            # Check for OAuth2 params first (Talk module integration)
            oauth2_params = request.session.pop('oauth2_params', {})
            if oauth2_params:
                try:
                    oauth2_params = OAuth2Params.model_validate(oauth2_params)
                    query_string = urlencode(oauth2_params.model_dump())
                    auth_url = reverse('eventyay_common:oauth2_provider.authorize')
                    # OAuth2 flow takes precedence - redirect to authorization endpoint
                    # Clean up socialauth_next_url to prevent it from being used later
                    request.session.pop('socialauth_next_url', None)
                    # Process login and set cookie, then redirect to auth URL
                    response = process_login_and_set_cookie(request, user, keep_logged_in)
                    response['Location'] = f'{auth_url}?{query_string}'
                    response.status_code = 302
                    return response
                except ValidationError as e:
                    logger.warning('Ignore invalid OAuth2 parameters: %s.', e)

            # Retrieve and re-validate the stored 'next' URL from session
            # Re-validation provides defense against session tampering
            next_url = request.session.pop('socialauth_next_url', None)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
                # Store in session with a clear key for process_login to use
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
        Get or create a user from social auth information.
        """
        social_account = request.user.socialaccount_set.filter(
            provider='mediawiki'
        ).last()  # Fetch only the latest signed in Wikimedia account
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

        # Update wikimedia_username if the user exists but has no wikimedia_username value set
        # (basically our existing users), or if the user has updated his username in his wikimedia account
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
        Set the initial state of the login providers.
        If the login providers are not valid, set them to the default.
        Persist normalized/validated config to ensure invariants are enforced at rest.
        """
        raw_providers = self.gs.settings.get('login_providers', as_type=dict)

        # Validate login providers
        if raw_providers is None:
            # No providers set - initialize with defaults
            self.gs.settings.set('login_providers', LoginProviders().model_dump())
        else:
            # Validate existing providers
            try:
                validated_providers = LoginProviders.model_validate(raw_providers)
                # Persist the validated/normalized result to keep invariants enforced
                normalized = validated_providers.model_dump()
                if normalized != raw_providers:
                    self.gs.settings.set('login_providers', normalized)
            except ValidationError as e:
                logger.error('Error while validating login providers: %s', e)
                # Invalid providers - reset to defaults
                self.gs.settings.set('login_providers', LoginProviders().model_dump())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get and validate login providers
        raw_providers = self.gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)

        # Calculate any_preferred considering only enabled providers
        context['any_preferred'] = any(
            # Only check ENABLED providers
            provider.state and provider.is_preferred
            for provider in providers.providers().values()
        )

        # Convert to dict for template
        context['login_providers'] = providers.model_dump()

        # tickets_domain is only used to append /github/..., so make sure we don't have a trailing /
        context['tickets_domain'] = urljoin(settings.SITE_URL, settings.BASE_PATH).rstrip("/")
        return context

    def post(self, request, *args, **kwargs):
        # Get current login providers
        raw_providers = self.gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)
        
        # Convert to mutable dict for updates
        login_providers = providers.model_dump()
        
        setting_state = request.POST.get('save_credentials', '').lower()

        # Handle preferred provider selection
        preferred_provider = request.POST.get('preferred_provider', '')

        # Reset all is_preferred flags
        for provider_name in LoginProviders.model_fields.keys():
            if provider_name in login_providers:
                login_providers[provider_name]['is_preferred'] = False

        # Set the selected provider as preferred (if any enabled provider was selected)
        # Validate that the preferred_provider is a valid provider from the schema
        if (preferred_provider 
            and preferred_provider in LoginProviders.model_fields.keys() 
            and preferred_provider in login_providers):
            if login_providers[preferred_provider].get('state', False):
                login_providers[preferred_provider]['is_preferred'] = True

        for provider_name in LoginProviders.model_fields.keys():
            if setting_state == self.SettingState.CREDENTIALS:
                self.update_credentials(request, provider_name, login_providers)
            else:
                self.update_provider_state(request, provider_name, login_providers)

        # Validate before saving
        try:
            validated_providers = LoginProviders.model_validate(login_providers)
            self.gs.settings.set('login_providers', validated_providers.model_dump())
        except ValidationError as e:
            logger.error('Error while validating updated login providers: %s', e)
            messages.error(request, _('Invalid provider configuration. Please check your settings.'))
        
        return redirect(self.get_success_url())

    def update_credentials(self, request, provider, login_providers):
        """Update OAuth credentials for a provider"""
        client_id_value = request.POST.get(f'{provider}_client_id', '')
        secret_value = request.POST.get(f'{provider}_secret', '')

        if client_id_value and secret_value:
            login_providers[provider]['client_id'] = client_id_value
            login_providers[provider]['secret'] = secret_value

            SocialApp.objects.update_or_create(
                provider=provider,
                defaults={
                    'client_id': client_id_value,
                    'secret': secret_value,
                },
            )

    def update_provider_state(self, request, provider, login_providers):
        """
        Update the state (enabled/disabled) of a login provider.
        
        When a provider is disabled, this method automatically removes its preferred status
        to prevent stale preferred_provider values. This handles the edge case where:
        1. A provider is marked as preferred and enabled
        2. User disables that provider without selecting a new preferred provider
        3. The disabled provider's radio button is removed from DOM (not in form submission)
        4. Without this logic, the disabled provider could remain marked as preferred
        """
        setting_state = request.POST.get(f'{provider}_login', '').lower()
        if setting_state in [s.value for s in self.SettingState]:
            was_enabled = login_providers[provider].get('state', False)
            is_now_enabled = setting_state == self.SettingState.ENABLED

            login_providers[provider]['state'] = is_now_enabled

            # Critical: If disabling a preferred provider, remove its preferred status
            # This prevents the form from retaining a stale preferred_provider value
            # when the provider's radio button is no longer in the DOM
            if was_enabled and not is_now_enabled and login_providers[provider].get('is_preferred', False):
                login_providers[provider]['is_preferred'] = False
    
    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
