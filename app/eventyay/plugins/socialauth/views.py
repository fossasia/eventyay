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

        # Store the 'next' URL in session for redirecting user back after login
        next_url = request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            request.session['socialauth_next_url'] = next_url

        # Parse and normalize login providers
        gs = GlobalSettingsObject()
        raw_providers = gs.settings.get('login_providers', as_type=dict)
        providers = validate_login_providers(raw_providers)

        # Validate provider against allowlist before accessing attributes
        # This prevents accessing unintended attributes/methods like 'providers', 'model_dump'
        if provider not in LoginProviders.model_fields:
            logger.warning(
                "Unknown provider '%s' requested. Valid providers: %s",
                provider,
                list(LoginProviders.model_fields.keys())
            )
            messages.error(request, _('Invalid login provider.'))
            return redirect('eventyay_common:auth.login')

        # Get provider configuration safely (now guaranteed to be a valid provider)
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
                    
                    # IMPORTANT: For OAuth2 integration (Talk module), we maintain the
                    # explicit redirect behavior to preserve external callback compatibility.
                    # If the user requires 2FA, the URL will be stored in session and
                    # retrieved after 2FA completion via process_login's next_url handling.
                    next_url = f'{auth_url}?{query_string}'
                    request.session['socialauth_next_url'] = next_url
                    
                    # Process login and set cookie, respecting 2FA if required.
                    # If 2FA is not required, user will be redirected to the authorize URL.
                    # If 2FA is required, user will complete 2FA, then be redirected to authorize URL.
                    response = process_login_and_set_cookie(request, user, keep_logged_in)
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
        
        # Calculate if any providers are enabled (for conditional rendering in template)
        context['has_enabled_providers'] = any(
            provider.state
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
        
        setting_state = request.POST.get('save_credentials', '').lower()

        # Update credentials or state for each provider
        for provider_name in LoginProviders.model_fields.keys():
            if setting_state == self.SettingState.CREDENTIALS:
                self.update_credentials(request, provider_name, providers)
            else:
                self.update_provider_state(request, provider_name, providers)

        # Handle preferred provider selection using centralized utility function
        # This ensures the single-preferred-provider invariant is enforced consistently
        preferred_provider = request.POST.get('preferred_provider', '')
        providers = set_preferred_provider(providers, preferred_provider)

        # Save the updated and validated providers
        try:
            self.gs.settings.set('login_providers', providers.model_dump())
        except Exception as e:
            logger.error('Error while saving login providers: %s', e)
            messages.error(request, _('Failed to save provider configuration. Please try again.'))
            # Re-render form with error message instead of redirecting
            return self.render_to_response(self.get_context_data())
    
        return redirect(self.get_success_url())

    def update_credentials(self, request: HttpRequest, provider: str, providers: LoginProviders):
        """
        Update OAuth credentials for a provider.
        
        Args:
            request: The current HttpRequest containing POST data with the
                    provider's client_id and secret values.
            provider: The login provider name whose credentials are being updated
                     (e.g., 'github', 'google', 'mediawiki').
            providers: LoginProviders instance that will be updated with
                      the new credentials for this provider.
        """
        client_id_value = request.POST.get(f'{provider}_client_id', '')
        secret_value = request.POST.get(f'{provider}_secret', '')

        if client_id_value and secret_value:
            # Update the provider configuration
            provider_config = getattr(providers, provider)
            updated_config = provider_config.model_copy(
                update={"client_id": client_id_value, "secret": secret_value}
            )
            setattr(providers, provider, updated_config)

            # Also update SocialApp for django-allauth
            SocialApp.objects.update_or_create(
                provider=provider,
                defaults={
                    'client_id': client_id_value,
                    'secret': secret_value,
                },
            )

    def update_provider_state(self, request: HttpRequest, provider: str, providers: LoginProviders):
        """
        Update the state (enabled/disabled) of a login provider.
        
        The schema validator (ensure_single_preferred) automatically clears
        is_preferred if a provider is disabled, so we don't need to handle
        that edge case manually here. This keeps the view logic thin and
        centralizes invariant enforcement in the schema layer.
        
        Args:
            request: The current HttpRequest containing POST data with the
                    provider's login state settings.
            provider: The login provider name whose state is being updated
                     (e.g., 'github', 'google', 'mediawiki').
            providers: LoginProviders instance that will be updated with
                      the new state for this provider.
        """
        setting_state = request.POST.get(f'{provider}_login', '').lower()
        if setting_state in [s.value for s in self.SettingState]:
            is_enabled = setting_state == self.SettingState.ENABLED

            # Update provider state
            provider_config = getattr(providers, provider)
            updated_config = provider_config.model_copy(update={"state": is_enabled})
            setattr(providers, provider, updated_config)

    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
