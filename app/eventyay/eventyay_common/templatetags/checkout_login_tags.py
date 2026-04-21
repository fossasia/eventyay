from django import template
from django.conf import settings

from eventyay.base.auth import get_auth_backends
from eventyay.base.settings import GlobalSettingsObject, global_settings_object
from eventyay.eventyay_common.services.auth_providers import (
    get_preferred_provider,
    order_login_providers,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def get_checkout_login_context(context):
    """
    Return context for checkout login modal using the same OAuth provider config and ordering
    as eventyay_common.views.auth.login.
    """
    request = context.get('request')

    gs = global_settings_object(request) if request else GlobalSettingsObject()
    raw_providers = gs.settings.get('login_providers', as_type=dict) or {}
    ordered = order_login_providers(raw_providers)
    enabled_providers = [
        (key, cfg)
        for key, cfg in ordered.items()
        if isinstance(cfg, dict) and cfg.get('state')
    ]
    preferred_provider = get_preferred_provider(raw_providers)
    if preferred_provider and not any(k == preferred_provider for k, _ in enabled_providers):
        preferred_provider = None
    has_secondary_oauth_providers = bool(
        preferred_provider and any(k != preferred_provider for k, _ in enabled_providers)
    )

    backends = context.get('backends')
    if backends:
        native = next((b for b in backends if b.identifier == 'native'), None)
    else:
        native = get_auth_backends().get('native')

    show_native_login = bool(native and native.visible)

    can_reset = show_native_login and settings.EVENTYAY_PASSWORD_RESET
    can_register = show_native_login and settings.EVENTYAY_REGISTRATION

    return {
        'request': request,
        'enabled_providers': enabled_providers,
        'preferred_provider': preferred_provider,
        'can_reset': can_reset,
        'can_register': can_register,
        'show_native_login': show_native_login,
        'has_oauth_providers': bool(enabled_providers),
        'has_secondary_oauth_providers': has_secondary_oauth_providers,
    }
