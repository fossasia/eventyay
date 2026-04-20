from functools import lru_cache
from importlib import import_module
from django import template
from django.conf import settings

from eventyay.base.auth import get_auth_backends
from eventyay.base.settings import GlobalSettingsObject, global_settings_object

register = template.Library()


@lru_cache(maxsize=1)
def get_auth_provider_helpers():
    """
    Lazily import the auth provider helper functions to avoid importing the heavy
    eventyay_common.views.auth module at template tag import time.
    """
    auth_module = import_module('eventyay.eventyay_common.views.auth')
    return auth_module.order_login_providers, auth_module.get_preferred_provider


@register.simple_tag(takes_context=True)
def get_checkout_login_context(context):
    """
    Return context for checkout login modal using the same OAuth provider config and ordering
    as eventyay_common.views.auth.login.
    """
    request = context.get('request')
    order_login_providers, get_preferred_provider = get_auth_provider_helpers()

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

    backenddict = get_auth_backends()
    native = backenddict.get('native')
    show_native_login = bool(native and native.visible)

    return {
        'request': request,
        'enabled_providers': enabled_providers,
        'preferred_provider': preferred_provider,
        'can_reset': settings.EVENTYAY_PASSWORD_RESET,
        'can_register': settings.EVENTYAY_REGISTRATION,
        'show_native_login': show_native_login,
        'has_oauth_providers': bool(enabled_providers),
        'has_secondary_oauth_providers': has_secondary_oauth_providers,
    }
