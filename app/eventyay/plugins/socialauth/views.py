import logging
from enum import StrEnum
from urllib.parse import parse_qs, urljoin, urlparse

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

from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.consts import KEY_SOCIAL_KEEP_LOGGED_IN
from eventyay.control.permissions import AdministratorPermissionRequiredMixin

from .schemas.login_providers import LoginProviders
from .schemas.oauth2_params import OAuth2Params

logger = logging.getLogger(__name__)


class OAuthLoginView(View):
    def get(self, request: HttpRequest, provider: str) -> HttpResponse:
        self.set_oauth2_params(request)

        next_url = request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            request.session['socialauth_next_url'] = next_url

        gs = GlobalSettingsObject()
        login_providers = gs.settings.get('login_providers', as_type=dict) or {}
        known_providers = frozenset(LoginProviders.model_fields.keys())
        if (
            provider not in known_providers
            or provider not in login_providers
            or not login_providers[provider].get('state')
            or not login_providers[provider].get('client_id')
            or not login_providers[provider].get('secret')
        ):
            messages.error(request, _('This login method is not available.'))
            return redirect('eventyay_common:auth.login')
        provider_config = login_providers[provider]
        if provider_config.get('is_preferred'):
            request.session[KEY_SOCIAL_KEEP_LOGGED_IN] = True
        else:
            request.session.pop(KEY_SOCIAL_KEEP_LOGGED_IN, None)
        client_id = provider_config.get('client_id')
        adapter = get_adapter()
        provider_instance = adapter.get_provider(request, provider, client_id=client_id)

        login_url = provider_instance.get_login_url(request)
        return redirect(login_url)

    @staticmethod
    def set_oauth2_params(request: HttpRequest) -> None:
        """Store OAuth2 params in session for Talk module SSO handoff."""
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
        Validate and normalize the login providers stored in global settings.

        Pydantic fills in defaults for missing keys (e.g. an empty ``{}``
        becomes the full three-provider schema). When the normalised result
        differs from what is stored, it is written back so that
        ``get_context_data`` and the template see the complete provider list.

        On a ``ValidationError`` we log and leave the existing DB row
        unchanged rather than silently overwriting with all-disabled defaults,
        which would wipe out the admin's configuration.
        """
        raw = self.gs.settings.get('login_providers', as_type=dict)
        try:
            validated = LoginProviders.model_validate(raw or {})
        except ValidationError as e:
            logger.error(
                'login_providers settings failed validation (not overwriting): %s', e
            )
            return
        normalized = validated.model_dump()
        if raw != normalized:
            self.gs.settings.set('login_providers', normalized)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        context['login_providers'] = login_providers
        context['any_preferred'] = any(
            p.get('state', False) and p.get('is_preferred', False) for p in login_providers.values()
        )
        context['tickets_domain'] = urljoin(settings.SITE_URL, settings.BASE_PATH).rstrip('/')
        return context

    def post(self, request, *args, **kwargs):
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        setting_state = request.POST.get('save_credentials', '').lower()

        self._apply_preferred_provider(request, login_providers)

        for provider in LoginProviders.model_fields.keys():
            if setting_state == self.SettingState.CREDENTIALS:
                self.update_credentials(request, provider, login_providers)
            else:
                self.update_provider_state(request, provider, login_providers)

        self.gs.settings.set('login_providers', login_providers)
        return redirect(self.get_success_url())

    def _apply_preferred_provider(self, request, login_providers):
        preferred = request.POST.get('preferred_provider', '').strip().lower()
        valid_providers = set(LoginProviders.model_fields.keys())

        # Explicitly selecting "none" clears all preferred flags.
        if preferred == 'none':
            for provider in valid_providers:
                login_providers.setdefault(provider, {})['is_preferred'] = False
            return

        # If the field is missing or empty, leave existing preferences unchanged.
        if not preferred:
            return

        # Ignore invalid provider values to avoid wiping existing preferences.
        if preferred not in valid_providers:
            logger.warning('Ignoring invalid preferred provider value: %s', preferred)
            return

        # If the selected provider is disabled, do not change the current preference.
        if not login_providers.get(preferred, {}).get('state'):
            return

        # Set the selected provider as the only preferred one.
        for provider in valid_providers:
            login_providers.setdefault(provider, {})['is_preferred'] = provider == preferred

    def update_credentials(self, request, provider, login_providers):
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
        setting_state = request.POST.get(f'{provider}_login', '').lower()
        if setting_state in [s.value for s in self.SettingState]:
            # Ensure provider dict exists
            provider_config = login_providers.setdefault(provider, {})

            is_enabled = setting_state == self.SettingState.ENABLED
            provider_config['state'] = is_enabled

            if not is_enabled:
                # Clear preferred flag when disabling the provider
                provider_config['is_preferred'] = False
                # Remove SocialApp so the provider cannot be used via allauth URLs
                SocialApp.objects.filter(provider=provider).delete()
            else:
                # When enabling, if we already have stored credentials, ensure SocialApp exists
                client_id = provider_config.get('client_id')
                secret = provider_config.get('secret')
                if client_id and secret:
                    SocialApp.objects.update_or_create(
                        provider=provider,
                        defaults={
                            'client_id': client_id,
                            'secret': secret,
                        },
                    )

    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
