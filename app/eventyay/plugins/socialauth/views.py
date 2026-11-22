import logging
from enum import StrEnum
from urllib.parse import parse_qs, urljoin, urlparse
from uuid import uuid4

from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError as FormValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from pydantic import ValidationError

from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event
from eventyay.base.settings import GlobalSettingsObject, GlobalSettingsObject_SettingsStore
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
            or not isinstance(login_providers.get(provider), dict)
            or not login_providers[provider].get('state')
            or not login_providers[provider].get('client_id')
            or not login_providers[provider].get('secret')
        ):
            messages.error(request, _('This login method is not available.'))
            log_event('core', 'auth.login', OUTCOME_FAILURE, error_code='social_provider_unavailable')
            return redirect('auth.login')
        provider_config = login_providers[provider]
        if provider_config.get('is_preferred'):
            request.session[KEY_SOCIAL_KEEP_LOGGED_IN] = True
        else:
            request.session.pop(KEY_SOCIAL_KEEP_LOGGED_IN, None)
        client_id = provider_config.get('client_id')
        adapter = get_adapter()
        provider_instance = adapter.get_provider(
            request, provider_config.get('provider_id', provider), client_id=client_id,
        )

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

    @transaction.atomic
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
        GlobalSettingsObject_SettingsStore.objects.select_for_update().get_or_create(
            key='login_providers', defaults={'value': '{}'},
        )
        self.gs.settings.flush()
        raw = self.gs.settings.get('login_providers', as_type=dict)
        try:
            values = raw or {}
            if isinstance(values, dict) and not isinstance(values.get('openid_connect', {}), dict):
                values = {**values, 'openid_connect': {}}
            validated = LoginProviders.model_validate(values)
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
        oidc = login_providers['openid_connect']
        context['oidc_callback'] = self.request.build_absolute_uri(
            reverse('openid_connect_callback', args=[oidc['provider_id']])
        )
        context['any_preferred'] = any(
            p.get('state', False) and p.get('is_preferred', False) for p in login_providers.values()
        )
        context['tickets_domain'] = urljoin(settings.SITE_URL, settings.BASE_PATH).rstrip('/')
        return context

    def post(self, request, *args, **kwargs):
        try:
            self.save_login_providers(request)
        except FormValidationError as exc:
            messages.error(request, exc.messages[0])
        return redirect(self.get_success_url())

    @transaction.atomic
    def save_login_providers(self, request):
        # Read the latest settings under lock before removing links for a changed issuer.
        GlobalSettingsObject_SettingsStore.objects.select_for_update().get(key='login_providers')
        self.gs.settings.flush()
        login_providers = self.gs.settings.get('login_providers', as_type=dict)
        setting_state = request.POST.get('save_credentials', '').lower()

        self._apply_preferred_provider(request, login_providers)

        for provider in LoginProviders.model_fields.keys():
            if setting_state == self.SettingState.CREDENTIALS:
                self.update_credentials(request, provider, login_providers)
            else:
                self.update_provider_state(request, provider, login_providers)

        self.gs.settings.set('login_providers', login_providers)

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
            if provider == 'openid_connect':
                config = login_providers[provider]
                if not config.get('state'):
                    return
                expected = config['provider_id'] if config.get('issuer') else ''
                if request.POST.get('previous_provider_id') != expected:
                    raise FormValidationError(_('The issuer changed. Reload the form and try again.'))
                if 'openid_connect_display_name' in request.POST:
                    config['display_name'] = request.POST['openid_connect_display_name'].strip()
            login_providers[provider]['client_id'] = client_id_value
            login_providers[provider]['secret'] = secret_value

            SocialApp.objects.update_or_create(
                provider=provider,
                defaults={
                    'client_id': client_id_value,
                    'secret': secret_value,
                    **self.social_app_settings(
                        provider, request.POST.get('openid_connect_issuer'), login_providers[provider],
                    ),
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
                            **self.social_app_settings(provider, None, provider_config),
                        },
                    )

    def social_app_settings(self, provider, submitted_issuer, config):
        if provider != 'openid_connect':
            return {}

        original = config.get('issuer', '')
        issuer = original if submitted_issuer is None else submitted_issuer.strip().rstrip('/')
        if not issuer:
            raise FormValidationError(_('Enter the issuer URL before saving OpenID Connect credentials.'))
        try:
            URLValidator(schemes=['https'])(issuer)
            parsed = urlparse(issuer)
            parsed.port  # Reject ports outside the allowed range.
            if parsed.username is not None or '?' in issuer or '#' in issuer:
                raise ValueError
        except (ValueError, FormValidationError):
            raise FormValidationError(_('Enter a valid HTTPS issuer URL.')) from None

        provider_id = config.get('provider_id', provider)
        if original and original != issuer:
            SocialAccount.objects.filter(provider=provider_id).delete()
            provider_id = f'oidc-{uuid4().hex}'
        elif not original and SocialAccount.objects.filter(provider=provider_id).exists():
            raise FormValidationError(_('The issuer for the existing OIDC links is unknown.'))

        config.update(issuer=issuer, provider_id=provider_id)
        return {'provider_id': provider_id, 'settings': {'server_url': issuer}}

    def get_success_url(self) -> str:
        return reverse('plugins:socialauth:admin.global.social.auth.settings')
